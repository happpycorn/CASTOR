import pytest
import numpy as np
from castor.physics import (
    calc_pixel_scale,
    calc_telescope_area,
    calc_photon_energy,
    calc_throughput,
    calc_flux_in_aperture,
    calc_source_count_rate,
    calc_exposure_time,
    calc_total_noise_and_snr
)

# ----------------------------------------------------------------------
# 1. Spatial & Geometry Tests
# ----------------------------------------------------------------------

def test_calc_pixel_scale_lulin_2m():
    """Verify pixel scale for Lulin 2-m telescope with 20 micron pixels."""
    # Based on etc2.cgi: focal=15.0, pixelsize=20.0 -> approx 0.275 arcsec/pix
    focal_m = 15.0
    pix_micron = 20.0
    result = calc_pixel_scale(focal_m, pix_micron)
    assert pytest.approx(result, rel=1e-4) == 0.2750

def test_calc_telescope_area_1m():
    """Verify gathering area for Lulin 1-m telescope."""
    # Area = pi * (0.5)^2 approx 0.78539[cite: 7]
    result = calc_telescope_area(1.0)
    assert pytest.approx(result, rel=1e-5) == np.pi * 0.25

# ----------------------------------------------------------------------
# 2. Photon & Energy Tests
# ----------------------------------------------------------------------

def test_calc_photon_energy_v_band():
    """Verify photon energy for V-band (~540nm)."""
    wavelength_m = 540e-9

    from castor.physics import PLANCK_CONSTANT, SPEED_OF_LIGHT
    
    expected = (PLANCK_CONSTANT * SPEED_OF_LIGHT) / wavelength_m
    result = calc_photon_energy(wavelength_m)
    
    assert result == pytest.approx(expected, rel=1e-9)

def test_calc_flux_in_aperture_gaussian():
    """Verify flux fraction using the analytical Gaussian solution."""
    # If aperture radius equals sigma, enclosed flux should be ~39.3%
    # If aperture radius = 2.3548 * sigma (i.e., radius = FWHM), enclosed flux is ~93.7%[cite: 4, 6]
    seeing = 1.0
    aperture = 1.0  # Radius = FWHM
    result = calc_flux_in_aperture(aperture, seeing)
    # 1 - exp(- (1^2) / (2 * (1/2.3548)^2)) approx 0.937
    assert result > 0.93 and result < 0.95

# ----------------------------------------------------------------------
# 3. Integration & Loop-back Tests (The "Big Boss")
# ----------------------------------------------------------------------

def test_snr_to_exposure_time_consistency():
    """
    Round-trip test: 
    Calculate SNR for a given time, then use that SNR to solve for time.
    The results must match.
    """
    # Mock parameters for a bright-ish source
    src_rate = 100.0   # e-/sec
    sky_rate = 10.0    # e-/sec/pix
    dark_rate = 0.1    # e-/sec/pix
    rd_noise = 5.0     # e-
    npix = 50.0        # pixels in aperture
    target_time = 300.0 # seconds
    
    # Step 1: Forward calculation (Get SNR)[cite: 5, 7]
    _, snr = calc_total_noise_and_snr(
        src_rate, sky_rate, dark_rate, rd_noise, npix, target_time
    )
    
    # Step 2: Reverse calculation (Solve for Time)[cite: 4, 6]
    solved_time = calc_exposure_time(
        src_rate, sky_rate, dark_rate, rd_noise, snr, npix
    )
    
    # They should be nearly identical
    assert pytest.approx(solved_time, rel=1e-5) == target_time

# ----------------------------------------------------------------------
# 4. Throughput & Rate Tests
# ----------------------------------------------------------------------

def test_calc_throughput_basic():
    """Verify total throughput calculation."""
    # 假設 M1=0.9, M2=0.9, Filter=0.8, Glass=0.95, QE=0.8
    result = calc_throughput(0.9, 0.9, 0.8, 0.95, 0.8)
    expected = 0.9 * 0.9 * 0.8 * 0.95 * 0.8  # 應為 0.49248
    assert pytest.approx(result) == expected

def test_calc_source_count_rate_standard():
    """Verify source count rate for a V=15 mag star."""
    # 模擬鹿林 1-m 望遠鏡與 V-band 參數
    params = {
        "zero_mag_flux": 3.6e-9,      # V-band 0等星通量
        "source_mag": 15.0,           # 15等星
        "extinction": 0.15,           # 大氣消光係數
        "airmass": 1.0,               # 天頂觀測
        "filter_width_m": 89e-9,      # V-band 頻寬
        "telescope_area_m2": 0.785,    # 1米口徑面積
        "photon_energy_j": 3.68e-19,  # V-band 單光子能量 (先前測過)
        "total_throughput": 0.5,      # 假設總穿透率 50%
        "enclosed_flux_fraction": 0.9 # 假設 90% 光線在光圈內
    }
    
    # 手動預算流程：
    # 1. 考慮消光後的星等 = 15 + (0.15 * 1.0) = 15.15
    # 2. Flux = 3.6e-9 * 10**(-0.4 * 15.15)
    # 3. Power = Flux * 89e-9 * 0.785
    # 4. Rate = (Power / 3.68e-19) * 0.5 * 0.9
    
    flux = params["zero_mag_flux"] * 10**(-0.4 * (params["source_mag"] + params["extinction"] * params["airmass"]))
    power = flux * params["filter_width_m"] * params["telescope_area_m2"]
    expected_rate = (power / params["photon_energy_j"]) * params["total_throughput"] * params["enclosed_flux_fraction"]
    
    result = calc_source_count_rate(**params)
    assert pytest.approx(result, rel=1e-5) == expected_rate