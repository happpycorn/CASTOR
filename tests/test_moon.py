import pytest
import numpy as np
import numpy.testing as npt

# 假設你的模組路徑是 castor.moon
from castor.moon import (
    krisciunas_schaefer_1991,
    calculate_sky_brightness,
    get_moon_and_target_geometry
)

# ==========================================
# 1. 核心物理引擎測試 (KS91 模型)
# ==========================================

def test_ks91_vectorization():
    """確保 KS91 經驗模型能完美支援 NumPy 陣列運算"""
    alpha = np.array([0.0, 90.0, 180.0])
    rho = np.array([30.0, 60.0, 90.0])
    z_moon = np.array([30.0, 45.0, 60.0])
    z_target = np.array([30.0, 45.0, 60.0])
    
    result = krisciunas_schaefer_1991(alpha, rho, z_moon, z_target)
    
    assert isinstance(result, np.ndarray)
    assert len(result) == 3

def test_ks91_physical_limits():
    """物理極限：確保滿月與新月、距離遠近的亮度關係符合真實物理"""
    # 基準參數：月亮與目標都在仰角 45 度 (天頂角 45 度)
    base_args = {"z_moon_deg": 45.0, "z_target_deg": 45.0}
    
    # 1. 月相效應 (Phase Effect)
    # 距離 60 度時，滿月(0度)的亮度必須遠大於新月(180度)
    b_full_moon = krisciunas_schaefer_1991(alpha_deg=0.0, rho_deg=60.0, **base_args)
    b_new_moon = krisciunas_schaefer_1991(alpha_deg=180.0, rho_deg=60.0, **base_args)
    assert b_full_moon > (b_new_moon * 10.0) # 滿月至少比新月亮一個數量級
    
    # 2. 角距離效應 (Angular Separation Effect)
    # 同樣是滿月，離月亮 10 度(近)的散射必須大於離 90 度(遠)的散射
    b_close = krisciunas_schaefer_1991(alpha_deg=0.0, rho_deg=10.0, **base_args)
    b_far = krisciunas_schaefer_1991(alpha_deg=0.0, rho_deg=90.0, **base_args)
    assert b_close > b_far

# ==========================================
# 2. 天光整合邏輯測試 (月球升降防呆)
# ==========================================

def test_sky_brightness_moon_below_horizon(monkeypatch):
    """防呆測試：月亮在地平線下時，總天光必須精確等於無月夜的暗空星等"""
    
    # 我們攔截 get_moon_and_target_geometry，強制回傳月球天頂角 = 95.0 (在地平線下)
    def mock_geometry(*args, **kwargs):
        # 回傳: (alpha, rho, z_moon, z_target)
        return (0.0, 60.0, 95.0, 45.0)
    
    monkeypatch.setattr("castor.moon.get_moon_and_target_geometry", mock_geometry)
    
    base_dark_sky = 21.5
    result_mag = calculate_sky_brightness(
        target_ra=0.0, target_dec=0.0, 
        obs_time_utc="2026-01-01T00:00:00", # 時間隨意，因為幾何被 mock 了
        mu_dark=base_dark_sky
    )
    
    # 斷言：完全沒有月光污染，星等不變
    assert result_mag == pytest.approx(base_dark_sky)

def test_sky_brightness_moon_above_horizon(monkeypatch):
    """邏輯測試：月亮在地平線上時，總天光一定會變亮 (星等數字變小)"""
    
    # 強制回傳滿月 (alpha=0)，且月球高掛天空 (z_moon=30.0)
    def mock_geometry(*args, **kwargs):
        return (0.0, 30.0, 30.0, 30.0)
    
    monkeypatch.setattr("castor.moon.get_moon_and_target_geometry", mock_geometry)
    
    base_dark_sky = 21.5
    result_mag = calculate_sky_brightness(
        target_ra=0.0, target_dec=0.0, 
        obs_time_utc="2026-01-01T00:00:00", 
        mu_dark=base_dark_sky
    )
    
    # 斷言：加了月光，星等數字必須小於純暗空 (數字越小代表越亮)
    assert result_mag < base_dark_sky

# ==========================================
# 3. 曆書引擎執行測試 (Ephemeris Sanity Check)
# ==========================================

def test_ephemeris_execution():
    """確保 Astropy 曆書運算能正常執行，沒有型別報錯或崩潰"""
    # 設定一個確定的時間與座標 (M31 仙女座星系附近的座標)
    result = get_moon_and_target_geometry(
        target_ra=10.68, target_dec=41.27, 
        obs_time_utc="2026-07-23T12:00:00" 
    )
    
    # 確保回傳 4 個值，且皆為 Python 內建的 float 型別 (這能驗證我們剛剛加的 cast 是否成功運作)
    assert len(result) == 4
    for val in result:
        assert isinstance(val, float)