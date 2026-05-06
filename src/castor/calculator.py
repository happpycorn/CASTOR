from typing import List
from castor import physics  # 假設你的物理公式都在這個 module
from castor.schema import ObservationRequest, CastorResponse

class CastorCalculator:
    """
    The core calculator for CASTOR ETC.
    It bridges the ObservationRequest payload with the pure physics engine.
    """
    
    def calculate(self, request: ObservationRequest) -> CastorResponse:
        # ==========================================
        # 階段 1 & 2：預計算 (與時間/SNR 無關的常數)
        # ==========================================
        
        # 1. 幾何與硬體常數
        eff_area = physics.calc_telescope_area(
            request.telescope.diameter_m, 
            request.telescope.central_obstruction_linear_ratio
        )
        
        pixel_scale = physics.calc_pixel_scale(
            request.telescope.focal_length_m, 
            request.camera.pixel_size_micron
        )
        
        # 2. 能量與效率
        wavelength_m = request.instrument_filter.central_wavelength_nm * 1e-9
        photon_energy = physics.calc_photon_energy(wavelength_m)
        
        throughput = physics.calc_throughput(
            request.telescope.m1_reflectance,
            request.telescope.m2_reflectance,
            request.instrument_filter.peak_transmission,
            request.telescope.glass_transmission,
            request.camera.quantum_efficiency
        )

        # 3. 孔徑 (Aperture) 邏輯
        # 若使用者未提供，預設為 seeing 的 1.5 倍
        aperture_radius = request.aperture_radius_arcsec or (request.seeing_fwhm_arcsec * 1.5)
        aperture_area = physics.calc_aperture_area(aperture_radius)
        n_pix_ap = physics.calc_npix_aperture(aperture_area, pixel_scale)
        flux_fraction = physics.calc_flux_in_aperture(aperture_radius, request.seeing_fwhm_arcsec)

        # 4. 計算核心率值 (Rates)
        # 消光：若未提供，退回濾鏡預設值
        extinction = request.extinction_coeff or request.instrument_filter.default_extinction
        filter_width_m = request.instrument_filter.fwhm_nm * 1e-9

        source_rate = physics.calc_source_count_rate(
            request.instrument_filter.zero_mag_flux,
            request.target_mag,
            extinction,
            request.airmass,
            filter_width_m,
            eff_area,
            photon_energy,
            throughput,
            flux_fraction
        )

        sky_rate = physics.calc_sky_count_rate(
            request.instrument_filter.zero_mag_flux,
            request.sky_brightness_mag_arcsec2,
            filter_width_m,
            eff_area,
            pixel_scale,
            photon_energy,
            throughput
        )

        readout_time = physics.calc_readout_time(
            request.camera.resolution_x,
            request.camera.resolution_y,
            request.camera.readout_speed_khz,
            request.camera.n_amplifiers
        )

        # ==========================================
        # 階段 3 & 4：陣列迭代與包裝
        # ==========================================
        
        # 準備輸出陣列
        out_snr = []
        out_time = []
        out_noise = []
        out_sat = []
        out_obs_time = []
        warnings = []
        
        # 取得實際運用的 Gain 與 Full Well
        actual_gain = request.gain_override or request.camera.gain
        full_well = request.camera.full_well_capacity_e

        # 模式 A：已知時間陣列算 SNR
        if request.exposure_time is not None:
            out_time = request.exposure_time
            for t in request.exposure_time:
                # 算 SNR 與 雜訊
                noise, snr = physics.calc_total_noise_and_snr(
                    source_rate, sky_rate, request.camera.dark_current_e_per_sec,
                    request.camera.read_noise_e, n_pix_ap, t
                )
                out_snr.append(snr)
                out_noise.append(noise)
                
                # 算總訊號與檢查飽和
                total_signal_e = physics.calc_total_signal(source_rate, t)
                is_sat = (full_well is not None) and (total_signal_e > full_well)
                out_sat.append(is_sat)
                
                # 算總觀測時間
                out_obs_time.append(physics.calc_total_observation_time(t, readout_time))

        # 模式 B：已知 SNR 陣列反推時間
        elif request.target_snr is not None:
            out_snr = request.target_snr
            for target in request.target_snr:
                req_t = physics.calc_exposure_time(
                    source_rate, sky_rate, request.camera.dark_current_e_per_sec,
                    request.camera.read_noise_e, target, n_pix_ap
                )
                out_time.append(req_t)
                
                # 為了結構完整，把目標時間的雜訊也算出來
                noise, _ = physics.calc_total_noise_and_snr(
                    source_rate, sky_rate, request.camera.dark_current_e_per_sec,
                    request.camera.read_noise_e, n_pix_ap, req_t
                )
                out_noise.append(noise)
                
                total_signal_e = physics.calc_total_signal(source_rate, req_t)
                is_sat = (full_well is not None) and (total_signal_e > full_well)
                out_sat.append(is_sat)
                
                out_obs_time.append(physics.calc_total_observation_time(req_t, readout_time))
        
        if any(out_sat):
            warnings.append("Warning: Some requested parameters exceed the camera's full well capacity. The target will be saturated.")

        return CastorResponse(
            snr=out_snr,
            exposure_time=out_time,
            total_noise_e=out_noise,
            is_saturated=out_sat,
            total_observation_time_sec=out_obs_time,
            source_rate_e_sec=source_rate,
            sky_rate_e_sec_pix=sky_rate,
            pixel_scale=pixel_scale,
            readout_time_sec=readout_time,
            warnings=warnings
        )