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
    preferred = ["llama-3.1-8b-instant", "openai/gpt-oss-20b", "qwen/qwen3-32b"]
    try:
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            ids = [m["id"] for m in json.loads(resp.read().decode()).get("data", [])]
            for m in preferred:
                if m in ids:
                    return m
    except Exception:
        pass
    return "llama-3.1-8b-instant"


def _build_fallback_chart(df: pd.DataFrame, out_path: str) -> bool:
    """Guarantees a clean multi-bar visual chart if LLM code omitted plt.savefig."""
    try:
        num_cols = [c for c in df.select_dtypes(include=[np.number]).columns if "id" not in c.lower()]
        cat_cols = [c for c in df.select_dtypes(exclude=[np.number]).columns if "id" not in c.lower() and "date" not in c.lower()]
        if not num_cols:
            return False
        plt.figure(figsize=(8, 4.4))
        if cat_cols:
            cat, val = cat_cols[0], num_cols[0]
            grouped = df.groupby(cat)[val].sum().sort_values(ascending=False).head(6)
            if len(grouped) >= 2:
                sns.barplot(x=grouped.index.astype(str), y=grouped.values, hue=grouped.index.astype(str), palette="viridis", legend=False)
                plt.title(f"Total {val} by {cat}", fontsize=12, fontweight="bold")
                plt.xlabel(cat)
                plt.ylabel(val)
                plt.xticks(rotation=20, ha="right")
            else:
                sns.histplot(df[val].dropna(), kde=True, color="#0ea5e9")
                plt.title(f"Distribution of {val}", fontsize=12, fontweight="bold")
        else:
            val = num_cols[0]
            sns.histplot(df[val].dropna(), kde=True, color="#0ea5e9")
            plt.title(f"Distribution of {val}", fontsize=12, fontweight="bold")
        sns.despine()
        plt.margins(y=0.15)
        plt.tight_layout()
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close("all")
        return os.path.exists(out_path)
    except Exception:
        plt.close("all")
        return False


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


def pandas_analyst_agent(state: UniversalAgentState) -> Dict[str, Any]:
    attempt = state.get("retry_count", 0) + 1
    llm = ChatGroq(model=get_active_groq_model(), temperature=0.1, max_tokens=950, timeout=20)

    work_dir = os.path.join(tempfile.gettempdir(), "generated_charts")
    os.makedirs(work_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    chart_candidates = [
        os.path.join(work_dir, f"chart_{timestamp}_1.png"),
        os.path.join(work_dir, f"chart_{timestamp}_2.png"),
        os.path.join(work_dir, f"chart_{timestamp}_3.png"),
    ]
    cleaned_csv_file = os.path.join(work_dir, f"cleaned_{timestamp}.csv")
    history_context = "\n".join(state.get("chat_history", [])[-3:]) or "None (First question)"

    system_prompt = (
        "You are an expert Python Data Analyst using Pandas 3.0+. Write concise, executable Python code using "
        "pandas, numpy, matplotlib.pyplot (as plt), and seaborn (as sns) to clean the dataset and answer the user's goal.\n"
        "STRICT RULES:\n"
        "1. Load CSV into `df` from `CSV_PATH` (already defined). NEVER import os, sys, or pathlib.\n"
        "2. NEVER use `inplace=True`. Use `df = df.drop_duplicates().copy()`, fill nulls safely, strip/title text columns, "
        "and fix invalid values (e.g., Quantity <= 0, Age > 100, Discount_Pct > 100).\n"
        "3. Save cleaned `df` via `df.to_csv(CLEANED_CSV_PATH, index=False)`.\n"
        "4. If `Order_Status` exists, exclude 'Returned' and 'Cancelled' orders for Net Revenue/AOV.\n"
        "5. Print concise labeled KPIs and summary tables using `print()`.\n"
        "6. MANDATORY CHARTS:\n"
        "   - Always save at least 1 chart to `CHART_PATHS[0]` (and `CHART_PATHS[1]`, `CHART_PATHS[2]` up to 3 max if multi-chart breakdown is requested).\n"
        "   - NEVER draw a 1-bar chart; compare 2 to 6 categories/items per chart.\n"
        "   - For each chart: `plt.figure(figsize=(8, 4.4))`, add title/labels, `plt.margins(y=0.15)`, `plt.tight_layout()`, "
        "`plt.savefig(CHART_PATHS[i], dpi=150, bbox_inches='tight')`, and `plt.close()`.\n"
        "7. Output ONLY raw Python code without markdown fences or explanations."
    )

    prompt = (
        f"USER GOAL: {state['user_goal']}\n\n"
        f"HISTORY:\n{history_context}\n\n"
        f"DATASET PROFILE:\n{state['dataset_profile']}"
    )
    if state.get("error_log"):
        prompt += f"\n\nPREVIOUS ERROR:\n{state['error_log']}\nOutput fixed Python code only."

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

        plt.close("all")
        cleaned_df = exec_globals.get("df")
        if not isinstance(cleaned_df, pd.DataFrame) or cleaned_df.empty:
            cleaned_df = pd.read_csv(state["csv_path"]).drop_duplicates()

        if not os.path.exists(cleaned_csv_file):
            cleaned_df.to_csv(cleaned_csv_file, index=False)

        saved_charts = [p for p in chart_candidates if os.path.exists(p)]
        if not saved_charts:
            if _build_fallback_chart(cleaned_df, chart_candidates[0]):
                saved_charts = [chart_candidates[0]]

        output_text = stdout_buffer.getvalue().strip() or "Dataset cleaned and analyzed successfully."
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
            "analysis_output": stdout_buffer.getvalue().strip() or f"Execution issue on attempt {attempt}: {e}",
            "error_log": str(e),
            "retry_count": attempt,
        }


def route_after_execution(state: UniversalAgentState) -> str:
    if state.get("error_log") and state.get("retry_count", 0) < 3:
        return "retry_analyst"
    return "strategist"


def executive_strategist_agent(state: UniversalAgentState) -> Dict[str, Any]:
    llm = ChatGroq(model=get_active_groq_model(), temperature=0.2, max_tokens=850, timeout=20)

    system_prompt = (
        "You are a Principal Data Consultant writing a concise business report in clean Markdown. "
        "NEVER output Python code. Based ONLY on the verified dataset profile and Python output, write:\n"
        "1. Data Cleaning & Quality Summary (Markdown table)\n"
        "2. Key Quantitative Findings (Markdown table citing exact numbers)\n"
        "3. Top 3 Actionable Business Recommendations\n"
        "RULES: Never nest Markdown tables inside cells; avoid `<br>` or `\\$`; use INR (₹) for Indian datasets."
    )

    verified_out = state.get("analysis_output") or "Analysis completed on cleaned dataset."
    user_msg = (
        f"USER GOAL: {state['user_goal']}\n\n"
        f"DATASET PROFILE:\n{state['dataset_profile']}\n\n"
        f"VERIFIED PYTHON EXECUTION OUTPUT:\n{verified_out}"
    )

    raw_report = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]).content
    report = clean_llm_text(raw_report) or f"### Verified Analysis Summary\n\n{verified_out}"
    updated_history = state.get("chat_history", []) + [
        f"Q: {state['user_goal']} | Summary: {report[:200]}..."
    ]
    return {"final_report": report, "chat_history": updated_history}


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