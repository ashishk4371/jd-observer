import sys
import os

# Ensure src/ directory is in sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import uvicorn

if __name__ == "__main__":
    print("🚀 Starting JD Glance API on http://127.0.0.1:8000 ...")
    uvicorn.run("jd_glance.main:app", host="127.0.0.1", port=8000, reload=True)
