import pytest
import numpy as np
import numpy.testing as npt

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
    base_args = {"z_moon_deg": 45.0, "z_target_deg": 45.0}
    
    b_full_moon = krisciunas_schaefer_1991(alpha_deg=0.0, rho_deg=60.0, **base_args)
    b_new_moon = krisciunas_schaefer_1991(alpha_deg=180.0, rho_deg=60.0, **base_args)
    assert b_full_moon > (b_new_moon * 10.0)
    
    b_close = krisciunas_schaefer_1991(alpha_deg=0.0, rho_deg=10.0, **base_args)
    b_far = krisciunas_schaefer_1991(alpha_deg=0.0, rho_deg=90.0, **base_args)
    assert b_close > b_far

# ==========================================
# 2. 天光整合邏輯測試 (月球升降防呆)
# ==========================================

def test_sky_brightness_moon_below_horizon(monkeypatch):
    """防呆測試：月亮在地平線下時，總天光必須精確等於無月夜的暗空星等"""
    def mock_geometry(*args, **kwargs):
        return (0.0, 60.0, 95.0, 45.0)
    
    monkeypatch.setattr("castor.moon.get_moon_and_target_geometry", mock_geometry)
    
    base_dark_sky = 21.5
    result_mag = calculate_sky_brightness(
        target_ra=0.0, target_dec=0.0, 
        obs_time_utc="2026-01-01T00:00:00", 
        mu_dark=base_dark_sky,
        extinction_coeff=0.15,
    )
    
    assert result_mag == pytest.approx(base_dark_sky)

def test_sky_brightness_moon_above_horizon(monkeypatch):
    """邏輯測試：月亮在地平線上時，總天光一定會變亮"""
    def mock_geometry(*args, **kwargs):
        return (0.0, 30.0, 30.0, 30.0)
    
    monkeypatch.setattr("castor.moon.get_moon_and_target_geometry", mock_geometry)
    
    base_dark_sky = 21.5
    result_mag = calculate_sky_brightness(
        target_ra=0.0, target_dec=0.0, 
        obs_time_utc="2026-01-01T00:00:00", 
        mu_dark=base_dark_sky,
        extinction_coeff=0.15,
    )
    
    assert result_mag < base_dark_sky

# ==========================================
# 3. 曆書引擎執行測試 (Ephemeris Sanity Check & Vectorization)
# ==========================================

def test_ephemeris_execution_scalar():
    """確保 Astropy 曆書運算單點執行，沒有型別報錯"""
    result = get_moon_and_target_geometry(
        target_ra=10.68, target_dec=41.27, 
        obs_time_utc="2026-07-23T12:00:00" 
    )
    
    assert len(result) == 4
    for val in result:
        # numpy.where 和 astropy 在解開封印後可能回傳 float, np.float64 或 0-d 陣列
        assert np.isscalar(val) or (isinstance(val, np.ndarray) and val.ndim == 0)

def test_ephemeris_time_series_vectorization():
    """確保核心曆書引擎能完美吞吐時間陣列 (List[str] -> NDArray)"""
    # 給定三個連續的時間點
    time_series = [
        "2026-07-23T12:00:00",
        "2026-07-23T13:00:00",
        "2026-07-23T14:00:00"
    ]
    
    # 1. 測試幾何計算是否輸出長度為 3 的陣列
    alpha, rho, z_moon, z_target = get_moon_and_target_geometry(
        target_ra=10.68, target_dec=41.27, obs_time_utc=time_series
    )
    assert isinstance(z_moon, np.ndarray)
    assert len(z_moon) == 3
    
    # 2. 測試天光計算是否輸出長度為 3 的陣列
    mu_sky_array = calculate_sky_brightness(
        target_ra=10.68, target_dec=41.27, 
        obs_time_utc=time_series, 
        mu_dark=21.5,
        extinction_coeff=0.15,
    )
    assert isinstance(mu_sky_array, np.ndarray)
    assert len(mu_sky_array) == 3
