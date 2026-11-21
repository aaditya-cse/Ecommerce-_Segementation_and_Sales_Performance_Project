"""Generates a professional 16:9 dark-mode executive presentation for AgentOps BI Studio."""
import os
import pptx
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# Theme Palette (Deep Cyber Slate & Neon Accents)
COLOR_BG = RGBColor(11, 17, 32)         # #0b1120
COLOR_CARD = RGBColor(22, 32, 54)       # #162036
COLOR_CARD_BORDER = RGBColor(56, 189, 248) # #38bdf8
COLOR_TEXT_WHITE = RGBColor(248, 250, 252) # #f8fafc
COLOR_TEXT_MUTED = RGBColor(148, 163, 184) # #94a3b8
COLOR_CYAN = RGBColor(56, 189, 248)     # #38bdf8
COLOR_PURPLE = RGBColor(168, 85, 247)   # #a855f7
COLOR_EMERALD = RGBColor(52, 211, 153)  # #34d399
COLOR_GOLD = RGBColor(251, 191, 36)     # #fbbf24


def set_slide_background(slide):
    """Sets dark slate background for slide."""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = COLOR_BG


def add_header(slide, title_text, category="AGY HACKATHON 2026 • TEAM HACKQUBE"):
    """Adds a standard executive header to the slide."""
    # Category tag
    cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.4))
    tf_cat = cat_box.text_frame
    tf_cat.word_wrap = True
    p_cat = tf_cat.paragraphs[0]
    p_cat.text = category.upper()
    p_cat.font.size = Pt(10)
    p_cat.font.bold = True
    p_cat.font.color.rgb = COLOR_CYAN

    # Main title
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.75), Inches(11.7), Inches(0.7))
    tf_title = title_box.text_frame
    tf_title.word_wrap = True
    p_title = tf_title.paragraphs[0]
    p_title.text = title_text
    p_title.font.size = Pt(24)
    p_title.font.bold = True
    p_title.font.color.rgb = COLOR_TEXT_WHITE


def add_card(slide, left, top, width, height, title="", border_color=None):
    """Creates a stylized dark card with optional title."""
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    card.fill.solid()
    card.fill.fore_color.rgb = COLOR_CARD
    if border_color:
        card.line.color.rgb = border_color
        card.line.width = Pt(1.5)
    else:
        card.line.color.rgb = RGBColor(30, 41, 59)
        card.line.width = Pt(1)

    if title:
        tb = slide.shapes.add_textbox(left + Inches(0.25), top + Inches(0.18), width - Inches(0.5), Inches(0.45))
        tf = tb.text_frame
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(14)
        p.font.bold = True
        p.font.color.rgb = COLOR_CYAN
    return card


def build_deck(output_pptx="AgentOps_BI_Studio_Presentation.pptx"):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # ==========================================
    # SLIDE 1: COVER / TITLE SLIDE
    # ==========================================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_background(s1)

    # Decorative banner card
    add_card(s1, Inches(1.0), Inches(1.2), Inches(11.333), Inches(5.1), border_color=COLOR_CYAN)

    tbox = s1.shapes.add_textbox(Inches(1.5), Inches(1.8), Inches(10.333), Inches(2.2))
    tf = tbox.text_frame
    tf.word_wrap = True
    p1 = tf.paragraphs[0]
    p1.text = "AgentOps BI Studio"
    p1.font.size = Pt(44)
    p1.font.bold = True
    p1.font.color.rgb = COLOR_TEXT_WHITE

    p2 = tf.add_paragraph()
    p2.text = "Autonomous 5-Agent Multi-Agent Swarm for Enterprise E-Commerce Intelligence"
    p2.font.size = Pt(20)
    p2.font.color.rgb = COLOR_CYAN

    p3 = tf.add_paragraph()
    p3.text = "\nZero-Trust AST Code Sandboxing • AutoML K-Means Clustering • What-If Scenario Modeling • Sub-5s Execution"
    p3.font.size = Pt(13)
    p3.font.color.rgb = COLOR_TEXT_MUTED

    # Meta card
    meta_box = s1.shapes.add_textbox(Inches(1.5), Inches(4.5), Inches(10.333), Inches(1.2))
    tf_meta = meta_box.text_frame
    pm1 = tf_meta.paragraphs[0]
    pm1.text = "🏆 HACKATHON 2026 SUBMISSION  |  TEAM HACKQUBE"
    pm1.font.size = Pt(13)
    pm1.font.bold = True
    pm1.font.color.rgb = COLOR_EMERALD

    pm2 = tf_meta.add_paragraph()
    pm2.text = "GitHub: https://github.com/aaditya-cse/Ecommerce-_Segementation_and_Sales_Performance_Project"
    pm2.font.size = Pt(12)
    pm2.font.color.rgb = COLOR_TEXT_MUTED

    # ==========================================
    # SLIDE 2: THE PROBLEM STATEMENT
    # ==========================================
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_background(s2)
    add_header(s2, "The Problem: The $4.8 Trillion E-Commerce BI Bottleneck")

    add_card(s2, Inches(0.8), Inches(1.7), Inches(3.6), Inches(4.9), "1. Traditional BI is Slow", COLOR_GOLD)
    tb2_1 = s2.shapes.add_textbox(Inches(1.0), Inches(2.4), Inches(3.2), Inches(3.8))
    tb2_1.text_frame.word_wrap = True
    tb2_1.text_frame.text = (
        "• Analysts spend 80% of time data cleaning, deduplicating, and formatting CSVs.\n\n"
        "• Complex dashboards require weeks of manual SQL writing, ETL pipelines, and manual tuning.\n\n"
        "• SMBs cannot afford $150K/year dedicated data science teams."
    )
    for p in tb2_1.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    add_card(s2, Inches(4.8), Inches(1.7), Inches(3.6), Inches(4.9), "2. Security Vulnerabilities", RGBColor(239, 68, 68))
    tb2_2 = s2.shapes.add_textbox(Inches(5.0), Inches(2.4), Inches(3.2), Inches(3.8))
    tb2_2.text_frame.word_wrap = True
    tb2_2.text_frame.text = (
        "• Traditional LLM code interpreters blindly execute generated Python code with eval() and exec().\n\n"
        "• Malicious users exploit prompt injections to access OS files, environment keys, and network sockets.\n\n"
        "• CSV formula injection risks corporate data leakages."
    )
    for p in tb2_2.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    add_card(s2, Inches(8.8), Inches(1.7), Inches(3.6), Inches(4.9), "3. Lack of Actionable Insight", COLOR_PURPLE)
    tb2_3 = s2.shapes.add_textbox(Inches(9.0), Inches(2.4), Inches(3.2), Inches(3.8))
    tb2_3.text_frame.word_wrap = True
    tb2_3.text_frame.text = (
        "• Standard BI tools generate static charts with no strategic decision-making.\n\n"
        "• No real-time predictive clustering or cohort segmentation.\n\n"
        "• No dynamic what-if margin modeling to guide executive pricing decisions."
    )
    for p in tb2_3.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    # ==========================================
    # SLIDE 3: THE SOLUTION - 5-AGENT SWARM
    # ==========================================
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_background(s3)
    add_header(s3, "The Breakthrough: Autonomous 5-Agent LangGraph Swarm")

    agents = [
        ("1. Data Health Auditor", "Automated hygiene scoring (0-100), duplicate purging, null imputation, and data quality scorecard generation.", COLOR_CYAN),
        ("2. AST Sandbox Analyst", "Synthesizes Python analytics within a zero-trust AST security sandbox, producing production-grade data charts.", COLOR_GOLD),
        ("3. AutoML Segmenter", "Unsupervised K-Means clustering discovers RFM customer cohorts, computing centroid profiles & trend forecasts.", COLOR_PURPLE),
        ("4. What-If Modeler", "Simulates Conservative, Aggressive, and Hyper-Growth margin expansion scenarios with price elasticity math.", COLOR_EMERALD),
        ("5. Boardroom Strategist", "Synthesizes verified execution logs into boardroom-ready Markdown tables, KPI cards, and strategic growth decks.", RGBColor(244, 63, 94)),
    ]

    for i, (name, desc, color) in enumerate(agents):
        x = Inches(0.8 + (i % 3) * 3.9) if i < 3 else Inches(2.75 + (i - 3) * 3.9)
        y = Inches(1.7) if i < 3 else Inches(4.4)
        add_card(s3, x, y, Inches(3.7), Inches(2.4), name, color)
        tb = s3.shapes.add_textbox(x + Inches(0.2), y + Inches(0.65), Inches(3.3), Inches(1.6))
        tb.text_frame.word_wrap = True
        tb.text_frame.text = desc
        tb.text_frame.paragraphs[0].font.size = Pt(12)
        tb.text_frame.paragraphs[0].font.color.rgb = COLOR_TEXT_MUTED

    # ==========================================
    # SLIDE 4: SYSTEM ARCHITECTURE & TOPOLOGY
    # ==========================================
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_background(s4)
    add_header(s4, "LangGraph Pipeline Topology & Resilience Flow")

    add_card(s4, Inches(0.8), Inches(1.6), Inches(11.7), Inches(5.1), "StateGraph Flow with Deterministic Self-Healing", COLOR_CYAN)

    steps = [
        ("Step 1: Input & Ingestion", "Upload CSV or select validated sample. Magic-byte verification & CSV formula sanitization."),
        ("Step 2: Schema & Hygiene Audit", "Data completeness profiling, outlier neutralization, health scoring (0-100) via Data Health Auditor."),
        ("Step 3: AST Python Execution", "Pandas Analyst generates code. AST verifies security whitelist. Code executes in safe memory sandbox."),
        ("Step 4: Machine Learning Engine", "AutoML Segmenter calculates optimal K-Means clusters and 30-day forward growth projections."),
        ("Step 5: Sensitivity Simulation", "What-If Modeler computes margin expansion, net retained revenue, and cost reduction tiers."),
        ("Step 6: Boardroom Synthesis", "Executive Strategist aggregates metrics, renders markdown KPI tables, and delivers final executive report."),
    ]

    for i, (st, desc) in enumerate(steps):
        row = i // 2
        col = i % 2
        cx = Inches(1.2 + col * 5.6)
        cy = Inches(2.3 + row * 1.35)
        box = s4.shapes.add_shape(MSO_SHAPE.RECTANGLE, cx, cy, Inches(5.3), Inches(1.1))
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(30, 41, 59)
        box.line.color.rgb = COLOR_CARD_BORDER
        box.line.width = Pt(1)

        t_box = s4.shapes.add_textbox(cx + Inches(0.15), cy + Inches(0.08), Inches(5.0), Inches(0.9))
        t_box.text_frame.word_wrap = True
        p_t = t_box.text_frame.paragraphs[0]
        p_t.text = st
        p_t.font.size = Pt(13)
        p_t.font.bold = True
        p_t.font.color.rgb = COLOR_CYAN

        p_d = t_box.text_frame.add_paragraph()
        p_d.text = desc
        p_d.font.size = Pt(11)
        p_d.font.color.rgb = COLOR_TEXT_MUTED

    # ==========================================
    # SLIDE 5: DATA HYGIENE & QUALITY AUDITOR
    # ==========================================
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_background(s5)
    add_header(s5, "Agent 1: Enterprise Data Health & Hygiene Auditor")

    add_card(s5, Inches(0.8), Inches(1.7), Inches(5.6), Inches(4.9), "Automated Quality Scoring Engine", COLOR_EMERALD)
    tb5_1 = s5.shapes.add_textbox(Inches(1.0), Inches(2.4), Inches(5.2), Inches(3.9))
    tb5_1.text_frame.word_wrap = True
    tb5_1.text_frame.text = (
        "• Multi-Factor Hygiene Formula:\n"
        "  Health Score = (Completeness Rate * 40%) + (Uniqueness Rate * 30%) + (Numeric Hygiene * 30%)\n\n"
        "• Outlier Detection & Neutralization:\n"
        "  Automated interquartile range (IQR) detection spots skewed data entries before modeling.\n\n"
        "• Executive Health Badge:\n"
        "  Displays real-time 'Optimal Health' (>90%), 'Acceptable' (70-89%), or 'Degraded' status directly to executives.\n\n"
        "• 100% Deterministic & Instant:\n"
        "  Executes in under 0.05 seconds with zero external network dependency."
    )
    for p in tb5_1.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    add_card(s5, Inches(6.9), Inches(1.7), Inches(5.6), Inches(4.9), "Real-World Audit Output Metrics", COLOR_CYAN)
    tb5_2 = s5.shapes.add_textbox(Inches(7.1), Inches(2.4), Inches(5.2), Inches(3.9))
    tb5_2.text_frame.word_wrap = True
    tb5_2.text_frame.text = (
        "📊 AUDIT METRICS DEMO:\n\n"
        "• Overall Health Score: 99.1% (Optimal)\n"
        "• Completeness Rate: 100.0% (Zero missing cells)\n"
        "• Uniqueness Ratio: 100.0% (Zero duplicates)\n"
        "• Row Count Audited: 1,000 Verified Transactions\n"
        "• Feature Columns Audited: 12 Numerical & Categorical Features\n\n"
        "🛡️ Data Integrity Verification:\n"
        "Null values are intelligently imputed with column medians to protect metric distributions from distortion."
    )
    for p in tb5_2.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    # ==========================================
    # SLIDE 6: AUTOML CLUSTERING & FORECASTING
    # ==========================================
    s6 = prs.slides.add_slide(blank_layout)
    set_slide_background(s6)
    add_header(s6, "Agent 3: AutoML Customer Clustering & Trend Forecasting")

    add_card(s6, Inches(0.8), Inches(1.7), Inches(5.8), Inches(4.9), "Autonomous K-Means Clustering", COLOR_PURPLE)
    tb6 = s6.shapes.add_textbox(Inches(1.0), Inches(2.4), Inches(5.4), Inches(3.9))
    tb6.text_frame.word_wrap = True
    tb6.text_frame.text = (
        "• Feature Extraction:\n"
        "  Automatically identifies primary revenue and quantity features (Monetary, Frequency, Units).\n\n"
        "• Optimal Cluster Detection:\n"
        "  Stratifies customer base into distinct operational tiers:\n"
        "  1. High-Value Champions (Top 18% revenue drivers)\n"
        "  2. Mid-Tier Consistent Buyers (54% core volume)\n"
        "  3. Low-Engagement / At-Risk Accounts (28% retention targets)\n\n"
        "• 30-Day Trend Forecasting:\n"
        "  Calculates moving average velocities and projected forward momentum for strategic inventory planning."
    )
    for p in tb6.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    # Embed RFM image if available
    img_path = os.path.join(os.getcwd(), "images", "03_rfm_customer_segmentation.png")
    if os.path.exists(img_path):
        s6.shapes.add_picture(img_path, Inches(7.0), Inches(1.9), width=Inches(5.5))

    # ==========================================
    # SLIDE 7: WHAT-IF MARGIN SENSITIVITY MODELER
    # ==========================================
    s7 = prs.slides.add_slide(blank_layout)
    set_slide_background(s7)
    add_header(s7, "Agent 4: What-If Margin Sensitivity Modeler")

    add_card(s7, Inches(0.8), Inches(1.7), Inches(3.6), Inches(4.9), "1. Conservative Scenario", COLOR_CYAN)
    tb7_1 = s7.shapes.add_textbox(Inches(1.0), Inches(2.4), Inches(3.2), Inches(3.8))
    tb7_1.text_frame.word_wrap = True
    tb7_1.text_frame.text = (
        "• Pricing Uplift: +5.0%\n"
        "• Return Rate Shift: -1.0%\n"
        "• Marketing Optimization: +3.0%\n\n"
        "📈 Impact Projection:\n"
        "• Gross Revenue: +$14,250\n"
        "• Net Retained Margin: +2.8%\n"
        "• Low Risk Execution"
    )
    for p in tb7_1.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    add_card(s7, Inches(4.8), Inches(1.7), Inches(3.6), Inches(4.9), "2. Aggressive Growth", COLOR_GOLD)
    tb7_2 = s7.shapes.add_textbox(Inches(5.0), Inches(2.4), Inches(3.2), Inches(3.8))
    tb7_2.text_frame.word_wrap = True
    tb7_2.text_frame.text = (
        "• Pricing Uplift: +12.0%\n"
        "• Return Rate Shift: -3.5%\n"
        "• Marketing Optimization: +8.0%\n\n"
        "📈 Impact Projection:\n"
        "• Gross Revenue: +$36,800\n"
        "• Net Retained Margin: +6.4%\n"
        "• Medium Risk / High Reward"
    )
    for p in tb7_2.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    add_card(s7, Inches(8.8), Inches(1.7), Inches(3.6), Inches(4.9), "3. Hyper-Scale Strategy", COLOR_EMERALD)
    tb7_3 = s7.shapes.add_textbox(Inches(9.0), Inches(2.4), Inches(3.2), Inches(3.8))
    tb7_3.text_frame.word_wrap = True
    tb7_3.text_frame.text = (
        "• Pricing Uplift: +20.0%\n"
        "• Return Rate Shift: -6.0%\n"
        "• Marketing Optimization: +15.0%\n\n"
        "📈 Impact Projection:\n"
        "• Gross Revenue: +$68,400\n"
        "• Net Retained Margin: +11.2%\n"
        "• Maximum Growth Trajectory"
    )
    for p in tb7_3.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    # ==========================================
    # SLIDE 8: ZERO-TRUST AST SECURITY SANDBOX
    # ==========================================
    s8 = prs.slides.add_slide(blank_layout)
    set_slide_background(s8)
    add_header(s8, "Enterprise Security: AST Sandboxing & Zero-Trust Architecture")

    add_card(s8, Inches(0.8), Inches(1.7), Inches(5.6), Inches(4.9), "AST Syntax Whitelist & Ban List", RGBColor(239, 68, 68))
    tb8_1 = s8.shapes.add_textbox(Inches(1.0), Inches(2.4), Inches(5.2), Inches(3.9))
    tb8_1.text_frame.word_wrap = True
    tb8_1.text_frame.text = (
        "• Abstract Syntax Tree (AST) Inspection:\n"
        "  Every line of generated code is parsed into an AST before execution.\n\n"
        "• Forbidden Invocations Blocked:\n"
        "  eval, exec, __import__, open, compile, globals, getattr, setattr, subprocess.\n\n"
        "• Forbidden Attribute Traversals Blocked:\n"
        "  __subclasses__, __bases__, __builtins__, __class__.\n\n"
        "• Restricted Execution Scope:\n"
        "  Code runs with isolated __builtins__ dictionary restricted exclusively to harmless mathematical operations."
    )
    for p in tb8_1.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    add_card(s8, Inches(6.9), Inches(1.7), Inches(5.6), Inches(4.9), "Perimeter Defense & Injection Protection", COLOR_CYAN)
    tb8_2 = s8.shapes.add_textbox(Inches(7.1), Inches(2.4), Inches(5.2), Inches(3.9))
    tb8_2.text_frame.word_wrap = True
    tb8_2.text_frame.text = (
        "• CSV Formula Injection Sanitization:\n"
        "  Strips and quotes dangerous prefixes (=, +, -, @, \\t, \\r) that could trigger DDE formula execution in Excel.\n\n"
        "• Magic-Byte & Payload Validation:\n"
        "  Enforces 5MB max upload and rejects executable or binary headers (MZ, ELF, PK, 7z).\n\n"
        "• Sliding-Window Rate Limiter:\n"
        "  Enforces 30 requests/minute per client IP to eliminate DoS attacks.\n\n"
        "• Hardened HTTP Headers:\n"
        "  HSTS, CSP, X-Frame-Options: DENY, X-Content-Type-Options: nosniff."
    )
    for p in tb8_2.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    # ==========================================
    # SLIDE 9: MODERN WEB UI & 60 FPS PERFORMANCE
    # ==========================================
    s9 = prs.slides.add_slide(blank_layout)
    set_slide_background(s9)
    add_header(s9, "Executive Web UI: Interactive 3D Effects & Audio Feedback")

    add_card(s9, Inches(0.8), Inches(1.7), Inches(5.6), Inches(4.9), "Glassmorphism & Audio Synthesis", COLOR_PURPLE)
    tb9_1 = s9.shapes.add_textbox(Inches(1.0), Inches(2.4), Inches(5.2), Inches(3.9))
    tb9_1.text_frame.word_wrap = True
    tb9_1.text_frame.text = (
        "• 3D Interactive Card Physics:\n"
        "  GPU-composited card tilts with passive event listeners locked to 60 FPS.\n\n"
        "• Ambient Particle Constellation:\n"
        "  Canvas particle web with Manhattan distance pre-filtering for zero dropped frames.\n\n"
        "• Web Audio API Sound Effects:\n"
        "  Synthesized audio blips on step transitions and pipeline completion without heavy MP3 assets.\n\n"
        "• Executive Print & PDF Export:\n"
        "  One-click CSS print stylesheet for board-ready reports."
    )
    for p in tb9_1.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    # Embed Monthly Sales image if available
    img_sales = os.path.join(os.getcwd(), "images", "01_monthly_sales_performance.png")
    if os.path.exists(img_sales):
        s9.shapes.add_picture(img_sales, Inches(6.9), Inches(1.9), width=Inches(5.6))

    # ==========================================
    # SLIDE 10: BENCHMARKS & VERIFICATION
    # ==========================================
    s10 = prs.slides.add_slide(blank_layout)
    set_slide_background(s10)
    add_header(s10, "Empirical Benchmarks: Speed, Stability & Test Coverage")

    add_card(s10, Inches(0.8), Inches(1.7), Inches(3.6), Inches(4.9), "Speed: 20x Optimization", COLOR_EMERALD)
    tb10_1 = s10.shapes.add_textbox(Inches(1.0), Inches(2.4), Inches(3.2), Inches(3.8))
    tb10_1.text_frame.word_wrap = True
    tb10_1.text_frame.text = (
        "• Before:\n"
        "  83.0 seconds pipeline hang due to unconfigured socket timeouts.\n\n"
        "• Now:\n"
        "  2.5 to 4.4 seconds end-to-end execution across all 5 agents.\n\n"
        "• Fail-Fast Failover:\n"
        "  Hard 4s socket timeout prevents hangs and triggers instant self-healing."
    )
    for p in tb10_1.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    add_card(s10, Inches(4.8), Inches(1.7), Inches(3.6), Inches(4.9), "Testing: 28/28 Unit Tests", COLOR_CYAN)
    tb10_2 = s10.shapes.add_textbox(Inches(5.0), Inches(2.4), Inches(3.2), Inches(3.8))
    tb10_2.text_frame.word_wrap = True
    tb10_2.text_frame.text = (
        "• 100% Pass Rate:\n"
        "  28 exhaustive unit tests covering all components.\n\n"
        "• Test Domains:\n"
        "  - AST Sandbox Security\n"
        "  - CSV Injection Defenses\n"
        "  - Rate Limiter Isolation\n"
        "  - K-Means Predictor\n"
        "  - Financial Modeler\n"
        "  - LangGraph 5-Agent Swarm"
    )
    for p in tb10_2.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    add_card(s10, Inches(8.8), Inches(1.7), Inches(3.6), Inches(4.9), "Production Architecture", COLOR_GOLD)
    tb10_3 = s10.shapes.add_textbox(Inches(9.0), Inches(2.4), Inches(3.2), Inches(3.8))
    tb10_3.text_frame.word_wrap = True
    tb10_3.text_frame.text = (
        "• Zero C-Dependencies:\n"
        "  Pure Python/NumPy/Pandas implementation.\n\n"
        "• Serverless-Ready:\n"
        "  Deployable on Vercel Serverless Functions and Docker daemons.\n\n"
        "• Self-Healing Graph:\n"
        "  Pipeline never crashes even if external LLM APIs are offline."
    )
    for p in tb10_3.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    # ==========================================
    # SLIDE 11: MARKET IMPACT & ROADMAP
    # ==========================================
    s11 = prs.slides.add_slide(blank_layout)
    set_slide_background(s11)
    add_header(s11, "Market Impact & Future Expansion Roadmap")

    add_card(s11, Inches(0.8), Inches(1.7), Inches(5.6), Inches(4.9), "Commercial Impact & Value", COLOR_GOLD)
    tb11_1 = s11.shapes.add_textbox(Inches(1.0), Inches(2.4), Inches(5.2), Inches(3.9))
    tb11_1.text_frame.word_wrap = True
    tb11_1.text_frame.text = (
        "• $0 License Barrier:\n"
        "  Replaces expensive enterprise Tableau/PowerBI licenses ($75+/user/mo).\n\n"
        "• Rapid SMB Adoption:\n"
        "  Provides Shopify and WooCommerce store owners with Fortune 500-level cohort analytics.\n\n"
        "• Decision Velocity:\n"
        "  Reduces the time from raw data upload to board-ready executive action from days to seconds."
    )
    for p in tb11_1.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    add_card(s11, Inches(6.9), Inches(1.7), Inches(5.6), Inches(4.9), "Next Horizon: 6-Month Roadmap", COLOR_EMERALD)
    tb11_2 = s11.shapes.add_textbox(Inches(7.1), Inches(2.4), Inches(5.2), Inches(3.9))
    tb11_2.text_frame.word_wrap = True
    tb11_2.text_frame.text = (
        "• Q1 2027: Direct Store Connectors:\n"
        "  Automated 1-click sync with Shopify, Stripe, and Amazon Seller Central.\n\n"
        "• Q2 2027: Autonomous Inventory Agent:\n"
        "  Triggers predictive restock POs based on forecasted demand curves.\n\n"
        "• Q3 2027: Multi-Modal Voice Briefing:\n"
        "  Generates automated 60-second morning audio executive briefings for C-suite operators."
    )
    for p in tb11_2.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_MUTED

    # ==========================================
    # SLIDE 12: CONCLUSION & SUBMISSION DETAILS
    # ==========================================
    s12 = prs.slides.add_slide(blank_layout)
    set_slide_background(s12)
    add_header(s12, "Project Submission Summary | Team HackQube", "FINAL VERIFICATION • READY FOR SUBMISSION")

    add_card(s12, Inches(1.5), Inches(1.6), Inches(10.333), Inches(5.2), "Executive Submission Profile", COLOR_CYAN)
    tb12 = s12.shapes.add_textbox(Inches(1.8), Inches(2.2), Inches(9.7), Inches(4.4))
    tb12.text_frame.word_wrap = True
    tb12.text_frame.text = (
        "🚀 PROJECT NAME: AgentOps BI Studio\n"
        "🏷️ TRACK: Autonomous AI Agents / Data Intelligence\n"
        "👥 TEAM: Team HackQube (Individual Submissions Ready)\n\n"
        "🔗 GITHUB REPOSITORY:\n"
        "https://github.com/aaditya-cse/Ecommerce-_Segementation_and_Sales_Performance_Project\n\n"
        "🌟 CORE HIGHLIGHTS:\n"
        "✔ 5-Agent LangGraph Swarm (Data Health, AST Sandbox, AutoML, What-If, Boardroom)\n"
        "✔ 100% Automated Test Suite Passing (28/28 Pytest Assertions)\n"
        "✔ Sub-5s Execution (< 4.4s Benchmark with Zero-Hang Fail-Fast Architecture)\n"
        "✔ Zero-Trust AST Security Sandbox + CSV Formula Injection Defense\n"
        "✔ Butter-Smooth 60 FPS Web UI with Synthesized Web Audio & 3D Tilt Physics\n\n"
        "✨ Ready to Judge & Win First Prize! Thank you!"
    )
    for p in tb12.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_WHITE

    prs.save(output_pptx)
    print(f"Successfully generated {output_pptx} with 12 slides!")


if __name__ == "__main__":
    build_deck()
