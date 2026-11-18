import os
import re
import sys
import html
import base64
import tempfile
import logging
import pandas as pd
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


def format_inline_md(text: str) -> str:
    cleaned = text.replace(r"\$", "$").replace(r"\|", " / ")
    cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)
    escaped = html.escape(cleaned).replace("\n", "<br>")
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    return escaped


def render_markdown_to_html(md_text: str) -> str:
    """Server-side Markdown to HTML renderer ensuring clean styled tables and lists."""
    lines = md_text.splitlines()
    out = []
    table_rows = []
    in_list = False

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return
        out.append('<div class="table-wrap"><table class="styled-table">')
        for idx, row in enumerate(table_rows):
            if idx == 1 and re.match(r"^[\s|:-]+$", row):
                continue
            cells = [c.strip() for c in row.strip("|").split("|")]
            if idx == 0:
                out.append("<thead><tr>" + "".join(f"<th>{format_inline_md(c)}</th>" for c in cells) + "</tr></thead><tbody>")
            else:
                out.append("<tr>" + "".join(f"<td>{format_inline_md(c)}</td>" for c in cells) + "</tr>")
        out.append("</tbody></table></div>")
        table_rows = []

    def flush_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw in lines:
        line = raw.strip()
        if "|" in line and (line.startswith("|") or line.count("|") >= 2):
            flush_list()
            table_rows.append(line)
            continue
        elif table_rows:
            flush_table()

        if not line or line == "---":
            flush_list()
            continue
        if line.startswith("### "):
            flush_list()
            out.append(f"<h3>{format_inline_md(line[4:])}</h3>")
        elif line.startswith("## "):
            flush_list()
            out.append(f"<h2>{format_inline_md(line[3:])}</h2>")
        elif line.startswith("# "):
            flush_list()
            out.append(f"<h2>{format_inline_md(line[2:])}</h2>")
        elif re.match(r"^([-*]|\d+\.)\s+", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = re.sub(r"^([-*]|\d+\.)\s+", "", line)
            out.append(f"<li>{format_inline_md(item)}</li>")
        else:
            flush_list()
            out.append(f"<p>{format_inline_md(line)}</p>")

    flush_table()
    flush_list()
    return "\n".join(out)


HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autonomous Multi-Agent CSV Analyst & Business Intelligence</title>
    <style>
        :root {
            --bg: #0b1120;
            --card: #111827;
            --card-alt: #1e293b;
            --border: #334155;
            --accent: #38bdf8;
            --accent-btn: #0284c7;
            --green-btn: #059669;
            --text: #f8fafc;
            --muted: #94a3b8;
        }
        body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); max-width: 1060px; margin: 28px auto; padding: 0 20px; line-height: 1.65; }
        .skip-link { position: absolute; left: -999px; background: var(--accent); color: #0f172a; padding: 8px 12px; font-weight: 700; }
        .skip-link:focus { left: 16px; top: 16px; z-index: 100; }
        .card { background: var(--card); padding: 26px; border-radius: 14px; border: 1px solid var(--border); margin-bottom: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.35); }
        header.card { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border-left: 4px solid var(--accent); }
        h1 { color: var(--accent); margin: 0 0 6px 0; font-size: 1.85rem; }
        h2 { color: #e2e8f0; font-size: 1.35rem; margin-top: 0; }
        label { display: block; margin: 14px 0 6px; font-weight: 600; color: #f1f5f9; }
        select, input[type="file"], textarea { width: 100%; padding: 11px 14px; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: var(--text); box-sizing: border-box; font-size: 1rem; }
        select:focus, input[type="file"]:focus, textarea:focus, button:focus, a.download-csv-btn:focus { outline: 3px solid var(--accent); outline-offset: 2px; }
        .btn-primary { margin-top: 18px; background: var(--accent-btn); color: #ffffff; border: none; padding: 12px 26px; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; }
        .btn-primary:hover { background: #0369a1; }
        .hint { font-size: 0.875rem; color: var(--muted); margin-top: 4px; }
        .error { color: #fecaca; font-weight: 600; background: #7f1d1d; padding: 14px; border-radius: 8px; border: 1px solid #f87171; }

        /* Toolbar & Action Buttons */
        .toolbar { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; padding-bottom: 16px; border-bottom: 1px solid var(--border); margin-bottom: 20px; }
        .tab-group, .action-group { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
        .tab-btn, .action-btn { background: var(--card-alt); color: #e2e8f0; border: 1px solid var(--border); padding: 8px 14px; border-radius: 8px; font-size: 0.9rem; font-weight: 600; cursor: pointer; text-decoration: none; }
        .tab-btn.active { background: var(--accent-btn); color: #ffffff; border-color: var(--accent); }
        .action-btn:hover, .tab-btn:hover { border-color: var(--accent); color: #ffffff; }
        .download-csv-btn { background: var(--green-btn); color: #ffffff; border: 1px solid #34d399; padding: 8px 16px; border-radius: 8px; font-size: 0.9rem; font-weight: 700; text-decoration: none; display: inline-block; }
        .download-csv-btn:hover { background: #047857; }

        /* Styled HTML Tables & Report Typography */
        .report-body h2 { color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: 6px; margin-top: 24px; }
        .report-body h3 { color: #7dd3fc; margin-top: 22px; font-size: 1.15rem; }
        .report-body p { color: #e2e8f0; margin: 10px 0; }
        .report-body ul { padding-left: 22px; color: #e2e8f0; }
        .report-body li { margin-bottom: 8px; }
        .table-wrap { overflow-x: auto; margin: 16px 0; border-radius: 10px; border: 1px solid var(--border); }
        table.styled-table { width: 100%; border-collapse: collapse; font-size: 0.94rem; text-align: left; }
        table.styled-table th { background: #1e293b; color: var(--accent); padding: 12px 14px; font-weight: 700; border-bottom: 2px solid var(--border); white-space: nowrap; }
        table.styled-table td { padding: 11px 14px; border-bottom: 1px solid #1e293b; color: #f1f5f9; }
        table.styled-table tbody tr:nth-child(even) { background: rgba(30, 41, 59, 0.45); }
        table.styled-table tbody tr:hover { background: rgba(56, 189, 248, 0.14); }

        .chart-box { background: #0f172a; padding: 18px; border-radius: 10px; border: 1px solid var(--border); margin-top: 22px; text-align: center; }
        .chart-box img { max-width: 100%; height: auto; border-radius: 8px; }
        .badge { background: #064e3b; color: #6ee7b7; padding: 3px 10px; border-radius: 999px; font-size: 0.82rem; font-weight: 600; border: 1px solid #10b981; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <a href="#main-content" class="skip-link">Skip to main content</a>
    <header class="card" role="banner">
        <h1>Autonomous Multi-Agent CSV Analyst</h1>
        <p style="margin:0; color:#cbd5e1;">LangGraph 3-Agent Pipeline: Schema Profiler &rarr; AST-Sandboxed Pandas Cleaner &amp; Analyst &rarr; Executive Strategist</p>
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

                <button type="submit" class="btn-primary">Run Multi-Agent Pipeline</button>
            </form>
        </section>

        <div aria-live="polite">
            {% if error %}
            <section class="card" role="alert">
                <h2>Processing Notice</h2>
                <p class="error">{{ error }}</p>
            </section>
            {% endif %}

            {% if report_html %}
            <section class="card" aria-labelledby="report-heading">
                <div class="toolbar">
                    <div class="tab-group" role="tablist" aria-label="Dashboard View Switcher">
                        <button type="button" class="tab-btn active" onclick="switchView('all', this)">Full Dashboard</button>
                        <button type="button" class="tab-btn" onclick="switchView('report', this)">Report &amp; Tables</button>
                        {% if cleaned_preview_html %}
                        <button type="button" class="tab-btn" onclick="switchView('data', this)">Cleaned CSV Data</button>
                        {% endif %}
                        {% if chart_b64 %}
                        <button type="button" class="tab-btn" onclick="switchView('chart', this)">Visual Chart</button>
                        {% endif %}
                    </div>
                    <div class="action-group">
                        {% if cleaned_csv_b64 %}
                        <a class="download-csv-btn" href="data:text/csv;base64,{{ cleaned_csv_b64 }}" download="cleaned_dataset.csv">Download Cleaned CSV</a>
                        {% endif %}
                        <button type="button" class="action-btn" id="copy-btn" onclick="copyReport()">Copy Report</button>
                        <button type="button" class="action-btn" onclick="downloadReport()">Download .MD</button>
                    </div>
                </div>

                <h2 id="report-heading" style="position:absolute;left:-9999px;">Executive Analysis Report</h2>
                <textarea id="raw-markdown" class="hidden" aria-hidden="true">{{ report_raw }}</textarea>

                <div id="report-section" class="report-body">
                    {{ report_html | safe }}
                </div>

                {% if cleaned_preview_html %}
                <div id="data-section" style="margin-top: 26px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                        <h3 style="color:#34d399; margin:0;">Cleaned Dataset Preview (Top 5 Rows) <span class="badge">{{ cleaned_shape }}</span></h3>
                        {% if cleaned_csv_b64 %}
                        <a class="download-csv-btn" href="data:text/csv;base64,{{ cleaned_csv_b64 }}" download="cleaned_dataset.csv">Download Full Cleaned CSV</a>
                        {% endif %}
                    </div>
                    <div class="table-wrap">
                        {{ cleaned_preview_html | safe }}
                    </div>
                </div>
                {% endif %}

                {% if chart_b64 %}
                <div id="chart-section" class="chart-box">
                    <h3 style="margin-top:0; color:#38bdf8;">Generated Statistical Visualization</h3>
                    <img src="data:image/png;base64,{{ chart_b64 }}" alt="Automated statistical visualization generated for: {{ goal }}">
                </div>
                {% endif %}
            </section>
            {% endif %}
        </div>
    </main>

    <script>
        function switchView(mode, btn) {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const rep = document.getElementById("report-section");
            const dat = document.getElementById("data-section");
            const ch = document.getElementById("chart-section");
            const show = (el, flag) => { if (el) el.classList.toggle("hidden", !flag); };

            if (mode === "all") { show(rep, true); show(dat, true); show(ch, true); }
            else if (mode === "report") { show(rep, true); show(dat, false); show(ch, false); }
            else if (mode === "data") { show(rep, false); show(dat, true); show(ch, false); }
            else if (mode === "chart") { show(rep, false); show(dat, false); show(ch, true); }
        }

        function copyReport() {
            const rawBox = document.getElementById("raw-markdown");
            if (!rawBox) return;
            navigator.clipboard.writeText(rawBox.value).then(() => {
                const btn = document.getElementById("copy-btn");
                btn.textContent = "Copied!";
                setTimeout(() => { btn.textContent = "Copy Report"; }, 2000);
            });
        }

        function downloadReport() {
            const rawBox = document.getElementById("raw-markdown");
            if (!rawBox) return;
            const blob = new Blob([rawBox.value], { type: "text/markdown;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "executive_analysis_report.md";
            a.click();
            URL.revokeObjectURL(url);
        }
    </script>
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
    report_raw = ""
    report_html = ""
    chart_b64 = ""
    cleaned_csv_b64 = ""
    cleaned_preview_html = ""
    cleaned_shape = ""
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
                "cleaned_csv_path": "",
                "generated_code": "",
                "analysis_output": "",
                "error_log": "",
                "retry_count": 0,
                "final_report": "",
            })

            report_raw = result.get("final_report", "")
            report_html = render_markdown_to_html(report_raw)

            c_path = result.get("chart_path", "")
            if c_path and os.path.exists(c_path):
                with open(c_path, "rb") as img_f:
                    chart_b64 = base64.b64encode(img_f.read()).decode("utf-8")

            clean_csv_path = result.get("cleaned_csv_path", "")
            if clean_csv_path and os.path.exists(clean_csv_path):
                with open(clean_csv_path, "rb") as csv_f:
                    cleaned_csv_b64 = base64.b64encode(csv_f.read()).decode("utf-8")
                df_clean = pd.read_csv(clean_csv_path)
                cleaned_shape = f"{df_clean.shape[0]} rows x {df_clean.shape[1]} cols"
                cleaned_preview_html = df_clean.head(5).to_html(index=False, classes="styled-table", border=0)

        except ValueError as ve:
            error = str(ve)
        except Exception as exc:
            logging.exception("Agent pipeline error")
            error = f"Unable to complete analysis: {type(exc).__name__}. Please verify your CSV format and try again."

    return render_template_string(
        HTML_TEMPLATE,
        report_raw=report_raw,
        report_html=report_html,
        chart_b64=chart_b64,
        cleaned_csv_b64=cleaned_csv_b64,
        cleaned_preview_html=cleaned_preview_html,
        cleaned_shape=cleaned_shape,
        error=error,
        goal=goal,
    )

