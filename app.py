"""Main application file for the Health Vault Flask app.

This file keeps everything in one place so it is easy
to read and understand for beginners.
"""

import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta

import base64
from io import BytesIO
import qrcode
from dotenv import load_dotenv

load_dotenv()
# AI REPORT SUMMARY FEATURE
from groq import Groq
from PyPDF2 import PdfReader

# AI SECURITY & OCR FEATURE
REDACTED = "[REDACTED]"

from flask import Flask, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename


# ----------------------
# Database configuration
# ----------------------

DATABASE_NAME = "health_vault.db"
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

# REPORT CATEGORIZATION FEATURE
REPORT_CATEGORIES = [
    {"key": "Heart", "emoji": "❤️", "label": "Heart", "color_slug": "heart"},
    {"key": "Lungs", "emoji": "🫁", "label": "Lungs", "color_slug": "lungs"},
    {"key": "Kidney", "emoji": "🫘", "label": "Kidney", "color_slug": "kidney"},
    {"key": "Brain", "emoji": "🧠", "label": "Brain", "color_slug": "brain"},
    {"key": "Liver", "emoji": "🫀", "label": "Liver", "color_slug": "liver"},
    {"key": "Blood Test", "emoji": "🩸", "label": "Blood Test", "color_slug": "blood"},
    {"key": "Diabetes", "emoji": "💉", "label": "Diabetes", "color_slug": "diabetes"},
    {"key": "Orthopedic", "emoji": "🦴", "label": "Orthopedic", "color_slug": "orthopedic"},
    {"key": "General", "emoji": "📋", "label": "General", "color_slug": "general"},
]
VALID_REPORT_CATEGORY_KEYS = {item["key"] for item in REPORT_CATEGORIES}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# MODERN CATEGORY DASHBOARD FEATURE
def get_latest_upload_label(reports):
    """Return a friendly label for the most recent report upload in a category."""
    if not reports:
        return ""

    latest = max(reports, key=lambda row: row["upload_date"] or "")
    raw_date = latest["upload_date"]
    if not raw_date:
        return "Unknown"

    try:
        uploaded = datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return raw_date

    days_ago = (datetime.now().date() - uploaded.date()).days
    if days_ago == 0:
        return "Today"
    if days_ago == 1:
        return "Yesterday"
    if days_ago < 7:
        return f"{days_ago} days ago"
    return uploaded.strftime("%d %b %Y")


# REPORT CATEGORIZATION FEATURE
def group_reports_by_category(reports):
    """Group report rows by category; only return categories that have reports."""
    buckets = {}
    for report in reports:
        category = (report["category"] or "General").strip()
        if category not in buckets:
            buckets[category] = []
        buckets[category].append(report)

    grouped = []
    seen = set()

    # Keep a stable order using the predefined category list
    for cat in REPORT_CATEGORIES:
        key = cat["key"]
        if key in buckets and buckets[key]:
            items = sorted(buckets[key], key=lambda row: row["upload_date"] or "", reverse=True)
            grouped.append(
                {
                    "key": key,
                    "emoji": cat["emoji"],
                    "label": cat["label"],
                    "color_slug": cat["color_slug"],
                    "reports": items,
                    "latest_upload_label": get_latest_upload_label(items),
                }
            )
            seen.add(key)

    # Show any unexpected legacy category values (if they exist)
    for key, items in buckets.items():
        if key not in seen and items:
            sorted_items = sorted(items, key=lambda row: row["upload_date"] or "", reverse=True)
            grouped.append(
                {
                    "key": key,
                    "emoji": "📋",
                    "label": key,
                    "color_slug": "general",
                    "reports": sorted_items,
                    "latest_upload_label": get_latest_upload_label(sorted_items),
                }
            )

    return grouped


def get_db_connection():
    """Open and return a new connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the required tables if they do not exist."""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                blood_group TEXT,
                allergies TEXT,
                chronic_disease TEXT
            );
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                original_filename TEXT,
                upload_date TEXT NOT NULL,
                category TEXT,
                extracted_text TEXT,
                summary TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients (id)
            );
            """
        )

        # Lightweight migration for existing databases:
        # - add original_filename column if missing
        # - backfill from legacy stored filenames (timestamp_uuid_original)
        cursor.execute("PRAGMA table_info(reports)")
        report_cols = {row[1] for row in cursor.fetchall()}
        if "original_filename" not in report_cols:
            cursor.execute("ALTER TABLE reports ADD COLUMN original_filename TEXT")

        # REPORT CATEGORIZATION FEATURE — safe column add for existing databases
        if "category" not in report_cols:
            cursor.execute("ALTER TABLE reports ADD COLUMN category TEXT")
            cursor.execute(
                "UPDATE reports SET category = 'General' WHERE category IS NULL OR TRIM(category) = ''"
            )

        if "extracted_text" not in report_cols:
            cursor.execute("ALTER TABLE reports ADD COLUMN extracted_text TEXT")

        if "summary" not in report_cols:
            cursor.execute("ALTER TABLE reports ADD COLUMN summary TEXT")

        cursor.execute(
            "SELECT id, file_name, original_filename FROM reports WHERE original_filename IS NULL OR TRIM(original_filename) = ''"
        )
        rows_to_backfill = cursor.fetchall()
        for report_id, stored_name, original_name in rows_to_backfill:
            if stored_name:
                parts = stored_name.split("_", 3)
                derived_original = parts[-1] if len(parts) >= 4 else stored_name
            else:
                derived_original = ""

            cursor.execute(
                "UPDATE reports SET original_filename = ? WHERE id = ?",
                (derived_original, report_id),
            )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS access_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                access_key TEXT NOT NULL,
                expiry_time TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients (id)
            );
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS key_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                access_key_id INTEGER NOT NULL,
                report_id INTEGER NOT NULL,
                FOREIGN KEY (access_key_id) REFERENCES access_keys (id),
                FOREIGN KEY (report_id) REFERENCES reports (id)
            );
            """
        )

API_KEY = os.getenv("API_KEY")


# AI SECURITY & OCR FEATURE
def redact_sensitive_info(text: str, extra_values=None) -> str:
    """
    Mask common patient identifiers before text is sent to the AI model.
    Uses regex patterns for labels (Name:, Age:, etc.) and standalone PII formats.
    """
    if not text:
        return ""

    cleaned = text
    extra_values = extra_values or []

    # Label-based redaction (Name: Karthik Kumar → Name: [REDACTED])
    label_fields = (
        r"patient\s*name|name|father(?:'?s)?\s*name|father\s*name|"
        r"mother(?:'?s)?\s*name|guardian\s*name|"
        r"doctor(?:'?s)?\s*name|physician|referring\s+doctor|consultant|"
        r"age|gender|sex|address|village|locality|taluk|district|pin\s*code|pincode|"
        r"phone|mobile|contact|email|e-?mail|aadhaar|aadhar|uid|"
        r"hospital\s*id|patient\s*id|uhid|mrn|mr\s*no|registration\s*no|reg\.?\s*no|"
        r"ip\s*no|op\s*no|dob|date\s*of\s*birth|birth\s*date"
    )
    label_pattern = re.compile(
        rf"(?i)\b({label_fields})\s*[:=\-]\s*([^\n\r;|]+)",
    )
    cleaned = label_pattern.sub(rf"\1: {REDACTED}", cleaned)

    # Standalone email, phone (India), Aadhaar-style 12-digit groups
    cleaned = re.sub(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        REDACTED,
        cleaned,
    )
    cleaned = re.sub(r"(?:\+91[\-\s]?)?[6-9]\d{9}", REDACTED, cleaned)
    cleaned = re.sub(r"\b\d{10}\b", REDACTED, cleaned)
    cleaned = re.sub(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b", REDACTED, cleaned)

    # DOB lines (e.g. DOB: 12/05/1990)
    cleaned = re.sub(
        r"(?i)\b(dob|date\s*of\s*birth|birth\s*date)\s*[:=\-]?\s*\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}",
        rf"\1: {REDACTED}",
        cleaned,
    )

    # Redact known values from the patient record (name, email, etc.)
    for value in extra_values:
        if value and len(str(value).strip()) >= 2:
            cleaned = re.sub(re.escape(str(value).strip()), REDACTED, cleaned, flags=re.IGNORECASE)

    return cleaned


# AI SECURITY & OCR FEATURE
def extract_text_with_ocr(file_path: str) -> str:
    """OCR fallback for scanned PDFs and image reports when normal extraction is empty."""
    try:
        import pytesseract
        from PIL import Image
        from pdf2image import convert_from_path
    except ImportError:
        return ""

    tesseract_cmd = os.getenv("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    parts = []

    try:
        if ext == ".pdf":
            poppler_path = os.getenv("POPPLER_PATH")
            kwargs = {"poppler_path": poppler_path} if poppler_path else {}
            for page_img in convert_from_path(file_path, **kwargs):
                parts.append(pytesseract.image_to_string(page_img))
        elif ext in {".jpg", ".jpeg", ".png"}:
            with Image.open(file_path) as img:
                parts.append(pytesseract.image_to_string(img))
    except Exception as exc:
        print(f"OCR failed for {file_path}: {exc}")
        return ""

    return "\n\n".join(p.strip() for p in parts if p and p.strip()).strip()


# AI REPORT SUMMARY FEATURE
def summarize_report(text):
    # AI SECURITY & OCR FEATURE — only de-identified text goes to Groq
    safe_text = redact_sensitive_info(text)

    client = Groq(api_key=API_KEY)

    prompt = f"""You are assisting a doctor reviewing a de-identified medical report.

Format your response with EXACTLY these section headers:

1. Summary
- Short bullet points of key findings

2. Important Values
- List important blood/lab values mentioned in the report

3. Abnormal Findings
- Highlight critical or abnormal values using ⚠️ where appropriate

4. Recommended Follow-Up
- Suggest follow-up tests or checkups only if clearly implied by the report

5. Overall Health Insight
- Brief doctor-friendly explanation

Rules:
- Use simple bullet points only (no long paragraphs)
- Do NOT invent diagnoses, medications, or advice not supported by the report
- If a section has no relevant information, write: Not mentioned in report.
- Keep the response concise and professional

De-identified report text:
{safe_text}"""

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
    )

    return completion.choices[0].message.content


# AI REPORT SUMMARY FEATURE
def extract_text_from_report_file(file_path: str) -> str:
    """Extract text from PDF/TXT first; use OCR only when normal extraction is empty."""
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    text = ""

    if ext == ".pdf":
        reader = PdfReader(file_path)
        parts = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                parts.append(page_text)
        text = "\n\n".join(parts).strip()

    elif ext in {".txt"}:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read().strip()

    # AI SECURITY & OCR FEATURE — fallback for scanned PDFs and images
    if not text.strip():
        text = extract_text_with_ocr(file_path)

    return text


def persist_report_text_and_summary(conn, report_id: int, save_path: str, patient) -> None:
    """
    Best-effort post-upload pipeline: extract text, store it, then generate and store summary.
    Failures are logged; the report row and file on disk are left intact.
    """
    try:
        extracted = extract_text_from_report_file(save_path)
        if not extracted or not extracted.strip():
            return

        conn.execute(
            "UPDATE reports SET extracted_text = ? WHERE id = ?",
            (extracted, report_id),
        )
        conn.commit()

        redacted = redact_sensitive_info(
            extracted,
            extra_values=[patient["name"], patient["email"]],
        )
        summary = summarize_report(redacted)
        conn.execute(
            "UPDATE reports SET summary = ? WHERE id = ?",
            (summary, report_id),
        )
        conn.commit()
    except Exception as exc:
        print(f"Report text processing failed for report {report_id}: {exc}")


# -----------------
# App configuration
# -----------------

def create_app():
    """Application factory: creates and configures the Flask app."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev-secret-key-change-later"
    app.config["UPLOAD_FOLDER"] = "uploads"

    # Ensure uploads folder exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Create database tables when the app starts
    with app.app_context():
        init_db()

    # -------------
    # Basic routes
    # -------------

    @app.route("/")
    def home():
        return render_template("home.html")

    def get_current_patient():
        """Return the logged-in patient's row, or None."""
        patient_id = session.get("patient_id")
        if not patient_id:
            return None

        conn = get_db_connection()
        patient = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        conn.close()
        return patient

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "").strip()
            blood_group = request.form.get("blood_group", "").strip()
            allergies = request.form.get("allergies", "").strip()
            chronic_disease = request.form.get("chronic_disease", "").strip()

            if not name or not email or not password:
                flash("Name, email, and password are required.", "error")
                return render_template("register.html")

            conn = get_db_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO patients (name, email, password, blood_group, allergies, chronic_disease)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (name, email, password, blood_group, allergies, chronic_disease),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                flash("This email is already registered. Please use a different email.", "error")
                return render_template("register.html")
            finally:
                conn.close()

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "").strip()

            if not email or not password:
                flash("Email and password are required.", "error")
                return render_template("login.html")

            conn = get_db_connection()
            patient = conn.execute("SELECT * FROM patients WHERE email = ?", (email,)).fetchone()
            conn.close()

            if not patient or patient["password"] != password:
                flash("Invalid email or password.", "error")
                return render_template("login.html")

            # Clear any data from a previous session (e.g. smart_retrieval, QR image)
            # before authenticating the new patient.
            session.clear()
            session["patient_id"] = patient["id"]
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    @app.route("/dashboard", methods=["GET", "POST"])
    def dashboard():
        patient = get_current_patient()
        if not patient:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))

        # QR image for the latest generated access key (if any)
        qr_code_image = session.pop("latest_qr_image", None)

        if request.method == "POST":
            if "report_file" not in request.files:
                flash("Please choose a file to upload.", "error")
                return redirect(url_for("dashboard"))

            file = request.files["report_file"]
            if not file or file.filename == "":
                flash("Please choose a file to upload.", "error")
                return redirect(url_for("dashboard"))

            original_name = secure_filename(file.filename)
            if not allowed_file(original_name):
                flash("Only PDF, JPG, and PNG files are allowed.", "error")
                return redirect(url_for("dashboard"))

            # REPORT CATEGORIZATION FEATURE
            category = request.form.get("report_category", "").strip()
            if category not in VALID_REPORT_CATEGORY_KEYS:
                flash("Please select a report category.", "error")
                return redirect(url_for("dashboard"))

            # Store file on disk with a UUID-based filename (keep original separately for display)
            unique_name = f"{uuid.uuid4().hex}_{original_name}"
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
            file.save(save_path)

            upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = get_db_connection()
            insert_cursor = conn.execute(
                """
                INSERT INTO reports (patient_id, file_name, original_filename, upload_date, category)
                VALUES (?, ?, ?, ?, ?)
                """,
                (patient["id"], unique_name, original_name, upload_date, category),
            )
            report_id = insert_cursor.lastrowid
            conn.commit()

            persist_report_text_and_summary(conn, report_id, save_path, patient)
            conn.close()

            flash("Report uploaded successfully.", "success")
            return redirect(url_for("dashboard"))

        conn = get_db_connection()
        reports = conn.execute(
            """
            SELECT id, file_name, original_filename, upload_date, category
            FROM reports
            WHERE patient_id = ?
            ORDER BY id DESC
            """,
            (patient["id"],),
        ).fetchall()

        latest_key = conn.execute(
            "SELECT access_key, expiry_time FROM access_keys WHERE patient_id = ? ORDER BY id DESC LIMIT 1",
            (patient["id"],),
        ).fetchone()
        conn.close()

        # REPORT CATEGORIZATION FEATURE — only categories with reports are included
        reports_by_category = group_reports_by_category(reports)

        smart_retrieval = session.get("smart_retrieval")
        if smart_retrieval and smart_retrieval.get("patient_id") != patient["id"]:
            session.pop("smart_retrieval", None)
            smart_retrieval = None

        recommended_report_ids = []
        if smart_retrieval and smart_retrieval.get("recommendations"):
            patient_report_ids = {row["id"] for row in reports}
            valid_recommendations = [
                item
                for item in smart_retrieval["recommendations"]
                if item.get("report_id") in patient_report_ids
            ]
            if not valid_recommendations:
                session.pop("smart_retrieval", None)
                smart_retrieval = None
            else:
                smart_retrieval = {**smart_retrieval, "recommendations": valid_recommendations}
                recommended_report_ids = [item["report_id"] for item in valid_recommendations]

        return render_template(
            "dashboard.html",
            patient=patient,
            reports=reports,
            reports_by_category=reports_by_category,
            report_categories=REPORT_CATEGORIES,
            latest_key=latest_key,
            qr_code_image=qr_code_image,
            smart_retrieval=smart_retrieval,
            recommended_report_ids=recommended_report_ids,
        )

    # DISEASE PREDICTION FEATURE — uses ml/service.py (no retraining)
    @app.route("/predict-disease", methods=["GET", "POST"])
    def predict_disease():
        patient = get_current_patient()
        if not patient:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))

        from ml.service import (
            InvalidSymptomsError,
            ModelNotAvailableError,
            get_available_symptoms,
            predict_diseases,
        )

        symptoms = []
        predictions = None
        selected_symptoms = []
        model_error = None

        try:
            symptoms = get_available_symptoms()
        except ModelNotAvailableError as exc:
            model_error = str(exc)
            flash(
                "Disease prediction is unavailable. Model files are missing. "
                "Run: python ml/train_model.py",
                "error",
            )

        if request.method == "POST":
            if model_error:
                flash("Cannot run prediction because the model is not available.", "error")
                return redirect(url_for("predict_disease"))

            selected_symptoms = request.form.getlist("symptoms")
            try:
                predictions, warnings = predict_diseases(selected_symptoms, top_k=3)
                for unknown in warnings:
                    flash(f"Ignored unknown symptom: {unknown}", "error")
            except InvalidSymptomsError as exc:
                flash(str(exc), "error")
            except ModelNotAvailableError:
                flash("Model files are missing. Please retrain the model.", "error")
            except Exception as exc:
                print(f"Disease prediction error: {exc}")
                flash("Something went wrong while predicting. Please try again.", "error")

        smart_retrieval = None
        if predictions:
            from services.smart_report_retrieval import (
                NoReportsError,
                SmartRetrievalError,
                run_smart_report_retrieval,
            )

            top_disease = predictions[0][0]
            try:
                conn = get_db_connection()
                smart_retrieval = run_smart_report_retrieval(
                    conn,
                    patient["id"],
                    top_disease,
                    selected_symptoms,
                    redact_sensitive_info,
                    api_key=API_KEY,
                )
                conn.close()
                smart_retrieval["patient_id"] = patient["id"]
                session["smart_retrieval"] = smart_retrieval
                if smart_retrieval.get("recommendations"):
                    flash(
                        "Smart report recommendations are ready. "
                        "Review them below or on your dashboard.",
                        "success",
                    )
            except NoReportsError as exc:
                flash(str(exc), "error")
            except SmartRetrievalError as exc:
                flash(str(exc), "error")
            except Exception as exc:
                print(f"Smart report retrieval error: {exc}")
                flash("Could not retrieve report recommendations. Please try again.", "error")

        return render_template(
            "predict_disease.html",
            patient=patient,
            symptoms=symptoms,
            predictions=predictions,
            selected_symptoms=selected_symptoms,
            model_error=model_error,
            smart_retrieval=smart_retrieval,
        )

    @app.route("/generate_key", methods=["POST"])
    def generate_key():
        patient = get_current_patient()
        if not patient:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))

        selected_reports = request.form.getlist("selected_reports")
        if not selected_reports:
            flash("Please select at least one report.", "error")
            return redirect(url_for("dashboard"))

        try:
            report_ids = [int(r_id) for r_id in selected_reports]
        except ValueError:
            # In case someone tampers with the form data
            flash("Invalid report selection.", "error")
            return redirect(url_for("dashboard"))

        # UUID-based random key (short and easy to share)
       # UUID-based random key (short and easy to share)
        access_key = uuid.uuid4().hex[:12].upper()
        expiry_time = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")

        # Local network QR URL
        local_ip = "10.196.72.51"   # replace with your system IP
        qr_url = f"http://{local_ip}:5000/doctor?key={access_key}"

        img = qrcode.make(qr_url)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # Store the latest QR image in the session so the dashboard can display it
        session["latest_qr_image"] = qr_base64

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO access_keys (patient_id, access_key, expiry_time) VALUES (?, ?, ?)",
            (patient["id"], access_key, expiry_time),
        )
        access_key_id = cursor.lastrowid

        for report_id in report_ids:
            cursor.execute(
                "INSERT INTO key_reports (access_key_id, report_id) VALUES (?, ?)",
                (access_key_id, report_id),
            )

        conn.commit()
        conn.close()

        session.pop("smart_retrieval", None)
        flash("Access key generated.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/doctor", methods=["GET", "POST"])
    def doctor():
        reports = None
        access_key = None
        expiry_time = None                                        # ← ADDED

        def handle_access_key(raw_key: str):
            nonlocal reports, access_key, expiry_time            # ← ADDED expiry_time

            entered_key = (raw_key or "").strip().upper()
            if not entered_key:
                flash("Please enter an access key.", "error")
                return

            conn = get_db_connection()
            key_row = conn.execute(
                "SELECT id, patient_id, access_key, expiry_time FROM access_keys WHERE access_key = ? ORDER BY id DESC LIMIT 1",
                (entered_key,),
            ).fetchone()

            if not key_row:
                conn.close()
                flash("Invalid access key.", "error")
                return

            expiry_dt = datetime.strptime(key_row["expiry_time"], "%Y-%m-%d %H:%M:%S")
            if expiry_dt < datetime.now():
                conn.close()
                flash("Access key expired.", "error")
                return

            expiry_time = key_row["expiry_time"]                 # ← ADDED (raw string for JS)

            access_key_id = key_row["id"]
            patient_id_for_key = key_row["patient_id"]

            link_rows = conn.execute(
                "SELECT report_id FROM key_reports WHERE access_key_id = ?",
                (access_key_id,),
            ).fetchall()

            if not link_rows:
                conn.close()
                flash("No reports linked to this access key.", "error")
                return

            report_ids = [row["report_id"] for row in link_rows]

            placeholders = ",".join("?" for _ in report_ids)
            reports = conn.execute(
                f"SELECT id, file_name, original_filename, upload_date FROM reports WHERE id IN ({placeholders}) ORDER BY id DESC",
                report_ids,
            ).fetchall()
            conn.close()

            session["doctor_patient_id"] = patient_id_for_key

            access_key = entered_key
            flash("Access key accepted.", "success")

        # Manual form submission (existing behavior)
        if request.method == "POST":
            handle_access_key(request.form.get("access_key"))
            return render_template(
                "doctor.html",
                reports=reports,
                access_key=access_key,
                expiry_time=expiry_time                          # ← ADDED
            )

        # QR / direct link: /doctor?key=ACCESSKEY
        key_from_query = request.args.get("key")
        if key_from_query is not None:
            handle_access_key(key_from_query)
            return render_template(
                "doctor.html",
                reports=reports,
                access_key=access_key,
                expiry_time=expiry_time                          # ← ADDED
            )

        # GET request without a key: just show the form
        return render_template("doctor.html", reports=reports)
    # AI REPORT SUMMARY FEATURE
    @app.route("/summarize/<int:report_id>", methods=["GET"])
    def summarize(report_id: int):
        """
        Returns an AI summary for a specific report.
        Called from the doctor dashboard using fetch() so the page does not reload.
        """
        conn = get_db_connection()
        report_row = conn.execute(
            """
            SELECT r.id, r.patient_id, r.file_name, p.name, p.email
            FROM reports r
            JOIN patients p ON p.id = r.patient_id
            WHERE r.id = ?
            """,
            (report_id,),
        ).fetchone()

        if not report_row:
            conn.close()
            return jsonify({"error": "Report not found."}), 404

        # Only allow summarization if the current session is allowed to see this patient's reports
        patient = get_current_patient()
        doctor_patient_id = session.get("doctor_patient_id")

        allowed = False
        if patient and patient["id"] == report_row["patient_id"]:
            allowed = True
        if doctor_patient_id and int(doctor_patient_id) == int(report_row["patient_id"]):
            allowed = True

        if not allowed:
            conn.close()
            return jsonify({"error": "Not authorized to summarize this report."}), 403

        conn.close()

        file_path = os.path.join(app.config["UPLOAD_FOLDER"], report_row["file_name"])
        if not os.path.exists(file_path):
            return jsonify({"error": "Report file not found on disk."}), 404

        text = extract_text_from_report_file(file_path)
        if not text:
            return jsonify({
                "error": "Could not extract text from this report. "
                "For scanned PDFs or images, install Tesseract OCR and Poppler."
            }), 400

        # AI SECURITY & OCR FEATURE — extra redaction using known patient fields from DB
        text = redact_sensitive_info(
            text,
            extra_values=[report_row["name"], report_row["email"]],
        )

        try:
            summary = summarize_report(text)
        except Exception as e:
            print(e)
            return jsonify({"error": str(e)}), 500

        return jsonify({"summary": summary})

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        patient = get_current_patient()
        doctor_patient_id = session.get("doctor_patient_id")

        if not patient and not doctor_patient_id:
            flash("Please log in or use a valid access key.", "error")
            return redirect(url_for("home"))

        # If a patient is logged in, always use their id.
        # Otherwise, use the patient id from the doctor's validated access key.
        patient_id_to_check = patient["id"] if patient else doctor_patient_id

        conn = get_db_connection()
        report = conn.execute(
            "SELECT id FROM reports WHERE patient_id = ? AND file_name = ?",
            (patient_id_to_check, filename),
        ).fetchone()
        conn.close()

        if not report:
            flash("File not found.", "error")
            if patient:
                return redirect(url_for("dashboard"))
            return redirect(url_for("doctor"))

        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
