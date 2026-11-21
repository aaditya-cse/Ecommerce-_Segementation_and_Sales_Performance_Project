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
    is_debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true")
    print("\n=======================================================")
    print("  🚀 AgentOps BI Studio - Autonomous 5-Agent Swarm")
    print(f"  Running locally at: http://127.0.0.1:{port} and http://localhost:{port}")
    print("=======================================================\n")
    app.run(host="0.0.0.0", port=port, debug=is_debug)
