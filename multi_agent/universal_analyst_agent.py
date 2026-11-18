import os
import io
import json
import contextlib
import urllib.request
from typing import TypedDict, Dict, Any
import pandas as pd
import numpy as np
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
    generated_code: str
    analysis_output: str
    error_log: str
    retry_count: int
    final_report: str


def get_active_groq_model() -> str:
    api_key = os.getenv("GROQ_API_KEY")
    preferred = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3-32b", "llama-3.1-8b-instant"]
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
    return "openai/gpt-oss-120b"


# ==========================================
# 2. AGENT 1: DYNAMIC SCHEMA & QUALITY PROFILER
# ==========================================
def schema_profiler_agent(state: UniversalAgentState) -> Dict[str, Any]:
    print(f"\n[Agent 1: Schema Profiler] Inspecting '{state['csv_path']}'...")
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
# 3. AGENT 2: AUTONOMOUS PANDAS CODE ANALYST
# ==========================================
def pandas_analyst_agent(state: UniversalAgentState) -> Dict[str, Any]:
    attempt = state.get("retry_count", 0) + 1
    print(f"[Agent 2: Pandas Analyst] Writing & executing analysis code (Attempt {attempt})...")

    llm = ChatGroq(model=get_active_groq_model(), temperature=0.1)

    system_prompt = (
        "You are an expert Python Data Analyst. Write executable Python code using pandas and numpy "
        "to clean the dataset (drop duplicates, handle nulls/outliers) and perform deep analysis "
        "aligned with the user's goal.\n"
        "RULES:\n"
        "1. Load the CSV from the variable `CSV_PATH` (already defined in scope).\n"
        "2. Print clear, labeled summary tables and exact KPIs using `print()`.\n"
        "3. Do NOT call `plt.show()` or open GUI windows.\n"
        "4. Return ONLY raw Python code—no markdown backticks (```) and no explanations."
    )

    prompt = f"USER GOAL: {state['user_goal']}\n\nDATASET PROFILE:\n{state['dataset_profile']}"
    if state.get("error_log"):
        prompt += f"\n\nPREVIOUS CODE FAILED WITH ERROR:\n{state['error_log']}\nFix the bug and output corrected Python code only."

    raw_code = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=prompt)]).content
    clean_code = raw_code.replace("```python", "").replace("```", "").strip()

    # Execute generated code and capture stdout
    stdout_buffer = io.StringIO()
    exec_globals = {"pd": pd, "np": np, "CSV_PATH": state["csv_path"]}
    try:
        with contextlib.redirect_stdout(stdout_buffer):
            exec(clean_code, exec_globals)
        output_text = stdout_buffer.getvalue()
        if not output_text.strip():
            output_text = "Code executed successfully, but nothing was printed."
        return {
            "generated_code": clean_code,
            "analysis_output": output_text,
            "error_log": "",
            "retry_count": attempt,
        }
    except Exception as e:
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
    print("[Agent 3: Executive Strategist] Generating final insights & action plan...")
    llm = ChatGroq(model=get_active_groq_model(), temperature=0.2)

    system_prompt = (
        "You are a Principal Data Consultant. Based ONLY on the verified dataset profile and "
        "Python execution output provided, write an executive report with:\n"
        "1. Data Quality & Cleaning Summary\n"
        "2. Key Quantitative Findings (cite exact numbers from the output)\n"
        "3. Top 4 Actionable Recommendations"
    )

    user_msg = (
        f"USER GOAL: {state['user_goal']}\n\n"
        f"DATASET PROFILE:\n{state['dataset_profile']}\n\n"
        f"VERIFIED PYTHON ANALYSIS OUTPUT:\n{state['analysis_output']}"
    )

    report = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]).content
    return {"final_report": report}


# ==========================================
# 5. BUILD LANGGRAPH WITH CONDITIONAL RETRY LOOP
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


if __name__ == "__main__":
    app = build_universal_graph()

    # Pass ANY CSV path and ANY business question here!
    result = app.invoke({
        "csv_path": "../data/raw/ecommerce_sales_data.csv",
        "user_goal": "Clean the data, find top revenue drivers, segment customers, and identify churn risks.",
        "dataset_profile": "",
        "generated_code": "",
        "analysis_output": "",
        "error_log": "",
        "retry_count": 0,
        "final_report": "",
    })

    print("\n" + "=" * 65)
    print("UNIVERSAL MULTI-AGENT ANALYSIS REPORT")
    print("=" * 65)
    print(result["final_report"])