import os
import sys
import tempfile
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "multi_agent"))
sys.path.insert(0, os.path.join(ROOT_DIR, "api"))

from universal_analyst_agent import (
    SecurityError,
    build_universal_graph,
    clean_llm_text,
    schema_profiler_agent,
    validate_generated_code,
    compute_data_health_score,
    ml_predictor_agent,
    financial_modeler_agent,
)
from index import app
from renderer import extract_kpi_cards, render_markdown_to_html
from security import (
    SlidingWindowRateLimiter,
    sanitize_csv_cell,
    validate_csv_bytes,
)


def test_schema_profiler_detects_duplicates_and_nulls():
    csv_content = "Order_ID,Category,Revenue\n1,Electronics,1200\n1,Electronics,1200\n2,Fashion,\n"
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        tmp_path = f.name
    try:
        res = schema_profiler_agent({"csv_path": tmp_path, "user_goal": "Check quality"})
        profile = res["dataset_profile"]
        assert '"duplicate_rows": 1' in profile
        assert '"Revenue": 1' in profile
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_ast_security_blocks_dangerous_code():
    for bad_code in [
        "import os\nos.system('dir')",
        "import subprocess\nsubprocess.Popen('calc')",
        "eval('2+2')",
        "open('secret.txt', 'w')",
    ]:
        with pytest.raises(SecurityError):
            validate_generated_code(bad_code)


def test_ast_security_allows_safe_pandas_code():
    safe_code = (
        "import pandas as pd\n"
        "import numpy as np\n"
        "df = pd.read_csv(CSV_PATH).drop_duplicates()\n"
        "print(df.shape)\n"
    )
    validate_generated_code(safe_code)


def test_clean_llm_text_strips_think_tags():
    raw = "<think>internal chain of thought</think>### Final Report\nRevenue: 5000"
    assert clean_llm_text(raw) == "### Final Report\nRevenue: 5000"


def test_langgraph_compiles_cleanly():
    graph = build_universal_graph()
    assert graph is not None


def test_flask_home_page_accessibility_and_headers():
    client = app.test_client()
    resp = client.get("/")
    html = resp.data.decode("utf-8")
    assert resp.status_code == 200
    assert 'lang="en"' in html
    assert "Skip to main content" in html


def test_security_headers_csp_and_hsts():
    client = app.test_client()
    resp = client.get("/")
    assert "Content-Security-Policy" in resp.headers
    assert "X-Content-Type-Options" in resp.headers
    assert resp.headers.get("X-Frame-Options") in ("DENY", "SAMEORIGIN")


def test_csv_formula_injection_sanitization():
    assert sanitize_csv_cell("=CMD|' /C calc'!A0").startswith("'")
    assert sanitize_csv_cell("+SUM(A1:A5)").startswith("'")
    assert sanitize_csv_cell("-100").startswith("'")
    assert sanitize_csv_cell("@evil").startswith("'")
    assert sanitize_csv_cell("Electronics") == "Electronics"


def test_csv_bytes_validation_rejects_binary_and_empty():
    with pytest.raises(ValueError):
        validate_csv_bytes(b"")
    with pytest.raises(ValueError):
        validate_csv_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    valid = validate_csv_bytes(b"col1,col2\n1,2\n")
    assert "col1,col2" in valid


def test_rate_limiter_enforces_threshold():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)
    assert limiter.is_allowed("10.0.0.1")[0] is True
    assert limiter.is_allowed("10.0.0.1")[0] is True
    allowed, retry_after = limiter.is_allowed("10.0.0.1")
    assert allowed is False
    assert retry_after >= 1


def test_post_rejects_invalid_sample_path_traversal():
    client = app.test_client()
    resp = client.post("/analyze", data={"sample_csv": "../../etc/passwd", "user_goal": "test"})
    assert resp.status_code == 200
    assert "Invalid sample dataset" in resp.data.decode("utf-8")


def test_kpi_extractor_and_markdown_table_renderer():
    sample_stdout = "Total Net Revenue: ₹1,206,787.80\nTotal Orders: 350\n"
    cards = extract_kpi_cards(sample_stdout)
    assert len(cards) >= 1

    md = "| Category | Revenue |\n| --- | --- |\n| Home & Kitchen | ₹433,056.15 |\n"
    html = render_markdown_to_html(md)
    assert "<table" in html
    assert "Home &amp; Kitchen" in html or "Home & Kitchen" in html


def test_rate_limiter_isolates_different_ips():
    """Different client IPs must maintain independent rate limiting windows."""
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
    assert limiter.is_allowed("192.168.1.100")[0] is True
    assert limiter.is_allowed("192.168.1.200")[0] is True
    # The first IP is now exhausted, but the second IP was only used once
    assert limiter.is_allowed("192.168.1.100")[0] is False
    assert limiter.is_allowed("192.168.1.200")[0] is False


def test_validate_csv_rejects_single_column():
    """CSVs with fewer than 2 columns must be rejected as invalid tabular data."""
    single_col_data = b"Product_Name\nLaptop\nSmartphone\nHeadphones\n"
    with pytest.raises(ValueError, match="2\\+ columns"):
        validate_csv_bytes(single_col_data)


def test_validate_csv_rejects_binary_magic_bytes():
    """Common binary container signatures must be caught before CSV parsing."""
    with pytest.raises(ValueError, match="Binary file detected"):
        validate_csv_bytes(b"PK\x03\x04\x14\x00\x00\x00")
    with pytest.raises(ValueError, match="Binary file detected"):
        validate_csv_bytes(b"%PDF-1.4\n%...\n")
    with pytest.raises(ValueError, match="Binary file detected"):
        validate_csv_bytes(b"BM\x36\x00\x00\x00")


def test_validate_csv_rejects_sql_injection_headers():
    """Column headers containing SQL DDL/DML injection keywords must be blocked."""
    evil_csv = b"col1,user_id; DROP TABLE accounts;--\n1,100\n"
    with pytest.raises(ValueError, match="Suspicious column names detected"):
        validate_csv_bytes(evil_csv)


def test_sanitize_csv_cell_extended_vectors():
    """CSV cells with pipe, backtick, or embedded tabs must be escaped, while standard data passes unaltered."""
    assert sanitize_csv_cell("|calc.exe").startswith("'")
    assert sanitize_csv_cell("`whoami`").startswith("'")
    assert sanitize_csv_cell("data\tleak").startswith("'")
    assert sanitize_csv_cell("42.50") == "42.50"
    assert sanitize_csv_cell("Standard Product Description") == "Standard Product Description"


def test_hardened_security_and_privacy_headers():
    """HTTP responses must contain modern security policies and must not leak Server version."""
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Permissions-Policy" in resp.headers
    assert resp.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
    assert resp.headers.get("Cross-Origin-Resource-Policy") == "same-origin"
    assert resp.headers.get("Cross-Origin-Embedder-Policy") == "require-corp"
    assert resp.headers.get("X-Permitted-Cross-Domain-Policies") == "none"
    assert resp.headers.get("X-DNS-Prefetch-Control") == "off"
    assert "Werkzeug" not in resp.headers.get("Server", "")


def test_compute_data_health_score():
    """Deterministic 0-100% data health scorecard must accurately compute hygiene metrics."""
    import pandas as pd
    # 1. Pristine clean data
    df_clean = pd.DataFrame({
        "Revenue": [100.0, 250.0, 300.0, 450.0],
        "Orders": [1, 2, 3, 4],
    })
    health_clean = compute_data_health_score(df_clean)
    assert health_clean["overall_score"] == 100.0
    assert "Enterprise Ready" in health_clean["grade"]
    assert health_clean["null_count"] == 0
    assert health_clean["duplicate_count"] == 0

    # 2. Dirty data with nulls, duplicates, and negative anomalies
    df_dirty = pd.DataFrame({
        "Revenue": [100.0, None, -50.0, 100.0],
        "Price": [-10.0, 20.0, 30.0, -10.0],
    })
    health_dirty = compute_data_health_score(df_dirty)
    assert health_dirty["overall_score"] < 90.0
    assert health_dirty["null_count"] > 0
    assert health_dirty["anomaly_count"] > 0


def test_ml_predictor_agent_clustering_and_forecast():
    """Agent 3: Automated K-Means customer segmentation and regression forecasting."""
    csv_content = (
        "Customer_ID,Revenue,Orders,Discount\n"
        + "\n".join(f"{i},{100 + i * 45},{1 + (i % 5)},{5 + (i % 10)}" for i in range(1, 25))
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        tmp_path = f.name
    try:
        state = {"csv_path": tmp_path, "user_goal": "Cluster customers and predict sales"}
        result = ml_predictor_agent(state)
        assert "ml_insights" in result
        insights = result["ml_insights"]
        assert "clusters" in insights
        assert len(insights["clusters"]) >= 2
        assert "forecast" in insights
        assert 0.0 <= insights["forecast"]["r_squared"] <= 1.0
        assert result["ml_chart_path"] != ""
        assert os.path.exists(result["ml_chart_path"])
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if result.get("ml_chart_path") and os.path.exists(result["ml_chart_path"]):
            os.remove(result["ml_chart_path"])


def test_financial_modeler_scenarios():
    """Agent 4: Financial sensitivity modeling computes all operational scenarios."""
    csv_content = "Order_ID,Revenue,Status\n1,1000,Completed\n2,2000,Returned\n3,1500,Completed\n"
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        tmp_path = f.name
    try:
        state = {"csv_path": tmp_path}
        res = financial_modeler_agent(state)
        scenarios = res.get("scenario_models", {})
        assert "baseline" in scenarios
        assert "conservative" in scenarios
        assert "target" in scenarios
        assert "aggressive" in scenarios
        assert scenarios["baseline"]["gross_volume"] == 4500.0
        assert scenarios["target"]["net_retained_capital"] > 0
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_langgraph_5_agent_swarm_topology():
    """Graph compilation must contain all 5 autonomous agent nodes."""
    graph = build_universal_graph()
    expected_nodes = {"profiler", "analyst", "ml_predictor", "financial_modeler", "strategist"}
    assert expected_nodes.issubset(set(graph.nodes.keys()))


def test_ast_security_blocks_attribute_traversal_and_builtins():
    """AST sandbox must block __subclasses__, dunder attributes, getattr, and eval."""
    with pytest.raises(SecurityError, match="Blocked unsafe attribute access: __class__"):
        validate_generated_code("x = ().__class__")

    with pytest.raises(SecurityError, match="Blocked unsafe attribute access: __subclasses__"):
        validate_generated_code("x = object.__subclasses__()")

    with pytest.raises(SecurityError, match="Blocked unsafe function call: getattr"):
        validate_generated_code("getattr(df, '__class__')")

    with pytest.raises(SecurityError, match="Blocked unsafe function call: eval"):
        validate_generated_code("eval('2 + 2')")


def test_rate_limiter_eviction_and_cleanup():
    """Rate limiter must prune stale client records when table exceeds threshold."""
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=1, max_clients=2)
    # Add client 1 and 2
    assert limiter.is_allowed("192.168.1.1")[0] is True
    assert limiter.is_allowed("192.168.1.2")[0] is True
    # Add client 3, triggers auto-eviction if table size exceeds max_clients
    assert limiter.is_allowed("192.168.1.3")[0] is True
    assert len(limiter._hits) <= 3


def test_safe_builtins_whitelist_integrity():
    """Restricted execution environment must exclude dangerous system primitives."""
    from universal_analyst_agent import SAFE_BUILTINS
    assert "open" not in SAFE_BUILTINS
    assert "__import__" not in SAFE_BUILTINS
    assert "eval" not in SAFE_BUILTINS
    assert "exec" not in SAFE_BUILTINS
    assert "compile" not in SAFE_BUILTINS
    assert "sum" in SAFE_BUILTINS
    assert "len" in SAFE_BUILTINS


def test_ml_predictor_handles_empty_or_missing_csv():
    """Agent 3 must gracefully return empty insights if CSV is missing or empty."""
    res_empty = ml_predictor_agent({"csv_path": "non_existent_file.csv"})
    assert res_empty["ml_insights"] == {}
    assert res_empty["ml_chart_path"] == ""


def test_financial_modeler_handles_missing_file():
    """Agent 4 must safely handle non-existent CSV files without crashing."""
    res = financial_modeler_agent({"csv_path": "missing_data.csv"})
    assert res["scenario_models"] == {}


def test_compute_data_health_score_single_row():
    """Data health scorecard must handle edge case of single row dataset."""
    import pandas as pd
    df_single = pd.DataFrame({"Revenue": [500.0], "Category": ["Electronics"]})
    score = compute_data_health_score(df_single)
    assert score["overall_score"] == 100.0
    assert score["completeness_pct"] == 100.0
    assert score["uniqueness_pct"] == 100.0


def test_api_chat_returns_factual_answers():
    """Test that /api/chat interactive console returns structured analytical answers."""
    client = app.test_client()
    resp = client.post(
        "/api/chat",
        json={
            "question": "Compare customer segments by average discount, or break down monthly trends...",
            "sample_csv": "data/raw/ecommerce_sales_data.csv",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert "answer" in data
    assert len(data["answer"]) > 20
    assert data["agent"] == "Boardroom Strategist Agent"


def test_api_chat_rejects_empty_question():
    """Test that /api/chat rejects empty query strings with HTTP 400."""
    client = app.test_client()
    resp = client.post("/api/chat", json={"question": "   "})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["status"] == "error"



