import pytest
from castor.schema import (
    TelescopeSchema, 
    CameraSchema, 
    FilterSchema, 
    InstrumentProfile,
    PointTarget,
    ManualEnvironment,
    SolveForSNR,
    SolveForTime,
    ArrayInput,
    ObservationRequest,
    SNRResponse,
    TimeResponse
)
from castor.calculator import CastorCalculator

# ==========================================
# 1. 定義 Fixtures (測試夾具)
# ==========================================
@pytest.fixture
def lot_telescope():
    return TelescopeSchema(
        diameter_m=1.0,
        focal_length_m=8.0,
        m1_reflectance=0.9,
        m2_reflectance=0.9,
        glass_transmission=0.95,
        central_obstruction_linear_ratio=0.3,
        additional_throughput=0
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
        full_well_capacity_e=100000.0,
        binning_x=1,
        binning_y=1,
        shutter_overhead_sec=0,
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
def instrument_profile(lot_telescope, sophia_camera, v_band_filter):
    """將硬體組態打包成單一 Instrument Profile，簡化後續的 Request 組裝"""
    return InstrumentProfile(
        telescope=lot_telescope,
        camera=sophia_camera,
        optic_filter=v_band_filter
    )

@pytest.fixture
def base_environment():
    """提供預設的觀測環境參數"""
    return ManualEnvironment(
        type="manual",
        seeing_fwhm_arcsec=1.5,
        airmass=1.0,
        extinction_coeff=None,
        sky_brightness_mag_arcsec2=21.0
    )

@pytest.fixture
def calculator():
    return CastorCalculator()

# ==========================================
# 2. 測試案例 (Test Cases)
# ==========================================

def test_calculator_array_exposure_time(calculator, instrument_profile, base_environment):
    """測試給定多個曝光時間，是否能正確產出對應長度的 SNR 陣列"""
    request = ObservationRequest(
        instrument=instrument_profile,
        target=PointTarget(
            type="point",         # 明確指定 discriminator
            sed_type="flat",      # 預設的光譜分佈
            temperature_k=None,   # flat 模式下不需要溫度，明確給 None
            redshift=0.0,         # 預設紅移為 0
            target_mag=18.0       # 這裡放你原本測試的星等 (18.0, 15.0 或 5.0)
        ),
        environment=base_environment,
        options=SolveForSNR(
            exposure_time=ArrayInput(values=[10.0, 60.0, 300.0])
        )
    )
    
    response = calculator.calculate(request)
    
    # 確認回傳型別正確
    assert isinstance(response, SNRResponse)
    
    # 驗證輸出長度是否匹配
    assert len(response.calculated_snr) == 3
    assert len(response.input_exposure_time) == 3
    assert len(response.is_saturated) == 3
    
    # 驗證 SNR 趨勢 (時間越長，SNR 應該越高)
    assert response.calculated_snr[0] < response.calculated_snr[1] < response.calculated_snr[2]
    
    # 驗證 18 等星拍 300 秒不該過曝
    assert response.is_saturated[2] is False


def test_calculator_target_snr(calculator, instrument_profile, base_environment):
    """測試給定目標 SNR，是否能反推出曝光時間"""
    request = ObservationRequest(
        instrument=instrument_profile,
        target=PointTarget(
            type="point",         # 明確指定 discriminator
            sed_type="flat",      # 預設的光譜分佈
            temperature_k=None,   # flat 模式下不需要溫度，明確給 None
            redshift=0.0,         # 預設紅移為 0
            target_mag=15.0       # 這裡放你原本測試的星等 (18.0, 15.0 或 5.0)
        ),
        environment=base_environment,
        options=SolveForTime(
            target_snr=ArrayInput(values=[10.0, 50.0])
        )
    )
    
    response = calculator.calculate(request)
    
    # 確認回傳型別正確
    assert isinstance(response, TimeResponse)
    
    assert len(response.calculated_exposure_time) == 2
    # 要求越高的 SNR，需要的時間應該越長
    assert response.calculated_exposure_time[0] < response.calculated_exposure_time[1]


def test_calculator_saturation_warning(calculator, instrument_profile, base_environment):
    """測試拍極亮星時，飽和機制是否會正常觸發"""
    request = ObservationRequest(
        instrument=instrument_profile,
            target=PointTarget(
            type="point",         # 明確指定 discriminator
            sed_type="flat",      # 預設的光譜分佈
            temperature_k=None,   # flat 模式下不需要溫度，明確給 None
            redshift=0.0,         # 預設紅移為 0
            target_mag=5.0       # 這裡放你原本測試的星等 (18.0, 15.0 或 5.0)
        ),  # 極亮星 (例如肉眼可見的恆星)
        environment=base_environment,
        options=SolveForSNR(
            exposure_time=ArrayInput(values=[1.0, 300.0])  # 1秒可能還好，300秒一定爆掉
        )
    )
    
    response = calculator.calculate(request)
    
    # 驗證 300 秒那次是否有抓到過曝
    assert response.is_saturated[1] is True
    # 驗證是否有產生警告訊息
    assert len(response.warnings) > 0
    assert "saturated" in response.warnings[0].lower()


def test_pixel_scale_calculation(calculator, instrument_profile, base_environment):
    """測試純粹的物理常數計算是否符合預期 (確保單位轉換正確)"""
    request = ObservationRequest(
        instrument=instrument_profile,
        target=PointTarget(
            type="point",         # 明確指定 discriminator
            sed_type="flat",      # 預設的光譜分佈
            temperature_k=None,   # flat 模式下不需要溫度，明確給 None
            redshift=0.0,         # 預設紅移為 0
            target_mag=18.0       # 這裡放你原本測試的星等 (18.0, 15.0 或 5.0)
        ),
        environment=base_environment,
        options=SolveForSNR(
            exposure_time=ArrayInput(values=[10.0])
        )
    )
    
    response = calculator.calculate(request)
    
    # 驗證 pixel scale (8m 焦距配 13.5um 像素，大約是 0.348 arcsec/pix)
    assert 0.34 < response.pixel_scale < 0.35