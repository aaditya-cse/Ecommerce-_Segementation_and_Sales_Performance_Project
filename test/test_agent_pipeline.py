import os
import sys
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "multi_agent"))
sys.path.insert(0, os.path.join(ROOT_DIR, "api"))

from universal_analyst_agent import (
    schema_profiler_agent,
    validate_generated_code,
    SecurityError,
    clean_llm_text,
    build_universal_graph,
)
from index import app


def test_schema_profiler_detects_duplicates_and_nulls():
    sample_csv = os.path.join(ROOT_DIR, "data", "raw", "ecommerce_sales_data.csv")
    state = {"csv_path": sample_csv, "dataset_profile": ""}
    result = schema_profiler_agent(state)
    assert "duplicate_rows" in result["dataset_profile"]
    assert "Total_Sales" in result["dataset_profile"]


def test_ast_security_blocks_dangerous_code():
    with pytest.raises(SecurityError):
        validate_generated_code("import os\nos.system('ls')")
    with pytest.raises(SecurityError):
        validate_generated_code("eval('2+2')")


def test_ast_security_allows_safe_pandas_code():
    safe_code = "import pandas as pd\nimport numpy as np\nx = np.mean([1, 2, 3])\nprint(x)"
    validate_generated_code(safe_code)


def test_clean_llm_text_strips_think_tags():
    raw = "<think>internal reasoning</think>Final Executive Summary"
    assert clean_llm_text(raw) == "Final Executive Summary"


def test_langgraph_compiles_cleanly():
    graph = build_universal_graph()
    assert graph is not None


def test_flask_home_page_accessibility_and_headers():
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert 'for="sample-csv"' in html
    assert 'aria-live="polite"' in html
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"