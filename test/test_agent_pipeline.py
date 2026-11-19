import os as _os
import sys as _sys

_CI_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _CI_ROOT not in _sys.path:
    _sys.path.insert(0, _CI_ROOT)
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

def test_security_headers_csp_and_hsts():
    from api.index import app

    client = app.test_client()
    res = client.get("/")
    assert res.status_code == 200
    assert "Content-Security-Policy" in res.headers
    assert "Strict-Transport-Security" in res.headers
    assert res.headers.get("X-Frame-Options") == "DENY"


def test_csv_formula_injection_sanitization():
    from api.security import sanitize_csv_cell

    assert sanitize_csv_cell("=CMD|' /C calc'!A0").startswith("'")
    assert sanitize_csv_cell("+SUM(A1:A5)").startswith("'")
    assert sanitize_csv_cell("@IMPORTXML()").startswith("'")
    assert sanitize_csv_cell("Electronics") == "Electronics"


def test_csv_bytes_validation_rejects_binary_and_empty():
    import pytest
    from api.security import validate_csv_bytes

    with pytest.raises(ValueError):
        validate_csv_bytes(b"")
    with pytest.raises(ValueError):
        validate_csv_bytes(b"col1,col2\x00\x01\n1,2")
    valid = validate_csv_bytes(b"Category,Sales\nElectronics,500\n")
    assert "Electronics" in valid


def test_rate_limiter_enforces_threshold():
    from api.security import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)
    assert limiter.is_allowed("10.0.0.1")[0] is True
    assert limiter.is_allowed("10.0.0.1")[0] is True
    allowed, retry_after = limiter.is_allowed("10.0.0.1")
    assert allowed is False
    assert retry_after >= 1


def test_post_rejects_invalid_sample_path_traversal():
    from api.index import app

    client = app.test_client()
    res = client.post("/analyze", data={"sample_csv": "../../etc/passwd", "user_goal": "Test"})
    assert res.status_code == 200
    assert b"Invalid sample dataset" in res.data or b"GROQ_API_KEY" in res.data


def test_kpi_extractor_and_markdown_table_renderer():
    from api.renderer import extract_kpi_cards, render_markdown_to_html

    sample_stdout = "Total Orders: 365\nNet Revenue: $786,127.15\n"
    cards = extract_kpi_cards(sample_stdout)
    assert len(cards) == 2
    assert cards[0]["label"] == "Total Orders"

    html_out = render_markdown_to_html("| ColA | ColB |\n| --- | --- |\n| 1 | 2 |")
    assert '<table class="styled-table">' in html_out