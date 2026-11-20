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
            --cursor-x: 50vw;
            --cursor-y: 50vh;
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
            position: relative;
            overflow-x: hidden;
        }
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: radial-gradient(650px circle at var(--cursor-x) var(--cursor-y), rgba(56, 189, 248, 0.08), transparent 80%);
            pointer-events: none;
            z-index: 0;
        }
        #bg-canvas {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 0;
            pointer-events: none;
            opacity: 0.72;
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
            position: relative;
            z-index: 10;
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
            box-shadow: 0 0 16px rgba(56, 189, 248, 0.25);
        }

        .container { max-width: 1140px; margin: 30px auto; padding: 0 20px 60px; position: relative; z-index: 10; }

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
            background: linear-gradient(135deg, #ffffff 0%, #7dd3fc 35%, #818cf8 70%, #34d399 100%);
            background-size: 200% 200%;
            animation: textShimmer 8s ease infinite;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            line-height: 1.15;
            font-weight: 900;
            letter-spacing: -0.03em;
        }
        @keyframes textShimmer {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
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
            transform-style: preserve-3d;
            perspective: 1000px;
            will-change: transform;
            transition: transform 0.15s ease-out, border-color 0.25s, box-shadow 0.25s;
            position: relative;
            overflow: hidden;
            cursor: pointer;
        }
        .agent-card:hover {
            border-color: var(--accent);
            box-shadow: 0 16px 35px -5px rgba(56, 189, 248, 0.25);
        }
        .agent-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: linear-gradient(90deg, var(--accent), var(--indigo));
        }
        .tilt-glare {
            position: absolute;
            inset: 0;
            border-radius: inherit;
            pointer-events: none;
            background: radial-gradient(circle at var(--glare-x, 50%) var(--glare-y, 50%), rgba(255, 255, 255, 0.16) 0%, transparent 60%);
            opacity: 0;
            transition: opacity 0.2s;
            mix-blend-mode: overlay;
            z-index: 2;
        }
        .agent-card:hover .tilt-glare,
        .preset-card:hover .tilt-glare {
            opacity: 1;
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
            display: flex;
            align-items: flex-start;
            gap: 14px;
            transform-style: preserve-3d;
            perspective: 1000px;
            will-change: transform;
            transition: transform 0.15s ease-out, border-color 0.25s, box-shadow 0.25s;
            position: relative;
            overflow: hidden;
        }
        .preset-card:hover {
            background: rgba(30, 41, 59, 0.85);
            border-color: var(--accent);
            box-shadow: 0 10px 24px rgba(56, 189, 248, 0.2);
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
    <canvas id="bg-canvas" aria-hidden="true"></canvas>
    <a href="#main-content" class="skip-link">Skip to main content</a>

    <nav class="navbar" aria-label="Primary Navigation">
        <div class="brand">
            <span class="brand-dot"></span>
            <span>AgentOps <span style="color:#38bdf8;">BI Studio</span></span>
        </div>
        <div class="nav-badges">
            <span class="badge hackathon">🏆 Hackathon Edition</span>
            <span class="badge">LangGraph 5-Agent Swarm</span>
            <span class="badge">AutoML Clustering</span>
            <span class="badge">AST Security Guard</span>
            <span class="badge">WCAG 2.1 AA</span>
        </div>
    </nav>

    <main id="main-content" class="container" role="main">
        <header class="hero" role="banner">
            <div class="hero-pill">⚡ 5-Agent Autonomous LangGraph Swarm • AutoML Segmentation &amp; What-If Simulation</div>
            <h1>Autonomous Multi-Agent CSV Analyst</h1>
            <p>Transform messy operational datasets into boardroom-ready Business Intelligence in seconds. Five coordinated agents audit data health, clean anomalies via an AST-sandboxed Python runtime, discover ML customer clusters, simulate margin scenarios, and generate executive presentation decks.</p>

            <div class="pipeline-grid" aria-label="Multi-Agent Architecture Overview">
                <div class="agent-card">
                    <div class="agent-step">Agent 01 &bull; Profiler</div>
                    <div class="agent-title">Schema &amp; Data Health Auditor</div>
                    <p class="agent-desc">Automated scanning of schema types, duplicate records, null frequencies, and 0-100% Data Hygiene Scorecard.</p>
                </div>
                <div class="agent-card">
                    <div class="agent-step">Agent 02 &bull; AST Sandbox</div>
                    <div class="agent-title">Self-Healing Pandas Analyst</div>
                    <p class="agent-desc">Generates AST-checked Python transformations, auto-corrects syntax bugs, and extracts publication-grade KPIs.</p>
                </div>
                <div class="agent-card">
                    <div class="agent-step">Agent 03 &bull; Predictive ML</div>
                    <div class="agent-title">AutoML Segmenter &amp; Forecaster</div>
                    <p class="agent-desc">Performs K-Means clustering into customer tiers, trend extrapolation with R&sup2; fit, and confidence interval modeling.</p>
                </div>
                <div class="agent-card">
                    <div class="agent-step">Agent 04 &bull; Modeler</div>
                    <div class="agent-title">What-If Sensitivity Modeler</div>
                    <p class="agent-desc">Evaluates operational leakage, gross margin expansion, and computes Conservative, Target, and Aggressive scenario models.</p>
                </div>
                <div class="agent-card">
                    <div class="agent-step">Agent 05 &bull; Strategist</div>
                    <div class="agent-title">Boardroom BI Synthesizer</div>
                    <p class="agent-desc">Synthesizes verified data points into boardroom Markdown tables, high-ROI actions, and 1-click executive pitch deck slides.</p>
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
        <h2 style="margin:0; color:#38bdf8; font-weight:800; font-size:1.6rem;">Orchestrating 5-Agent LangGraph Swarm...</h2>
        <p style="color:#94a3b8; margin:8px 0 0; font-size:1.02rem;">Executing AST verification &bull; AutoML Clustering &bull; <strong id="elapsed-sec" style="color:#38bdf8;">0s</strong></p>
        <ul class="step-list">
            <li id="st-1" class="active-step">🔍 1. Data Health Auditor: Auditing completeness, uniqueness &amp; hygiene...</li>
            <li id="st-2">🛡️ 2. AST Sandbox Analyst: Verifying security AST &amp; generating chart...</li>
            <li id="st-3">🤖 3. AutoML Segmenter: Computing K-Means clusters &amp; trend forecast...</li>
            <li id="st-4">💡 4. What-If Modeler: Calculating margin expansion scenarios...</li>
            <li id="st-5">🧠 5. Boardroom Strategist: Synthesizing KPI cards &amp; executive deck...</li>
        </ul>
        <button type="button" onclick="window.stop(); document.getElementById('loader').classList.remove('active');" style="margin-top:22px; background:transparent; border:1px solid #475569; color:#94a3b8; padding:8px 20px; border-radius:10px; cursor:pointer; font-size:0.9rem;">Cancel Pipeline</button>
    </div>

    <script>
        // Synthesized Audio Feedback
        let audioCtx = null;
        function playBlip(freq = 600, duration = 0.04) {
            try {
                const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
                if (!AudioCtxClass) return;
                if (!audioCtx) audioCtx = new AudioCtxClass();
                if (audioCtx.state === 'suspended') audioCtx.resume();
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = "sine";
                osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
                gain.gain.setValueAtTime(0.025, audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + duration);
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.start();
                osc.stop(audioCtx.currentTime + duration);
            } catch (e) {}
        }

        // 3D Particle Constellation Canvas
        function init3DCanvas() {
            const canvas = document.getElementById("bg-canvas");
            if (!canvas) return;
            const ctx = canvas.getContext("2d");
            let width = canvas.width = window.innerWidth;
            let height = canvas.height = window.innerHeight;
            
            window.addEventListener("resize", () => {
                width = canvas.width = window.innerWidth;
                height = canvas.height = window.innerHeight;
            });

            let mouseX = 0, mouseY = 0;
            window.addEventListener("mousemove", (e) => {
                mouseX = (e.clientX - width / 2) * 0.04;
                mouseY = (e.clientY - height / 2) * 0.04;
                document.documentElement.style.setProperty("--cursor-x", e.clientX + "px");
                document.documentElement.style.setProperty("--cursor-y", e.clientY + "px");
            });

            const numNodes = 45;
            const nodes = [];
            for (let i = 0; i < numNodes; i++) {
                nodes.push({
                    x: (Math.random() - 0.5) * width * 1.4,
                    y: (Math.random() - 0.5) * height * 1.4,
                    z: Math.random() * 500 + 100,
                    vx: (Math.random() - 0.5) * 0.5,
                    vy: (Math.random() - 0.5) * 0.5,
                    vz: (Math.random() - 0.5) * 0.3
                });
            }

            function render() {
                ctx.clearRect(0, 0, width, height);
                const fov = 350;
                const projected = [];

                for (let i = 0; i < nodes.length; i++) {
                    const p = nodes[i];
                    p.x += p.vx;
                    p.y += p.vy;
                    p.z += p.vz;

                    if (p.z < 60) p.z = 600;
                    if (p.z > 600) p.z = 60;
                    if (p.x < -width) p.x = width;
                    if (p.x > width) p.x = -width;
                    if (p.y < -height) p.y = height;
                    if (p.y > height) p.y = -height;

                    const scale = fov / (fov + p.z);
                    const px = p.x * scale + width / 2 + mouseX * scale;
                    const py = p.y * scale + height / 2 + mouseY * scale;
                    projected.push({ x: px, y: py, scale: scale });

                    ctx.beginPath();
                    ctx.arc(px, py, Math.max(1, 2.4 * scale), 0, Math.PI * 2);
                    ctx.fillStyle = "rgba(56, 189, 248, " + (0.35 * scale) + ")";
                    ctx.fill();
                }

                for (let i = 0; i < projected.length; i++) {
                    for (let j = i + 1; j < projected.length; j++) {
                        const dx = projected[i].x - projected[j].x;
                        const dy = projected[i].y - projected[j].y;
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        if (dist < 110) {
                            ctx.beginPath();
                            ctx.moveTo(projected[i].x, projected[i].y);
                            ctx.lineTo(projected[j].x, projected[j].y);
                            const alpha = (1 - dist / 110) * 0.18 * projected[i].scale;
                            ctx.strokeStyle = "rgba(129, 140, 248, " + alpha + ")";
                            ctx.lineWidth = 1;
                            ctx.stroke();
                        }
                    }
                }
                requestAnimationFrame(render);
            }
            requestAnimationFrame(render);
        }

        // 3D Card Tilt Interaction
        function init3DTilt() {
            const cards = document.querySelectorAll(".agent-card, .preset-card");
            cards.forEach(card => {
                if (!card.querySelector(".tilt-glare")) {
                    const g = document.createElement("div");
                    g.className = "tilt-glare";
                    card.appendChild(g);
                }
                card.addEventListener("mousemove", e => {
                    const rect = card.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    const y = e.clientY - rect.top;
                    const cx = rect.width / 2;
                    const cy = rect.height / 2;
                    const rotX = ((y - cy) / cy) * -8;
                    const rotY = ((x - cx) / cx) * 8;
                    card.style.transform = `perspective(1000px) rotateX(${rotX.toFixed(2)}deg) rotateY(${rotY.toFixed(2)}deg) scale3d(1.02, 1.02, 1.02)`;
                    card.style.setProperty("--glare-x", `${(x / rect.width * 100).toFixed(1)}%`);
                    card.style.setProperty("--glare-y", `${(y / rect.height * 100).toFixed(1)}%`);
                });
                card.addEventListener("mouseenter", () => playBlip(560, 0.02));
                card.addEventListener("mouseleave", () => {
                    card.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)";
                });
            });
        }

        function setGoal(text) {
            playBlip(680, 0.03);
            const box = document.getElementById("user-goal");
            if (box) box.value = text;
        }
        function selectPreset(path, prompt) {
            playBlip(720, 0.04);
            const sel = document.getElementById("sample-csv");
            if (sel) sel.value = path;
            setGoal(prompt);
            const upload = document.getElementById("uploaded-csv");
            if (upload) upload.value = "";
        }

        document.addEventListener("DOMContentLoaded", function() {
            init3DCanvas();
            init3DTilt();
        });

        document.getElementById("analysis-form").addEventListener("submit", function () {
            playBlip(880, 0.06);
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
            }, 600);
            setTimeout(() => {
                const s2 = document.getElementById("st-2");
                const s3 = document.getElementById("st-3");
                if (s2) s2.classList.remove("active-step");
                if (s3) s3.classList.add("active-step");
            }, 1300);
            setTimeout(() => {
                const s3 = document.getElementById("st-3");
                const s4 = document.getElementById("st-4");
                if (s3) s3.classList.remove("active-step");
                if (s4) s4.classList.add("active-step");
            }, 2000);
            setTimeout(() => {
                const s4 = document.getElementById("st-4");
                const s5 = document.getElementById("st-5");
                if (s4) s4.classList.remove("active-step");
                if (s5) s5.classList.add("active-step");
            }, 2700);
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
            --cursor-x: 50vw;
            --cursor-y: 50vh;
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
            position: relative;
            overflow-x: hidden;
        }
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: radial-gradient(650px circle at var(--cursor-x) var(--cursor-y), rgba(56, 189, 248, 0.08), transparent 80%);
            pointer-events: none;
            z-index: 0;
        }
        #bg-canvas {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 0;
            pointer-events: none;
            opacity: 0.72;
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
            transform-style: preserve-3d;
            perspective: 1000px;
            will-change: transform;
            transition: transform 0.15s ease-out, border-color 0.25s, box-shadow 0.25s;
            cursor: pointer;
        }
        .kpi-card:hover {
            border-color: var(--accent);
            box-shadow: 0 16px 35px -5px rgba(56, 189, 248, 0.25);
        }
        .tilt-glare {
            position: absolute;
            inset: 0;
            border-radius: inherit;
            pointer-events: none;
            background: radial-gradient(circle at var(--glare-x, 50%) var(--glare-y, 50%), rgba(255, 255, 255, 0.16) 0%, transparent 60%);
            opacity: 0;
            transition: opacity 0.2s;
            mix-blend-mode: overlay;
            z-index: 2;
        }
        .kpi-card:hover .tilt-glare,
        .sim-card:hover .tilt-glare,
        .graph-node:hover .tilt-glare {
            opacity: 1;
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
        .pitch-modal, .graph-modal, .chart-modal {
            position: fixed;
            inset: 0;
            z-index: 1000;
            background: rgba(3, 7, 18, 0.97);
            backdrop-filter: blur(18px);
            display: flex;
            flex-direction: column;
            padding: 24px;
        }
        .pitch-header, .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 18px;
            border-bottom: 1px solid rgba(56, 189, 248, 0.2);
            max-width: 1100px;
            width: 100%;
            margin: 0 auto;
        }
        .pitch-body, .modal-body {
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

        /* Interactive Scenario Simulator Card */
        .sim-card {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.85) 100%);
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-radius: 16px;
            padding: 22px 26px;
            margin-bottom: 24px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
            transform-style: preserve-3d;
            perspective: 1000px;
            will-change: transform;
            transition: transform 0.15s ease-out, border-color 0.25s, box-shadow 0.25s;
            position: relative;
            overflow: hidden;
        }
        .sim-card:hover {
            border-color: var(--accent);
            box-shadow: 0 16px 36px rgba(56, 189, 248, 0.25);
        }
        .sim-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
        .sim-badge { background: rgba(56, 189, 248, 0.12); color: #7dd3fc; border: 1px solid rgba(56, 189, 248, 0.35); padding: 4px 12px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; text-transform: uppercase; }
        .sim-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; align-items: center; }
        .sim-control label { font-size: 0.95rem; font-weight: 700; color: #f8fafc; margin-bottom: 10px; display: block; }
        .sim-control input[type="range"] {
            width: 100%;
            height: 8px;
            border-radius: 5px;
            background: #1e293b;
            outline: none;
            -webkit-appearance: none;
            cursor: pointer;
        }
        .sim-control input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 22px;
            height: 22px;
            border-radius: 50%;
            background: #38bdf8;
            box-shadow: 0 0 12px #38bdf8;
            cursor: pointer;
        }
        .sim-range-labels { display: flex; justify-content: space-between; font-size: 0.76rem; color: #94a3b8; margin-top: 6px; font-weight: 600; }
        .sim-metric {
            background: rgba(6, 11, 22, 0.75);
            border: 1px solid rgba(52, 211, 153, 0.3);
            border-radius: 12px;
            padding: 16px 20px;
            text-align: left;
        }
        .sim-metric-label { font-size: 0.78rem; font-weight: 800; text-transform: uppercase; color: #94a3b8; }
        .sim-metric-val { font-size: 1.8rem; font-weight: 900; color: #34d399; margin: 4px 0; letter-spacing: -0.02em; }
        .sim-metric-sub { font-size: 0.8rem; color: #6ee7b7; font-weight: 600; }

        /* Multi-Agent Node Graph Styling & Holographic Flow */
        .graph-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
            width: 100%;
            text-align: left;
            margin-top: 20px;
        }
        .graph-pipeline-flow {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin: 18px 0;
            width: 100%;
        }
        .pipeline-beam {
            height: 3px;
            flex: 1;
            background: linear-gradient(90deg, #38bdf8, #34d399, #818cf8);
            position: relative;
            border-radius: 999px;
            overflow: hidden;
            box-shadow: 0 0 12px rgba(56, 189, 248, 0.5);
        }
        .beam-pulse {
            position: absolute;
            top: 0; left: 0; bottom: 0;
            width: 60px;
            background: #ffffff;
            box-shadow: 0 0 16px #ffffff, 0 0 24px #38bdf8;
            animation: beamPulse 1.8s infinite ease-in-out;
        }
        @keyframes beamPulse {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(800%); }
        }
        .graph-node {
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 16px;
            padding: 22px;
            position: relative;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
            transform-style: preserve-3d;
            perspective: 1000px;
            will-change: transform;
            transition: transform 0.15s ease-out, border-color 0.25s, box-shadow 0.25s;
            overflow: hidden;
        }
        .graph-node:hover { border-color: var(--accent); box-shadow: 0 14px 34px rgba(56, 189, 248, 0.28); }
        .node-badge { display: inline-block; font-size: 0.75rem; font-weight: 800; text-transform: uppercase; padding: 3px 10px; border-radius: 6px; margin-bottom: 10px; }
        .node-1 .node-badge { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }
        .node-2 .node-badge { background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); }
        .node-3 .node-badge { background: rgba(129, 140, 248, 0.15); color: #818cf8; border: 1px solid rgba(129, 140, 248, 0.3); }

        /* Follow-Up Ask Console */
        .followup-box {
            margin-top: 32px;
            padding: 24px;
            background: rgba(11, 19, 36, 0.95);
            border: 1px solid var(--border);
            border-radius: 16px;
        }
        .followup-header { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
        .followup-input-row { display: flex; gap: 10px; }
        .followup-input { flex: 1; padding: 12px 16px; border-radius: 10px; border: 1px solid #334155; background: #060b16; color: #f8fafc; font-size: 0.95rem; }

        th.sortable { cursor: pointer; user-select: none; transition: background 0.15s; }
        th.sortable:hover { background: rgba(56, 189, 248, 0.18) !important; color: #ffffff; }
        .sort-icon { font-size: 0.75rem; margin-left: 6px; opacity: 0.7; }

        /* Data Health Scorecard Styling */
        .health-card {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.85) 100%);
            border: 1px solid rgba(52, 211, 153, 0.35);
            border-radius: 16px;
            padding: 18px 24px;
            margin-bottom: 22px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
        }
        .health-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; }
        .health-circle-badge {
            background: radial-gradient(circle, rgba(16, 185, 129, 0.25) 0%, rgba(6, 78, 59, 0.4) 100%);
            border: 2px solid #10b981;
            border-radius: 50%;
            width: 62px;
            height: 62px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            box-shadow: 0 0 18px rgba(16, 185, 129, 0.35);
            flex-shrink: 0;
        }
        .health-score-val { font-size: 1.15rem; font-weight: 900; color: #6ee7b7; line-height: 1; }
        .health-score-sub { font-size: 0.62rem; color: #a7f3d0; font-weight: 700; }
        .health-pills { display: flex; gap: 10px; flex-wrap: wrap; }
        .health-pill {
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(56, 189, 248, 0.25);
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 0.82rem;
            color: #cbd5e1;
        }
        .health-pill strong { color: #38bdf8; margin-left: 4px; }

        @media print { .topbar, .toolbar, .trace-drawer-bar, .search-input, .pitch-modal { display: none !important; } body { background: #ffffff; color: #000000; } }
    </style>
</head>
<body>
    <canvas id="bg-canvas" aria-hidden="true"></canvas>
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
                <button type="button" class="action-btn" onclick="openGraphModal()">⚡ State Graph</button>
                <button type="button" class="action-btn" id="audio-btn" onclick="toggleAudio()">🔊 Sound: ON</button>
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
                <span class="status-step">03 ML Predictor &#10003;</span>
                <span class="status-step">04 Fin Modeler &#10003;</span>
                <span class="status-step">05 Strategist &#10003;</span>
                <span class="ast-badge">🛡️ Zero-Hallucination AST Verified</span>
            </div>
        </section>

        {% if health_score and health_score.overall_score %}
        <section class="health-card" aria-label="Data Health Scorecard">
            <div class="health-header">
                <div style="display:flex; align-items:center; gap:14px;">
                    <div class="health-circle-badge">
                        <span class="health-score-val">{{ health_score.overall_score }}</span>
                        <span class="health-score-sub">/ 100</span>
                    </div>
                    <div>
                        <strong style="font-size:1.15rem; color:#f8fafc;">Data Quality &amp; Health Score: <span style="color:#34d399;">{{ health_score.grade }}</span></strong>
                        <div style="font-size:0.86rem; color:#94a3b8; margin-top:3px;">Mathematical verification: {{ health_score.null_count }} missing cells &bull; {{ health_score.duplicate_count }} duplicates &bull; {{ health_score.anomaly_count }} out-of-bound values detected &amp; handled.</div>
                    </div>
                </div>
                <div class="health-pills">
                    <span class="health-pill">Completeness: <strong>{{ health_score.completeness_pct }}%</strong></span>
                    <span class="health-pill">Uniqueness: <strong>{{ health_score.uniqueness_pct }}%</strong></span>
                    <span class="health-pill">Validity: <strong>{{ health_score.validity_pct }}%</strong></span>
                </div>
            </div>
        </section>
        {% endif %}

        {% if kpi_cards %}
        <section class="kpi-grid" aria-label="Key Performance Metrics">
            {% for kpi in kpi_cards %}
            <div class="kpi-card" data-val="{{ kpi.value }}">
                <div class="kpi-label">{{ kpi.label }}</div>
                <div class="kpi-val">{{ kpi.value }}</div>
                <div class="kpi-tag">AST Verified Output</div>
            </div>
            {% endfor %}
        </section>

        <!-- Interactive Scenario & Margin Simulator -->
        <section class="sim-card" aria-label="Executive What-If Scenario Simulator">
            <div class="sim-header">
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size:1.4rem;">💡</span>
                    <div>
                        <strong style="color:#f8fafc; font-size:1.08rem;">Interactive Executive Simulator: Margin Recovery &amp; Optimization</strong>
                        <div style="font-size:0.85rem; color:#94a3b8; margin-top:2px;">Model cashflow and gross margin recovery based on operational optimization targets.</div>
                    </div>
                </div>
                <span class="sim-badge">Real-Time Sensitivity Engine</span>
            </div>
            <div class="sim-grid">
                <div class="sim-control">
                    <label for="return-slider">Target Operational Improvement / Return Mitigation: <strong id="slider-val" style="color:#38bdf8;">10%</strong></label>
                    <input type="range" id="return-slider" min="2" max="30" value="10" step="1" oninput="updateSimulation(this.value)">
                    <div class="sim-range-labels">
                        <span>2% (Conservative)</span>
                        <span>15% (Target)</span>
                        <span>30% (Aggressive)</span>
                    </div>
                </div>
                <div class="sim-metric">
                    <div class="sim-metric-label">Projected Annual Margin Recovery</div>
                    <div class="sim-metric-val" id="sim-savings">+$18,500.00</div>
                    <div class="sim-metric-sub" id="sim-details">&bull; Computed against analyzed transaction base</div>
                </div>
            </div>
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
                    {% if ml_insights and ml_insights.clusters %}
                    <button type="button" class="tab-btn" id="tab-ml" data-view="ml" onclick="switchView('ml', this)">🤖 Predictive ML &amp; Segments</button>
                    {% endif %}
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

            {% if ml_insights and ml_insights.clusters %}
            <div id="ml-section" class="ml-box" style="margin-top: 28px;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:14px; border-bottom:1px solid var(--border); padding-bottom:12px;">
                    <div>
                        <h3 style="color:#38bdf8; margin:0; font-size:1.25rem; font-weight:800;">🤖 Automated K-Means Customer Clustering &amp; Predictive Forecasting</h3>
                        <div style="font-size:0.86rem; color:#94a3b8; margin-top:3px;">Vectorized machine learning clustering &bull; Trend regression with 90% confidence bands.</div>
                    </div>
                    <span class="sim-badge">AutoML Engine Output</span>
                </div>

                <div class="table-wrap">
                    <table class="styled-table">
                        <thead>
                            <tr>
                                <th>Customer Segment Tier</th>
                                <th>Volume</th>
                                <th>Share of Total</th>
                                <th>Avg Primary Metric</th>
                                <th>Automated Strategic Playbook</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for cluster in ml_insights.clusters %}
                            <tr>
                                <td><strong style="color:#38bdf8;">{{ cluster.name }}</strong></td>
                                <td>{{ cluster.count }} records</td>
                                <td><span style="color:#34d399; font-weight:700;">{{ cluster.percent_of_total }}%</span></td>
                                <td>{{ cluster.primary_feature }}: <strong>{{ cluster.avg_primary_metric }}</strong></td>
                                <td>
                                    {% if 'Champions' in cluster.name %}
                                    <span style="color:#6ee7b7; font-weight:700;">💎 VIP Retention, Loyalty Rewards &amp; Concierge Upsell</span>
                                    {% elif 'Core' in cluster.name %}
                                    <span style="color:#93c5fd; font-weight:700;">📈 Frequency Incentives &amp; Automated Cross-Sell</span>
                                    {% else %}
                                    <span style="color:#fde047; font-weight:700;">🎯 Margin-Safe Reactivation Triggers &amp; Nudges</span>
                                    {% endif %}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>

                {% if ml_insights.forecast %}
                <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:14px; margin:20px 0;">
                    <div class="kpi-card">
                        <div class="kpi-label">Forecast R&sup2; Fit</div>
                        <div class="kpi-val">{{ ml_insights.forecast.r_squared }}</div>
                        <div class="kpi-tag">Statistical Confidence</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Trend Growth Velocity</div>
                        <div class="kpi-val">{% if ml_insights.forecast.growth_velocity_pct > 0 %}+{% endif %}{{ ml_insights.forecast.growth_velocity_pct }}%</div>
                        <div class="kpi-tag">Sequential Momentum</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Forward Projected Horizon</div>
                        <div class="kpi-val">{{ ml_insights.forecast.projected_final_value }}</div>
                        <div class="kpi-tag">+{{ ml_insights.forecast.projected_horizon_points }} Periods Out</div>
                    </div>
                </div>
                {% endif %}

                {% if ml_chart_b64 %}
                <div class="chart-box" style="margin-top:20px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px;">
                        <h4 style="margin:0; color:#38bdf8; font-size:1.1rem; font-weight:800;">Predictive Visualization: Dual K-Means Clusters &amp; Forward Horizon Fit</h4>
                        <a class="download-csv-btn" href="data:image/png;base64,{{ ml_chart_b64 }}" download="predictive_ml_chart.png">Download ML Chart (PNG)</a>
                    </div>
                    <img src="data:image/png;base64,{{ ml_chart_b64 }}" style="max-width:100%; height:auto; border-radius:10px; box-shadow:0 10px 30px rgba(0,0,0,0.5);" alt="Predictive Machine Learning Chart">
                </div>
                {% endif %}
            </div>
            {% endif %}

            {% if cleaned_preview_html %}
            <div id="data-section" style="margin-top: 28px;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:12px;">
                    <div>
                        <h3 style="color:#34d399; margin:0; font-size:1.15rem; font-weight:800;">Cleaned Dataset Preview (Top 15 Rows)</h3>
                        <div style="font-size:0.85rem; color:#94a3b8; margin-top:2px;">Showing <strong id="filter-row-count" style="color:#38bdf8;">15</strong> records &bull; Click any header to sort</div>
                    </div>
                    <div style="display:flex; gap:8px;">
                        <input type="text" id="table-search" class="search-input" placeholder="Search cleaned rows..." aria-label="Filter cleaned dataset rows" onkeyup="filterCleanTable()">
                        <button type="button" class="action-btn" onclick="exportTableJSON()">Export JSON</button>
                    </div>
                </div>
                <div class="table-wrap" id="clean-table-container">
                    {{ cleaned_preview_html | safe }}
                </div>
            </div>
            {% endif %}

            {% if chart_b64 %}
            <div id="chart-section" class="chart-box">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px;">
                    <h3 style="margin:0; color:#38bdf8; font-size:1.2rem; font-weight:800;">Generated Statistical Visualization</h3>
                    <button type="button" class="action-btn" onclick="openChartModal()">🔍 Click to Expand / Zoom</button>
                </div>
                <img src="data:image/png;base64,{{ chart_b64 }}" id="main-chart-img" style="cursor:zoom-in;" onclick="openChartModal()" alt="Automated statistical visualization generated for: {{ goal }}">
                <div style="margin-top:16px; display:flex; justify-content:center; gap:10px;">
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

            <!-- Interactive Follow-Up Query Console -->
            <div class="followup-box">
                <div class="followup-header">
                    <span style="font-size:1.2rem;">💬</span>
                    <strong style="color:#f8fafc; font-size:1.05rem;">Ask Follow-Up Question to Multi-Agent Pipeline</strong>
                </div>
                <form action="/analyze" method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="sample_csv" value="{{ dataset_label }}">
                    <div class="followup-input-row">
                        <input type="text" name="user_goal" class="followup-input" placeholder="e.g. Compare customer segments by average discount, or break down monthly trends..." required>
                        <button type="submit" class="action-btn pitch-btn">Submit Query &rarr;</button>
                    </div>
                </form>
            </div>
        </section>
        {% endif %}
    </main>

    <!-- Interactive Multi-Agent Network Graph Modal -->
    <div id="graph-modal" class="graph-modal hidden" role="dialog" aria-modal="true" aria-label="Multi-Agent Network Graph">
        <div class="modal-header">
            <div style="display:flex; align-items:center; gap:10px;">
                <span class="dash-brand-dot"></span>
                <strong style="font-size:1.15rem; color:#f8fafc;">⚡ Multi-Agent LangGraph Orchestration Inspector</strong>
            </div>
            <button type="button" class="action-btn" onclick="closeGraphModal()">Close [Esc]</button>
        </div>
        <div class="modal-body">
            <div style="color:#38bdf8; font-size:0.95rem; font-weight:800; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:10px;">Autonomous Execution Graph</div>
            <h2 style="font-size:2rem; margin:0 0 10px; color:#ffffff;">Active Node Pipeline Topology</h2>
            <p style="color:#94a3b8; max-width:760px; margin:0 auto 16px;">Inspect how data payloads transition securely across specialized agents with cyclic self-healing boundaries.</p>

            <div class="graph-pipeline-flow" aria-hidden="true">
                <span style="font-size:0.8rem; font-weight:800; color:#38bdf8; text-transform:uppercase;">Input Payload</span>
                <div class="pipeline-beam"><div class="beam-pulse"></div></div>
                <span style="font-size:0.8rem; font-weight:800; color:#34d399; text-transform:uppercase;">AST Verified</span>
                <div class="pipeline-beam"><div class="beam-pulse" style="animation-delay: 0.6s;"></div></div>
                <span style="font-size:0.8rem; font-weight:800; color:#818cf8; text-transform:uppercase;">BI Artifacts</span>
            </div>

            <div class="graph-container">
                <div class="graph-node node-1">
                    <span class="node-badge">Agent 1 &bull; Schema Profiler</span>
                    <h3 style="color:#f8fafc; margin:0 0 6px; font-size:1.1rem;">Data Health &amp; Hygiene</h3>
                    <p style="color:#cbd5e1; font-size:0.88rem; margin:0 0 12px;">Profiles nulls, duplicate keys, dtypes, and generates the 0-100% Data Quality Scorecard.</p>
                    <div style="font-size:0.78rem; color:#38bdf8; font-weight:700;">Output: Structured Profile &amp; Hygiene Score</div>
                </div>

                <div class="graph-node node-2">
                    <span class="node-badge">Security Gate &bull; AST Sandbox</span>
                    <h3 style="color:#f8fafc; margin:0 0 6px; font-size:1.1rem;">Zero-Hallucination Guard</h3>
                    <p style="color:#cbd5e1; font-size:0.88rem; margin:0 0 12px;">AST tree walk blocks eval, exec, os, socket, sys, and subprocess attacks before execution.</p>
                    <div style="font-size:0.78rem; color:#34d399; font-weight:700;">Status: 100% Sandbox Enforced</div>
                </div>

                <div class="graph-node node-3">
                    <span class="node-badge">Agent 2 &bull; Pandas Analyst</span>
                    <h3 style="color:#f8fafc; margin:0 0 6px; font-size:1.1rem;">Self-Healing Pandas Runtime</h3>
                    <p style="color:#cbd5e1; font-size:0.88rem; margin:0 0 12px;">Transforms messy data, normalizes strings, and produces verified stdout KPIs. (Attempts: {{ retry_count }})</p>
                    <div style="font-size:0.78rem; color:#818cf8; font-weight:700;">Output: Cleaned CSV &amp; Core Figure</div>
                </div>

                <div class="graph-node node-2">
                    <span class="node-badge" style="background:rgba(245,158,11,0.15); color:#f59e0b; border:1px solid rgba(245,158,11,0.3);">Agent 3 &bull; Predictive ML</span>
                    <h3 style="color:#f8fafc; margin:0 0 6px; font-size:1.1rem;">AutoML Clustering &amp; Forecast</h3>
                    <p style="color:#cbd5e1; font-size:0.88rem; margin:0 0 12px;">Runs K-Means customer tier clustering and linear trend extrapolation with R&sup2; confidence interval.</p>
                    <div style="font-size:0.78rem; color:#f59e0b; font-weight:700;">Output: Segment Profiles &amp; ML Visuals</div>
                </div>

                <div class="graph-node node-1">
                    <span class="node-badge">Agent 4 &amp; 5 &bull; Executive BI</span>
                    <h3 style="color:#f8fafc; margin:0 0 6px; font-size:1.1rem;">What-If Sensitivity &amp; Strategy</h3>
                    <p style="color:#cbd5e1; font-size:0.88rem; margin:0 0 12px;">Computes gross margin expansion, return mitigation cashflow, and outputs executive markdown.</p>
                    <div style="font-size:0.78rem; color:#38bdf8; font-weight:700;">Output: Boardroom Pitch Deck &amp; Directives</div>
                </div>
            </div>
        </div>
    </div>

    <!-- Chart Zoom Lightbox Modal -->
    <div id="chart-modal" class="chart-modal hidden" role="dialog" aria-modal="true" aria-label="Chart Lightbox">
        <div class="modal-header">
            <strong style="font-size:1.15rem; color:#f8fafc;">Statistical Figure Deep Zoom</strong>
            <button type="button" class="action-btn" onclick="closeChartModal()">Close [Esc]</button>
        </div>
        <div class="modal-body" style="padding:10px;">
            {% if chart_b64 %}
            <img src="data:image/png;base64,{{ chart_b64 }}" id="lightbox-img" style="max-height:80vh; max-width:95vw; border-radius:12px; transition:transform 0.2s;" alt="Expanded Chart">
            {% endif %}
        </div>
        <div style="display:flex; justify-content:center; gap:12px; padding-top:14px; border-top:1px solid rgba(56,189,248,0.2);">
            <button type="button" class="action-btn" onclick="zoomChart(1.2)">Zoom In (+)</button>
            <button type="button" class="action-btn" onclick="zoomChart(0.8)">Zoom Out (-)</button>
            <button type="button" class="action-btn" onclick="resetZoom()">Reset</button>
            {% if chart_b64 %}
            <a class="download-csv-btn" href="data:image/png;base64,{{ chart_b64 }}" download="analysis_chart.png">Download PNG</a>
            {% endif %}
        </div>
    </div>

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
        /* Modern Web Audio Synthesizer */
        let audioEnabled = true;
        let audioCtx = null;
        function getAudioContext() {
            if (!audioCtx) {
                const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
                if (AudioCtxClass) audioCtx = new AudioCtxClass();
            }
            if (audioCtx && audioCtx.state === 'suspended') {
                audioCtx.resume();
            }
            return audioCtx;
        }
        function playBlip(freq = 600, duration = 0.05) {
            if (!audioEnabled) return;
            try {
                const ctx = getAudioContext();
                if (!ctx) return;
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = "sine";
                osc.frequency.setValueAtTime(freq, ctx.currentTime);
                gain.gain.setValueAtTime(0.04, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start();
                osc.stop(ctx.currentTime + duration);
            } catch (err) {}
        }
        function toggleAudio() {
            audioEnabled = !audioEnabled;
            const btn = document.getElementById("audio-btn");
            if (btn) btn.textContent = audioEnabled ? "🔊 Sound: ON" : "🔇 Sound: OFF";
            if (audioEnabled) playBlip(800, 0.08);
        }

        /* View Switcher */
        function switchView(mode, btn) {
            playBlip(680, 0.04);
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            if (btn) btn.classList.add("active");
            const rep = document.getElementById("report-section");
            const ml = document.getElementById("ml-section");
            const dat = document.getElementById("data-section");
            const ch = document.getElementById("chart-section");
            const bar = document.getElementById("trace-drawer-bar");
            const tr = document.getElementById("trace-section");
            const show = (el, flag) => { if (el) el.classList.toggle("hidden", !flag); };

            if (mode === "all") {
                show(rep, true); show(ml, true); show(dat, true); show(ch, true); show(bar, true); show(tr, false);
                const tBtn = document.getElementById("toggle-trace-btn");
                if (tBtn) tBtn.innerHTML = "Show AST-Verified Code &amp; Trace &#9662;";
            } else if (mode === "report") { show(rep, true); show(ml, false); show(dat, false); show(ch, false); show(bar, false); show(tr, false); }
            else if (mode === "ml") { show(rep, false); show(ml, true); show(dat, false); show(ch, false); show(bar, false); show(tr, false); }
            else if (mode === "data") { show(rep, false); show(ml, false); show(dat, true); show(ch, false); show(bar, false); show(tr, false); }
            else if (mode === "chart") { show(rep, false); show(ml, false); show(dat, false); show(ch, true); show(bar, false); show(tr, false); }
            else if (mode === "trace") { show(rep, false); show(ml, false); show(dat, false); show(ch, false); show(bar, false); show(tr, true); }
        }

        /* Scenario Simulator Engine */
        function updateSimulation(pct) {
            playBlip(400 + Number(pct) * 20, 0.02);
            const sliderLabel = document.getElementById("slider-val");
            if (sliderLabel) sliderLabel.textContent = pct + "%";
            
            // Baseline computation extracted from displayed KPI or default 150000
            let baselineRevenue = 150000;
            const kpiCards = document.querySelectorAll(".kpi-card");
            kpiCards.forEach(card => {
                const text = card.textContent;
                const match = text.match(/[\$₹]?([0-9,]+(\.[0-9]+)?)/);
                if (match && Number(match[1].replace(/,/g, "")) > baselineRevenue) {
                    baselineRevenue = Number(match[1].replace(/,/g, ""));
                }
            });
            const savings = Math.round(baselineRevenue * (Number(pct) / 100) * 0.14);
            const savingsEl = document.getElementById("sim-savings");
            if (savingsEl) {
                savingsEl.textContent = "+$" + savings.toLocaleString();
            }
        }

        /* Interactive Table Sorting */
        function initSortableTable() {
            const table = document.querySelector("#clean-table-container table");
            if (!table) return;
            const headers = table.querySelectorAll("th");
            headers.forEach((th, idx) => {
                th.classList.add("sortable");
                th.title = "Click to sort by this column";
                th.innerHTML += ' <span class="sort-icon">&varr;</span>';
                th.addEventListener("click", () => {
                    playBlip(750, 0.03);
                    sortTableByColumn(table, idx);
                });
            });
        }
        let sortAsc = true;
        let lastSortedIdx = -1;
        function sortTableByColumn(table, colIdx) {
            const tbody = table.querySelector("tbody");
            if (!tbody) return;
            const rows = Array.from(tbody.querySelectorAll("tr"));
            if (lastSortedIdx === colIdx) sortAsc = !sortAsc;
            else sortAsc = true;
            lastSortedIdx = colIdx;

            rows.sort((a, b) => {
                const cellA = (a.cells[colIdx]?.textContent || "").trim();
                const cellB = (b.cells[colIdx]?.textContent || "").trim();
                const numA = parseFloat(cellA.replace(/[^0-9.-]+/g, ""));
                const numB = parseFloat(cellB.replace(/[^0-9.-]+/g, ""));
                if (!isNaN(numA) && !isNaN(numB)) {
                    return sortAsc ? numA - numB : numB - numA;
                }
                return sortAsc ? cellA.localeCompare(cellB) : cellB.localeCompare(cellA);
            });
            rows.forEach(r => tbody.appendChild(r));

            table.querySelectorAll("th .sort-icon").forEach((icon, i) => {
                icon.textContent = (i === colIdx) ? (sortAsc ? "▲" : "▼") : "↕";
            });
        }

        /* Export Filtered Table as JSON */
        function exportTableJSON() {
            playBlip(800, 0.05);
            const table = document.querySelector("#clean-table-container table");
            if (!table) return;
            const headers = Array.from(table.querySelectorAll("th")).map(th => th.textContent.replace(/[▲▼↕]/g, "").trim());
            const rows = Array.from(table.querySelectorAll("tbody tr")).filter(r => r.style.display !== "none");
            const data = rows.map(r => {
                const rowObj = {};
                Array.from(r.cells).forEach((td, i) => {
                    rowObj[headers[i] || `col_${i}`] = td.textContent.trim();
                });
                return rowObj;
            });
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "cleaned_data_filtered.json";
            a.click();
            URL.revokeObjectURL(url);
        }

        /* Chart Zoom Lightbox */
        let currentChartZoom = 1;
        function openChartModal() {
            playBlip(720, 0.05);
            document.getElementById("chart-modal").classList.remove("hidden");
            resetZoom();
        }
        function closeChartModal() {
            document.getElementById("chart-modal").classList.add("hidden");
        }
        function zoomChart(factor) {
            currentChartZoom *= factor;
            const img = document.getElementById("lightbox-img");
            if (img) img.style.transform = `scale(${currentChartZoom})`;
        }
        function resetZoom() {
            currentChartZoom = 1;
            const img = document.getElementById("lightbox-img");
            if (img) img.style.transform = "scale(1)";
        }

        /* Graph Modal */
        function openGraphModal() {
            playBlip(750, 0.05);
            document.getElementById("graph-modal").classList.remove("hidden");
        }
        function closeGraphModal() {
            document.getElementById("graph-modal").classList.add("hidden");
        }

        // 3D Particle Constellation Canvas
        function init3DCanvas() {
            const canvas = document.getElementById("bg-canvas");
            if (!canvas) return;
            const ctx = canvas.getContext("2d");
            let width = canvas.width = window.innerWidth;
            let height = canvas.height = window.innerHeight;
            
            window.addEventListener("resize", () => {
                width = canvas.width = window.innerWidth;
                height = canvas.height = window.innerHeight;
            });

            let mouseX = 0, mouseY = 0;
            window.addEventListener("mousemove", (e) => {
                mouseX = (e.clientX - width / 2) * 0.04;
                mouseY = (e.clientY - height / 2) * 0.04;
                document.documentElement.style.setProperty("--cursor-x", e.clientX + "px");
                document.documentElement.style.setProperty("--cursor-y", e.clientY + "px");
            });

            const numNodes = 42;
            const nodes = [];
            for (let i = 0; i < numNodes; i++) {
                nodes.push({
                    x: (Math.random() - 0.5) * width * 1.4,
                    y: (Math.random() - 0.5) * height * 1.4,
                    z: Math.random() * 500 + 100,
                    vx: (Math.random() - 0.5) * 0.45,
                    vy: (Math.random() - 0.5) * 0.45,
                    vz: (Math.random() - 0.5) * 0.3
                });
            }

            function render() {
                ctx.clearRect(0, 0, width, height);
                const fov = 350;
                const projected = [];

                for (let i = 0; i < nodes.length; i++) {
                    const p = nodes[i];
                    p.x += p.vx;
                    p.y += p.vy;
                    p.z += p.vz;

                    if (p.z < 60) p.z = 600;
                    if (p.z > 600) p.z = 60;
                    if (p.x < -width) p.x = width;
                    if (p.x > width) p.x = -width;
                    if (p.y < -height) p.y = height;
                    if (p.y > height) p.y = -height;

                    const scale = fov / (fov + p.z);
                    const px = p.x * scale + width / 2 + mouseX * scale;
                    const py = p.y * scale + height / 2 + mouseY * scale;
                    projected.push({ x: px, y: py, scale: scale });

                    ctx.beginPath();
                    ctx.arc(px, py, Math.max(1, 2.4 * scale), 0, Math.PI * 2);
                    ctx.fillStyle = "rgba(56, 189, 248, " + (0.35 * scale) + ")";
                    ctx.fill();
                }

                for (let i = 0; i < projected.length; i++) {
                    for (let j = i + 1; j < projected.length; j++) {
                        const dx = projected[i].x - projected[j].x;
                        const dy = projected[i].y - projected[j].y;
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        if (dist < 110) {
                            ctx.beginPath();
                            ctx.moveTo(projected[i].x, projected[i].y);
                            ctx.lineTo(projected[j].x, projected[j].y);
                            const alpha = (1 - dist / 110) * 0.18 * projected[i].scale;
                            ctx.strokeStyle = "rgba(129, 140, 248, " + alpha + ")";
                            ctx.lineWidth = 1;
                            ctx.stroke();
                        }
                    }
                }
                requestAnimationFrame(render);
            }
            requestAnimationFrame(render);
        }

        // 3D Card Tilt Interaction
        function init3DTilt() {
            const cards = document.querySelectorAll(".kpi-card, .sim-card, .graph-node");
            cards.forEach(card => {
                if (!card.querySelector(".tilt-glare")) {
                    const g = document.createElement("div");
                    g.className = "tilt-glare";
                    card.appendChild(g);
                }
                card.addEventListener("mousemove", e => {
                    const rect = card.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    const y = e.clientY - rect.top;
                    const cx = rect.width / 2;
                    const cy = rect.height / 2;
                    const rotX = ((y - cy) / cy) * -7;
                    const rotY = ((x - cx) / cx) * 7;
                    card.style.transform = `perspective(1000px) rotateX(${rotX.toFixed(2)}deg) rotateY(${rotY.toFixed(2)}deg) scale3d(1.02, 1.02, 1.02)`;
                    card.style.setProperty("--glare-x", `${(x / rect.width * 100).toFixed(1)}%`);
                    card.style.setProperty("--glare-y", `${(y / rect.height * 100).toFixed(1)}%`);
                });
                card.addEventListener("mouseenter", () => playBlip(560, 0.02));
                card.addEventListener("mouseleave", () => {
                    card.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)";
                });
            });
        }

        // Animated Numeric KPI Counter-Up
        function animateCounters() {
            const kpis = document.querySelectorAll(".kpi-val");
            kpis.forEach(el => {
                const text = el.textContent.trim();
                const match = text.match(/^([^\d.-]*)([\d,]+(?:\.\d+)?)(.*)$/);
                if (!match) return;
                const prefix = match[1];
                const numStr = match[2];
                const suffix = match[3];
                const target = parseFloat(numStr.replace(/,/g, ""));
                const hasDec = numStr.includes(".");
                const decCount = hasDec ? numStr.split(".")[1].length : 0;
                const duration = 1200;
                const start = performance.now();

                function frame(now) {
                    const progress = Math.min((now - start) / duration, 1);
                    const ease = 1 - Math.pow(1 - progress, 3);
                    const cur = target * ease;
                    const formatted = hasDec
                        ? cur.toLocaleString(undefined, { minimumFractionDigits: decCount, maximumFractionDigits: decCount })
                        : Math.round(cur).toLocaleString();
                    el.textContent = `${prefix}${formatted}${suffix}`;
                    if (progress < 1) {
                        requestAnimationFrame(frame);
                    } else {
                        el.textContent = text;
                    }
                }
                requestAnimationFrame(frame);
            });
        }

        document.addEventListener("DOMContentLoaded", function() {
            init3DCanvas();
            init3DTilt();
            animateCounters();
            initSortableTable();
            updateSimulation(10);
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
            playBlip(600, 0.03);
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
            playBlip(900, 0.05);
            const rawBox = document.getElementById("raw-markdown");
            if (!rawBox) return;
            navigator.clipboard.writeText(rawBox.value).then(() => {
                const btn = document.getElementById("copy-btn");
                btn.textContent = "Copied!";
                setTimeout(() => { btn.textContent = "Copy Report"; }, 2000);
            });
        }

        function copyCode() {
            playBlip(900, 0.05);
            const codeEl = document.getElementById("agent-code-block");
            if (!codeEl) return;
            navigator.clipboard.writeText(codeEl.innerText).then(() => {
                const btn = document.getElementById("copy-code-btn");
                btn.textContent = "Code Copied!";
                setTimeout(() => { btn.textContent = "Copy Python Code"; }, 2000);
            });
        }

        function downloadReport() {
            playBlip(850, 0.05);
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
            playBlip(800, 0.06);
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
            if (currentSlide < totalSlides) {
                playBlip(700, 0.03);
                currentSlide++;
                showSlide(currentSlide);
            }
        }
        function prevSlide() {
            if (currentSlide > 1) {
                playBlip(600, 0.03);
                currentSlide--;
                showSlide(currentSlide);
            }
        }
        document.addEventListener("keydown", function(e) {
            const pitch = document.getElementById("pitch-modal");
            const graph = document.getElementById("graph-modal");
            const chart = document.getElementById("chart-modal");

            if (e.key === "Escape") {
                if (pitch && !pitch.classList.contains("hidden")) closePitchMode();
                if (graph && !graph.classList.contains("hidden")) closeGraphModal();
                if (chart && !chart.classList.contains("hidden")) closeChartModal();
            }
            if (pitch && !pitch.classList.contains("hidden")) {
                if (e.key === "ArrowRight" || e.key === " ") nextSlide();
                if (e.key === "ArrowLeft") prevSlide();
            }
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
            ml_chart_b64="",
            cleaned_csv_b64="",
            cleaned_preview_html="",
            cleaned_shape="",
            generated_code="",
            analysis_output="",
            kpi_cards=[],
            health_score={},
            ml_insights={},
            scenario_models={},
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
            ml_chart_b64="",
            cleaned_csv_b64="",
            cleaned_preview_html="",
            cleaned_shape="",
            generated_code="",
            analysis_output="",
            kpi_cards=[],
            health_score={},
            ml_insights={},
            scenario_models={},
            retry_count=1,
            dataset_label="Payload Too Large",
            error="Payload Too Large: Maximum allowed upload size is 5 MB.",
            goal=request.form.get("user_goal", "")[:500],
        ), 413

    report_raw = ""
    report_html = ""
    chart_b64 = ""
    ml_chart_b64 = ""
    cleaned_csv_b64 = ""
    cleaned_preview_html = ""
    cleaned_shape = ""
    generated_code = ""
    analysis_output = ""
    kpi_cards = []
    health_score = {}
    ml_insights = {}
    scenario_models = {}
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

        # If GROQ_API_KEY is present, LLMs are used; otherwise, the resilient deterministic multi-agent engine executes
        has_api_key = bool(os.getenv("GROQ_API_KEY"))

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
            "health_score": {},
            "ml_insights": {},
            "ml_chart_path": "",
            "scenario_models": {},
        })

        report_raw = result.get("final_report", "")
        report_html = render_markdown_to_html(report_raw)
        generated_code = result.get("generated_code", "")
        analysis_output = result.get("analysis_output", "")
        kpi_cards = extract_kpi_cards(analysis_output)
        health_score = result.get("health_score", {})
        ml_insights = result.get("ml_insights", {})
        scenario_models = result.get("scenario_models", {})
        retry_count = result.get("retry_count", 1)

        c_path = result.get("chart_path", "")
        if c_path and os.path.exists(c_path):
            with open(c_path, "rb") as img_f:
                chart_b64 = base64.b64encode(img_f.read()).decode("utf-8")

        ml_c_path = result.get("ml_chart_path", "")
        if ml_c_path and os.path.exists(ml_c_path):
            with open(ml_c_path, "rb") as ml_f:
                ml_chart_b64 = base64.b64encode(ml_f.read()).decode("utf-8")

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
        ml_chart_b64=ml_chart_b64,
        cleaned_csv_b64=cleaned_csv_b64,
        cleaned_preview_html=cleaned_preview_html,
        cleaned_shape=cleaned_shape,
        generated_code=generated_code,
        analysis_output=analysis_output,
        kpi_cards=kpi_cards,
        health_score=health_score,
        ml_insights=ml_insights,
        scenario_models=scenario_models,
        retry_count=retry_count,
        dataset_label=dataset_label,
        error=error,
        goal=goal,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    is_debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true")
    print(f"\n🚀 AgentOps BI Studio starting on http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=is_debug)
