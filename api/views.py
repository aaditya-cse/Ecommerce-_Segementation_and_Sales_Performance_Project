"""HTML templates stored as Python constants for reliable Vercel serverless bundling."""

STUDIO_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgentOps BI Studio | Autonomous Multi-Agent CSV Analyst</title>
    <style>
        :root {
            --bg: #060b16;
            --card: #0f172a;
            --border: #263348;
            --accent: #38bdf8;
            --text: #f8fafc;
            --muted: #94a3b8;
        }
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: radial-gradient(circle at 85% 10%, #0f2d4a 0%, var(--bg) 52%); color: var(--text); margin: 0; padding: 0; line-height: 1.65; min-height: 100vh; }
        .skip-link { position: absolute; left: -999px; background: var(--accent); color: #0f172a; padding: 8px 12px; font-weight: 700; }
        .skip-link:focus { left: 16px; top: 16px; z-index: 100; }

        .navbar { display: flex; justify-content: space-between; align-items: center; max-width: 1120px; margin: 0 auto; padding: 18px 24px; border-bottom: 1px solid rgba(51,65,85,0.55); }
        .brand { font-weight: 800; font-size: 1.18rem; color: #f8fafc; display: flex; align-items: center; gap: 10px; }
        .brand-dot { width: 10px; height: 10px; background: #10b981; border-radius: 50%; box-shadow: 0 0 12px #10b981; }
        .nav-pills { display: flex; gap: 10px; flex-wrap: wrap; }
        .pill { background: rgba(30,41,59,0.75); border: 1px solid var(--border); color: #cbd5e1; padding: 4px 12px; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }

        .container { max-width: 1060px; margin: 26px auto; padding: 0 20px 52px; }
        .hero { text-align: center; padding: 18px 12px 26px; }
        .hero h1 { font-size: 2.4rem; margin: 0 0 12px; background: linear-gradient(90deg, #38bdf8, #818cf8, #34d399); -webkit-background-clip: text; -webkit-text-fill-color: transparent; line-height: 1.2; }
        .hero p { color: #cbd5e1; max-width: 720px; margin: 0 auto 24px; font-size: 1.04rem; }

        .pipeline-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; margin-bottom: 26px; }
        .agent-card { background: rgba(15,23,42,0.85); border: 1px solid var(--border); border-radius: 14px; padding: 16px 18px; text-align: left; }
        .agent-step { color: var(--accent); font-size: 0.76rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }
        .agent-title { font-weight: 700; font-size: 1.02rem; margin: 4px 0; color: #f1f5f9; }
        .agent-desc { font-size: 0.85rem; color: var(--muted); margin: 0; }

        .card { background: var(--card); padding: 28px; border-radius: 16px; border: 1px solid var(--border); box-shadow: 0 20px 45px rgba(0,0,0,0.48); }
        h2 { color: #f1f5f9; font-size: 1.35rem; margin-top: 0; }
        label { display: block; margin: 16px 0 6px; font-weight: 600; color: #f1f5f9; }
        select, input[type="file"], textarea { width: 100%; padding: 12px 14px; border-radius: 10px; border: 1px solid #334155; background: #060b16; color: var(--text); font-size: 1rem; }
        select:focus, input[type="file"]:focus, textarea:focus, button:focus { outline: 3px solid var(--accent); outline-offset: 2px; }
        .hint { font-size: 0.85rem; color: var(--muted); margin-top: 5px; }

        .chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 10px; }
        .chip-btn { background: #1e293b; color: #7dd3fc; border: 1px solid #334155; padding: 7px 14px; border-radius: 999px; font-size: 0.84rem; cursor: pointer; transition: 0.15s; }
        .chip-btn:hover { border-color: var(--accent); background: #0f172a; transform: translateY(-1px); }

        .btn-launch { margin-top: 22px; width: 100%; background: linear-gradient(90deg, #0284c7, #2563eb); color: #ffffff; border: none; padding: 15px 28px; border-radius: 10px; font-size: 1.08rem; font-weight: 700; cursor: pointer; box-shadow: 0 8px 22px rgba(2,132,199,0.38); transition: 0.2s; }
        .btn-launch:hover { filter: brightness(1.1); transform: translateY(-1px); }

        .loader-overlay { display: none; position: fixed; inset: 0; background: rgba(6, 11, 22, 0.95); z-index: 999; flex-direction: column; justify-content: center; align-items: center; padding: 24px; text-align: center; }
        .loader-overlay.active { display: flex; }
        .spinner { width: 54px; height: 54px; border: 4px solid #1e293b; border-top-color: #38bdf8; border-radius: 50%; animation: spin 0.9s linear infinite; margin-bottom: 20px; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .step-list { list-style: none; padding: 0; margin: 16px 0 0; text-align: left; max-width: 430px; width: 100%; }
        .step-list li { padding: 10px 14px; margin-bottom: 8px; border-radius: 8px; background: #0f172a; border: 1px solid #334155; color: #94a3b8; font-size: 0.92rem; }
        .step-list li.active-step { border-color: #38bdf8; color: #f8fafc; font-weight: 600; }
    </style>
</head>
<body>
    <a href="#main-content" class="skip-link">Skip to main content</a>

    <nav class="navbar" aria-label="Primary Navigation">
        <div class="brand"><span class="brand-dot"></span> AgentOps BI Studio</div>
        <div class="nav-pills">
            <span class="pill">LangGraph 3-Agent</span>
            <span class="pill">AST Security Sandbox</span>
            <span class="pill">WCAG Accessible</span>
        </div>
    </nav>

    <main id="main-content" class="container" role="main">
        <header class="hero" role="banner">
            <h1>Autonomous Multi-Agent CSV Analyst</h1>
            <p>Upload any raw operational CSV or choose a benchmark dataset. Three autonomous agents clean anomalies, verify computations in an AST sandbox, and launch a dedicated Executive Dashboard.</p>

            <div class="pipeline-grid" aria-label="Multi-Agent Architecture Overview">
                <div class="agent-card">
                    <div class="agent-step">Agent 01 &bull; Profiler</div>
                    <div class="agent-title">Schema &amp; Anomaly Inspector</div>
                    <p class="agent-desc">Profiles column types, duplicate rows, missing values, and distribution skew automatically.</p>
                </div>
                <div class="agent-card">
                    <div class="agent-step">Agent 02 &bull; AST Sandbox</div>
                    <div class="agent-title">Self-Healing Pandas Cleaner</div>
                    <p class="agent-desc">Runs AST-verified Pandas code, exports a downloadable clean CSV, and plots charts.</p>
                </div>
                <div class="agent-card">
                    <div class="agent-step">Agent 03 &bull; Strategist</div>
                    <div class="agent-title">Executive BI Synthesizer</div>
                    <p class="agent-desc">Converts verified outputs into structured KPI cards, tables, and strategic actions.</p>
                </div>
            </div>
        </header>

        <section class="card" aria-labelledby="form-heading">
            <h2 id="form-heading">Configure Dataset &amp; Launch Dashboard</h2>
            <form id="analysis-form" action="/analyze" method="POST" enctype="multipart/form-data">
                <label for="sample-csv">1. Choose Built-in Sample Dataset:</label>
                <select id="sample-csv" name="sample_csv">
                    <option value="data/raw/ecommerce_sales_data.csv">E-Commerce Sales &amp; RFM Segmentation (371 rows)</option>
                    <option value="data/raw/edtech_student_enrollments.csv">EdTech Student Enrollments (184 rows)</option>
                    <option value="data/raw/food_delivery_operations.csv">Food Delivery Operations (250 rows)</option>
                </select>

                <label for="uploaded-csv">OR Upload Custom CSV File (Max 5 MB):</label>
                <input id="uploaded-csv" type="file" name="uploaded_csv" accept=".csv" aria-describedby="csv-hint">
                <p id="csv-hint" class="hint">Only valid .csv files up to 5 MB are accepted. Cleaned output will be ready for download on the dashboard.</p>

                <label for="user-goal">2. Ask Any Business or Data Analysis Question (Press Enter to Run):</label>
                <div class="chip-row" aria-label="Sample Analysis Prompts">
                    <button type="button" class="chip-btn" onclick="setGoal('Clean duplicates, missing values, and inconsistent text casing; calculate core KPIs and Net Revenue by primary category; and plot a summary bar chart.')">Executive KPIs &amp; Revenue Chart</button>
                    <button type="button" class="chip-btn" onclick="setGoal('Audit data quality anomalies, clean outliers and nulls, compare performance across regions/cities, and visualize regional distribution.')">Data Quality &amp; Regional Audit</button>
                    <button type="button" class="chip-btn" onclick="setGoal('Clean the dataset, analyze customer ratings, discounts, and cancellation/return rates, and plot key operational drivers.')">Ratings &amp; Operations Deep-Dive</button>
                </div>
                <textarea id="user-goal" name="user_goal" rows="3" required placeholder="e.g., Clean duplicates and nulls, calculate net revenue by category, and plot a chart.">Clean duplicates and missing values, summarize top KPIs, and plot the primary revenue driver.</textarea>

                <button type="submit" class="btn-launch">Launch Executive Dashboard &rarr;</button>
            </form>
        </section>
    </main>

    <div id="loader" class="loader-overlay" role="status" aria-live="polite">
        <div class="spinner"></div>
        <h2 style="margin:0; color:#38bdf8;">Orchestrating 3-Agent Pipeline...</h2>
        <p style="color:#94a3b8; margin:6px 0 0;">Preparing your dedicated interactive Executive Dashboard &bull; <strong id="elapsed-sec" style="color:#38bdf8;">0s</strong></p>
        <ul class="step-list">
            <li id="st-1" class="active-step">1. Schema Profiler: Scanning rows, nulls &amp; duplicates...</li>
            <li id="st-2">2. AST Sandbox Analyst: Cleaning data &amp; generating chart...</li>
            <li id="st-3">3. Executive Strategist: Building KPI cards &amp; report...</li>
        </ul>
        <button type="button" onclick="window.stop(); document.getElementById('loader').classList.remove('active');" style="margin-top:18px; background:transparent; border:1px solid #475569; color:#94a3b8; padding:7px 16px; border-radius:8px; cursor:pointer; font-size:0.85rem;">Cancel Request</button>
    </div>

    <script>
        function setGoal(text) {
            const box = document.getElementById("user-goal");
            if (box) box.value = text;
        }
        document.getElementById("user-goal").addEventListener("keydown", function(e) {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                document.getElementById("analysis-form").requestSubmit();
            }
        });
        document.getElementById("analysis-form").addEventListener("submit", function () {
            document.getElementById("loader").classList.add("active");
            let sec = 0;
            setInterval(() => {
                sec++;
                const el = document.getElementById("elapsed-sec");
                if (el) el.textContent = sec + "s";
            }, 1000);
            setTimeout(() => {
                document.getElementById("st-1").classList.remove("active-step");
                document.getElementById("st-2").classList.add("active-step");
            }, 1200);
            setTimeout(() => {
                document.getElementById("st-2").classList.remove("active-step");
                document.getElementById("st-3").classList.add("active-step");
            }, 2600);
        });
    </script>
</body>
</html>
"""

DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Executive Intelligence Dashboard | AgentOps BI</title>
    <style>
        :root {
            --bg: #060b16;
            --card: #0f172a;
            --card-alt: #1e293b;
            --border: #263348;
            --accent: #38bdf8;
            --accent-btn: #0284c7;
            --green-btn: #059669;
            --text: #f8fafc;
            --muted: #94a3b8;
        }
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: radial-gradient(circle at top left, #0c223a 0%, var(--bg) 45%); color: var(--text); margin: 0; padding: 0; line-height: 1.65; }
        .skip-link { position: absolute; left: -999px; background: var(--accent); color: #0f172a; padding: 8px 12px; font-weight: 700; }
        .skip-link:focus { left: 16px; top: 16px; z-index: 100; }

        .topbar { position: sticky; top: 0; z-index: 50; background: rgba(15, 23, 42, 0.94); backdrop-filter: blur(10px); border-bottom: 1px solid var(--border); padding: 14px 24px; }
        .topbar-inner { max-width: 1160px; margin: 0 auto; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; }
        .back-btn { background: #1e293b; color: #38bdf8; border: 1px solid #38bdf8; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 0.9rem; display: inline-flex; align-items: center; gap: 6px; transition: 0.15s; }
        .back-btn:hover { background: #0284c7; color: #ffffff; }
        .dash-title { font-weight: 800; font-size: 1.12rem; color: #f8fafc; letter-spacing: 0.01em; }

        .container { max-width: 1160px; margin: 24px auto; padding: 0 20px 54px; }

        .context-banner { background: linear-gradient(135deg, #0f172a 0%, #17253b 100%); border: 1px solid var(--border); border-left: 4px solid var(--accent); border-radius: 14px; padding: 18px 22px; margin-bottom: 20px; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 14px; }
        .pipeline-status { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
        .status-step { background: rgba(6, 78, 59, 0.55); color: #6ee7b7; border: 1px solid #10b981; padding: 4px 11px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; }

        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; margin-bottom: 22px; }
        .kpi-card { background: linear-gradient(180deg, #111c33 0%, #0f172a 100%); border: 1px solid var(--border); border-top: 3px solid var(--accent); border-radius: 12px; padding: 16px 18px; box-shadow: 0 8px 20px rgba(0,0,0,0.3); }
        .kpi-label { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); font-weight: 700; }
        .kpi-val { font-size: 1.45rem; font-weight: 800; color: #f8fafc; margin-top: 4px; }

        .card { background: var(--card); padding: 26px; border-radius: 16px; border: 1px solid var(--border); box-shadow: 0 14px 34px rgba(0,0,0,0.42); }
        .error { color: #fecaca; font-weight: 600; background: #7f1d1d; padding: 16px; border-radius: 10px; border: 1px solid #f87171; }

        .toolbar { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; padding-bottom: 16px; border-bottom: 1px solid var(--border); margin-bottom: 22px; }
        .tab-group, .action-group { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
        .tab-btn, .action-btn { background: var(--card-alt); color: #e2e8f0; border: 1px solid var(--border); padding: 9px 15px; border-radius: 8px; font-size: 0.9rem; font-weight: 600; cursor: pointer; text-decoration: none; transition: 0.15s; }
        .tab-btn.active { background: var(--accent-btn); color: #ffffff; border-color: var(--accent); }
        .action-btn:hover, .tab-btn:hover { border-color: var(--accent); color: #ffffff; }
        .download-csv-btn { background: var(--green-btn); color: #ffffff; border: 1px solid #34d399; padding: 9px 16px; border-radius: 8px; font-size: 0.9rem; font-weight: 700; text-decoration: none; display: inline-block; }
        .download-csv-btn:hover { background: #047857; }
        a:focus, button:focus, input:focus { outline: 3px solid var(--accent); outline-offset: 2px; }

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

        .search-input { padding: 8px 12px; border-radius: 8px; border: 1px solid #334155; background: #060b16; color: #f8fafc; font-size: 0.9rem; width: 240px; }
        .chart-box { background: #060b16; padding: 20px; border-radius: 12px; border: 1px solid var(--border); margin-top: 24px; text-align: center; }
        .chart-box img { max-width: 100%; max-height: 390px; object-fit: contain; background: #ffffff; padding: 8px; border-radius: 8px; }

        .trace-drawer-bar { margin-top: 26px; padding: 16px 20px; background: #0b1324; border: 1px dashed #334155; border-radius: 12px; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; }
        .trace-box { background: #060b16; padding: 20px; border-radius: 12px; border: 1px solid var(--border); margin-top: 14px; }
        pre.code-block { background: #020617; color: #cbd5e1; padding: 14px; border-radius: 8px; overflow-x: auto; font-size: 0.87rem; border: 1px solid #1e293b; }
        .hidden { display: none; }
        @media print { .topbar, .toolbar, .trace-drawer-bar, .search-input { display: none !important; } body { background: #ffffff; color: #000000; } }
    </style>
</head>
<body>
    <a href="#main-content" class="skip-link">Skip to main content</a>

    <header class="topbar" role="banner">
        <div class="topbar-inner">
            <a href="/" class="back-btn">&larr; Run New Analysis</a>
            <div class="dash-title">Executive Business Intelligence Dashboard</div>
            <div class="action-group">
                {% if cleaned_csv_b64 %}
                <a class="download-csv-btn" href="data:text/csv;base64,{{ cleaned_csv_b64 }}" download="cleaned_dataset.csv">Download Cleaned CSV</a>
                {% endif %}
                {% if report_raw %}
                <button type="button" class="action-btn" id="copy-btn" onclick="copyReport()">Copy Report</button>
                <button type="button" class="action-btn" onclick="downloadReport()">Export .MD</button>
                <button type="button" class="action-btn" onclick="window.print()">Print / PDF</button>
                {% endif %}
            </div>
        </div>
    </header>

    <main id="main-content" class="container" role="main" aria-live="polite">
        <section class="context-banner" aria-label="Analysis Summary Context">
            <div>
                <div style="font-size:0.8rem; color:#94a3b8; font-weight:700; text-transform:uppercase;">Dataset: {{ dataset_label }} {% if cleaned_shape %}({{ cleaned_shape }}){% endif %}</div>
                <div style="font-size:1.05rem; font-weight:700; color:#f8fafc; margin-top:3px;">Goal: {{ goal }}</div>
            </div>
            <div class="pipeline-status" aria-label="Agent Execution Status">
                <span class="status-step">01 Profiler &#10003;</span>
                <span class="status-step">02 AST Sandbox &#10003; ({{ retry_count }} try)</span>
                <span class="status-step">03 Strategist &#10003;</span>
            </div>
        </section>

        {% if kpi_cards %}
        <section class="kpi-grid" aria-label="Key Performance Metrics">
            {% for kpi in kpi_cards %}
            <div class="kpi-card">
                <div class="kpi-label">{{ kpi.label }}</div>
                <div class="kpi-val">{{ kpi.value }}</div>
            </div>
            {% endfor %}
        </section>
        {% endif %}

        {% if error %}
        <section class="card" role="alert">
            <h2 style="margin-top:0; color:#f87171;">Analysis Could Not Complete</h2>
            <p class="error">{{ error }}</p>
            <p style="margin-top:16px;"><a href="/" class="back-btn">&larr; Return to Dataset Configuration</a></p>
        </section>
        {% endif %}

        {% if report_html %}
        <section class="card" aria-labelledby="report-heading">
            <div class="toolbar">
                <div class="tab-group" role="tablist" aria-label="Dashboard View Switcher">
                    <button type="button" class="tab-btn active" id="tab-all" onclick="switchView('all', this)">Executive Overview</button>
                    <button type="button" class="tab-btn" id="tab-report" onclick="switchView('report', this)">KPI Report &amp; Tables</button>
                    {% if cleaned_preview_html %}
                    <button type="button" class="tab-btn" id="tab-data" onclick="switchView('data', this)">Cleaned Dataset</button>
                    {% endif %}
                    {% if charts_b64 %}
                    <button type="button" class="tab-btn" id="tab-chart" onclick="switchView('chart', this)">Visual Chart</button>
                    {% endif %}
                    <div style="margin-top:22px; padding:14px 18px; background:#0b1324; border-left:4px solid #38bdf8; border-radius:8px; font-size:0.88rem; color:#cbd5e1;">
                <strong style="color:#38bdf8;">Methodology &amp; Responsible AI Guardrails:</strong>
                All metrics and charts are computed deterministically by AST-sandboxed Python code (zero LLM number hallucination). Correlation and outlier flags highlight statistical associations for review and do not imply causation. Uploaded CSVs are processed ephemerally in memory/temp storage and purged immediately after execution.
            </div>
            {% if generated_code %}
                    <button type="button" class="tab-btn" id="tab-trace" onclick="switchView('trace', this)">AST Code &amp; Audit</button>
                    {% endif %}
                </div>
            </div>

            <h1 id="report-heading" style="position:absolute;left:-9999px;">Executive Analysis Report</h1>
            <textarea id="raw-markdown" class="hidden" aria-hidden="true">{{ report_raw }}</textarea>

            <div id="report-section" class="report-body">
                {{ report_html | safe }}
            </div>

            {% if cleaned_preview_html %}
            <div id="data-section" style="margin-top: 28px;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                    <h3 style="color:#34d399; margin:0;">Cleaned Dataset Preview (Top 15 Rows)</h3>
                    <input type="text" id="table-search" class="search-input" placeholder="Filter preview rows..." aria-label="Filter cleaned dataset rows" onkeyup="filterCleanTable()">
                </div>
                <div class="table-wrap" id="clean-table-container">
                    {{ cleaned_preview_html | safe }}
                </div>
            </div>
            {% endif %}

            {% if charts_b64 %}
            <div id="chart-section" class="chart-box">
                <h3 style="margin-top:0; color:#38bdf8;">Generated Statistical Visualizations ({{ charts_b64|length }})</h3>
                <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:18px; margin-top:14px;">
                    {% for img_b64 in charts_b64 %}
                    <div style="background:#0b1324; border:1px solid #263348; border-radius:10px; padding:14px;">
                        <img src="data:image/png;base64,{{ img_b64 }}" alt="Chart {{ loop.index }} generated for: {{ goal }}">
                        <div style="margin-top:12px;">
                            <a class="download-csv-btn" href="data:image/png;base64,{{ img_b64 }}" download="analysis_chart_{{ loop.index }}.png">Download Chart {{ loop.index }} (PNG)</a>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}

            <div style="margin-top:22px; padding:14px 18px; background:#0b1324; border-left:4px solid #38bdf8; border-radius:8px; font-size:0.88rem; color:#cbd5e1;">
                <strong style="color:#38bdf8;">Methodology &amp; Responsible AI Guardrails:</strong>
                All metrics and charts are computed deterministically by AST-sandboxed Python code (zero LLM number hallucination). Correlation and outlier flags highlight statistical associations for review and do not imply causation. Uploaded CSVs are processed ephemerally in memory/temp storage and purged immediately after execution.
            </div>
            {% if generated_code %}
            <div id="trace-drawer-bar" class="trace-drawer-bar">
                <div>
                    <strong style="color:#e2e8f0;">Zero-Hallucination Audit &amp; AST Sandbox Verification</strong>
                    <div style="font-size:0.84rem; color:#94a3b8;">Click to inspect the exact Python code &amp; verified stdout metrics behind this report.</div>
                </div>
                <button type="button" class="action-btn" id="toggle-trace-btn" onclick="toggleTraceDrawer()">Show AST-Verified Code &amp; Trace &#9662;</button>
            </div>

            <div id="trace-section" class="trace-box hidden">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:10px;">
                    <h3 style="margin:0; color:#38bdf8;">AST-Verified Pandas Code (Attempts: {{ retry_count }})</h3>
                    <button type="button" class="action-btn" id="copy-code-btn" onclick="copyCode()">Copy Python Code</button>
                </div>
                <pre class="code-block" id="agent-code-block"><code>{{ generated_code }}</code></pre>
                {% if analysis_output %}
                <h4 style="color:#94a3b8; margin-bottom:6px;">Verified Stdout Output:</h4>
                <pre class="code-block"><code>{{ analysis_output }}</code></pre>
                {% endif %}
            </div>
            {% endif %}
        </section>
        {% endif %}

        {% if not report_html and not error %}
        <section class="card">
            <h2 style="margin-top:0; color:#38bdf8;">Verified Execution Output</h2>
            <pre class="code-block"><code>{{ analysis_output or "Analysis completed. Click Run New Analysis to test another query." }}</code></pre>
        </section>
        {% endif %}
    </main>

    <script>
        function switchView(mode, btn) {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const rep = document.getElementById("report-section");
            const dat = document.getElementById("data-section");
            const ch = document.getElementById("chart-section");
            const bar = document.getElementById("trace-drawer-bar");
            const tr = document.getElementById("trace-section");
            const show = (el, flag) => { if (el) el.classList.toggle("hidden", !flag); };

            if (mode === "all") {
                show(rep, true); show(dat, true); show(ch, true); show(bar, true); show(tr, false);
                const tBtn = document.getElementById("toggle-trace-btn");
                if (tBtn) tBtn.innerHTML = "Show AST-Verified Code &amp; Trace &#9662;";
            } else if (mode === "report") { show(rep, true); show(dat, false); show(ch, false); show(bar, false); show(tr, false); }
            else if (mode === "data") { show(rep, false); show(dat, true); show(ch, false); show(bar, false); show(tr, false); }
            else if (mode === "chart") { show(rep, false); show(dat, false); show(ch, true); show(bar, false); show(tr, false); }
            else if (mode === "trace") { show(rep, false); show(dat, false); show(ch, false); show(bar, false); show(tr, true); }
        }

        function toggleTraceDrawer() {
            const tr = document.getElementById("trace-section");
            const btn = document.getElementById("toggle-trace-btn");
            if (!tr || !btn) return;
            const isHidden = tr.classList.toggle("hidden");
            btn.innerHTML = isHidden ? "Show AST-Verified Code &amp; Trace &#9662;" : "Hide AST-Verified Code &amp; Trace &#9652;";
        }

        function filterCleanTable() {
            const q = document.getElementById("table-search").value.toLowerCase();
            const rows = document.querySelectorAll("#clean-table-container tbody tr");
            rows.forEach(r => {
                r.style.display = r.textContent.toLowerCase().includes(q) ? "" : "none";
            });
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

        function copyCode() {
            const codeEl = document.getElementById("agent-code-block");
            if (!codeEl) return;
            navigator.clipboard.writeText(codeEl.innerText).then(() => {
                const btn = document.getElementById("copy-code-btn");
                btn.textContent = "Code Copied!";
                setTimeout(() => { btn.textContent = "Copy Python Code"; }, 2000);
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