"""
Smart Medical Report Retrieval — standalone service layer.

Workflow:
    1. Receive predicted disease + selected symptoms (from ML module).
    2. Load patient reports from SQLite (summary + extracted_text).
    3. Locally score/filter reports to reduce Groq payload size.
    4. Ask Groq to rank filtered reports and explain relevance.
    5. Return top recommendations for the dashboard sharing UI.

Does NOT retrain ML models or modify QR / access-key logic.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from groq import Groq

MAX_REPORTS_TO_GROQ = 8
SUMMARY_SNIPPET_LEN = 1200
EXTRACTED_SNIPPET_LEN = 1500


class SmartRetrievalError(Exception):
    """Base error for smart report retrieval."""


class NoReportsError(SmartRetrievalError):
    """Patient has no uploaded reports."""


def _tokenize_disease(disease_name: str) -> List[str]:
    """Split a disease label into lowercase keywords for local matching."""
    tokens = re.findall(r"[a-z0-9]+", (disease_name or "").lower())
    return [t for t in tokens if len(t) > 2]


def _normalize_symptom_token(symptom: str) -> str:
    cleaned = symptom.strip().lower().replace(" ", "_")
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_")


def fetch_patient_reports(conn, patient_id: int) -> List[Dict[str, Any]]:
    """
    Database query — load all reports for the logged-in patient.

    SQL:
        SELECT id, file_name, original_filename, upload_date, category,
               summary, extracted_text
        FROM reports
        WHERE patient_id = ?
        ORDER BY upload_date DESC
    """
    rows = conn.execute(
        """
        SELECT id, file_name, original_filename, upload_date, category,
               summary, extracted_text
        FROM reports
        WHERE patient_id = ?
        ORDER BY upload_date DESC
        """,
        (patient_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def score_report_locally(
    report: Dict[str, Any],
    predicted_disease: str,
    symptoms: List[str],
) -> int:
    """
    Local pre-filter scoring (no AI).

    Higher score = more likely relevant to predicted disease/symptoms.
    Checks summary, extracted_text, category, and filename.
    """
    parts = [
        report.get("summary") or "",
        report.get("extracted_text") or "",
        report.get("category") or "",
        report.get("original_filename") or "",
        report.get("file_name") or "",
    ]
    haystack = " ".join(parts).lower()

    score = 0
    for token in _tokenize_disease(predicted_disease):
        if token in haystack:
            score += 3

    disease_lower = predicted_disease.lower()
    category = (report.get("category") or "").lower()
    if category and (category in disease_lower or disease_lower in category):
        score += 8

    for symptom in symptoms:
        key = _normalize_symptom_token(symptom)
        if not key:
            continue
        if key in haystack or key.replace("_", " ") in haystack:
            score += 2

    if report.get("summary"):
        score += 1
    if report.get("extracted_text"):
        score += 1

    return score


def locally_filter_reports(
    reports: List[Dict[str, Any]],
    predicted_disease: str,
    symptoms: List[str],
) -> List[Tuple[int, Dict[str, Any]]]:
    """
    Rank reports locally and return the top candidates for Groq.

    Only reports with score > 0 are preferred. If none match, fall back to
    reports that have summary/text, then to the most recent uploads.
    """
    if not reports:
        return []

    scored = [
        (score_report_locally(report, predicted_disease, symptoms), report)
        for report in reports
    ]
    scored.sort(key=lambda item: item[0], reverse=True)

    positive = [(score, report) for score, report in scored if score > 0]
    if positive:
        return positive[:MAX_REPORTS_TO_GROQ]

    with_content = [
        (score, report)
        for score, report in scored
        if (report.get("summary") or report.get("extracted_text"))
    ]
    if with_content:
        return with_content[:MAX_REPORTS_TO_GROQ]

    return scored[: min(MAX_REPORTS_TO_GROQ, len(scored))]


def _truncate(text: str, limit: int) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def build_retrieval_prompt(
    predicted_disease: str,
    symptoms: List[str],
    filtered_reports: List[Tuple[int, Dict[str, Any]]],
    redact_fn,
) -> str:
    """
    Prompt engineering for Groq report retrieval.

    Design choices:
        - Role: clinical assistant helping a patient share relevant records.
        - Inputs: predicted disease, symptom list, compact report bundles.
        - Task: pick reports a doctor would need for this presentation.
        - Output: strict JSON only (easy to parse in Python).
        - Rules: use only provided report IDs; score 0-100; brief reasons.
    """
    if redact_fn is None:
        raise SmartRetrievalError("Redaction function is required for Groq calls.")

    symptom_labels = ", ".join(symptoms) if symptoms else "None listed"

    report_blocks = []
    for local_score, report in filtered_reports:
        summary = redact_fn(_truncate(report.get("summary") or "", SUMMARY_SNIPPET_LEN))
        extracted = redact_fn(
            _truncate(report.get("extracted_text") or "", EXTRACTED_SNIPPET_LEN)
        )
        block = (
            f"Report ID: {report['id']}\n"
            f"Filename: {report.get('original_filename') or report.get('file_name')}\n"
            f"Category: {report.get('category') or 'General'}\n"
            f"Upload date: {report.get('upload_date') or 'Unknown'}\n"
            f"Local relevance score: {local_score}\n"
            f"Summary:\n{summary or 'Not available'}\n"
            f"Extracted text:\n{extracted or 'Not available'}\n"
        )
        report_blocks.append(block)

    reports_section = "\n---\n".join(report_blocks)

    return f"""You are a clinical assistant helping a patient share the most relevant medical reports with a doctor.

Predicted disease (highest ML confidence): {predicted_disease}
Patient-selected symptoms: {symptom_labels}

Below are pre-filtered patient reports. Each has a Report ID, summary, and extracted text (de-identified).

Your task:
1. Choose up to 3 reports most relevant to the predicted disease and symptoms.
2. Assign each a relevance_score from 0 to 100 (integer).
3. Give a one-sentence reason for each selection.

Rules:
- Use ONLY Report IDs from the list below.
- Do NOT invent reports or medical facts not supported by the text.
- Prefer reports with lab values, diagnoses, or findings related to {predicted_disease}.
- If no report is clearly relevant, return an empty JSON array [].
- Return ONLY valid JSON — no markdown, no extra text.

JSON format:
[
  {{"report_id": 1, "relevance_score": 85, "reason": "Contains elevated HbA1c consistent with diabetes."}}
]

Reports:
{reports_section}
"""


def _parse_groq_json(raw_content: str) -> List[Dict[str, Any]]:
    """Extract and parse a JSON array from Groq model output."""
    content = (raw_content or "").strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
    if fence_match:
        content = fence_match.group(1).strip()

    array_match = re.search(r"\[\s*\{.*?\}\s*\]", content, re.DOTALL)
    if array_match:
        content = array_match.group(0)

    parsed = json.loads(content)
    if not isinstance(parsed, list):
        raise ValueError("Groq response is not a JSON array.")
    return parsed


def rank_reports_with_groq(
    predicted_disease: str,
    symptoms: List[str],
    filtered_reports: List[Tuple[int, Dict[str, Any]]],
    redact_fn,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Send filtered reports to Groq and return structured recommendations."""
    if not filtered_reports:
        return []

    key = api_key or os.getenv("API_KEY")
    if not key:
        raise SmartRetrievalError("API_KEY is not configured for Groq.")

    prompt = build_retrieval_prompt(
        predicted_disease, symptoms, filtered_reports, redact_fn
    )
    client = Groq(api_key=key)
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    raw = completion.choices[0].message.content
    items = _parse_groq_json(raw)

    allowed_ids = {report["id"] for _, report in filtered_reports}
    report_lookup = {report["id"]: report for _, report in filtered_reports}

    recommendations = []
    for item in items:
        if not isinstance(item, dict):
            continue
        report_id = item.get("report_id")
        try:
            report_id = int(report_id)
        except (TypeError, ValueError):
            continue
        if report_id not in allowed_ids:
            continue

        score = item.get("relevance_score", 0)
        try:
            score = max(0, min(100, int(round(float(score)))))
        except (TypeError, ValueError):
            score = 0

        reason = str(item.get("reason") or "Relevant to predicted condition.").strip()
        source = report_lookup[report_id]
        recommendations.append(
            {
                "report_id": report_id,
                "relevance_score": score,
                "reason": reason,
                "filename": source.get("original_filename") or source.get("file_name"),
                "category": source.get("category") or "General",
            }
        )

    recommendations.sort(key=lambda row: row["relevance_score"], reverse=True)
    return recommendations[:3]


def fallback_recommendations(
    filtered_reports: List[Tuple[int, Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Use local scores when Groq is unavailable or returns nothing."""
    results = []
    for local_score, report in filtered_reports[:3]:
        results.append(
            {
                "report_id": report["id"],
                "relevance_score": min(100, max(10, local_score * 8)),
                "reason": (
                    "Selected by local keyword matching against the predicted disease "
                    "and your symptoms (AI ranking unavailable)."
                ),
                "filename": report.get("original_filename") or report.get("file_name"),
                "category": report.get("category") or "General",
            }
        )
    return results


def run_smart_report_retrieval(
    conn,
    patient_id: int,
    predicted_disease: str,
    symptoms: List[str],
    redact_fn,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    End-to-end smart retrieval for one patient.

    Returns:
        {
            "predicted_disease": str,
            "symptoms": list,
            "recommendations": [ {report_id, relevance_score, reason, filename, category}, ... ],
            "filtered_count": int,
            "total_reports": int,
            "used_groq": bool,
        }
    """
    reports = fetch_patient_reports(conn, patient_id)
    if not reports:
        raise NoReportsError("You have no uploaded reports. Upload reports on the dashboard first.")

    filtered = locally_filter_reports(reports, predicted_disease, symptoms)
    recommendations: List[Dict[str, Any]] = []
    used_groq = False

    try:
        recommendations = rank_reports_with_groq(
            predicted_disease, symptoms, filtered, redact_fn, api_key=api_key
        )
        used_groq = bool(recommendations)
    except Exception as exc:
        print(f"Groq report retrieval failed, using local fallback: {exc}")

    if not recommendations:
        recommendations = fallback_recommendations(filtered)

    return {
        "predicted_disease": predicted_disease,
        "symptoms": symptoms,
        "recommendations": recommendations,
        "filtered_count": len(filtered),
        "total_reports": len(reports),
        "used_groq": used_groq,
    }
