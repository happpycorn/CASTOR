import sys
from pathlib import Path

current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import json
import webview
import uvicorn
import threading
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from castor.calculator import CastorCalculator
from castor.schema import ObservationRequest

app = FastAPI()
calculator = CastorCalculator()

@app.post("/api/calculate")
def calculate_exposure(request: ObservationRequest):
    result = calculator.calculate(request)
    return result

@app.get("/api/presets")
def get_presets():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_dir = Path(sys._MEIPASS) # type: ignore
    else: 
        base_dir = Path(__file__).resolve().parent

    json_path = base_dir / "data" / "presets.json"

    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"找不到設定檔：{json_path}")

    with open(json_path, 'r', encoding='utf-8') as f:
        presets_data = json.load(f)
        
    return presets_data

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