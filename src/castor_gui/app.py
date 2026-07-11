import webview
import uvicorn
import threading
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from castor.calculator import CastorCalculator
from castor.schema import ObservationRequest

import sys
from pathlib import Path

app = FastAPI()
calculator = CastorCalculator()

@app.post("/api/calculate")
def calculate_exposure(request: ObservationRequest):
    result = calculator.calculate(request)
    return result

def get_frontend_path() -> str:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        meipass_path = getattr(sys, '_MEIPASS')
        base_dir = Path(meipass_path)
    else: 
        base_dir = Path(__file__).resolve().parent

    frontend_dir = base_dir / "frontend"

    if not frontend_dir.exists():
        raise RuntimeError(f"找不到前端資料夾：{frontend_dir}")
        
    return str(frontend_dir)

app.mount("/", StaticFiles(directory=get_frontend_path(), html=True), name="static")

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

if __name__ == '__main__':
    t = threading.Thread(target=start_server)
    t.daemon = True
    t.start()

    webview.create_window('CASTOR GUI', 'http://127.0.0.1:8000', width=1024, height=768)
    webview.start()