"""
run.py  — Simple launcher for the signals package.
Run this from anywhere with:  python run.py
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "signals.main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
    )
