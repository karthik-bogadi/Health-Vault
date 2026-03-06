"""Main application file for the Health Vault Flask app.

This file keeps everything in one place so it is easy
to read and understand for beginners.
"""

import os
import sqlite3
import uuid
from datetime import datetime, timedelta

import base64
from io import BytesIO
import qrcode
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()
# AI REPORT SUMMARY FEATURE
from groq import Groq
from PyPDF2 import PdfReader

from flask import Flask, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename


# ----------------------
# Database configuration
# ----------------------

DATABASE_NAME = "health_vault.db"
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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
# AI REPORT SUMMARY FEATURE
def summarize_report(text):
    client = Groq(api_key=API_KEY)

    prompt = f"Summarize this medical report in simple bullet points for a doctor:\n\n{text}"

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return completion.choices[0].message.content


# AI REPORT SUMMARY FEATURE
def extract_text_from_report_file(file_path: str) -> str:
    """Extract text from supported report types (PDF, TXT)."""
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext == ".pdf":
        reader = PdfReader(file_path)
        parts = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                parts.append(page_text)
        return "\n\n".join(parts).strip()

    if ext in {".txt"}:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()

    # Images (jpg/png) are supported uploads, but we don't OCR them here.
    return ""


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

            # Store file on disk with a UUID-based filename (keep original separately for display)
            unique_name = f"{uuid.uuid4().hex}_{original_name}"
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
            file.save(save_path)

            upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO reports (patient_id, file_name, original_filename, upload_date) VALUES (?, ?, ?, ?)",
                (patient["id"], unique_name, original_name, upload_date),
            )
            conn.commit()
            conn.close()

            flash("Report uploaded successfully.", "success")
            return redirect(url_for("dashboard"))

        conn = get_db_connection()
        reports = conn.execute(
            "SELECT id, file_name, original_filename, upload_date FROM reports WHERE patient_id = ? ORDER BY id DESC",
            (patient["id"],),
        ).fetchall()

        latest_key = conn.execute(
            "SELECT access_key, expiry_time FROM access_keys WHERE patient_id = ? ORDER BY id DESC LIMIT 1",
            (patient["id"],),
        ).fetchone()
        conn.close()

        return render_template(
            "dashboard.html",
            patient=patient,
            reports=reports,
            latest_key=latest_key,
            qr_code_image=qr_code_image,
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
        access_key = uuid.uuid4().hex[:12].upper()
        expiry_time = (datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")

        # Build a QR code that points to the doctor page with this key
        qr_url = url_for("doctor", key=access_key, _external=True)

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
            "SELECT id, patient_id, file_name FROM reports WHERE id = ?",
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
            return jsonify({"error": "Could not extract text from this report type."}), 400

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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
