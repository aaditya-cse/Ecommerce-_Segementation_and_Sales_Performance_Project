"""Top-level entry point for AgentOps BI Studio."""
import os
import sys

# Ensure api and multi_agent are in sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "multi_agent"))
sys.path.insert(0, os.path.join(ROOT_DIR, "api"))

from api.index import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n=======================================================")
    print(f"  AgentOps BI Studio - Autonomous Multi-Agent Analyst")
    print(f"  Running locally at: http://127.0.0.1:{port}")
    print(f"=======================================================\n")
    app.run(host="0.0.0.0", port=port, debug=True)
