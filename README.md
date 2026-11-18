# Autonomous Multi-Agent CSV Analyst & Business Intelligence Platform

**Hackathon Track:** Generative AI / Agentic AI & Automated Business Intelligence  
**Architecture:** LangGraph 3-Agent Orchestration + AST Security Sandbox + Flask Serverless Web App

## Problem Statement
Business teams and analysts spend over 70% of their workflow manually cleaning messy CSV exports, debugging Pandas 3.0 Copy-on-Write errors, writing repetitive aggregation scripts, and formatting executive summaries.

## Solution: Self-Healing 3-Agent LangGraph System
This platform automates end-to-end tabular data analysis across any domain (E-Commerce RFM Segmentation, EdTech Analytics, Food Delivery Operations, or custom CSV uploads) using three specialized AI agents:
1. **Schema & Quality Profiler Agent:** Automatically detects data types, duplicate rows, missing values, and numeric/categorical distributions.
2. **AST-Sandboxed Pandas & Chart Analyst Agent:** Generates and executes Pandas 3.0+ compliant analysis code inside an Abstract Syntax Tree (AST) security sandbox with an automated 3-retry self-healing loop and Matplotlib/Seaborn chart generation.
3. **Executive Strategist Agent:** Synthesizes verified numerical outputs into structured, actionable business recommendations.

## Security, Accessibility & Automated Testing
- **AST Code Sandboxing & Web Hardening:** Static AST inspection blocks unsafe imports (`os`, `sys`, `subprocess`, `socket`) and builtins (`eval`, `exec`, `open`) before execution; enforces 5 MB CSV upload limits, `secure_filename`, and OWASP HTTP headers (`X-Content-Type-Options`, `X-Frame-Options`).
- **WCAG-Compliant Accessible Interface:** Semantic HTML5 landmarks (`header`, `main`, `section`), explicit `<label for>` bindings, keyboard focus rings, skip-to-content navigation, and `aria-live` status regions.
- **Automated `pytest` Suite:** Unit and integration tests in `tests/test_agent_pipeline.py` validating schema profiling, AST security blocking, LangGraph compilation, and Flask accessibility/security headers.

## Quick Start & Testing
```bash
pip install -r requirements.txt
pytest -v