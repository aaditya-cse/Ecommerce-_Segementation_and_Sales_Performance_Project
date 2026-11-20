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

_cur_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_cur_dir)
load_dotenv(os.path.join(_root_dir, ".env"))
load_dotenv(os.path.join(_cur_dir, ".env"))

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
    api_key = os.getenv("GROQ_API_KEY", "")
    preferred = [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-20b",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "qwen/qwen3-32b",
    ]
    blocked_keywords = ("whisper", "guard", "tts", "orpheus", "safeguard", "prompt-guard")
    try:
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode()).get("data", [])
            ids = [
                m["id"] for m in data
                if m.get("id") and not any(b in m["id"].lower() for b in blocked_keywords)
            ]
            for m in preferred:
                if m in ids:
                    return m
            if ids:
                return ids[0]
    except Exception:
        pass
    return "llama-3.1-8b-instant"


def _ensure_multi_charts(df: pd.DataFrame, chart_candidates: list, existing: list) -> list:
    """Ensures up to 3 diverse charts (Bar, Line/Horizontal Bar, Distribution/Donut) across different parameters."""
    saved = list(existing)
    if len(saved) >= 3 or df is None or df.empty:
        return saved

    num_cols = [
        c for c in df.select_dtypes(include=[np.number]).columns
        if not any(k in c.lower() for k in ("id", "zip", "pin", "code", "year"))
    ]
    cat_cols = [
        c for c in df.select_dtypes(exclude=[np.number]).columns
        if not any(k in c.lower() for k in ("id", "date", "time", "name", "email", "phone"))
        and 2 <= df[c].nunique(dropna=True) <= 15
    ]
    date_cols = [
        c for c in df.columns
        if any(k in c.lower() for k in ("date", "time", "month", "day"))
    ]

    if not num_cols:
        return saved

    primary_num = next((c for c in num_cols if any(k in c.lower() for k in ("rev", "sales", "amount", "total", "price", "fee", "profit"))), num_cols[0])
    secondary_num = next((c for c in num_cols if c != primary_num), primary_num)

    # Chart 1: Vertical Bar Chart on Primary Category vs Primary Metric
    if len(saved) < 1 and len(chart_candidates) >= 1 and cat_cols:
        try:
            c1 = cat_cols[0]
            grp = df.groupby(c1)[primary_num].sum().sort_values(ascending=False).head(6)
            if len(grp) >= 2:
                plt.figure(figsize=(8, 4.4))
                sns.barplot(x=grp.index.astype(str), y=grp.values, hue=grp.index.astype(str), palette="viridis", legend=False)
                plt.title(f"Total {primary_num} by {c1} (Bar Analysis)", fontsize=12, fontweight="bold")
                plt.xlabel(c1)
                plt.ylabel(primary_num)
                plt.xticks(rotation=20, ha="right")
                sns.despine()
                plt.tight_layout()
                plt.savefig(chart_candidates[0], dpi=150, bbox_inches="tight")
                plt.close("all")
                if os.path.exists(chart_candidates[0]):
                    saved.append(chart_candidates[0])
        except Exception:
            plt.close("all")

    # Chart 2: Time-Series Line Chart (if date column exists) OR Horizontal Bar on 2nd Parameter
    if len(saved) < 2 and len(chart_candidates) >= 2:
        try:
            drawn = False
            if date_cols:
                dcol = date_cols[0]
                dt_series = pd.to_datetime(df[dcol], errors="coerce")
                if dt_series.notna().sum() >= 5:
                    temp = df.assign(_dt=dt_series).dropna(subset=["_dt"])
                    trend = temp.groupby(temp["_dt"].dt.to_period("M"))[primary_num].sum()
                    if len(trend) >= 2:
                        plt.figure(figsize=(8, 4.4))
                        plt.plot(trend.index.astype(str), trend.values, marker="o", linewidth=2.5, color="#38bdf8")
                        plt.fill_between(trend.index.astype(str), trend.values, alpha=0.15, color="#38bdf8")
                        plt.title(f"{primary_num} Trend Over Time (Line Chart)", fontsize=12, fontweight="bold")
                        plt.xlabel("Period")
                        plt.ylabel(primary_num)
                        plt.xticks(rotation=25, ha="right")
                        plt.grid(True, linestyle="--", alpha=0.3)
                        sns.despine()
                        plt.tight_layout()
                        plt.savefig(chart_candidates[1], dpi=150, bbox_inches="tight")
                        plt.close("all")
                        if os.path.exists(chart_candidates[1]):
                            saved.append(chart_candidates[1])
                            drawn = True
            if not drawn and len(cat_cols) >= 2:
                c2 = cat_cols[1]
                grp2 = df.groupby(c2)[primary_num].sum().sort_values(ascending=True).tail(6)
                if len(grp2) >= 2:
                    plt.figure(figsize=(8, 4.4))
                    plt.barh(grp2.index.astype(str), grp2.values, color="#10b981")
                    plt.title(f"{primary_num} Breakdown by {c2} (Horizontal Bar)", fontsize=12, fontweight="bold")
                    plt.xlabel(primary_num)
                    plt.ylabel(c2)
                    sns.despine()
                    plt.tight_layout()
                    plt.savefig(chart_candidates[1], dpi=150, bbox_inches="tight")
                    plt.close("all")
                    if os.path.exists(chart_candidates[1]):
                        saved.append(chart_candidates[1])
        except Exception:
            plt.close("all")

    # Chart 3: Distribution (Histogram + KDE) or Share Chart on Secondary Parameter
    if len(saved) < 3 and len(chart_candidates) >= 3:
        try:
            plt.figure(figsize=(8, 4.4))
            vals = pd.to_numeric(df[secondary_num], errors="coerce").dropna()
            if len(vals) >= 5 and vals.nunique() >= 4:
                sns.histplot(vals, kde=True, color="#a855f7", bins=15)
                plt.title(f"Distribution & Density of {secondary_num} (Histogram + KDE)", fontsize=12, fontweight="bold")
                plt.xlabel(secondary_num)
                plt.ylabel("Frequency")
                sns.despine()
            elif len(cat_cols) >= 1:
                c_share = cat_cols[-1]
                share = df[c_share].value_counts().head(5)
                plt.pie(share.values, labels=share.index.astype(str), autopct="%1.1f%%", startangle=140, wedgeprops={"width": 0.45})
                plt.title(f"Share Distribution by {c_share} (Donut Chart)", fontsize=12, fontweight="bold")
            plt.tight_layout()
            plt.savefig(chart_candidates[2], dpi=150, bbox_inches="tight")
            plt.close("all")
            if os.path.exists(chart_candidates[2]):
                saved.append(chart_candidates[2])
        except Exception:
            plt.close("all")

    return saved


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
    llm = ChatGroq(model=get_active_groq_model(), temperature=0.1)

    work_dir = os.path.join(tempfile.gettempdir(), "generated_charts")
    os.makedirs(work_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    chart_file = os.path.join(work_dir, f"chart_{timestamp}.png")
    cleaned_csv_file = os.path.join(work_dir, f"cleaned_{timestamp}.csv")

    history_context = "\n".join(state.get("chat_history", [])[-4:]) or "None (First question)"

    system_prompt = (
        "You are an expert Python Data Analyst using Pandas 3.0+. Write executable Python code using "
        "pandas, numpy, matplotlib.pyplot (as plt), and seaborn (as sns) to clean the dataset and "
        "answer the user's goal.\n"
        "STRICT RULES:\n"
        "1. Load the CSV into `df` from `CSV_PATH` (already defined in scope). Do NOT import os, sys, or pathlib.\n"
        "2. NEVER use `inplace=True`. Always use direct assignment like `df[col] = df[col].fillna(...)`, "
        "drop duplicates (`df = df.drop_duplicates().copy()`), normalize all text columns with `.str.strip().str.title()` so case variants like FASHION/fashion merge cleanly, and fix outliers (e.g., Quantity <= 0, Age > 100, Discount_Pct > 100).\n"
        "3. Save the cleaned DataFrame `df` to `CLEANED_CSV_PATH` (already defined in scope) using `df.to_csv(CLEANED_CSV_PATH, index=False)`.\n"
        "4. If an `Order_Status` column exists, exclude 'Returned' and 'Cancelled' orders when computing Net Revenue or AOV.\n"
        "5. Print clear, labeled summary tables and exact KPIs using `print()`.\n"
        "6. Create ONE clean matplotlib/seaborn figure, call `plt.tight_layout()`, save to `CHART_PATH` "
        "(already defined in scope) with `dpi=150`, and call `plt.close()`. NEVER call `plt.show()`.\n"
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
        "CHART_PATH": chart_file,
        "CLEANED_CSV_PATH": cleaned_csv_file,
    }

    try:
        validate_generated_code(clean_code)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with contextlib.redirect_stdout(stdout_buffer):
                exec(clean_code, {"__builtins__": __builtins__, **exec_globals})

        # Fallback: if LLM forgot to call df.to_csv(CLEANED_CSV_PATH), save the cleaned df automatically
        if not os.path.exists(cleaned_csv_file):
            cleaned_df = exec_globals.get("df")
            if isinstance(cleaned_df, pd.DataFrame) and not cleaned_df.empty:
                cleaned_df.to_csv(cleaned_csv_file, index=False)

        output_text = stdout_buffer.getvalue() or "Code executed successfully."
        saved_chart = chart_file if os.path.exists(chart_file) else ""
        saved_csv = cleaned_csv_file if os.path.exists(cleaned_csv_file) else ""
        return {
            "generated_code": clean_code,
            "analysis_output": output_text,
            "chart_path": saved_chart,
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
    llm = ChatGroq(model=get_active_groq_model(), temperature=0.2)

    system_prompt = (
        "You are a Principal Data Consultant writing a business report in clean Markdown. "
        "NEVER output Python code. Based ONLY on the verified dataset profile and Python execution output "
        "provided, write a crisp executive summary with:\n"
        "1. Data Cleaning & Quality Summary (as a Markdown table)\n"
        "2. Key Quantitative Findings (as a Markdown table citing exact numbers)\n"
        "3. Top 3-4 Actionable Business Recommendations\nSTRICT FORMATTING RULES:\n- NEVER put a Markdown table inside another table cell.\n- NEVER use `<br>` HTML tags or escaped `\\$` backslashes; format multi-item breakdowns as 'Name: ?Value; Name2: ?Value2' and match exact counts (never label 4 items as Top 5).\n- Use INR (₹) for Indian datasets (like prices 699, 1899) unless another currency is explicitly specified."
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


