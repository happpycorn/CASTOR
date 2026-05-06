import pytest
from castor.schema import (
    TelescopeSchema, 
    CameraSchema, 
    FilterSchema, 
    ObservationRequest
)
from castor.calculator import CastorCalculator

# ==========================================
# 1. 定義 Fixtures (測試夾具)
# 這樣我們就不用在每個 test 裡面重複寫望遠鏡參數
# ==========================================
@pytest.fixture
def lot_telescope():
    return TelescopeSchema(
        diameter_m=1.0,
        focal_length_m=8.0,
        m1_reflectance=0.9,
        m2_reflectance=0.9,
        glass_transmission=0.95,
        central_obstruction_linear_ratio=0.3
    )

@pytest.fixture
def sophia_camera():
    return CameraSchema(
        pixel_size_micron=13.5,
        resolution_x=2048,
        resolution_y=2048,
        read_noise_e=5.0,
        dark_current_e_per_sec=0.001,
        quantum_efficiency=0.85,
        readout_speed_khz=100.0,
        n_amplifiers=2,
        gain=1.2,
        full_well_capacity_e=100000.0
    )

@pytest.fixture
def v_band_filter():
    return FilterSchema(
        name="V",
        central_wavelength_nm=550.0,
        fwhm_nm=89.0,
        peak_transmission=0.9,
        zero_mag_flux=3.63e-2,
        default_extinction=0.15
    )

@pytest.fixture
def calculator():
    return CastorCalculator()

# ==========================================
# 2. 測試案例 (Test Cases)
# ==========================================

def test_calculator_array_exposure_time(calculator, lot_telescope, sophia_camera, v_band_filter):
    """測試給定多個曝光時間，是否能正確產出對應長度的 SNR 陣列"""
    request = ObservationRequest(
        telescope=lot_telescope,
        camera=sophia_camera,
        instrument_filter=v_band_filter,
        target_mag=18.0,
        sky_brightness_mag_arcsec2=21.0,
        exposure_time=[10.0, 60.0, 300.0]  # 測試陣列輸入
    )
    
    response = calculator.calculate(request)
    
    # 驗證輸出長度是否匹配
    assert len(response.snr) == 3
    assert len(response.exposure_time) == 3
    assert len(response.is_saturated) == 3
    
    # 驗證 SNR 趨勢 (時間越長，SNR 應該越高)
    assert response.snr[0] < response.snr[1] < response.snr[2]
    
    # 驗證 18 等星拍 300 秒不該過曝
    assert response.is_saturated[2] is False

def test_calculator_target_snr(calculator, lot_telescope, sophia_camera, v_band_filter):
    """測試給定目標 SNR，是否能反推出曝光時間"""
    request = ObservationRequest(
        telescope=lot_telescope,
        camera=sophia_camera,
        instrument_filter=v_band_filter,
        target_mag=15.0,  # 比較亮的星
        sky_brightness_mag_arcsec2=21.0,
        target_snr=[10.0, 50.0]  # 測試要求不同 SNR
    )
    
    response = calculator.calculate(request)
    
    assert len(response.exposure_time) == 2
    # 要求越高的 SNR，需要的時間應該越長
    assert response.exposure_time[0] < response.exposure_time[1]

def test_calculator_saturation_warning(calculator, lot_telescope, sophia_camera, v_band_filter):
    """測試拍極亮星時，飽和機制是否會正常觸發"""
    request = ObservationRequest(
        telescope=lot_telescope,
        camera=sophia_camera,
        instrument_filter=v_band_filter,
        target_mag=5.0,  # 極亮星 (例如肉眼可見的恆星)
        sky_brightness_mag_arcsec2=21.0,
        exposure_time=[1.0, 300.0]  # 1秒可能還好，300秒一定爆掉
    )
    
    response = calculator.calculate(request)
    
    # 驗證 300 秒那次是否有抓到過曝
    assert response.is_saturated[1] is True
    # 驗證是否有產生警告訊息
    assert len(response.warnings) > 0
    assert "saturated" in response.warnings[0].lower()

def test_pixel_scale_calculation(calculator, lot_telescope, sophia_camera, v_band_filter):
    """測試純粹的物理常數計算是否符合預期 (確保單位轉換正確)"""
    request = ObservationRequest(
        telescope=lot_telescope,
        camera=sophia_camera,
        instrument_filter=v_band_filter,
        target_mag=18.0,
        sky_brightness_mag_arcsec2=21.0,
        exposure_time=[10.0]
    )
    
    response = calculator.calculate(request)
    
    # 驗證 pixel scale (8m 焦距配 13.5um 像素，大約是 0.348 arcsec/pix)
    assert 0.34 < response.pixel_scale < 0.35