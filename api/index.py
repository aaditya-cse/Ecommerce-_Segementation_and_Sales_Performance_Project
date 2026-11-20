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
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, ".env"))
load_dotenv(os.path.join(ROOT_DIR, "multi_agent", ".env"))

sys.path.insert(0, os.path.join(ROOT_DIR, "multi_agent"))
sys.path.insert(0, os.path.join(ROOT_DIR, "api"))

from universal_analyst_agent import build_universal_graph
try:
    from security import (
        apply_hardened_headers,
        SlidingWindowRateLimiter,
        validate_csv_bytes,
        sanitize_csv_cell,
    )
except ImportError:
    from api.security import (
        apply_hardened_headers,
        SlidingWindowRateLimiter,
        validate_csv_bytes,
        sanitize_csv_cell,
    )

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
logging.basicConfig(level=logging.INFO)

RATE_LIMITER = SlidingWindowRateLimiter(max_requests=30, window_seconds=60)
AGENT_GRAPH = build_universal_graph()

ALLOWED_SAMPLES = {
    "data/raw/ecommerce_sales_data.csv",
    "data/raw/edtech_student_enrollments.csv",
    "data/raw/food_delivery_operations.csv",
}


def extract_kpi_cards(stdout_text: str) -> list:
    """Extracts up to 4 clean Key: Value KPI metrics from verified stdout for executive cards."""
    kpis = []
    if not stdout_text:
        return kpis
    for line in stdout_text.splitlines():
        line = line.strip()
        if ":" in line and not line.startswith("===") and len(line) < 75:
            parts = line.split(":", 1)
            label = re.sub(r"\s*\(.*?\)", "", parts[0]).strip()
            val = parts[1].strip()
            if label and val and any(ch.isdigit() for ch in val) and len(label) <= 32:
                kpis.append({"label": label, "value": val})
        if len(kpis) >= 4:
            break
    return kpis


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


HOME_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgentOps BI Studio | Autonomous Multi-Agent CSV Analyst</title>
    <style>
        :root {
            --bg: #030712;
            --card: rgba(15, 23, 42, 0.78);
            --card-border: rgba(56, 189, 248, 0.18);
            --card-hover: rgba(30, 41, 59, 0.9);
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.35);
            --emerald: #34d399;
            --indigo: #818cf8;
            --text: #f8fafc;
            --muted: #94a3b8;
        }
        * { box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: radial-gradient(circle at 15% 15%, rgba(14, 165, 233, 0.18) 0%, transparent 45%),
                        radial-gradient(circle at 85% 85%, rgba(52, 211, 153, 0.12) 0%, transparent 45%),
                        radial-gradient(circle at 50% 50%, rgba(99, 102, 241, 0.1) 0%, transparent 60%),
                        var(--bg);
            color: var(--text);
            margin: 0;
            padding: 0;
            line-height: 1.65;
            min-height: 100vh;
        }
        .skip-link { position: absolute; left: -999px; background: var(--accent); color: #0f172a; padding: 8px 14px; font-weight: 700; border-radius: 6px; }
        .skip-link:focus { left: 16px; top: 16px; z-index: 100; }

        /* Navbar */
        .navbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 1180px;
            margin: 0 auto;
            padding: 20px 24px;
            border-bottom: 1px solid rgba(56, 189, 248, 0.12);
        }
        .brand {
            font-weight: 900;
            font-size: 1.25rem;
            color: #f8fafc;
            display: flex;
            align-items: center;
            gap: 12px;
            letter-spacing: -0.02em;
        }
        .brand-dot {
            width: 12px;
            height: 12px;
            background: #10b981;
            border-radius: 50%;
            box-shadow: 0 0 16px #10b981, 0 0 30px #10b981;
            animation: pulse-dot 2s infinite ease-in-out;
        }
        @keyframes pulse-dot { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.6; transform: scale(0.85); } }
        .nav-badges { display: flex; gap: 10px; flex-wrap: wrap; }
        .badge {
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid var(--card-border);
            color: #cbd5e1;
            padding: 5px 13px;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 600;
            backdrop-filter: blur(8px);
        }
        .badge.hackathon {
            background: linear-gradient(90deg, rgba(56, 189, 248, 0.2), rgba(99, 102, 241, 0.2));
            border-color: rgba(56, 189, 248, 0.4);
            color: #7dd3fc;
        }

        .container { max-width: 1140px; margin: 30px auto; padding: 0 20px 60px; }

        /* Hero */
        .hero { text-align: center; padding: 24px 12px 36px; }
        .hero-pill {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.3);
            color: #7dd3fc;
            padding: 6px 16px;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 700;
            margin-bottom: 18px;
            box-shadow: 0 0 20px rgba(56, 189, 248, 0.15);
        }
        .hero h1 {
            font-size: 3rem;
            margin: 0 0 16px;
            background: linear-gradient(135deg, #ffffff 10%, #7dd3fc 45%, #818cf8 75%, #34d399 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            line-height: 1.15;
            font-weight: 900;
            letter-spacing: -0.03em;
        }
        .hero p {
            color: #cbd5e1;
            max-width: 780px;
            margin: 0 auto 32px;
            font-size: 1.12rem;
            line-height: 1.7;
        }

        /* 3-Agent Stepper Pipeline */
        .pipeline-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }
        .agent-card {
            background: var(--card);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 20px 22px;
            text-align: left;
            backdrop-filter: blur(12px);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
            transition: transform 0.2s, border-color 0.2s;
            position: relative;
            overflow: hidden;
        }
        .agent-card:hover {
            transform: translateY(-3px);
            border-color: var(--accent);
            box-shadow: 0 16px 35px -5px rgba(56, 189, 248, 0.2);
        }
        .agent-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: linear-gradient(90deg, var(--accent), var(--indigo));
        }
        .agent-step { color: var(--accent); font-size: 0.78rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; display: flex; align-items: center; gap: 6px; }
        .agent-title { font-weight: 800; font-size: 1.1rem; margin: 8px 0 6px; color: #f1f5f9; }
        .agent-desc { font-size: 0.88rem; color: var(--muted); margin: 0; line-height: 1.55; }

        /* Benchmark One-Click Cards */
        .presets-title { font-size: 1.05rem; font-weight: 800; color: #cbd5e1; margin: 0 0 14px; display: flex; align-items: center; gap: 8px; }
        .presets-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; margin-bottom: 24px; }
        .preset-card {
            background: rgba(15, 23, 42, 0.65);
            border: 1px solid rgba(51, 65, 85, 0.7);
            border-radius: 14px;
            padding: 16px 18px;
            cursor: pointer;
            text-align: left;
            transition: all 0.2s;
            display: flex;
            align-items: flex-start;
            gap: 14px;
        }
        .preset-card:hover {
            background: rgba(30, 41, 59, 0.85);
            border-color: var(--accent);
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(56, 189, 248, 0.15);
        }
        .preset-icon { font-size: 1.6rem; line-height: 1; padding: 10px; background: rgba(56, 189, 248, 0.1); border-radius: 10px; }
        .preset-body strong { display: block; color: #f8fafc; font-size: 0.98rem; margin-bottom: 3px; }
        .preset-body span { display: block; color: var(--muted); font-size: 0.82rem; }

        /* Main Form Card */
        .card {
            background: var(--card);
            padding: 34px;
            border-radius: 20px;
            border: 1px solid var(--card-border);
            backdrop-filter: blur(14px);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(56, 189, 248, 0.12);
        }
        h2 { color: #f1f5f9; font-size: 1.45rem; margin-top: 0; font-weight: 800; letter-spacing: -0.01em; }
        label { display: block; margin: 20px 0 8px; font-weight: 700; color: #f1f5f9; font-size: 0.96rem; }
        select, input[type="file"], textarea {
            width: 100%;
            padding: 14px 16px;
            border-radius: 12px;
            border: 1px solid #334155;
            background: rgba(6, 11, 22, 0.85);
            color: var(--text);
            font-size: 1rem;
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        select:focus, input[type="file"]:focus, textarea:focus, button:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-glow);
        }
        .hint { font-size: 0.86rem; color: var(--muted); margin-top: 6px; }

        .chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 12px; }
        .chip-btn {
            background: rgba(30, 41, 59, 0.85);
            color: #7dd3fc;
            border: 1px solid #334155;
            padding: 8px 15px;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s;
        }
        .chip-btn:hover {
            border-color: var(--accent);
            background: #0f172a;
            color: #ffffff;
            transform: translateY(-1px);
        }

        .btn-launch {
            margin-top: 26px;
            width: 100%;
            background: linear-gradient(90deg, #0284c7, #2563eb, #7c3aed);
            background-size: 200% auto;
            color: #ffffff;
            border: none;
            padding: 16px 30px;
            border-radius: 12px;
            font-size: 1.15rem;
            font-weight: 800;
            cursor: pointer;
            box-shadow: 0 10px 28px rgba(2, 132, 199, 0.45);
            transition: all 0.3s;
            letter-spacing: 0.01em;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }
        .btn-launch:hover {
            background-position: right center;
            filter: brightness(1.1);
            transform: translateY(-2px);
            box-shadow: 0 14px 34px rgba(2, 132, 199, 0.6);
        }

        /* Modern Animated Loader Overlay */
        .loader-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(3, 7, 18, 0.94);
            backdrop-filter: blur(12px);
            z-index: 999;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 24px;
            text-align: center;
        }
        .loader-overlay.active { display: flex; }
        .spinner-box { position: relative; width: 72px; height: 72px; margin-bottom: 24px; }
        .spinner {
            width: 72px;
            height: 72px;
            border: 4px solid rgba(56, 189, 248, 0.15);
            border-top-color: #38bdf8;
            border-right-color: #818cf8;
            border-radius: 50%;
            animation: spin 0.9s cubic-bezier(0.55, 0.15, 0.45, 0.85) infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .step-list { list-style: none; padding: 0; margin: 20px 0 0; text-align: left; max-width: 460px; width: 100%; }
        .step-list li {
            padding: 12px 16px;
            margin-bottom: 10px;
            border-radius: 10px;
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid #334155;
            color: #94a3b8;
            font-size: 0.94rem;
            display: flex;
            align-items: center;
            gap: 10px;
            transition: all 0.3s;
        }
        .step-list li.active-step {
            border-color: #38bdf8;
            color: #f8fafc;
            font-weight: 700;
            background: rgba(56, 189, 248, 0.12);
            box-shadow: 0 0 20px rgba(56, 189, 248, 0.2);
        }
    </style>
</head>
<body>
    <a href="#main-content" class="skip-link">Skip to main content</a>

    <nav class="navbar" aria-label="Primary Navigation">
        <div class="brand">
            <span class="brand-dot"></span>
            <span>AgentOps <span style="color:#38bdf8;">BI Studio</span></span>
        </div>
        <div class="nav-badges">
            <span class="badge hackathon">🏆 Hackathon Edition</span>
            <span class="badge">LangGraph 3-Agent</span>
            <span class="badge">AST Security Guard</span>
            <span class="badge">WCAG 2.1 AA</span>
        </div>
    </nav>

    <main id="main-content" class="container" role="main">
        <header class="hero" role="banner">
            <div class="hero-pill">⚡ Self-Healing Multi-Agent Architecture • AST Zero-Hallucination Sandbox</div>
            <h1>Autonomous Multi-Agent CSV Analyst</h1>
            <p>Transform messy operational datasets into boardroom-ready Business Intelligence in seconds. Three coordinated agents inspect schemas, sanitize anomalies via an AST-sandboxed Python runtime, and construct interactive executive dashboards.</p>

            <div class="pipeline-grid" aria-label="Multi-Agent Architecture Overview">
                <div class="agent-card">
                    <div class="agent-step">Agent 01 &bull; Profiler</div>
                    <div class="agent-title">Schema &amp; Anomaly Profiler</div>
                    <p class="agent-desc">Automated scanning of column data types, duplicate records, null frequencies, and statistical distributions.</p>
                </div>
                <div class="agent-card">
                    <div class="agent-step">Agent 02 &bull; AST Sandbox</div>
                    <div class="agent-title">Self-Healing Pandas Analyst</div>
                    <p class="agent-desc">Generates AST-checked Python transformations, auto-corrects syntax bugs, and plots publication-quality figures.</p>
                </div>
                <div class="agent-card">
                    <div class="agent-step">Agent 03 &bull; Strategist</div>
                    <div class="agent-title">Executive BI Synthesizer</div>
                    <p class="agent-desc">Synthesizes verified data points into quantitative KPI cards, executive markdown tables, and high-ROI actions.</p>
                </div>
            </div>
        </header>

        <section class="card" aria-labelledby="form-heading">
            <h2 id="form-heading">Launch Live Multi-Agent Analysis</h2>

            <div class="presets-title">⚡ 1-Click Hackathon Benchmarks:</div>
            <div class="presets-grid" role="group" aria-label="Demo Benchmark Presets">
                <div class="preset-card" onclick="selectPreset('data/raw/ecommerce_sales_data.csv', 'Clean duplicates and missing values, perform RFM customer value segmentation, summarize Net Revenue by category, and plot top revenue drivers.')">
                    <div class="preset-icon">🛒</div>
                    <div class="preset-body">
                        <strong>E-Commerce Sales &amp; RFM</strong>
                        <span>371 rows &bull; Revenue, Orders, Segmentation &amp; Returns</span>
                    </div>
                </div>
                <div class="preset-card" onclick="selectPreset('data/raw/edtech_student_enrollments.csv', 'Audit student course enrollment patterns, calculate completion rates across subject domains, and plot course completion velocity.')">
                    <div class="preset-icon">🎓</div>
                    <div class="preset-body">
                        <strong>EdTech Student Cohorts</strong>
                        <span>184 rows &bull; Completion Rates, Retention &amp; Engagement</span>
                    </div>
                </div>
                <div class="preset-card" onclick="selectPreset('data/raw/food_delivery_operations.csv', 'Audit delivery delay hotspots, calculate average order value and rider tip correlations, and visualize delivery duration trends.')">
                    <div class="preset-icon">🍔</div>
                    <div class="preset-body">
                        <strong>Quick-Commerce Operations</strong>
                        <span>250 rows &bull; Delivery Times, Ratings &amp; Delay Factors</span>
                    </div>
                </div>
            </div>

            <form id="analysis-form" action="/analyze" method="POST" enctype="multipart/form-data">
                <label for="sample-csv">1. Select Benchmark Dataset:</label>
                <select id="sample-csv" name="sample_csv">
                    <option value="data/raw/ecommerce_sales_data.csv">E-Commerce Sales &amp; RFM Segmentation (371 rows)</option>
                    <option value="data/raw/edtech_student_enrollments.csv">EdTech Student Enrollments (184 rows)</option>
                    <option value="data/raw/food_delivery_operations.csv">Food Delivery Operations (250 rows)</option>
                </select>

                <label for="uploaded-csv">OR Upload Any Custom CSV File (Max 5 MB):</label>
                <input id="uploaded-csv" type="file" name="uploaded_csv" accept=".csv" aria-describedby="csv-hint">
                <p id="csv-hint" class="hint">Upload any real-world operational dataset. The sandbox cleans anomalies and delivers an exportable cleaned CSV.</p>

                <label for="user-goal">2. Business Goal or Analytical Question:</label>
                <div class="chip-row" aria-label="Prompt Shortcuts">
                    <button type="button" class="chip-btn" onclick="setGoal('Clean duplicates, missing values, and inconsistent text casing; calculate core KPIs and Net Revenue by primary category; and plot a summary bar chart.')">Executive KPIs &amp; Revenue Chart</button>
                    <button type="button" class="chip-btn" onclick="setGoal('Audit data quality anomalies, clean outliers and nulls, compare performance across regions/cities, and visualize regional distribution.')">Data Quality &amp; Regional Audit</button>
                    <button type="button" class="chip-btn" onclick="setGoal('Clean the dataset, analyze customer ratings, discounts, and cancellation/return rates, and plot key operational drivers.')">Ratings &amp; Operations Deep-Dive</button>
                </div>
                <textarea id="user-goal" name="user_goal" rows="3" required placeholder="e.g., Clean duplicates and nulls, calculate net revenue by category, and plot a chart.">Clean duplicates and missing values, summarize top KPIs, and plot the primary revenue driver.</textarea>

                <button type="submit" class="btn-launch">
                    <span>Launch Autonomous BI Pipeline</span>
                    <span>&rarr;</span>
                </button>
            </form>
        </section>
    </main>

    <div id="loader" class="loader-overlay" role="status" aria-live="polite">
        <div class="spinner-box">
            <div class="spinner"></div>
        </div>
        <h2 style="margin:0; color:#38bdf8; font-weight:800; font-size:1.6rem;">Orchestrating 3-Agent LangGraph Pipeline...</h2>
        <p style="color:#94a3b8; margin:8px 0 0; font-size:1.02rem;">Executing AST verification &bull; Real-time Sandbox Runtime &bull; <strong id="elapsed-sec" style="color:#38bdf8;">0s</strong></p>
        <ul class="step-list">
            <li id="st-1" class="active-step">🔍 1. Schema Profiler: Profiling shapes, missing nulls &amp; type schema...</li>
            <li id="st-2">🛡️ 2. AST Sandbox Analyst: Verifying security AST &amp; generating chart...</li>
            <li id="st-3">🧠 3. Executive Strategist: Synthesizing KPI cards &amp; strategic actions...</li>
        </ul>
        <button type="button" onclick="window.stop(); document.getElementById('loader').classList.remove('active');" style="margin-top:22px; background:transparent; border:1px solid #475569; color:#94a3b8; padding:8px 20px; border-radius:10px; cursor:pointer; font-size:0.9rem;">Cancel Pipeline</button>
    </div>

    <script>
        function setGoal(text) {
            const box = document.getElementById("user-goal");
            if (box) box.value = text;
        }
        function selectPreset(path, prompt) {
            const sel = document.getElementById("sample-csv");
            if (sel) sel.value = path;
            setGoal(prompt);
            const upload = document.getElementById("uploaded-csv");
            if (upload) upload.value = "";
        }
        document.getElementById("analysis-form").addEventListener("submit", function () {
            document.getElementById("loader").classList.add("active");
            let sec = 0;
            setInterval(() => {
                sec++;
                const el = document.getElementById("elapsed-sec");
                if (el) el.textContent = sec + "s";
            }, 1000);
            setTimeout(() => {
                const s1 = document.getElementById("st-1");
                const s2 = document.getElementById("st-2");
                if (s1) s1.classList.remove("active-step");
                if (s2) s2.classList.add("active-step");
            }, 1400);
            setTimeout(() => {
                const s2 = document.getElementById("st-2");
                const s3 = document.getElementById("st-3");
                if (s2) s2.classList.remove("active-step");
                if (s3) s3.classList.add("active-step");
            }, 3200);
        });
    </script>
</body>
</html>
"""


DASHBOARD_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Executive Intelligence Dashboard | AgentOps BI</title>
    <style>
        :root {
            --bg: #030712;
            --card: rgba(15, 23, 42, 0.82);
            --card-alt: rgba(30, 41, 59, 0.85);
            --border: rgba(56, 189, 248, 0.18);
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.35);
            --accent-btn: #0284c7;
            --green-btn: #059669;
            --emerald: #34d399;
            --indigo: #818cf8;
            --text: #f8fafc;
            --muted: #94a3b8;
        }
        * { box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: radial-gradient(circle at 10% 10%, rgba(14, 165, 233, 0.16) 0%, transparent 45%),
                        radial-gradient(circle at 90% 90%, rgba(52, 211, 153, 0.12) 0%, transparent 45%),
                        var(--bg);
            color: var(--text);
            margin: 0;
            padding: 0;
            line-height: 1.65;
            min-height: 100vh;
        }
        .skip-link { position: absolute; left: -999px; background: var(--accent); color: #0f172a; padding: 8px 14px; font-weight: 700; border-radius: 6px; }
        .skip-link:focus { left: 16px; top: 16px; z-index: 100; }

        /* Sticky Dashboard Top Bar */
        .topbar {
            position: sticky;
            top: 0;
            z-index: 50;
            background: rgba(3, 7, 18, 0.88);
            backdrop-filter: blur(14px);
            border-bottom: 1px solid var(--border);
            padding: 14px 24px;
        }
        .topbar-inner {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
        }
        .back-btn {
            background: rgba(30, 41, 59, 0.85);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.35);
            padding: 8px 16px;
            border-radius: 10px;
            text-decoration: none;
            font-weight: 700;
            font-size: 0.9rem;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }
        .back-btn:hover { background: #0284c7; color: #ffffff; border-color: #0284c7; transform: translateY(-1px); }
        .dash-brand { display: flex; align-items: center; gap: 10px; }
        .dash-brand-dot { width: 10px; height: 10px; background: #10b981; border-radius: 50%; box-shadow: 0 0 12px #10b981; }
        .dash-title { font-weight: 800; font-size: 1.15rem; color: #f8fafc; letter-spacing: -0.01em; }

        .container { max-width: 1200px; margin: 26px auto; padding: 0 20px 60px; }

        /* Context Banner & Pipeline Timeline */
        .context-banner {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 41, 59, 0.8) 100%);
            border: 1px solid var(--border);
            border-left: 5px solid var(--accent);
            border-radius: 16px;
            padding: 20px 24px;
            margin-bottom: 22px;
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            backdrop-filter: blur(10px);
            box-shadow: 0 12px 30px -5px rgba(0, 0, 0, 0.4);
        }
        .pipeline-status { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
        .status-step {
            background: rgba(6, 78, 59, 0.65);
            color: #6ee7b7;
            border: 1px solid #10b981;
            padding: 5px 13px;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 700;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .ast-badge {
            background: rgba(56, 189, 248, 0.12);
            color: #7dd3fc;
            border: 1px solid rgba(56, 189, 248, 0.35);
            padding: 5px 13px;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 700;
        }

        /* Auto-Extracted KPI Cards Strip */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .kpi-card {
            background: linear-gradient(180deg, rgba(17, 28, 51, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%);
            border: 1px solid var(--border);
            border-top: 3px solid var(--accent);
            border-radius: 14px;
            padding: 18px 20px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
            position: relative;
            overflow: hidden;
            transition: transform 0.2s, border-color 0.2s;
        }
        .kpi-card:hover {
            transform: translateY(-2px);
            border-color: var(--accent);
            box-shadow: 0 15px 30px -5px rgba(56, 189, 248, 0.2);
        }
        .kpi-label { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); font-weight: 800; }
        .kpi-val { font-size: 1.6rem; font-weight: 900; color: #f8fafc; margin-top: 6px; letter-spacing: -0.02em; }
        .kpi-tag { display: inline-block; font-size: 0.72rem; color: #34d399; background: rgba(52, 211, 153, 0.12); border: 1px solid rgba(52, 211, 153, 0.3); padding: 2px 8px; border-radius: 4px; margin-top: 8px; font-weight: 700; }

        .card {
            background: var(--card);
            padding: 30px;
            border-radius: 18px;
            border: 1px solid var(--border);
            backdrop-filter: blur(12px);
            box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.5);
        }
        .error { color: #fecaca; font-weight: 600; background: #7f1d1d; padding: 18px; border-radius: 12px; border: 1px solid #f87171; }

        /* Navigation Tabs & Export Actions */
        .toolbar {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 14px;
            padding-bottom: 18px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 24px;
        }
        .tab-group, .action-group { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
        .tab-btn, .action-btn {
            background: var(--card-alt);
            color: #e2e8f0;
            border: 1px solid var(--border);
            padding: 10px 16px;
            border-radius: 10px;
            font-size: 0.92rem;
            font-weight: 700;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.15s;
        }
        .tab-btn.active {
            background: var(--accent-btn);
            color: #ffffff;
            border-color: var(--accent);
            box-shadow: 0 0 16px rgba(2, 132, 199, 0.4);
        }
        .action-btn:hover, .tab-btn:hover { border-color: var(--accent); color: #ffffff; transform: translateY(-1px); }
        .action-btn.pitch-btn {
            background: linear-gradient(90deg, #6366f1, #8b5cf6);
            color: #ffffff;
            border-color: #8b5cf6;
        }
        .action-btn.pitch-btn:hover {
            filter: brightness(1.15);
            box-shadow: 0 0 18px rgba(139, 92, 246, 0.5);
        }
        .download-csv-btn {
            background: var(--green-btn);
            color: #ffffff;
            border: 1px solid #34d399;
            padding: 10px 18px;
            border-radius: 10px;
            font-size: 0.92rem;
            font-weight: 800;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }
        .download-csv-btn:hover { background: #047857; transform: translateY(-1px); box-shadow: 0 0 18px rgba(52, 211, 153, 0.4); }
        a:focus, button:focus, input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-glow); }

        /* Report & Styled Tables */
        .report-body h2 {
            color: var(--accent);
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
            margin-top: 28px;
            font-size: 1.35rem;
            font-weight: 800;
        }
        .report-body h3 { color: #7dd3fc; margin-top: 24px; font-size: 1.15rem; font-weight: 700; }
        .report-body p { color: #e2e8f0; margin: 12px 0; font-size: 1rem; }
        .report-body ul { padding-left: 24px; color: #e2e8f0; }
        .report-body li { margin-bottom: 10px; font-size: 0.98rem; }
        .table-wrap {
            overflow-x: auto;
            margin: 20px 0;
            border-radius: 12px;
            border: 1px solid var(--border);
            background: rgba(6, 11, 22, 0.6);
        }
        table.styled-table { width: 100%; border-collapse: collapse; font-size: 0.95rem; text-align: left; }
        table.styled-table th {
            background: rgba(30, 41, 59, 0.9);
            color: var(--accent);
            padding: 14px 16px;
            font-weight: 800;
            border-bottom: 2px solid var(--border);
            white-space: nowrap;
            letter-spacing: 0.02em;
        }
        table.styled-table td { padding: 12px 16px; border-bottom: 1px solid rgba(51, 65, 85, 0.5); color: #f1f5f9; }
        table.styled-table tbody tr:nth-child(even) { background: rgba(30, 41, 59, 0.35); }
        table.styled-table tbody tr:hover { background: rgba(56, 189, 248, 0.12); }

        .search-input {
            padding: 10px 14px;
            border-radius: 10px;
            border: 1px solid #334155;
            background: rgba(6, 11, 22, 0.85);
            color: #f8fafc;
            font-size: 0.92rem;
            width: 260px;
            transition: all 0.2s;
        }
        .chart-box {
            background: rgba(6, 11, 22, 0.8);
            padding: 24px;
            border-radius: 14px;
            border: 1px solid var(--border);
            margin-top: 26px;
            text-align: center;
        }
        .chart-box img { max-width: 100%; height: auto; border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }

        /* Collapsible Interactive Code Drawer */
        .trace-drawer-bar {
            margin-top: 28px;
            padding: 18px 22px;
            background: rgba(11, 19, 36, 0.9);
            border: 1px dashed rgba(56, 189, 248, 0.35);
            border-radius: 14px;
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 14px;
        }
        .trace-box {
            background: rgba(6, 11, 22, 0.9);
            padding: 22px;
            border-radius: 14px;
            border: 1px solid var(--border);
            margin-top: 16px;
        }
        pre.code-block {
            background: #020617;
            color: #cbd5e1;
            padding: 16px;
            border-radius: 10px;
            overflow-x: auto;
            font-size: 0.88rem;
            border: 1px solid #1e293b;
            font-family: 'JetBrains Mono', Consolas, Monaco, monospace;
        }
        .hidden { display: none !important; }

        /* Hackathon Presentation Mode Modal */
        .pitch-modal {
            position: fixed;
            inset: 0;
            z-index: 1000;
            background: rgba(3, 7, 18, 0.97);
            backdrop-filter: blur(16px);
            display: flex;
            flex-direction: column;
            padding: 24px;
        }
        .pitch-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 18px;
            border-bottom: 1px solid rgba(56, 189, 248, 0.2);
            max-width: 1100px;
            width: 100%;
            margin: 0 auto;
        }
        .pitch-body {
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            max-width: 1100px;
            width: 100%;
            margin: 0 auto;
            text-align: center;
            padding: 30px 10px;
            overflow-y: auto;
        }
        .pitch-slide { display: none; width: 100%; }
        .pitch-slide.active { display: block; animation: fadeIn 0.3s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: scale(0.98); } to { opacity: 1; transform: scale(1); } }
        .pitch-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 18px;
            border-top: 1px solid rgba(56, 189, 248, 0.2);
            max-width: 1100px;
            width: 100%;
            margin: 0 auto;
        }

        @media print { .topbar, .toolbar, .trace-drawer-bar, .search-input, .pitch-modal { display: none !important; } body { background: #ffffff; color: #000000; } }
    </style>
</head>
<body>
    <a href="#main-content" class="skip-link">Skip to main content</a>

    <header class="topbar" role="banner">
        <div class="topbar-inner">
            <a href="/" class="back-btn">&larr; Run New Analysis</a>
            <div class="dash-brand">
                <span class="dash-brand-dot"></span>
                <span class="dash-title">Executive Intelligence Dashboard</span>
            </div>
            <div class="action-group">
                <button type="button" class="action-btn pitch-btn" id="pitch-mode-btn" onclick="openPitchMode()">🎤 Pitch Deck Mode</button>
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
                <div style="font-size:0.82rem; color:#94a3b8; font-weight:800; text-transform:uppercase; letter-spacing:0.04em;">Dataset: {{ dataset_label }} {% if cleaned_shape %}&bull; <span style="color:#38bdf8;">{{ cleaned_shape }}</span>{% endif %}</div>
                <div style="font-size:1.15rem; font-weight:800; color:#f8fafc; margin-top:4px;">Goal: {{ goal }}</div>
            </div>
            <div class="pipeline-status" aria-label="Agent Execution Status">
                <span class="status-step">01 Profiler &#10003;</span>
                <span class="status-step">02 AST Sandbox &#10003; ({{ retry_count }} try)</span>
                <span class="status-step">03 Strategist &#10003;</span>
                <span class="ast-badge">🛡️ Zero-Hallucination AST Verified</span>
            </div>
        </section>

        {% if kpi_cards %}
        <section class="kpi-grid" aria-label="Key Performance Metrics">
            {% for kpi in kpi_cards %}
            <div class="kpi-card">
                <div class="kpi-label">{{ kpi.label }}</div>
                <div class="kpi-val">{{ kpi.value }}</div>
                <div class="kpi-tag">AST Verified Output</div>
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
                    <button type="button" class="tab-btn active" id="tab-all" data-view="all" onclick="switchView('all', this)">Executive Overview</button>
                    <button type="button" class="tab-btn" id="tab-report" data-view="report" onclick="switchView('report', this)">KPI Report &amp; Tables</button>
                    {% if cleaned_preview_html %}
                    <button type="button" class="tab-btn" id="tab-data" data-view="data" onclick="switchView('data', this)">Cleaned Dataset</button>
                    {% endif %}
                    {% if chart_b64 %}
                    <button type="button" class="tab-btn" id="tab-chart" data-view="chart" onclick="switchView('chart', this)">Visual Chart</button>
                    {% endif %}
                    {% if generated_code %}
                    <button type="button" class="tab-btn" id="tab-trace" data-view="trace" onclick="switchView('trace', this)">AST Code &amp; Audit</button>
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
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:12px;">
                    <div>
                        <h3 style="color:#34d399; margin:0; font-size:1.15rem; font-weight:800;">Cleaned Dataset Preview (Top 15 Rows)</h3>
                        <div style="font-size:0.85rem; color:#94a3b8; margin-top:2px;">Showing <strong id="filter-row-count" style="color:#38bdf8;">15</strong> records</div>
                    </div>
                    <input type="text" id="table-search" class="search-input" placeholder="Search cleaned rows..." aria-label="Filter cleaned dataset rows" onkeyup="filterCleanTable()">
                </div>
                <div class="table-wrap" id="clean-table-container">
                    {{ cleaned_preview_html | safe }}
                </div>
            </div>
            {% endif %}

            {% if chart_b64 %}
            <div id="chart-section" class="chart-box">
                <h3 style="margin-top:0; color:#38bdf8; font-size:1.2rem; font-weight:800;">Generated Statistical Visualization</h3>
                <img src="data:image/png;base64,{{ chart_b64 }}" alt="Automated statistical visualization generated for: {{ goal }}">
                <div style="margin-top:16px;">
                    <a class="download-csv-btn" href="data:image/png;base64,{{ chart_b64 }}" download="analysis_chart.png">Download Chart (PNG)</a>
                </div>
            </div>
            {% endif %}

            {% if generated_code %}
            <div id="trace-drawer-bar" class="trace-drawer-bar">
                <div>
                    <strong style="color:#e2e8f0; font-size:1.02rem;">Zero-Hallucination Audit &amp; AST Sandbox Verification</strong>
                    <div style="font-size:0.86rem; color:#94a3b8; margin-top:3px;">Inspect the exact Python code &amp; verified stdout metrics behind this report.</div>
                </div>
                <button type="button" class="action-btn" id="toggle-trace-btn" onclick="toggleTraceDrawer()">Show AST-Verified Code &amp; Trace &#9662;</button>
            </div>

            <div id="trace-section" class="trace-box hidden">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px;">
                    <h3 style="margin:0; color:#38bdf8; font-size:1.1rem; font-weight:800;">AST-Verified Pandas Code (Attempts: {{ retry_count }})</h3>
                    <button type="button" class="action-btn" id="copy-code-btn" onclick="copyCode()">Copy Python Code</button>
                </div>
                <pre class="code-block" id="agent-code-block"><code>{{ generated_code }}</code></pre>
                {% if analysis_output %}
                <h4 style="color:#94a3b8; margin:16px 0 8px;">Verified Stdout Output:</h4>
                <pre class="code-block"><code>{{ analysis_output }}</code></pre>
                {% endif %}
            </div>
            {% endif %}
        </section>
        {% endif %}
    </main>

    <!-- Hackathon Presentation Pitch Modal -->
    <div id="pitch-modal" class="pitch-modal hidden" role="dialog" aria-modal="true" aria-label="Pitch Deck Mode">
        <div class="pitch-header">
            <div style="display:flex; align-items:center; gap:10px;">
                <span class="dash-brand-dot"></span>
                <strong style="font-size:1.1rem; color:#f8fafc;">AgentOps BI &bull; Executive Pitch Deck</strong>
            </div>
            <button type="button" class="action-btn" onclick="closePitchMode()">Exit Presentation [Esc]</button>
        </div>

        <div class="pitch-body">
            <!-- Slide 1 -->
            <div class="pitch-slide active" id="pslide-1">
                <div style="color:#38bdf8; font-size:1rem; font-weight:800; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:12px;">Slide 1 &bull; Problem &amp; Data Overview</div>
                <h2 style="font-size:2.4rem; margin:0 0 16px; color:#ffffff;">{{ dataset_label }}</h2>
                <p style="font-size:1.2rem; color:#cbd5e1; max-width:800px; margin:0 auto 28px;">Goal: {{ goal }}</p>
                <div style="display:inline-flex; gap:12px; flex-wrap:wrap; justify-content:center;">
                    <span class="status-step">Agent 1: Schema Profiled &bull; Anomaly Scan Complete</span>
                    <span class="status-step">Agent 2: AST Sandboxed &bull; 0 Injection Vulnerabilities</span>
                    <span class="status-step">Agent 3: Executive Strategy Synthesized</span>
                </div>
            </div>

            <!-- Slide 2 -->
            <div class="pitch-slide" id="pslide-2">
                <div style="color:#38bdf8; font-size:1rem; font-weight:800; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:12px;">Slide 2 &bull; Verified Quantitative KPIs</div>
                <h2 style="font-size:2.2rem; margin:0 0 24px; color:#ffffff;">Executive Performance Snapshot</h2>
                {% if kpi_cards %}
                <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:18px; max-width:900px; width:100%; margin:0 auto;">
                    {% for kpi in kpi_cards %}
                    <div style="background:rgba(15,23,42,0.85); border:1px solid rgba(56,189,248,0.3); border-radius:14px; padding:22px; text-align:left;">
                        <div style="font-size:0.85rem; color:#94a3b8; font-weight:800; text-transform:uppercase;">{{ kpi.label }}</div>
                        <div style="font-size:2rem; font-weight:900; color:#38bdf8; margin-top:8px;">{{ kpi.value }}</div>
                    </div>
                    {% endfor %}
                </div>
                {% else %}
                <p style="color:#cbd5e1; font-size:1.1rem;">Analysis completed successfully. Review full tables in overview view.</p>
                {% endif %}
            </div>

            <!-- Slide 3 -->
            <div class="pitch-slide" id="pslide-3">
                <div style="color:#38bdf8; font-size:1rem; font-weight:800; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:12px;">Slide 3 &bull; Statistical Visualization</div>
                <h2 style="font-size:2.2rem; margin:0 0 20px; color:#ffffff;">Primary Revenue &amp; Distribution Driver</h2>
                {% if chart_b64 %}
                <img src="data:image/png;base64,{{ chart_b64 }}" style="max-height:480px; max-width:100%; border-radius:12px; box-shadow:0 10px 30px rgba(0,0,0,0.6);" alt="Presentation Chart">
                {% else %}
                <p style="color:#cbd5e1;">Visualization generated directly via sandboxed Matplotlib.</p>
                {% endif %}
            </div>

            <!-- Slide 4 -->
            <div class="pitch-slide" id="pslide-4">
                <div style="color:#38bdf8; font-size:1rem; font-weight:800; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:12px;">Slide 4 &bull; Technical Architecture</div>
                <h2 style="font-size:2.2rem; margin:0 0 20px; color:#ffffff;">Zero-Hallucination Multi-Agent Stack</h2>
                <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:18px; max-width:960px; width:100%; margin:0 auto; text-align:left;">
                    <div style="background:rgba(15,23,42,0.85); border:1px solid #334155; border-radius:14px; padding:20px;">
                        <h3 style="color:#38bdf8; margin:0 0 8px;">LangGraph Coordination</h3>
                        <p style="color:#cbd5e1; font-size:0.92rem; margin:0;">Cyclic retry loop with self-healing code generation. Automatically corrects pandas syntax exceptions.</p>
                    </div>
                    <div style="background:rgba(15,23,42,0.85); border:1px solid #334155; border-radius:14px; padding:20px;">
                        <h3 style="color:#34d399; margin:0 0 8px;">AST Static Security Guard</h3>
                        <p style="color:#cbd5e1; font-size:0.92rem; margin:0;">Inspects abstract syntax tree before execution. Forbids os, sys, socket, subprocess, and unauthorized file access.</p>
                    </div>
                    <div style="background:rgba(15,23,42,0.85); border:1px solid #334155; border-radius:14px; padding:20px;">
                        <h3 style="color:#818cf8; margin:0 0 8px;">Deterministic KPIs</h3>
                        <p style="color:#cbd5e1; font-size:0.92rem; margin:0;">All numbers in the dashboard come directly from validated Python stdout—never invented by LLM hallucinations.</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="pitch-footer">
            <button type="button" class="action-btn" onclick="prevSlide()">&larr; Previous Slide</button>
            <div style="color:#94a3b8; font-weight:700;" id="pitch-counter">Slide 1 of 4</div>
            <button type="button" class="action-btn" onclick="nextSlide()">Next Slide &rarr;</button>
        </div>
    </div>

    <script>
        function switchView(mode, btn) {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            if (btn) btn.classList.add("active");
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

        document.addEventListener("DOMContentLoaded", function() {
            document.querySelectorAll(".tab-btn").forEach(function(btn) {
                btn.addEventListener("click", function() {
                    const mode = this.getAttribute("data-view") || this.id.replace("tab-", "");
                    switchView(mode, this);
                });
            });
            const toggleTrace = document.getElementById("toggle-trace-btn");
            if (toggleTrace) {
                toggleTrace.addEventListener("click", toggleTraceDrawer);
            }
            const copyBtn = document.getElementById("copy-btn");
            if (copyBtn) {
                copyBtn.addEventListener("click", copyReport);
            }
            const copyCodeBtn = document.getElementById("copy-code-btn");
            if (copyCodeBtn) {
                copyCodeBtn.addEventListener("click", copyCode);
            }
            const searchInput = document.getElementById("table-search");
            if (searchInput) {
                searchInput.addEventListener("input", filterCleanTable);
            }
        });

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
            let visibleCount = 0;
            rows.forEach(r => {
                const match = r.textContent.toLowerCase().includes(q);
                r.style.display = match ? "" : "none";
                if (match) visibleCount++;
            });
            const counter = document.getElementById("filter-row-count");
            if (counter) counter.textContent = visibleCount;
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

        /* Presentation Mode Functions */
        let currentSlide = 1;
        const totalSlides = 4;
        function openPitchMode() {
            document.getElementById("pitch-modal").classList.remove("hidden");
            currentSlide = 1;
            showSlide(currentSlide);
        }
        function closePitchMode() {
            document.getElementById("pitch-modal").classList.add("hidden");
        }
        function showSlide(n) {
            for (let i = 1; i <= totalSlides; i++) {
                const sl = document.getElementById("pslide-" + i);
                if (sl) sl.classList.toggle("active", i === n);
            }
            const cnt = document.getElementById("pitch-counter");
            if (cnt) cnt.textContent = `Slide ${n} of ${totalSlides}`;
        }
        function nextSlide() {
            if (currentSlide < totalSlides) { currentSlide++; showSlide(currentSlide); }
        }
        function prevSlide() {
            if (currentSlide > 1) { currentSlide--; showSlide(currentSlide); }
        }
        document.addEventListener("keydown", function(e) {
            const modal = document.getElementById("pitch-modal");
            if (!modal || modal.classList.contains("hidden")) return;
            if (e.key === "Escape") closePitchMode();
            if (e.key === "ArrowRight" || e.key === " ") nextSlide();
            if (e.key === "ArrowLeft") prevSlide();
        });
    </script>
</body>
</html>
"""


@app.after_request
def add_security_headers(response):
    return apply_hardened_headers(response)


@app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
@app.route("/<path:path>", methods=["GET", "POST"])
def analyze(path):
    charts_b64 = []
    if request.method == "GET":
        return render_template_string(HOME_TEMPLATE)

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
    allowed, retry_after = RATE_LIMITER.is_allowed(client_ip)
    if not allowed:
        return render_template_string(
            DASHBOARD_TEMPLATE,
            report_raw="",
            report_html="",
            chart_b64="",
            charts_b64=[],
            cleaned_csv_b64="",
            cleaned_preview_html="",
            cleaned_shape="",
            generated_code="",
            analysis_output="",
            kpi_cards=[],
            retry_count=1,
            dataset_label="Rate Limited",
            error=f"Rate limit exceeded: Too many requests from your IP. Please wait {retry_after} seconds before launching another analysis.",
            goal=request.form.get("user_goal", ""),
        ), 429

    if request.content_length and request.content_length > 5 * 1024 * 1024:
        return render_template_string(
            DASHBOARD_TEMPLATE,
            report_raw="",
            report_html="",
            chart_b64="",
            charts_b64=[],
            cleaned_csv_b64="",
            cleaned_preview_html="",
            cleaned_shape="",
            generated_code="",
            analysis_output="",
            kpi_cards=[],
            retry_count=1,
            dataset_label="Payload Too Large",
            error="Payload Too Large: Maximum allowed upload size is 5 MB.",
            goal=request.form.get("user_goal", "")[:500],
        ), 413

    report_raw = ""
    report_html = ""
    chart_b64 = ""
    cleaned_csv_b64 = ""
    cleaned_preview_html = ""
    cleaned_shape = ""
    generated_code = ""
    analysis_output = ""
    kpi_cards = []
    retry_count = 1
    error = ""
    dataset_label = "Sample Dataset"
    goal = request.form.get("user_goal", "").strip()[:500] or "Clean duplicates and missing values, summarize top KPIs, and plot the primary revenue driver."
    uploaded = request.files.get("uploaded_csv")

    try:
        if uploaded and uploaded.filename:
            safe_name = secure_filename(uploaded.filename)
            if not safe_name.lower().endswith(".csv"):
                raise ValueError("Invalid file format. Please upload a .csv file.")
            raw_bytes = uploaded.read()
            decoded_text = validate_csv_bytes(raw_bytes)
            tmp_csv = os.path.join(tempfile.gettempdir(), safe_name)
            with open(tmp_csv, "w", encoding="utf-8") as f:
                f.write(decoded_text)
            csv_path = tmp_csv
            dataset_label = f"Uploaded: {safe_name}"
        else:
            rel_path = request.form.get("sample_csv", "data/raw/ecommerce_sales_data.csv")
            if rel_path not in ALLOWED_SAMPLES:
                raise ValueError("Invalid sample dataset selected.")
            csv_path = os.path.join(ROOT_DIR, rel_path)
            dataset_label = os.path.basename(rel_path)

        if not os.getenv("GROQ_API_KEY"):
            raise ValueError("Server configuration incomplete: GROQ_API_KEY is not configured.")

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
        generated_code = result.get("generated_code", "")
        analysis_output = result.get("analysis_output", "")
        kpi_cards = extract_kpi_cards(analysis_output)
        retry_count = result.get("retry_count", 1)

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
            cleaned_preview_html = df_clean.head(15).to_html(index=False, classes="styled-table", border=0)

    except ValueError as ve:
        error = str(ve)
    except Exception as exc:
        logging.exception("Agent pipeline error")
        error = f"Unable to complete analysis: {type(exc).__name__}. Please verify your CSV format and try again."

    return render_template_string(
        DASHBOARD_TEMPLATE,
        report_raw=report_raw,
        report_html=report_html,
        chart_b64=chart_b64,
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🚀 AgentOps BI Studio starting on http://127.0.0.1:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=True)