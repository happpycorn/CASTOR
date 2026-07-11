from skyfield.api import load, wgs84, Star, Timescale
from skyfield.almanac import fraction_illuminated
import numpy as np

from castor.schema import ObservationRequest

def calc_moonlight_background(
    request: ObservationRequest, 
) -> None:
    
    if request.target.ra is None or request.target.dec is None:
        return  # Cannot compute moonlight background without target coordinates
    
    if request.environment.observatory_position is None:
        return  # Cannot compute moonlight background without observatory 
    
    if request.environment.observing_time is None:
        return  # Cannot compute moonlight background without observing time
    
    eph = load('de421.bsp')
    

    target_star: Star = Star(
        ra_hours=request.target.ra,
        dec_degrees=request.target.dec
    )
    
    obs_position = eph['earth'] + wgs84.latlon(
        request.environment.observatory_position[0], 
        request.environment.observatory_position[1], 
        elevation_m=request.environment.observatory_position[2]
    )

    ts = load.timescale()
    t = ts.from_datetime(request.environment.observing_time)

    moon_observation = obs_position.at(t).observe(eph['moon']).apparent()
    alt, az, distance = moon_observation.altaz()

    moon_zenith_angle_deg = 90.0 - alt.degrees
    moon_phase = fraction_illuminated(eph, 'moon', t) * 100.0

    target_observation = obs_position.at(t).observe(target_star).apparent()
    moon_target_separation_deg = target_observation.separation_from(moon_observation).degrees

    request.environment.sky_brightness_mag_arcsec2 = calc_moonlight_environment(
        base_sky_mag=request.environment.sky_brightness_mag_arcsec2,
        moon_phase=moon_phase,
        separation_angle_deg=moon_target_separation_deg,
        moon_zenith_angle_deg=moon_zenith_angle_deg
    )

def calc_moonlight_environment(
    base_sky_mag: float,
    moon_phase: float,
    separation_angle_deg: float,
    moon_zenith_angle_deg: float
) -> float:
    """
    Calculate the effective sky background magnitude considering moonlight scattering.
    Based on a simplified Krisciunas and Schaefer (1991) model.
    (Assumes inputs are pre-validated by the caller)

    Args:
        base_sky_mag (float): The dark sky background brightness (mag/arcsec^2).
        moon_phase (float): Moon illuminated fraction (0.0 for New Moon, 1.0 for Full Moon).
        separation_angle_deg (float): Angle between the target and the moon in degrees.
        moon_zenith_angle_deg (float): Zenith angle of the moon in degrees.

    Returns:
        float: The degraded (brighter) effective sky background magnitude.
    """
    # 1. Constrain separation angle to prevent mathematical divergence 
    # The KS91 model is generally only valid for rho >= 10 degrees.
    separation_angle_deg = np.clip(separation_angle_deg, 10.0, 180.0)
    rho_rad = np.radians(separation_angle_deg)
    
    # 2. Calculate the core scattering function f(rho)
    # First term: Rayleigh scattering (air molecules)
    # Second term: Mie scattering (aerosols/particulates)
    f_rho = (10**5.36) * (1.06 + np.cos(rho_rad)**2) + 10**(6.15 - separation_angle_deg / 40.0)
    
    # 3. Calculate the relative moonlight flux factor
    # Incorporates the illuminated fraction and a simplified atmospheric extinction based on zenith angle
    moon_flux_factor = f_rho * moon_phase * np.exp(-0.4 * (moon_zenith_angle_deg / 90.0))
    
    # 4. Convert magnitudes to linear flux for superposition
    # The 1e-6 multiplier is an empirical scaling constant for this simplified model
    moon_sky_flux = moon_flux_factor * 1e-6 
    base_sky_flux = 10 ** (-0.4 * base_sky_mag)
    
    # 5. Calculate total flux and convert back to magnitude
    total_sky_flux = base_sky_flux + moon_sky_flux
    dynamic_sky_mag = -2.5 * np.log10(total_sky_flux)
    
    return dynamic_sky_mag

if __name__ == "__main__":
    from skyfield.api import load
    from castor.schema import ObservationRequest, PointTarget, ManualEnvironment, TelescopeSchema, CameraSchema, FilterSchema
    from datetime import datetime, timezone

    print("準備望遠鏡與環境參數...")

    # 1. 建立一個包含經緯度的環境 (鹿林天文台大約位置)
    # 假設你們的 schema 有擴充這些欄位，這裡用一個模擬的環境
    environment : ManualEnvironment = ManualEnvironment(
        sky_brightness_mag_arcsec2=21.0, # 原本無月的黑夜是 21 等
        airmass=1.2,
        seeing_fwhm_arcsec=1.5
    )
    # 動態加上 Skyfield 需要的參數 (這部分要看你們的 schema 怎麼設計，這裡先直接賦值測試)
    environment.observing_time = datetime(2026, 7, 2, 14, 0, tzinfo=timezone.utc) # 隨便挑一個有月亮的時間
    environment.observatory_position = (23.4686, 120.8736, 2862) # 鹿林天文台 (緯度, 經度, 海拔)

    # 2. 設定觀測目標 (假設目標在天赤道附近)
    target: PointTarget = PointTarget(
        target_mag=15.0,
        sed_type="flat",
        # ra 和 dec 需要改成包含三個 float 的 Tuple (請根據實際的時分秒/度分秒數值做調整)
        ra=(12.0, 0.0, 0.0), 
        dec=(0.0, 0.0, 0.0),
        
        # 補上缺少的必填參數 (以下數值請依你的實際觀測需求調整)
        temperature_k=None,  # 因為型別是 PositiveFloat | None
        redshift=0.0,        # 假設紅移為 0
        type="point"         # 型別限制為 Literal['point']，只能填 'point'
    )

    # 3. 隨便塞個硬體讓 Request 不會報錯 (沿用你上次查到的 LOT 數據)
    dummy_telescope = TelescopeSchema(diameter_m=1.0, focal_length_m=8.0)
    dummy_camera = CameraSchema(pixel_size_micron=15.0, resolution_x=2048, resolution_y=2048, read_noise_e=5.0, quantum_efficiency=0.85)
    dummy_filter = FilterSchema(name="V", central_wavelength_nm=550.0, fwhm_nm=89.0, zero_mag_flux=3.63e-11)

    # 4. 打包 Request
    instrument = {
        "telescope": dummy_telescope,
        "camera": dummy_camera,
        "optic_filter": dummy_filter
    }
    request = ObservationRequest(
        instrument=instrument,
        target=target,
        environment=environment,
        options={"type": "solve_snr", "exposure_time": {"type": "single", "value": 60.0}}
    )

    print(f"🌖 月光摧殘前，鹿林夜空背景亮度：{request.environment.sky_brightness_mag_arcsec2} 等")

    # 5. 啟動月光外掛！
    print("呼叫 Skyfield 計算月光散射模型...")
    calc_moonlight_background(request)

    print(f"✨ 月光摧殘後，實際動態背景亮度：{request.environment.sky_brightness_mag_arcsec2:.2f} 等")