import os
import io
import re
import json
import warnings
import contextlib
import urllib.request
from datetime import datetime
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
# 1. SHARED GRAPH STATE
# ==========================================
class UniversalAgentState(TypedDict):
    csv_path: str
    user_goal: str
    dataset_profile: str
    chat_history: List[str]
    chart_path: str
    generated_code: str
    analysis_output: str
    error_log: str
    retry_count: int
    final_report: str


def clean_llm_text(text: str) -> str:
    # Remove <think>...</think> blocks if a reasoning model is selected
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text


def get_active_groq_model() -> str:
    api_key = os.getenv("GROQ_API_KEY")
    preferred = [
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b",
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

    print(f"\n[Agent 1: Schema Profiler] Scanning '{state['csv_path']}'...")
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
# 3. AGENT 2: AUTONOMOUS CODE & CHART ANALYST
# ==========================================
def pandas_analyst_agent(state: UniversalAgentState) -> Dict[str, Any]:
    attempt = state.get("retry_count", 0) + 1
    print(f"[Agent 2: Pandas & Chart Analyst] Running analysis & generating chart (Attempt {attempt})...")

    llm = ChatGroq(model=get_active_groq_model(), temperature=0.1)

    charts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_charts")
    os.makedirs(charts_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chart_file = os.path.join(charts_dir, f"chart_{timestamp}.png")

    history_context = "\n".join(state.get("chat_history", [])[-4:]) or "None (First question)"

    system_prompt = (
        "You are an expert Python Data Analyst using Pandas 3.0+. Write executable Python code using "
        "pandas, numpy, matplotlib.pyplot (as plt), and seaborn (as sns) to clean the dataset and "
        "answer the user's goal.\n"
        "STRICT RULES:\n"
        "1. Load the CSV from `CSV_PATH` (already defined in scope).\n"
        "2. NEVER use `inplace=True`. Always use direct assignment like `df[col] = df[col].fillna(...)`, "
        "drop duplicates (`df = df.drop_duplicates().copy()`), strip whitespace on text columns, and fix outliers.\n"
        "3. If an `Order_Status` column exists, exclude 'Returned' and 'Cancelled' orders when computing Net Revenue or AOV.\n"
        "4. Print clear, labeled summary tables and exact KPIs using `print()`.\n"
        "5. Create ONE clean matplotlib/seaborn figure, call `plt.tight_layout()`, save to `CHART_PATH` "
        "(already defined in scope) with `dpi=150`, and call `plt.close()`. NEVER call `plt.show()`.\n"
        "6. Return ONLY raw Python code—no markdown backticks (```) and no explanations."
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
    }

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with contextlib.redirect_stdout(stdout_buffer):
                exec(clean_code, exec_globals)
        output_text = stdout_buffer.getvalue()
        if not output_text.strip():
            output_text = "Code executed successfully, but nothing was printed."
        saved_chart = chart_file if os.path.exists(chart_file) else ""
        return {
            "generated_code": clean_code,
            "analysis_output": output_text,
            "chart_path": saved_chart,
            "error_log": "",
            "retry_count": attempt,
        }
    except Exception as e:
        plt.close("all")
        print(f"  -> Execution error caught: {e}")
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
    print("[Agent 3: Executive Strategist] Synthesizing insights & recommendations...")
    llm = ChatGroq(model=get_active_groq_model(), temperature=0.2)

    system_prompt = (
        "You are a Principal Data Consultant writing a business report in plain English and Markdown. "
        "NEVER output Python code. Based ONLY on the verified dataset profile and Python execution output "
        "provided, write a crisp executive summary with:\n"
        "1. Data Cleaning & Quality Summary\n"
        "2. Key Quantitative Findings (cite exact numbers from the execution output)\n"
        "3. Top 3-4 Actionable Business Recommendations"
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
        {
            "retry_analyst": "analyst",
            "strategist": "strategist",
        },
    )
    graph.add_edge("strategist", END)

    return graph.compile()


# ==========================================
# 6. INTERACTIVE MULTI-TURN CLI LOOP
# ==========================================
if __name__ == "__main__":
    app = build_universal_graph()

    print("=" * 65)
    print("UNIVERSAL MULTI-AGENT CSV ANALYST (Multi-Turn + Auto-Charts)")
    print("Commands: type 'new' to switch CSV | type 'exit' to quit")
    print("=" * 65)

    while True:
        csv_input = input("\nEnter CSV path (default: ../data/raw/edtech_student_enrollments.csv): ").strip()
        if csv_input.lower() == "exit":
            break
        if not csv_input:
            csv_input = "../data/raw/edtech_student_enrollments.csv"

        if not os.path.exists(csv_input):
            print(f"[Error] File not found: {csv_input}. Try again.")
            continue

        cached_profile = ""
        chat_history: List[str] = []

        while True:
            goal_input = input("\nAsk a question about this dataset (or 'new' / 'exit'): ").strip()
            if goal_input.lower() == "exit":
                exit(0)
            if goal_input.lower() == "new":
                break
            if not goal_input:
                goal_input = "Clean duplicates and nulls, summarize key KPIs, and plot the top revenue driver."

            result = app.invoke({
                "csv_path": csv_input,
                "user_goal": goal_input,
                "dataset_profile": cached_profile,
                "chat_history": chat_history,
                "chart_path": "",
                "generated_code": "",
                "analysis_output": "",
                "error_log": "",
                "retry_count": 0,
                "final_report": "",
            })

            cached_profile = result["dataset_profile"]
            chat_history = result["chat_history"]

            print("\n" + "=" * 65)
            print("EXECUTIVE REPORT")
            print("=" * 65)
            print(result["final_report"])
            if result.get("chart_path"):
                print(f"\n[Chart Saved]: {result['chart_path']}")
            print("=" * 65)