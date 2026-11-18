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
            --text: #f8fafc;
            --muted: #94a3b8;
        }
        body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); max-width: 1020px; margin: 28px auto; padding: 0 20px; line-height: 1.65; }
        .skip-link { position: absolute; left: -999px; background: var(--accent); color: #0f172a; padding: 8px 12px; font-weight: 700; }
        .skip-link:focus { left: 16px; top: 16px; z-index: 100; }
        .card { background: var(--card); padding: 26px; border-radius: 14px; border: 1px solid var(--border); margin-bottom: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.35); }
        header.card { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border-left: 4px solid var(--accent); }
        h1 { color: var(--accent); margin: 0 0 6px 0; font-size: 1.85rem; }
        h2 { color: #e2e8f0; font-size: 1.35rem; margin-top: 0; }
        label { display: block; margin: 14px 0 6px; font-weight: 600; color: #f1f5f9; }
        select, input[type="file"], textarea { width: 100%; padding: 11px 14px; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: var(--text); box-sizing: border-box; font-size: 1rem; }
        select:focus, input[type="file"]:focus, textarea:focus, button:focus { outline: 3px solid var(--accent); outline-offset: 2px; }
        .btn-primary { margin-top: 18px; background: var(--accent-btn); color: #ffffff; border: none; padding: 12px 26px; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: background 0.2s; }
        .btn-primary:hover { background: #0369a1; }
        .hint { font-size: 0.875rem; color: var(--muted); margin-top: 4px; }
        .error { color: #fecaca; font-weight: 600; background: #7f1d1d; padding: 14px; border-radius: 8px; border: 1px solid #f87171; }

        /* Interactive Report Toolbar & Tabs */
        .toolbar { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; padding-bottom: 16px; border-bottom: 1px solid var(--border); margin-bottom: 20px; }
        .tab-group, .action-group { display: flex; gap: 8px; flex-wrap: wrap; }
        .tab-btn, .action-btn { background: var(--card-alt); color: #e2e8f0; border: 1px solid var(--border); padding: 8px 14px; border-radius: 8px; font-size: 0.9rem; font-weight: 600; cursor: pointer; transition: all 0.15s; }
        .tab-btn.active { background: var(--accent-btn); color: #ffffff; border-color: var(--accent); }
        .action-btn:hover, .tab-btn:hover { border-color: var(--accent); color: #ffffff; }

        /* Rendered Markdown Dashboard Styles */
        .report-body h2 { color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: 6px; margin-top: 24px; }
        .report-body h3 { color: #7dd3fc; margin-top: 22px; font-size: 1.15rem; }
        .report-body p { color: #e2e8f0; margin: 10px 0; }
        .report-body ul, .report-body ol { padding-left: 22px; color: #e2e8f0; }
        .report-body li { margin-bottom: 8px; }
        .report-body strong { color: #ffffff; }
        .table-wrap { overflow-x: auto; margin: 16px 0; border-radius: 10px; border: 1px solid var(--border); }
        table.styled-table { width: 100%; border-collapse: collapse; font-size: 0.95rem; text-align: left; }
        table.styled-table th { background: #1e293b; color: var(--accent); padding: 12px 14px; font-weight: 700; border-bottom: 2px solid var(--border); }
        table.styled-table td { padding: 11px 14px; border-bottom: 1px solid #1e293b; color: #f1f5f9; }
        table.styled-table tr:nth-child(even) { background: rgba(30, 41, 59, 0.45); }
        table.styled-table tr:hover { background: rgba(56, 189, 248, 0.12); }

        .chart-box { background: #0f172a; padding: 16px; border-radius: 10px; border: 1px solid var(--border); margin-top: 20px; text-align: center; }
        .chart-box img { max-width: 100%; height: auto; border-radius: 8px; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <a href="#main-content" class="skip-link">Skip to main content</a>
    <header class="card" role="banner">
        <h1>Autonomous Multi-Agent CSV Analyst</h1>
        <p style="margin:0; color:#cbd5e1;">LangGraph 3-Agent Pipeline: Schema Profiler &rarr; AST-Sandboxed Pandas Analyst &rarr; Executive Strategist</p>
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

            {% if report %}
            <section class="card" aria-labelledby="report-heading">
                <div class="toolbar">
                    <div class="tab-group" role="tablist" aria-label="Report View Switcher">
                        <button type="button" class="tab-btn active" onclick="switchView('all', this)">Full Dashboard</button>
                        <button type="button" class="tab-btn" onclick="switchView('report', this)">Tables &amp; Insights</button>
                        {% if chart_b64 %}
                        <button type="button" class="tab-btn" onclick="switchView('chart', this)">Visual Chart</button>
                        {% endif %}
                    </div>
                    <div class="action-group">
                        <button type="button" class="action-btn" id="copy-btn" onclick="copyReport()">Copy Report</button>
                        <button type="button" class="action-btn" onclick="downloadReport()">Download .MD</button>
                    </div>
                </div>

                <h2 id="report-heading" class="sr-only" style="position:absolute;left:-9999px;">Executive Analysis Report</h2>
                <textarea id="raw-markdown" class="hidden" aria-hidden="true">{{ report }}</textarea>
                <div id="rendered-report" class="report-body"></div>

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
        function escapeHtml(str) {
            return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }

        function formatInline(text) {
            return escapeHtml(text)
                .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
                .replace(/\*(.+?)\*/g, "<em>$1</em>")
                .replace(/`(.+?)`/g, "<code style='background:#1e293b;padding:2px 6px;border-radius:4px;'>$1</code>");
        }

        function renderMarkdownDashboard(md) {
            const lines = md.split(/\r?\n/);
            let html = "";
            let inTable = false;
            let tableRows = [];
            let inList = false;

            function flushTable() {
                if (!tableRows.length) return;
                html += '<div class="table-wrap"><table class="styled-table">';
                tableRows.forEach((row, idx) => {
                    if (idx === 1 && /^[\s|:-]+$/.test(row)) return;
                    const cells = row.replace(/^\||\|$/g, "").split("|").map(c => c.trim());
                    const tag = idx === 0 ? "th" : "td";
                    html += "<tr>" + cells.map(c => `<${tag}>${formatInline(c)}</${tag}>`).join("") + "</tr>";
                });
                html += "</table></div>";
                tableRows = [];
                inTable = false;
            }

            function flushList() {
                if (inList) { html += "</ul>"; inList = false; }
            }

            for (let rawLine of lines) {
                const line = rawLine.trim();
                if (line.startsWith("|") && line.endsWith("|")) {
                    flushList();
                    inTable = true;
                    tableRows.push(line);
                    continue;
                } else if (inTable) {
                    flushTable();
                }

                if (!line) {
                    flushList();
                    continue;
                }
                if (line.startsWith("### ")) {
                    flushList();
                    html += `<h3>${formatInline(line.slice(4))}</h3>`;
                } else if (line.startsWith("## ")) {
                    flushList();
                    html += `<h2>${formatInline(line.slice(3))}</h2>`;
                } else if (line.startsWith("# ")) {
                    flushList();
                    html += `<h2>${formatInline(line.slice(2))}</h2>`;
                } else if (/^[-*]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
                    if (!inList) { html += "<ul>"; inList = true; }
                    const itemText = line.replace(/^[-*]\s+|^\d+\.\s+/, "");
                    html += `<li>${formatInline(itemText)}</li>`;
                } else {
                    flushList();
                    html += `<p>${formatInline(line)}</p>`;
                }
            }
            flushTable();
            flushList();
            return html;
        }

        const rawBox = document.getElementById("raw-markdown");
        const targetBox = document.getElementById("rendered-report");
        if (rawBox && targetBox) {
            targetBox.innerHTML = renderMarkdownDashboard(rawBox.value);
        }

        function switchView(mode, btn) {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const rep = document.getElementById("rendered-report");
            const ch = document.getElementById("chart-section");
            if (mode === "all") {
                if (rep) rep.classList.remove("hidden");
                if (ch) ch.classList.remove("hidden");
            } else if (mode === "report") {
                if (rep) rep.classList.remove("hidden");
                if (ch) ch.classList.add("hidden");
            } else if (mode === "chart") {
                if (rep) rep.classList.add("hidden");
                if (ch) ch.classList.remove("hidden");
            }
        }

        function copyReport() {
            if (!rawBox) return;
            navigator.clipboard.writeText(rawBox.value).then(() => {
                const btn = document.getElementById("copy-btn");
                btn.textContent = "Copied!";
                setTimeout(() => { btn.textContent = "Copy Report"; }, 2000);
            });
        }

        function downloadReport() {
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

