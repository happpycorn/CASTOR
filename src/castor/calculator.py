from typing import cast
from castor import physics
from castor.schema import ObservationRequest, CastorResponse

import numpy as np
from castor import physics
from castor.schema import (
    ObservationRequest, CastorResponse, InputValue,
    SNRResponse, TimeResponse, PointTarget, ExtendedTarget,
    TargetProfile, InstrumentProfile, EnvironmentCondition,
    SolveForTime, SolveForSNR, TimeResponse,
)

from castor import moon

class CastorCalculator:
    def calculate(self, request: ObservationRequest) -> CastorResponse:

        # Context Enrichment        
        moon.calc_moonlight_background(request)

        # Core Computation
        hw = self._precompute_hardware_constants(request.instrument)
        
        pixel_scale = hw["pixel_scale"]
        filter_width_m = request.instrument.optic_filter.fwhm_nm * 1e-9
        zero_mag_flux_si = request.instrument.optic_filter.zero_mag_flux * 1e9
        
        sky_rate = physics.calc_sky_count_rate(
            zero_mag_flux_si,
            request.environment.sky_brightness_mag_arcsec2,
            filter_width_m, hw["eff_area"], pixel_scale,
            hw["photon_energy"], hw["throughput"]
        )
        
        readout_time = physics.calc_readout_time(
            request.instrument.camera.resolution_x,
            request.instrument.camera.resolution_y,
            request.instrument.camera.readout_speed_khz,
            request.instrument.camera.n_amplifiers
        )
        
        source_rate, hw["n_pix_ap"] = self._resolve_source_rate(
            request.target, request.instrument, request.environment, 
            hw["eff_area"], hw["photon_energy"], hw["throughput"], hw["pixel_scale"]
        )
        
        if request.options.type == "solve_snr":
            return self._execute_solve_snr(
                request, source_rate, sky_rate, pixel_scale, readout_time, hw["n_pix_ap"]
            )
        elif request.options.type == "solve_time":
            return self._execute_solve_time(
                request, source_rate, sky_rate, pixel_scale, readout_time, hw["n_pix_ap"]
            )
        else:
            raise ValueError(f"Unknown calculation type: {request.options.type}")

    def _precompute_hardware_constants(self, instrument) -> dict:
        hw = {}

        hw["eff_area"] = physics.calc_telescope_area(
            instrument.telescope.diameter_m, 
            instrument.telescope.central_obstruction_linear_ratio
        )
        
        hw["pixel_scale"] = physics.calc_pixel_scale(
            instrument.telescope.focal_length_m, 
            instrument.camera.pixel_size_micron
        )

        wavelength_m = instrument.optic_filter.central_wavelength_nm * 1e-9
        hw["photon_energy"] = physics.calc_photon_energy(wavelength_m)
        
        hw["throughput"] = physics.calc_throughput(
            instrument.telescope.m1_reflectance,
            instrument.telescope.m2_reflectance,
            instrument.optic_filter.peak_transmission,
            instrument.telescope.glass_transmission,
            instrument.camera.quantum_efficiency
        )

        return hw

    def _resolve_source_rate(
        self, 
        target: TargetProfile, 
        instrument: InstrumentProfile, 
        environment: EnvironmentCondition, 
        eff_area: float, 
        photon_energy: float, 
        throughput: float,
        pixel_scale: float,
    ) -> tuple[float, float]:
        zero_mag_flux = instrument.optic_filter.zero_mag_flux * 1e9
        airmass = environment.airmass
        filter_width_m = instrument.optic_filter.fwhm_nm * 1e-9

        extinction = environment.extinction_coeff or instrument.optic_filter.default_extinction

        aperture_radius = environment.seeing_fwhm_arcsec * 1.5
        aperture_area = physics.calc_aperture_area(aperture_radius)

        n_pix_ap = physics.calc_npix_aperture(aperture_area, pixel_scale)

        if target.type == "point":
            flux_fraction = physics.calc_flux_in_aperture(aperture_radius, environment.seeing_fwhm_arcsec)
            
            source_rate = physics.calc_source_count_rate(
                zero_mag_flux=zero_mag_flux,
                source_mag=target.target_mag,  # 點源星等
                extinction=extinction,
                airmass=airmass,
                filter_width_m=filter_width_m,
                telescope_area_m2=eff_area,
                photon_energy_j=photon_energy,
                total_throughput=throughput,
                enclosed_flux_fraction=flux_fraction
            )
            return source_rate, n_pix_ap

        elif target.type == "extended":
            equivalent_mag = target.surface_brightness - 2.5 * np.log10(aperture_area)
            
            source_rate = physics.calc_source_count_rate(
                zero_mag_flux=zero_mag_flux,
                source_mag=equivalent_mag,
                extinction=extinction,
                airmass=airmass,
                filter_width_m=filter_width_m,
                telescope_area_m2=eff_area,
                photon_energy_j=photon_energy,
                total_throughput=throughput,
                enclosed_flux_fraction=1.0
            )
            return source_rate, n_pix_ap
            
        else:
            raise ValueError(f"Unsupported target type: {target.type}")

    def _normalize_input(self, input_value: InputValue) -> np.ndarray:
        if input_value.type == "single":
            return np.array([input_value.value])
        return np.array(input_value.values)

    def _execute_solve_snr(
        self, 
        request: ObservationRequest, 
        source_rate: float, 
        sky_rate: float, 
        pixel_scale: float, 
        readout_time: float, 
        n_pix_ap: float
    ) -> SNRResponse:
        options = cast(SolveForSNR, request.options)
        times = self._normalize_input(options.exposure_time)

        dark_current = request.instrument.camera.dark_current_e_per_sec
        read_noise = request.instrument.camera.read_noise_e
        full_well = request.instrument.camera.full_well_capacity_e
        
        noise_arr, snr_arr = physics.calc_total_noise_and_snr(
            source_count_rate=source_rate,
            sky_count_rate=sky_rate,
            dark_count_rate=dark_current,
            readout_noise=read_noise,
            n_pix_aperture=n_pix_ap,
            exposure_time=times
        )
        
        total_signal_e = physics.calc_total_signal(source_rate, times)
        if full_well is not None: sat_arr = total_signal_e > full_well
        else: sat_arr = np.zeros_like(times, dtype=bool)
            
        obs_time_arr = physics.calc_total_observation_time(times, readout_time)

        warnings = []
        if np.any(sat_arr):
            warnings.append("Warning: Some requested parameters exceed the camera's full well capacity. The target will be saturated.")
            
        return SNRResponse(
            source_rate_e_sec=source_rate,
            sky_rate_e_sec_pix=sky_rate,
            pixel_scale=pixel_scale,
            readout_time_sec=readout_time,
            total_noise_e=noise_arr.tolist(),
            is_saturated=sat_arr.tolist(),
            total_observation_time_sec=obs_time_arr.tolist(),
            warnings=warnings,
            calculated_snr=snr_arr.tolist(),
            input_exposure_time=times.tolist(),
            type="snr_result",
        )

    def _execute_solve_time(
        self, 
        request: ObservationRequest, 
        source_rate: float, 
        sky_rate: float, 
        pixel_scale: float, 
        readout_time: float, 
        n_pix_ap: float
    ) -> TimeResponse:
        options = cast(SolveForTime, request.options)
        target_snrs = self._normalize_input(options.target_snr)

        dark_current = request.instrument.camera.dark_current_e_per_sec
        read_noise = request.instrument.camera.read_noise_e
        full_well = request.instrument.camera.full_well_capacity_e

        times_arr = physics.calc_exposure_time(
            source_count_rate=source_rate,
            sky_count_rate=sky_rate,
            dark_count_rate=dark_current,
            readout_noise=read_noise,
            target_snr=target_snrs,
            n_pix_aperture=n_pix_ap
        )

        noise_arr, _ = physics.calc_total_noise_and_snr(
            source_count_rate=source_rate,
            sky_count_rate=sky_rate,
            dark_count_rate=dark_current,
            readout_noise=read_noise,
            n_pix_aperture=n_pix_ap,
            exposure_time=times_arr
        )

        total_signal_e = physics.calc_total_signal(source_rate, times_arr)
        if full_well is not None: sat_arr = total_signal_e > full_well
        else: sat_arr = np.zeros_like(times_arr, dtype=bool)

        obs_time_arr = physics.calc_total_observation_time(times_arr, readout_time)

        warnings = []
        if np.any(sat_arr):
            warnings.append("Warning: Some requested parameters exceed the camera's full well capacity. The target will be saturated.")

        return TimeResponse(
            source_rate_e_sec=source_rate,
            sky_rate_e_sec_pix=sky_rate,
            pixel_scale=pixel_scale,
            readout_time_sec=readout_time,
            total_noise_e=noise_arr.tolist(),
            is_saturated=sat_arr.tolist(),
            total_observation_time_sec=obs_time_arr.tolist(),
            warnings=warnings,
            calculated_exposure_time=times_arr.tolist(),
            input_target_snr=target_snrs.tolist(),
            type="time_result",
        )
