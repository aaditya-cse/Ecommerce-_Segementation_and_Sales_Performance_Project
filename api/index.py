import os
import sys
import base64
import tempfile
import traceback

# Vercel read-only filesystem fix for Matplotlib & Temp files (MUST be before importing matplotlib)
os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

from flask import Flask, request, render_template_string

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "multi_agent"))

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Universal Multi-Agent CSV Analyst</title>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #f8fafc; max-width: 900px; margin: 40px auto; padding: 0 20px; }
        .card { background: #1e293b; padding: 24px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 24px; }
        h1 { color: #38bdf8; margin-top: 0; }
        label { display: block; margin: 12px 0 6px; font-weight: 600; color: #cbd5e1; }
        select, input[type="file"], textarea { width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: #f8fafc; box-sizing: border-box; }
        button { margin-top: 16px; background: #0284c7; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; }
        button:hover { background: #0369a1; }
        pre { white-space: pre-wrap; background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #334155; line-height: 1.6; font-family: inherit; }
        img { max-width: 100%; border-radius: 8px; margin-top: 16px; border: 1px solid #334155; }
        .error { color: #f87171; font-weight: 600; background: #450a0a; padding: 12px; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Universal Multi-Agent CSV Analyst</h1>
        <p>Powered by LangGraph (Schema Profiler &rarr; Self-Healing Pandas Analyst &rarr; Executive Strategist)</p>
        <form method="POST" enctype="multipart/form-data">
            <label>1. Choose Built-in Sample Dataset:</label>
            <select name="sample_csv">
                <option value="data/raw/ecommerce_sales_data.csv">E-Commerce Sales & Segmentation (371 rows)</option>
                <option value="data/raw/edtech_student_enrollments.csv">EdTech Student Enrollments (184 rows)</option>
                <option value="data/raw/food_delivery_operations.csv">Food Delivery Operations (250 rows)</option>
            </select>

            <label>OR Upload Your Own CSV File (Optional):</label>
            <input type="file" name="uploaded_csv" accept=".csv">

            <label>2. Ask Any Business / Data Analysis Question:</label>
            <textarea name="user_goal" rows="3" placeholder="e.g., Clean duplicates and nulls, calculate net revenue by category, and plot a chart.">{{ goal }}</textarea>

            <button type="submit">Run Multi-Agent Pipeline</button>
        </form>
    </div>

    {% if error %}
    <div class="card"><pre class="error">{{ error }}</pre></div>
    {% endif %}

    {% if report %}
    <div class="card">
        <h2>Executive Report</h2>
        <pre>{{ report }}</pre>
        {% if chart_b64 %}
        <h2>Generated Visualization</h2>
        <img src="data:image/png;base64,{{ chart_b64 }}" alt="Generated Chart">
        {% endif %}
    </div>
    {% endif %}
</body>
</html>
"""

@app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
@app.route("/<path:path>", methods=["GET", "POST"])
def home(path):
    report = ""
    chart_b64 = ""
    error = ""
    goal = "Clean duplicates and missing values, summarize top KPIs, and plot the primary revenue driver."

    if request.method == "POST":
        goal = request.form.get("user_goal", "").strip() or goal
        uploaded = request.files.get("uploaded_csv")

        try:
            if not os.getenv("GROQ_API_KEY"):
                raise ValueError("GROQ_API_KEY is missing! Add it in Vercel Project Settings -> Environment Variables and Redeploy.")

            from universal_analyst_agent import build_universal_graph
            agent_graph = build_universal_graph()

            if uploaded and uploaded.filename:
                tmp_csv = os.path.join(tempfile.gettempdir(), uploaded.filename)
                uploaded.save(tmp_csv)
                csv_path = tmp_csv
            else:
                rel_path = request.form.get("sample_csv", "data/raw/ecommerce_sales_data.csv")
                csv_path = os.path.join(ROOT_DIR, rel_path)
                if not os.path.exists(csv_path):
                    raise FileNotFoundError(f"Sample dataset not found at {csv_path}. Try uploading a CSV file directly.")

            result = agent_graph.invoke({
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
        except Exception:
            error = traceback.format_exc()

    return render_template_string(HTML_TEMPLATE, report=report, chart_b64=chart_b64, error=error, goal=goal)