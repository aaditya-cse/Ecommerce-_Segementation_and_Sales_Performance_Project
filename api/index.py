"""Flask entrypoint for the Autonomous Multi-Agent CSV Analyst web application."""

import base64
import logging
import os
import sys
import tempfile
import uuid
from typing import Tuple

import pandas as pd
from flask import Flask, Response, render_template_string, request
from werkzeug.utils import secure_filename

os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

API_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(API_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)
if os.path.join(ROOT_DIR, "multi_agent") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT_DIR, "multi_agent"))

from renderer import extract_kpi_cards, render_markdown_to_html  # noqa: E402
from security import (  # noqa: E402
    SlidingWindowRateLimiter,
    apply_hardened_headers,
    sanitize_csv_cell,
    validate_csv_bytes,
)
from universal_analyst_agent import build_universal_graph  # noqa: E402
from views import DASHBOARD_HTML, STUDIO_HTML  # noqa: E402

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
logging.basicConfig(level=logging.INFO)

AGENT_GRAPH = build_universal_graph()
RATE_LIMITER = SlidingWindowRateLimiter(max_requests=25, window_seconds=60)

ALLOWED_SAMPLES = {
    "data/raw/ecommerce_sales_data.csv",
    "data/raw/edtech_student_enrollments.csv",
    "data/raw/food_delivery_operations.csv",
}


def _resolve_input_csv() -> Tuple[str, str, bool]:
    """Validate uploaded CSV or sample dataset selection and return (path, label, is_temp)."""
    uploaded = request.files.get("uploaded_csv")
    if uploaded and uploaded.filename:
        safe_name = secure_filename(uploaded.filename)
        if not safe_name.lower().endswith(".csv"):
            raise ValueError("Invalid file format. Only .csv files are permitted.")
        raw_bytes = uploaded.read()
        decoded_csv = validate_csv_bytes(raw_bytes)
        unique_name = f"upload_{uuid.uuid4().hex}_{safe_name}"
        tmp_csv = os.path.join(tempfile.gettempdir(), unique_name)
        with open(tmp_csv, "w", encoding="utf-8", newline="") as out_f:
            out_f.write(decoded_csv)
        return tmp_csv, f"Uploaded: {safe_name}", True

    rel_path = request.form.get("sample_csv", "data/raw/ecommerce_sales_data.csv")
    if rel_path not in ALLOWED_SAMPLES:
        raise ValueError("Invalid sample dataset selected.")
    return os.path.join(ROOT_DIR, rel_path), os.path.basename(rel_path), False


@app.after_request
def add_security_headers(response: Response) -> Response:
    """Apply strict security headers to all outgoing responses."""
    return apply_hardened_headers(response)


@app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
@app.route("/<path:path>", methods=["GET", "POST"])
def analyze(path: str):
    """Render the Studio landing page on GET or execute the 3-agent pipeline on POST."""
    if request.method == "GET":
        return render_template_string(STUDIO_HTML)

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "local").split(",")[0].strip()
    allowed, retry_after = RATE_LIMITER.is_allowed(client_ip)
    if not allowed:
        return (
            render_template_string(
                DASHBOARD_HTML,
                report_raw="",
                report_html="",
                charts_b64=[],
                cleaned_csv_b64="",
                cleaned_preview_html="",
                cleaned_shape="",
                generated_code="",
                analysis_output="",
                kpi_cards=[],
                retry_count=0,
                dataset_label="Rate Limited",
                error=f"Too many requests. Please wait {retry_after} seconds before running another analysis.",
                goal="",
            ),
            429,
        )

    goal = (
        request.form.get("user_goal", "").strip()[:500]
        or "Clean duplicates and missing values, summarize top KPIs, and plot the primary revenue driver."
    )
    report_raw = ""
    report_html = ""
    charts_b64 = []
    cleaned_csv_b64 = ""
    cleaned_preview_html = ""
    cleaned_shape = ""
    generated_code = ""
    analysis_output = ""
    kpi_cards = []
    retry_count = 1
    error = ""
    dataset_label = "Sample Dataset"
    tmp_path = ""
    is_temp = False

    try:
        if not os.getenv("GROQ_API_KEY"):
            raise ValueError("Server configuration incomplete: GROQ_API_KEY is not configured.")

        csv_path, dataset_label, is_temp = _resolve_input_csv()
        if is_temp:
            tmp_path = csv_path

        result = AGENT_GRAPH.invoke({
            "csv_path": csv_path,
            "user_goal": goal,
            "dataset_profile": "",
            "chat_history": [],
            "chart_path": "",
            "chart_paths": [],
            "cleaned_csv_path": "",
            "generated_code": "",
            "analysis_output": "",
            "error_log": "",
            "retry_count": 0,
            "final_report": "",
        })

        report_raw = result.get("final_report", "")
        report_html = render_markdown_to_html(report_raw)
        generated_code = result.get("generated_code", "")
        analysis_output = result.get("analysis_output", "")
        kpi_cards = extract_kpi_cards(analysis_output)
        retry_count = result.get("retry_count", 1)

        charts_b64 = []
        raw_paths = result.get("chart_paths") or ([result.get("chart_path")] if result.get("chart_path") else [])
        for c_path in [p for p in raw_paths if p and os.path.exists(p)][:3]:
            with open(c_path, "rb") as img_f:
                charts_b64.append(base64.b64encode(img_f.read()).decode("utf-8"))

        clean_csv_path = result.get("cleaned_csv_path", "")
        if clean_csv_path and os.path.exists(clean_csv_path):
            with open(clean_csv_path, "rb") as csv_f:
                cleaned_csv_b64 = base64.b64encode(csv_f.read()).decode("utf-8")
            df_clean = pd.read_csv(clean_csv_path)
            cleaned_shape = f"{df_clean.shape[0]} rows x {df_clean.shape[1]} cols"
            preview_df = df_clean.head(15).copy()
            for col in preview_df.select_dtypes(include="object").columns:
                preview_df[col] = preview_df[col].astype(str).map(sanitize_csv_cell)
            cleaned_preview_html = preview_df.to_html(index=False, classes="styled-table", border=0)

    except ValueError as ve:
        error = str(ve)
    except Exception as exc:
        logging.exception("Agent pipeline error")
        error = f"Unable to complete analysis: {type(exc).__name__}. Please verify your CSV format and try again."
    finally:
        if is_temp and tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    return render_template_string(
        DASHBOARD_HTML,
        report_raw=report_raw,
        report_html=report_html,
        charts_b64=charts_b64,
        cleaned_csv_b64=cleaned_csv_b64,
        cleaned_preview_html=cleaned_preview_html,
        cleaned_shape=cleaned_shape,
        generated_code=generated_code,
        analysis_output=analysis_output,
        kpi_cards=kpi_cards,
        retry_count=retry_count,
        dataset_label=dataset_label,
        error=error,
        goal=goal,
    )