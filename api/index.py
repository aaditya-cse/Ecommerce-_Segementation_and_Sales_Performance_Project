import os
import sys
import base64
import tempfile
import logging
from werkzeug.utils import secure_filename

os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

from flask import Flask, request, render_template_string

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "multi_agent"))

from universal_analyst_agent import build_universal_graph

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
logging.basicConfig(level=logging.INFO)

AGENT_GRAPH = build_universal_graph()

ALLOWED_SAMPLES = {
    "data/raw/ecommerce_sales_data.csv",
    "data/raw/edtech_student_enrollments.csv",
    "data/raw/food_delivery_operations.csv",
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autonomous Multi-Agent CSV Analyst & Business Intelligence</title>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #f8fafc; max-width: 900px; margin: 32px auto; padding: 0 20px; line-height: 1.6; }
        .skip-link { position: absolute; left: -999px; background: #38bdf8; color: #0f172a; padding: 8px 12px; font-weight: 700; }
        .skip-link:focus { left: 16px; top: 16px; z-index: 100; }
        .card { background: #1e293b; padding: 24px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 24px; }
        h1 { color: #38bdf8; margin-top: 0; font-size: 1.75rem; }
        h2 { color: #e2e8f0; font-size: 1.3rem; }
        label { display: block; margin: 14px 0 6px; font-weight: 600; color: #f1f5f9; }
        select, input[type="file"], textarea { width: 100%; padding: 10px 12px; border-radius: 8px; border: 1px solid #64748b; background: #0f172a; color: #f8fafc; box-sizing: border-box; font-size: 1rem; }
        select:focus, input[type="file"]:focus, textarea:focus, button:focus { outline: 3px solid #38bdf8; outline-offset: 2px; }
        button { margin-top: 18px; background: #0284c7; color: #ffffff; border: none; padding: 12px 24px; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; }
        button:hover { background: #0369a1; }
        pre { white-space: pre-wrap; background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #334155; font-family: inherit; color: #f8fafc; }
        img { max-width: 100%; height: auto; border-radius: 8px; margin-top: 16px; border: 1px solid #334155; }
        .error { color: #fecaca; font-weight: 600; background: #7f1d1d; padding: 14px; border-radius: 8px; border: 1px solid #f87171; }
        .hint { font-size: 0.875rem; color: #cbd5e1; margin-top: 4px; }
    </style>
</head>
<body>
    <a href="#main-content" class="skip-link">Skip to main content</a>
    <header class="card" role="banner">
        <h1>Autonomous Multi-Agent CSV Analyst</h1>
        <p>LangGraph 3-Agent Pipeline: Schema Profiler &rarr; AST-Sandboxed Pandas Analyst &rarr; Executive Strategist</p>
    </header>

    <main id="main-content" role="main">
        <section class="card" aria-labelledby="form-heading">
            <h2 id="form-heading">Configure Dataset &amp; Analysis Goal</h2>
            <form method="POST" enctype="multipart/form-data">
                <label for="sample-csv">1. Choose Built-in Sample Dataset:</label>
                <select id="sample-csv" name="sample_csv">
                    <option value="data/raw/ecommerce_sales_data.csv">E-Commerce Sales &amp; RFM Segmentation (371 rows)</option>
                    <option value="data/raw/edtech_student_enrollments.csv">EdTech Student Enrollments (184 rows)</option>
                    <option value="data/raw/food_delivery_operations.csv">Food Delivery Operations (250 rows)</option>
                </select>

                <label for="uploaded-csv">OR Upload Custom CSV File (Max 5 MB):</label>
                <input id="uploaded-csv" type="file" name="uploaded_csv" accept=".csv" aria-describedby="csv-hint">
                <p id="csv-hint" class="hint">Only valid .csv files up to 5 MB are accepted.</p>

                <label for="user-goal">2. Ask Any Business or Data Analysis Question:</label>
                <textarea id="user-goal" name="user_goal" rows="3" required placeholder="e.g., Clean duplicates and nulls, calculate net revenue by category, and plot a chart.">{{ goal }}</textarea>

                <button type="submit">Run Multi-Agent Pipeline</button>
            </form>
        </section>

        <div aria-live="polite">
            {% if error %}
            <section class="card" role="alert">
                <h2>Processing Notice</h2>
                <p class="error">{{ error }}</p>
            </section>
            {% endif %}

            {% if report %}
            <section class="card" aria-labelledby="report-heading">
                <h2 id="report-heading">Executive Analysis Report</h2>
                <pre>{{ report }}</pre>
                {% if chart_b64 %}
                <h3>Generated Data Visualization</h3>
                <img src="data:image/png;base64,{{ chart_b64 }}" alt="Automated statistical visualization generated for: {{ goal }}">
                {% endif %}
            </section>
            {% endif %}
        </div>
    </main>
</body>
</html>
"""


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
@app.route("/<path:path>", methods=["GET", "POST"])
def home(path):
    report = ""
    chart_b64 = ""
    error = ""
    goal = "Clean duplicates and missing values, summarize top KPIs, and plot the primary revenue driver."

    if request.method == "POST":
        goal = request.form.get("user_goal", "").strip()[:500] or goal
        uploaded = request.files.get("uploaded_csv")

        try:
            if not os.getenv("GROQ_API_KEY"):
                raise ValueError("Server configuration incomplete: GROQ_API_KEY is not configured.")

            if uploaded and uploaded.filename:
                safe_name = secure_filename(uploaded.filename)
                if not safe_name.lower().endswith(".csv"):
                    raise ValueError("Invalid file format. Please upload a .csv file.")
                tmp_csv = os.path.join(tempfile.gettempdir(), safe_name)
                uploaded.save(tmp_csv)
                csv_path = tmp_csv
            else:
                rel_path = request.form.get("sample_csv", "data/raw/ecommerce_sales_data.csv")
                if rel_path not in ALLOWED_SAMPLES:
                    raise ValueError("Invalid sample dataset selected.")
                csv_path = os.path.join(ROOT_DIR, rel_path)

            result = AGENT_GRAPH.invoke({
                "csv_path": csv_path,
                "user_goal": goal,
                "dataset_profile": "",
                "chat_history": [],
                "chart_path": "",
                "generated_code": "",
                "analysis_output": "",
                "error_log": "",
                "retry_count": 0,
                "final_report": "",
            })

            report = result.get("final_report", "")
            c_path = result.get("chart_path", "")
            if c_path and os.path.exists(c_path):
                with open(c_path, "rb") as img_f:
                    chart_b64 = base64.b64encode(img_f.read()).decode("utf-8")
        except ValueError as ve:
            error = str(ve)
        except Exception as exc:
            logging.exception("Agent pipeline error")
            error = f"Unable to complete analysis: {type(exc).__name__}. Please verify your CSV format and try again."

    return render_template_string(HTML_TEMPLATE, report=report, chart_b64=chart_b64, error=error, goal=goal)
