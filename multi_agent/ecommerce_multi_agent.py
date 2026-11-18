import os
from typing import TypedDict, Dict, Any, List
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

# Load API keys from .env
load_dotenv()

# ==========================================
# 1. SHARED GRAPH STATE (Agents ka Memory)
# ==========================================
class EcommerceAgentState(TypedDict):
    raw_csv_path: str
    clean_csv_path: str
    cleaning_report: Dict[str, Any]
    sales_kpis: Dict[str, Any]
    rfm_summary: Dict[str, Any]
    at_risk_vips: List[Dict[str, Any]]
    ops_audit: Dict[str, Any]
    final_executive_report: str


# ==========================================
# 2. AGENT 1: DATA ENGINEER AGENT
# ==========================================
def data_engineer_agent(state: EcommerceAgentState) -> Dict[str, Any]:
    print("\n[Agent 1: Data Engineer] Loading and cleaning raw e-commerce dataset...")
    df_raw = pd.read_csv(state["raw_csv_path"])
    raw_rows = len(df_raw)
    duplicates_count = int(df_raw.duplicated().sum())

    df = df_raw.drop_duplicates().reset_index(drop=True)

    # Standardize text columns
    df["Region"] = df["Region"].astype(str).str.strip().str.title()
    df["Category"] = df["Category"].astype(str).str.strip().str.title()

    # Fix impossible outliers
    df.loc[(df["Age"] < 15) | (df["Age"] > 100), "Age"] = np.nan
    df["Quantity"] = df["Quantity"].abs()
    df.loc[(df["Discount_Pct"] < 0) | (df["Discount_Pct"] > 100), "Discount_Pct"] = np.nan

    # Impute missing values
    df["Age"] = df["Age"].fillna(df["Age"].median()).astype(int)
    df["Discount_Pct"] = df["Discount_Pct"].fillna(df["Discount_Pct"].median())
    df["Payment_Method"] = df["Payment_Method"].fillna(df["Payment_Method"].mode()[0])
    df["Customer_Rating"] = df.groupby("Order_Status")["Customer_Rating"].transform(
        lambda x: x.fillna(round(x.median(), 1))
    )

    # Recalculate Total_Sales accurately
    df["Total_Sales"] = np.round(
        df["Unit_Price"] * df["Quantity"] * (1 - df["Discount_Pct"] / 100.0), 2
    )
    df["Order_Date"] = pd.to_datetime(df["Order_Date"])
    df["Order_Month"] = df["Order_Date"].dt.to_period("M").astype(str)

    os.makedirs(os.path.dirname(state["clean_csv_path"]), exist_ok=True)
    df.to_csv(state["clean_csv_path"], index=False)

    delivered_df = df[df["Order_Status"] == "Delivered"]
    net_rev = round(float(delivered_df["Total_Sales"].sum()), 2)
    aov = round(float(delivered_df["Total_Sales"].mean()), 2)
    ret_cancel_rate = round(((len(df) - len(delivered_df)) / len(df)) * 100, 1)

    cat_rev = (
        delivered_df.groupby("Category")["Total_Sales"]
        .sum()
        .sort_values(ascending=False)
        .round(2)
        .to_dict()
    )
    reg_rev = (
        delivered_df.groupby("Region")["Total_Sales"]
        .sum()
        .sort_values(ascending=False)
        .round(2)
        .to_dict()
    )

    return {
        "cleaning_report": {
            "raw_rows": raw_rows,
            "duplicates_removed": duplicates_count,
            "clean_rows": len(df),
            "remaining_nulls": int(df.isnull().sum().sum()),
        },
        "sales_kpis": {
            "total_unique_orders": len(df),
            "delivered_orders": len(delivered_df),
            "return_cancellation_rate_pct": ret_cancel_rate,
            "net_delivered_revenue_inr": net_rev,
            "average_order_value_inr": aov,
            "revenue_by_category": cat_rev,
            "revenue_by_region": reg_rev,
        },
    }


# ==========================================
# 3. AGENT 2: RFM SEGMENTATION ANALYST AGENT
# ==========================================
def rfm_analyst_agent(state: EcommerceAgentState) -> Dict[str, Any]:
    print("[Agent 2: RFM Analyst] Computing Recency, Frequency & Monetary customer segments...")
    df = pd.read_csv(state["clean_csv_path"])
    df["Order_Date"] = pd.to_datetime(df["Order_Date"])
    snapshot_date = df["Order_Date"].max() + pd.Timedelta(days=1)

    rfm = df.groupby("Customer_ID").agg(
        Recency=("Order_Date", lambda x: int((snapshot_date - x.max()).days)),
        Frequency=("Order_ID", "count"),
        Monetary=("Total_Sales", "sum"),
        Region=("Region", "first"),
        Favorite_Category=("Category", lambda x: x.mode()[0]),
    ).reset_index()

    def classify(row):
        if row["Recency"] > 150:
            return "At Risk"
        elif row["Frequency"] >= 4 and row["Monetary"] >= 10000:
            return "Champions / VIP"
        elif row["Frequency"] >= 2:
            return "Loyal Customers"
        else:
            return "New / Potential"

    rfm["Segment"] = rfm.apply(classify, axis=1)

    seg_table = (
        rfm.groupby("Segment")
        .agg(
            Customers=("Customer_ID", "count"),
            Avg_Recency_Days=("Recency", "mean"),
            Avg_Frequency=("Frequency", "mean"),
            Avg_Spend_INR=("Monetary", "mean"),
            Total_Spend_INR=("Monetary", "sum"),
        )
        .round(1)
        .to_dict(orient="index")
    )

    # Top 5 highest-spending At-Risk customers for targeted win-back
    top_at_risk = (
        rfm[rfm["Segment"] == "At Risk"]
        .sort_values(by="Monetary", ascending=False)
        .head(5)
        .round(2)
        .to_dict(orient="records")
    )

    return {
        "rfm_summary": seg_table,
        "at_risk_vips": top_at_risk,
    }


# ==========================================
# 4. AGENT 3: OPS & DISCOUNT AUDITOR AGENT
# ==========================================
def ops_auditor_agent(state: EcommerceAgentState) -> Dict[str, Any]:
    print("[Agent 3: Ops & Discount Auditor] Auditing discount margins, returns, and ratings...")
    df = pd.read_csv(state["clean_csv_path"])
    delivered_df = df[df["Order_Status"] == "Delivered"]

    aov_by_discount = (
        delivered_df.groupby("Discount_Pct")["Total_Sales"]
        .mean()
        .round(2)
        .to_dict()
    )

    rating_by_status = (
        df.groupby("Order_Status")["Customer_Rating"]
        .mean()
        .round(2)
        .to_dict()
    )

    non_delivered = df[df["Order_Status"] != "Delivered"]
    worst_categories = (
        non_delivered["Category"]
        .value_counts()
        .head(3)
        .to_dict()
    )

    return {
        "ops_audit": {
            "aov_by_discount_pct": aov_by_discount,
            "avg_rating_by_order_status": rating_by_status,
            "top_returned_or_cancelled_categories": worst_categories,
        }
    }


# ==========================================
# 5. AGENT 4: CHIEF RETENTION STRATEGIST (LLM)
# ==========================================
def retention_strategist_agent(state: EcommerceAgentState) -> Dict[str, Any]:
    print("[Agent 4: Chief Strategist] Synthesizing executive strategy & win-back campaigns via LLM...")
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0.2,
    )

    system_prompt = (
        "You are the Chief E-Commerce Retention & Growth Strategist. "
        "You receive verified analytical outputs from three specialist agents (Data Engineer, RFM Analyst, Ops Auditor). "
        "Use ONLY the exact numbers provided in the context—never invent or alter any metric. "
        "Produce a crisp, executive-ready action plan with:\n"
        "1. Executive KPI & Health Summary\n"
        "2. Segment-Specific Growth & Retention Playbook (Champions/VIP, Loyal, At Risk, New)\n"
        "3. Discount & Fulfillment Fix Plan (addressing return rate, rating drop, and West region lag)\n"
        "4. Personalized Win-Back Email/SMS Templates for the top 3 At-Risk high-value Customer IDs."
    )

    user_payload = f"""
    VERIFIED DATA CLEANING REPORT:
    {state['cleaning_report']}

    VERIFIED SALES & REGIONAL KPIs:
    {state['sales_kpis']}

    VERIFIED RFM SEGMENTATION SUMMARY:
    {state['rfm_summary']}

    TOP AT-RISK CUSTOMERS TO RECOVER:
    {state['at_risk_vips']}

    OPERATIONS, DISCOUNT & RATING AUDIT:
    {state['ops_audit']}
    """

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_payload),
    ])

    return {"final_executive_report": response.content}


# ==========================================
# 6. BUILD & COMPILE LANGGRAPH WORKFLOW
# ==========================================
def build_multi_agent_graph():
    workflow = StateGraph(EcommerceAgentState)

    # Add agent nodes
    workflow.add_node("data_engineer", data_engineer_agent)
    workflow.add_node("rfm_analyst", rfm_analyst_agent)
    workflow.add_node("ops_auditor", ops_auditor_agent)
    workflow.add_node("retention_strategist", retention_strategist_agent)

    # Define sequential pipeline edges
    workflow.set_entry_point("data_engineer")
    workflow.add_edge("data_engineer", "rfm_analyst")
    workflow.add_edge("rfm_analyst", "ops_auditor")
    workflow.add_edge("ops_auditor", "retention_strategist")
    workflow.add_edge("retention_strategist", END)

    return workflow.compile()


if __name__ == "__main__":
    app = build_multi_agent_graph()

    initial_state: EcommerceAgentState = {
        "raw_csv_path": "../data/raw/ecommerce_sales_data.csv",
        "clean_csv_path": "../data/processed/ecommerce_sales_clean.csv",
        "cleaning_report": {},
        "sales_kpis": {},
        "rfm_summary": {},
        "at_risk_vips": [],
        "ops_audit": {},
        "final_executive_report": "",
    }

    final_state = app.invoke(initial_state)

    print("\n" + "=" * 65)
    print("FINAL MULTI-AGENT EXECUTIVE STRATEGY REPORT")
    print("=" * 65)
    print(final_state["final_executive_report"])

    # Save report to markdown file
    with open("multi_agent_strategy_report.md", "w", encoding="utf-8") as f:
        f.write(final_state["final_executive_report"])
    print("\nSaved full report to: multi_agent/multi_agent_strategy_report.md")