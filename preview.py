"""Loopback-only local preview. Does not change production availability."""
import argparse
from app import app

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--dashboard-fixtures", action="store_true")
    args = parser.parse_args()
    if args.dashboard_fixtures:
        app.config.update(DEBUG=True, NURTURE_DEV_PREVIEW=True)
    app.run(host="127.0.0.1", port=args.port, use_reloader=False, use_debugger=False)
