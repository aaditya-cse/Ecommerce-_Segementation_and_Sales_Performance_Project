import os
import io
import re
import ast
import json
import warnings
import tempfile
import contextlib
import urllib.request
from datetime import datetime
from functools import lru_cache
from typing import TypedDict, Dict, Any, List

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

load_dotenv()

# ==========================================
# SECURITY: AST STATIC ANALYZER FOR SANDBOX
# ==========================================
FORBIDDEN_IMPORTS = {
    "os", "sys", "subprocess", "shutil", "socket",
    "requests", "urllib", "pathlib", "pickle", "pty", "ctypes"
}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "open", "__import__", "input", "breakpoint"}


class SecurityError(Exception):
    """Raised when LLM-generated code attempts an unsafe import or function call."""
    pass


def validate_generated_code(code_str: str) -> None:
    """Inspects AST of generated Python code before execution to block unsafe operations."""
    tree = ast.parse(code_str)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                if root_pkg in FORBIDDEN_IMPORTS:
                    raise SecurityError(f"Blocked unsafe import: {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            root_pkg = node.module.split(".")[0]
            if root_pkg in FORBIDDEN_IMPORTS:
                raise SecurityError(f"Blocked unsafe import from: {node.module}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                raise SecurityError(f"Blocked unsafe function call: {node.func.id}")


# ==========================================
# 1. SHARED GRAPH STATE
# ==========================================
class UniversalAgentState(TypedDict):
    csv_path: str
    user_goal: str
    dataset_profile: str
    chat_history: List[str]
    chart_path: str
    chart_paths: List[str]
    cleaned_csv_path: str
    generated_code: str
    analysis_output: str
    error_log: str
    retry_count: int
    final_report: str


def clean_llm_text(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


@lru_cache(maxsize=1)
def get_active_groq_model() -> str:
    api_key = os.getenv("GROQ_API_KEY")
    preferred = [
        "llama-3.1-8b-instant",
        "openai/gpt-oss-20b",
        "qwen/qwen3-32b",
    ]
    try:
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            ids = [m["id"] for m in json.loads(resp.read().decode()).get("data", [])]
            for m in preferred:
                if m in ids:
                    return m
    except Exception:
        pass
    return "llama-3.1-8b-instant"


# ==========================================
# 2. AGENT 1: DYNAMIC SCHEMA & QUALITY PROFILER
# ==========================================
def schema_profiler_agent(state: UniversalAgentState) -> Dict[str, Any]:
    if state.get("dataset_profile"):
        return {"retry_count": 0}

    df = pd.read_csv(state["csv_path"])
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()

    cat_samples = {
        col: df[col].dropna().astype(str).value_counts().head(5).to_dict()
        for col in cat_cols[:8]
    }

    profile = {
        "shape": {"rows": len(df), "columns": len(df.columns)},
        "columns_and_dtypes": df.dtypes.astype(str).to_dict(),
        "duplicate_rows": int(df.duplicated().sum()),
        "missing_values": df.isnull().sum()[df.isnull().sum() > 0].to_dict(),
        "numeric_summary": df[num_cols].describe().round(2).to_dict() if num_cols else {},
        "top_categorical_values": cat_samples,
        "sample_rows": df.head(3).to_dict(orient="records"),
    }

    return {"dataset_profile": json.dumps(profile, indent=2, default=str), "retry_count": 0}


# ==========================================
# 3. AGENT 2: AST-SANDBOXED CODE, CLEANER & CHART ANALYST
# ==========================================
def pandas_analyst_agent(state: UniversalAgentState) -> Dict[str, Any]:
    attempt = state.get("retry_count", 0) + 1
    llm = ChatGroq(model=get_active_groq_model(), temperature=0.1, max_tokens=1600)

    work_dir = os.path.join(tempfile.gettempdir(), "generated_charts")
    os.makedirs(work_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    chart_candidates = [
        os.path.join(work_dir, f"chart_{timestamp}_1.png"),
        os.path.join(work_dir, f"chart_{timestamp}_2.png"),
        os.path.join(work_dir, f"chart_{timestamp}_3.png"),
    ]
    cleaned_csv_file = os.path.join(work_dir, f"cleaned_{timestamp}.csv")

    history_context = "\n".join(state.get("chat_history", [])[-4:]) or "None (First question)"

    system_prompt = (
        "You are an expert Python Data Analyst using Pandas 3.0+. Write executable Python code using "
        "pandas, numpy, matplotlib.pyplot (as plt), and seaborn (as sns) to clean the dataset and "
        "answer the user's goal.\n"
        "STRICT RULES:\n"
        "1. Load the CSV into `df` from `CSV_PATH` (already defined in scope). Do NOT import os, sys, or pathlib.\n"
        "2. NEVER use `inplace=True`. Always use direct assignment like `df[col] = df[col].fillna(...)`, "
        "drop duplicates (`df = df.drop_duplicates().copy()`), normalize text columns with `.str.strip().str.title()`, "
        "and fix outliers (e.g., Quantity <= 0, Age > 100, Discount_Pct > 100).\n"
        "3. Save the cleaned DataFrame `df` to `CLEANED_CSV_PATH` using `df.to_csv(CLEANED_CSV_PATH, index=False)`.\n"
        "4. If an `Order_Status` column exists, exclude 'Returned' and 'Cancelled' orders when computing Net Revenue or AOV.\n"
        "5. Print clear, labeled summary tables and exact KPIs using `print()`.\n"
        "6. VISUALIZATIONS TAILORED TO USER GOAL & DATA:\n"
        "   - Choose chart types matching the user's prompt and data columns (bar/horizontal bar for category comparisons, "
        "line chart for time/date trends, scatter/heatmap for correlations, box/hist for distributions).\n"
        "   - Generate 1 focused chart for a single-question prompt, OR 2 to 3 distinct charts (maximum 3) when the user asks "
        "for multiple charts, multi-dimensional comparisons, or a full breakdown.\n"
        "   - Save chart 1 to `CHART_PATHS[0]` (or `CHART_PATH`), chart 2 (if needed) to `CHART_PATHS[1]`, and chart 3 (if needed) to `CHART_PATHS[2]`. "
        "For EACH chart: create a fresh `plt.figure(figsize=(8, 4.8))`, add clear title and axis labels, call `plt.tight_layout()`, "
        "save with `dpi=150`, and call `plt.close()`. NEVER call `plt.show()`.\n"
        "7. Return ONLY raw Python code—no markdown backticks (```) and no explanations."
    )

    prompt = (
        f"USER GOAL: {state['user_goal']}\n\n"
        f"PREVIOUS CONVERSATION CONTEXT:\n{history_context}\n\n"
        f"DATASET PROFILE:\n{state['dataset_profile']}"
    )
    if state.get("error_log"):
        prompt += f"\n\nPREVIOUS CODE FAILED WITH ERROR:\n{state['error_log']}\nFix the bug and output corrected Python code only."

    raw_reply = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=prompt)]).content
    clean_code = clean_llm_text(raw_reply).replace("```python", "").replace("```", "").strip()

    stdout_buffer = io.StringIO()
    exec_globals = {
        "pd": pd,
        "np": np,
        "plt": plt,
        "sns": sns,
        "CSV_PATH": state["csv_path"],
        "CHART_PATH": chart_candidates[0],
        "CHART_PATHS": chart_candidates,
        "CLEANED_CSV_PATH": cleaned_csv_file,
    }

    try:
        validate_generated_code(clean_code)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with contextlib.redirect_stdout(stdout_buffer):
                exec(clean_code, {"__builtins__": __builtins__, **exec_globals})

        if not os.path.exists(cleaned_csv_file):
            cleaned_df = exec_globals.get("df")
            if isinstance(cleaned_df, pd.DataFrame) and not cleaned_df.empty:
                cleaned_df.to_csv(cleaned_csv_file, index=False)

        output_text = stdout_buffer.getvalue() or "Code executed successfully."
        saved_charts = [p for p in chart_candidates if os.path.exists(p)]
        saved_csv = cleaned_csv_file if os.path.exists(cleaned_csv_file) else ""
        return {
            "generated_code": clean_code,
            "analysis_output": output_text,
            "chart_path": saved_charts[0] if saved_charts else "",
            "chart_paths": saved_charts,
            "cleaned_csv_path": saved_csv,
            "error_log": "",
            "retry_count": attempt,
        }
    except Exception as e:
        plt.close("all")
        return {
            "generated_code": clean_code,
            "error_log": str(e),
            "retry_count": attempt,
        }


def route_after_execution(state: UniversalAgentState) -> str:
    if state.get("error_log") and state.get("retry_count", 0) < 3:
        return "retry_analyst"
    return "strategist"


# ==========================================
# 4. AGENT 3: EXECUTIVE STRATEGIST
# ==========================================
def executive_strategist_agent(state: UniversalAgentState) -> Dict[str, Any]:
    llm = ChatGroq(model=get_active_groq_model(), temperature=0.2, max_tokens=1400)

    system_prompt = (
        "You are a Principal Data Consultant writing a business report in clean Markdown. "
        "NEVER output Python code. Based ONLY on the verified dataset profile and Python execution output "
        "provided, write a crisp executive summary with:\n"
        "1. Data Cleaning & Quality Summary (as a Markdown table)\n"
        "2. Key Quantitative Findings (as a Markdown table citing exact numbers)\n"
        "3. Top 3-4 Actionable Business Recommendations\n"
        "STRICT FORMATTING RULES:\n"
        "- NEVER put a Markdown table inside another table cell.\n"
        "- NEVER use `<br>` HTML tags or escaped `\\$` backslashes; separate multiple items in a cell with semicolons (;).\n"
        "- Use INR (₹) for Indian datasets (like prices 699, 1899) unless another currency is explicitly specified."
    )

    user_msg = (
        f"USER GOAL: {state['user_goal']}\n\n"
        f"DATASET PROFILE:\n{state['dataset_profile']}\n\n"
        f"VERIFIED PYTHON EXECUTION OUTPUT:\n{state['analysis_output']}"
    )

    raw_report = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]).content
    report = clean_llm_text(raw_report)
    updated_history = state.get("chat_history", []) + [
        f"Q: {state['user_goal']} | Summary: {report[:250]}..."
    ]
    return {"final_report": report, "chat_history": updated_history}


# ==========================================
# 5. BUILD LANGGRAPH WITH RETRY LOOP
# ==========================================
def build_universal_graph():
    graph = StateGraph(UniversalAgentState)
    graph.add_node("profiler", schema_profiler_agent)
    graph.add_node("analyst", pandas_analyst_agent)
    graph.add_node("strategist", executive_strategist_agent)

    graph.set_entry_point("profiler")
    graph.add_edge("profiler", "analyst")
    graph.add_conditional_edges(
        "analyst",
        route_after_execution,
        {"retry_analyst": "analyst", "strategist": "strategist"},
    )
    graph.add_edge("strategist", END)
    return graph.compile()


if __name__ == "__main__":
    app = build_universal_graph()
    print("UNIVERSAL MULTI-AGENT CSV ANALYST READY")