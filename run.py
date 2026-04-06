# run.py
# PasekSaaS — Application Entry Point
# ──────────────────────────────────────────────────────
"""
Start the backend server.

Usage:
    python run.py

This replaces the old `if __name__ == "__main__"` block in main.py.
For production, use:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
