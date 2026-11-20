"""Markdown-to-HTML renderer and verified KPI extractor for executive dashboards."""

import html
import re
from typing import Dict, List


def extract_kpi_cards(analysis_output: str) -> list[dict]:
    """Extracts clean, deduplicated numeric KPI cards while ignoring Pandas dtype/Name footers."""
    if not analysis_output:
        return []
    cards = []
    seen_labels = set()
    blocked_terms = ("dtype", "int64", "float64", "object", "length:", "name:", "=== ", "---")
    for raw_line in analysis_output.splitlines():
        line = raw_line.strip().lstrip("-*• ")
        if not line or ":" not in line:
            continue
        low = line.lower()
        if any(b in low for b in blocked_terms):
            continue
        label, val = line.split(":", 1)
        label = label.strip(" *#_`")
        val = val.strip(" *#_`")
        if not label or not val or len(label) > 36 or len(val) > 28:
            continue
        if label.lower() in ("name", "dtype", "index", "columns", "shape", "error", "warning"):
            continue
        if not any(ch.isdigit() for ch in val) or "dtype" in val.lower():
            continue
        norm_key = "".join(ch for ch in label.lower() if ch.isalnum())
        if norm_key in seen_labels:
            continue
        seen_labels.add(norm_key)
        cards.append({"label": label, "value": val})
        if len(cards) >= 4:
            break
    return cards


def format_inline_md(text: str) -> str:
    """Escape HTML entities and format bold, italic, and inline code spans."""
    cleaned = text.replace(r"\$", "$").replace(r"\|", " / ")
    cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)
    escaped = html.escape(cleaned).replace("\n", "<br>")
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    return escaped



def _format_cell_items(cell_html: str) -> str:
    """Splits semicolon-separated breakdown lists in table cells into clean stacked lines."""
    if ";" not in cell_html or "<" in cell_html:
        return cell_html
    parts = [p.strip() for p in cell_html.split(";") if p.strip()]
    if len(parts) < 2:
        return cell_html
    formatted = []
    for p in parts:
        # Add clean ': ' between label and currency/number if missing (e.g. 'North ?367,834' -> 'North: ?367,834')
        p = re.sub(r"^([A-Za-z &/()-]+?)\s+((?:?|\$|INR|USD)?[0-9][0-9,.%]*)$", r"<strong>\1:</strong> \2", p)
        formatted.append(f"<div style='padding:2px 0;'>&bull; {p}</div>")
    return "".join(formatted)


def render_markdown_to_html(md_text: str) -> str:
    """Convert structured Markdown into accessible, styled HTML elements."""
    lines = md_text.splitlines()
    out: List[str] = []
    table_rows: List[str] = []
    in_list = False

    def flush_table() -> None:
        nonlocal table_rows
        if not table_rows:
            return
        out.append('<div class="table-wrap"><table class="styled-table">')
        for idx, row in enumerate(table_rows):
            if idx == 1 and re.match(r"^[\s|:-]+$", row):
                continue
            cells = [c.strip() for c in row.strip("|").split("|")]
            if idx == 0:
                header_cells = "".join(f"<th>{format_inline_md(c)}</th>" for c in cells)
                out.append(f"<thead><tr>{header_cells}</tr></thead><tbody>")
            else:
                body_cells = "".join(f"<td>{format_inline_md(c)}</td>" for c in cells)
                out.append(f"<tr>{body_cells}</tr>")
        out.append("</tbody></table></div>")
        table_rows = []

    def flush_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw in lines:
        line = raw.strip()
        if "|" in line and (line.startswith("|") or line.count("|") >= 2):
            flush_list()
            table_rows.append(line)
            continue
        if table_rows:
            flush_table()

        if not line or line == "---":
            flush_list()
            continue
        if line.startswith("### "):
            flush_list()
            out.append(f"<h3>{format_inline_md(line[4:])}</h3>")
        elif line.startswith("## "):
            flush_list()
            out.append(f"<h2>{format_inline_md(line[3:])}</h2>")
        elif line.startswith("# "):
            flush_list()
            out.append(f"<h2>{format_inline_md(line[2:])}</h2>")
        elif re.match(r"^([-*]|\d+\.)\s+", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = re.sub(r"^([-*]|\d+\.)\s+", "", line)
            out.append(f"<li>{format_inline_md(item)}</li>")
        else:
            flush_list()
            out.append(f"<p>{format_inline_md(line)}</p>")

    flush_table()
    flush_list()
    return "\n".join(out)
