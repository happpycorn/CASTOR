import sys
from pathlib import Path

# Setup Python path for local module loading
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

# 導入新的純函數與 Pydantic Schemas
from castor import schema
from castor.calculator import run_calculation
from castor.batch_calculator import run_batch_calculation

app = FastAPI(title="CASTOR API", description="Optical Exposure Time Calculator Engine")

# ==========================================
# 1. 單次計算端點 (Single Calculation API)
# ==========================================
@app.post("/api/calculate", response_model=schema.ObservationResponse)
def calculate_exposure(request: schema.ObservationRequest):
    try:
        # Pydantic 已經在 request 層把所有無效資料擋掉了
        result = run_calculation(request)
        return result
    except ValueError as e:
        # 攔截物理公式拋出的邊界錯誤
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# ==========================================
# 2. 批次計算端點 (Batch Calculation API)
# ==========================================
@app.post("/api/calculate/batch", response_model=schema.BatchObservationResponse)
def calculate_batch_exposure(request: schema.BatchObservationRequest):
    try:
        # 專門接收帶有時間序列 (TimeSeriesEnvironment) 的請求
        result = run_batch_calculation(request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# ==========================================
# 3. 取得硬體預設值 (Hardware Presets API)
# ==========================================
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

# ==========================================
# 4. 前端靜態檔案掛載 (Frontend Mounting)
# ==========================================
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

# ==========================================
# 5. 桌面應用程式啟動 (Desktop GUI)
# ==========================================
def start_server():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

if __name__ == '__main__':
    t = threading.Thread(target=start_server)
    t.daemon = True
    t.start()

    webview.create_window('CASTOR GUI', 'http://127.0.0.1:8000', width=1024, height=768)
    webview.start()