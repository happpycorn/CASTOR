import math
import numpy as np
from datetime import timedelta

from castor import schema
from castor import physics
from castor import moon
# 為了不重複造輪子，我們直接借用 calculator 的輔助函數
from castor.calculator import _unify_flux

__all__ = ["run_batch_calculation"]

# ==========================================
# Helper: Time-Series Expansion
# ==========================================

def _expand_time_series(start: schema.AwareDatetime, end: schema.AwareDatetime, step_minutes: float) -> list[str]:
    """將使用者的開始與結束時間，依據 step_minutes 展開成離散的 ISO 8601 字串陣列"""
    times = []
    current = start
    delta = timedelta(minutes=step_minutes)
    
    max_points = 1000 
    
    while current <= end and len(times) < max_points:
        times.append(current.isoformat())
        current += delta
        
    return times

# ==========================================
# Main Batch Orchestrator
# ==========================================

def run_batch_calculation(request: schema.BatchObservationRequest) -> schema.BatchObservationResponse:
    """
    CASTOR 批次計算管線。
    接收時間序列合約，展開陣列並利用 NumPy Broadcasting 一次性完成整晚的物理計算。
    """
    inst = request.instrument
    tgt = request.target
    env = request.environment
    opt = request.options

    # ---------------------------------------------------------
    # Phase 0: 展開時間序列矩陣
    # ---------------------------------------------------------
    time_series_iso = _expand_time_series(env.start_time_utc, env.end_time_utc, env.time_step_minutes)
    if not time_series_iso:
        raise ValueError("Time series expansion resulted in an empty array. Check start and end times.")

    # ---------------------------------------------------------
    # Phase 1: 動態幾何與陣列物理量
    # ---------------------------------------------------------
    # Astropy 與 moon.py 會直接吐出與 time_series_iso 等長的 NumPy 陣列
    alpha_arr, rho_arr, z_moon_arr, z_target_arr = moon.get_moon_and_target_geometry(
        target_ra=tgt.ra, target_dec=tgt.dec,
        obs_time_utc=time_series_iso,
        lon=env.location.longitude_deg, lat=env.location.latitude_deg,
        elevation=env.location.elevation_m
    )
    
    # 批次安全處理天頂角 (np.clip 取代 min)
    z_target_safe = np.clip(z_target_arr, 0.0, 89.0)
    airmass_arr = physics.calculate_airmass(z_target_safe)
    
    mu_sky_arr = moon.calculate_sky_brightness(
        target_ra=tgt.ra, target_dec=tgt.dec,
        obs_time_utc=time_series_iso, mu_dark=env.mu_dark,
        lon=env.location.longitude_deg, lat=env.location.latitude_deg,
        elevation=env.location.elevation_m
    )

    # 固定硬體參數前置計算 (純量 Scalars)
    eff_area = float(physics.calculate_effective_area(inst.telescope.primary_mirror_diameter, inst.telescope.secondary_mirror_diameter))
    photon_energy = float(physics.calculate_photon_energy(inst.optic_filter.central_wavelength))
    total_throughput = float(physics.calculate_total_throughput(inst.telescope.optical_throughput, inst.optic_filter.filter_transmission, inst.camera.quantum_efficiency))
    pixel_scale = float(physics.calculate_pixel_scale(inst.camera.pixel_pitch, inst.telescope.focal_length))
    total_fwhm = float(physics.calculate_total_fwhm(env.seeing_fwhm, env.diffraction_fwhm, env.optical_fwhm, env.tracking_fwhm))
    n_pix, f_enc = physics.calculate_aperture_geometry(opt.aperture_factor, total_fwhm, pixel_scale)
    n_pix, f_enc = float(n_pix), float(f_enc)

    # ---------------------------------------------------------
    # Phase 2: NumPy Broadcasting 計算光電子計數
    # ---------------------------------------------------------
    f_lambda_target = _unify_flux(tgt.brightness, inst.optic_filter.central_wavelength)
    
    # 注意：f_lambda_sky_arr 現在是一個陣列，因為 mu_sky_arr 是隨時間變動的
    f_lambda_sky_arr = physics.convert_ab_to_wavelength_flux(mu_sky_arr, inst.optic_filter.central_wavelength)

    # 這裡發生廣播魔法：純量與陣列交織，吐出整晚的計數率變化曲線
    sky_rate_arr = physics.calculate_sky_background_rate(
        f_lambda_sky_arr, env.extinction_coeff, airmass_arr, 
        inst.optic_filter.filter_bandwidth, eff_area, photon_energy, total_throughput, pixel_scale
    )

    match tgt.morphology:
        case schema.PointMorphology():
            source_rate_arr = physics.calculate_point_source_rate(
                f_lambda_target, env.extinction_coeff, airmass_arr,
                inst.optic_filter.filter_bandwidth, eff_area, photon_energy, total_throughput, f_enc
            )
        case schema.ExtendedMorphology():
            source_rate_arr = physics.calculate_extended_source_rate(
                f_lambda_target, env.extinction_coeff, airmass_arr,
                inst.optic_filter.filter_bandwidth, eff_area, photon_energy, total_throughput, n_pix, pixel_scale
            )
        case _:
            raise ValueError("Unknown target morphology")

    peak_rate_arr = physics.calculate_peak_pixel_rate(source_rate_arr, total_fwhm, pixel_scale)

    # ---------------------------------------------------------
    # Phase 3: 向量化策略解算
    # ---------------------------------------------------------
    single_snr_arr = physics.calculate_single_snr(
        source_rate_arr, sky_rate_arr, inst.camera.dark_current_rate, inst.camera.readout_noise,
        n_pix, opt.single_exp_time
    )

    match opt:
        case schema.BatchSolveForSNR(num_exposures=n_exp):
            total_exp_time = opt.single_exp_time * n_exp
            total_snr_arr = physics.calculate_total_snr(
                source_rate_arr, sky_rate_arr, inst.camera.dark_current_rate, inst.camera.readout_noise,
                n_pix, opt.single_exp_time, total_exp_time, n_exp
            )

        case schema.BatchSolveForTime(target_snr=t_snr):
            # 批次反推曝光：每一個時間點所需的曝光次數都不同！
            req_exp_float_arr = physics.solve_required_exposures(t_snr, single_snr_arr)
            
            # 使用 numpy 向量化的 ceil
            req_exp_int_arr = np.ceil(req_exp_float_arr)
            total_exp_time_arr = opt.single_exp_time * req_exp_int_arr
            
            total_snr_arr = physics.calculate_total_snr(
                source_rate_arr, sky_rate_arr, inst.camera.dark_current_rate, inst.camera.readout_noise,
                n_pix, opt.single_exp_time, total_exp_time_arr, req_exp_int_arr
            )
            
        case _:
            raise ValueError("Unknown batch calculation option")

    t_sat_arr = physics.calculate_saturation_time(
        inst.camera.full_well_capacity, peak_rate_arr, sky_rate_arr, inst.camera.dark_current_rate
    )
    
    warnings = []
    # 如果時間序列中有「任何一個點」的 Airmass 超過 2.0，就亮起警告
    if np.any(airmass_arr > 2.0):
        warnings.append("Airmass > 2.0 detected in time series: Extinction model accuracy may degrade.")

    # ---------------------------------------------------------
    # Phase 4: NumPy Array 轉回 Python List 以滿足 Pydantic 合約
    # ---------------------------------------------------------
    # np.atleast_1d 確保即使只展開了一個時間點，它也能順利變成 list，而不會當機
    def to_list(arr) -> list[float]:
        return np.atleast_1d(arr).tolist()

    return schema.BatchObservationResponse(
        core=schema.BatchCoreResult(
            timestamps_iso=time_series_iso,
            total_snr=to_list(total_snr_arr),
            single_snr=to_list(single_snr_arr),
            saturation_time_limit=to_list(t_sat_arr)
        ),
        flags=schema.SystemFlags(
            # 只要整晚有任何一個時刻會造成飽和，is_saturated 就是 True
            is_saturated=bool(np.any(opt.single_exp_time > t_sat_arr)),
            warnings=warnings
        )
    )