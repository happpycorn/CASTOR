import numpy as np
from scipy import constants

__all__ = [
    "calc_pixel_scale",
    "calc_telescope_area",
    "calc_aperture_area",
    "calc_npix_aperture",
    "calc_photon_energy",
    "calc_throughput",
    "calc_flux_in_aperture",
    "calc_source_count_rate",
    "calc_sky_count_rate",
    "calc_exposure_time",
    "calc_total_noise_and_snr",
    "calc_total_signal",
    "calc_readout_time",
    "calc_total_observation_time"
]

PLANCK_CONSTANT, SPEED_OF_LIGHT = constants.h, constants.c

# ==========================================
# 1. Spatial & Geometry (空間與幾何光學)
# ==========================================

def calc_pixel_scale(focal_length_m: float, pixel_size_micron: float) -> float:
    """
    Calculate the pixel scale of the instrument in arcseconds per pixel.
    (Assumes inputs are strictly positive and validated by the caller)

    Args:
        focal_length_m (float): The effective focal length of the telescope in meters.
        pixel_size_micron (float): The physical size of a single pixel on the CCD in microns.

    Returns:
        float: The pixel scale in arcseconds per pixel (arcsec/pix).
    """
    pixel_size_m = pixel_size_micron * 1e-6
    scale_radians = pixel_size_m / focal_length_m
    scale_arcsec = scale_radians * (180.0 / constants.pi) * 3600.0
    
    return scale_arcsec

def calc_telescope_area(diameter_m: float) -> float:
    """
    Calculate the effective light-gathering area of the telescope's primary mirror.
    (Assumes diameter is strictly positive and validated by the caller)

    Args:
        diameter_m (float): The diameter of the primary mirror in meters.

    Returns:
        float: The effective gathering area in square meters.
    """
    radius = diameter_m / 2.0
    area = constants.pi * (radius ** 2)
    
    return area

def calc_aperture_area(aperture_radius_arcsec: float) -> float:
    """
    Calculate the area of the software aperture on the celestial sphere.
    (Assumes radius is non-negative and validated by the caller)

    Args:
        aperture_radius_arcsec (float): The radius of the measurement aperture in arcseconds.

    Returns:
        float: The area of the aperture in square arcseconds.
    """
    area = constants.pi * (aperture_radius_arcsec ** 2)
    return area

def calc_npix_aperture(aperture_area_sq_arcsec: float, pixel_scale_arcsec_per_pix: float) -> float:
    """
    Calculate the number of pixels covered by the software aperture on the CCD.
    (Assumes inputs are valid, non-negative, and pixel_scale > 0)

    Args:
        aperture_area_sq_arcsec (float): The area of the aperture in square arcseconds.
        pixel_scale_arcsec_per_pix (float): The pixel scale in arcseconds per pixel.

    Returns:
        float: The number of pixels enclosed by the aperture.
    """
    pixel_area_sq_arcsec = pixel_scale_arcsec_per_pix ** 2
    n_pixels = aperture_area_sq_arcsec / pixel_area_sq_arcsec
    
    return n_pixels

# ==========================================
# 2. Photon & Energy (光子與能量轉換)
# ==========================================

def calc_photon_energy(wavelength_m: float) -> float:
    """
    Calculate the energy of a single photon at a given wavelength.

    Args:
        wavelength_m (float): The wavelength of the photon in meters.

    Returns:
        float: The energy of the photon in Joules.
    """
    # h = Planck constant, c = Speed of light
    return (constants.h * constants.c) / wavelength_m

def calc_throughput(
    m1_reflectance: float, 
    m2_reflectance: float, 
    filter_transmittance: float, 
    glass_transmittance: float, 
    quantum_efficiency: float
) -> float:
    """
    Calculate the total system throughput by multiplying various efficiency factors.
    (Assumes all inputs are ratios between 0.0 and 1.0)

    Args:
        m1_reflectance (float): Reflectance of the primary mirror.
        m2_reflectance (float): Reflectance of the secondary mirror.
        filter_transmittance (float): Peak transmittance of the filter.
        glass_transmittance (float): Transmittance of the camera glass window.
        quantum_efficiency (float): Quantum efficiency (QE) of the CCD at the given band.

    Returns:
        float: The total system throughput as a ratio (0.0 to 1.0).
    """
    # Simply the product of all efficiency stages
    return m1_reflectance * m2_reflectance * filter_transmittance * glass_transmittance * quantum_efficiency

def calc_flux_in_aperture(aperture_radius_arcsec: float, seeing_arcsec: float) -> float:
    """
    Calculate the fraction of source flux enclosed within a software aperture, 
    assuming a 2D Gaussian Point Spread Function (PSF).
    (Assumes inputs are positive. Uses a numerical integration approximation)

    Args:
        aperture_radius_arcsec (float): The radius of the measurement aperture in arcseconds.
        seeing_arcsec (float): The FWHM of the atmospheric seeing in arcseconds.

    Returns:
        float: The enclosed flux fraction (0.0 to 1.0).
    """
    # sigma = FWHM / sqrt(8 * ln(2))
    sigma = seeing_arcsec / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    fraction = 1.0 - np.exp(-(aperture_radius_arcsec**2) / (2.0 * sigma**2))
    
    return fraction

# ==========================================
# 3. Rates: e-/sec (每秒訊號計數率)
# ==========================================

def calc_source_count_rate(
    zero_mag_flux: float,
    source_mag: float,
    extinction: float,
    airmass: float,
    filter_width_m: float,
    telescope_area_m2: float,
    photon_energy_j: float,
    total_throughput: float,
    enclosed_flux_fraction: float
) -> float:
    """
    Calculate the source count rate in electrons per second.
    (Assumes all inputs are pre-validated positive floats)

    Args:
        zero_mag_flux (float): Flux of a 0-mag star (W m^-2 m^-1).
        source_mag (float): Magnitude of the target source.
        extinction (float): Atmospheric extinction coefficient (mag/airmass).
        airmass (float): Airmass of the observation.
        filter_width_m (float): Full-width of the filter passband in meters.
        telescope_area_m2 (float): Effective area of the telescope in m^2.
        photon_energy_j (float): Energy of a single photon in Joules.
        total_throughput (float): Combined efficiency of the system.
        enclosed_flux_fraction (float): Fraction of flux within the aperture.

    Returns:
        float: Source count rate (e-/sec).
    """
    # 1. Calculate the flux of the source at the top of the atmosphere, 
    # then apply extinction
    flux = zero_mag_flux * 10**(-0.4 * (source_mag + extinction * airmass))
    
    # 2. Total power (Watts) received by the telescope within the filter band
    total_power = flux * filter_width_m * telescope_area_m2
    
    # 3. Convert power to photon rate, apply throughput and aperture fraction
    source_count_rate = (total_power / photon_energy_j) * total_throughput * enclosed_flux_fraction
    
    return source_count_rate

def calc_sky_count_rate(
    zero_mag_flux: float,
    sky_brightness: float,
    filter_width_m: float,
    telescope_area_m2: float,
    pixel_scale_arcsec_per_pix: float,
    photon_energy_j: float,
    total_throughput: float
) -> float:
    """
    Calculate the sky background count rate per pixel in electrons per second.
    (Assumes all inputs are pre-validated positive floats)

    Args:
        zero_mag_flux (float): Flux of a 0-mag star (W m^-2 m^-1).
        sky_brightness (float): Sky background brightness (mag/arcsec^2).
        filter_width_m (float): Full-width of the filter passband in meters.
        telescope_area_m2 (float): Effective area of the telescope in m^2.
        pixel_scale_arcsec_per_pix (float): Pixel scale (arcsec/pix).
        photon_energy_j (float): Energy of a single photon in Joules.
        total_throughput (float): Combined efficiency of the system.

    Returns:
        float: Sky count rate per pixel (e-/sec/pix).
    """
    # 1. Calculate sky flux per square arcsecond
    sky_flux_per_arcsec2 = zero_mag_flux * 10**(-0.4 * sky_brightness)
    
    # 2. Total power per pixel (Watts/pix)
    # We multiply by the square of pixel_scale to convert area to per-pixel.
    power_per_pix = sky_flux_per_arcsec2 * filter_width_m * telescope_area_m2 * (pixel_scale_arcsec_per_pix**2)
    
    # 3. Convert power to photon rate and apply throughput[cite: 4, 6]
    sky_count_rate = (power_per_pix / photon_energy_j) * total_throughput
    
    return sky_count_rate

# ==========================================
# 4. Observation Metrics (觀測指標評估)
# ==========================================

def calc_total_signal(source_count_rate: float, exposure_time: float) -> float:
    """
    Calculate the total accumulated electrons from the source over a given exposure time.

    Args:
        source_count_rate (float): Source count rate in e-/sec.
        exposure_time (float): Exposure time in seconds.

    Returns:
        float: Total source signal in electrons.
    """
    return source_count_rate * exposure_time

def calc_readout_time(
    npix1: int, 
    npix2: int, 
    readout_speed_khz: float, 
    n_amplifiers: int
) -> float:
    """
    Calculate the time required to read out the CCD image.

    Args:
        npix1 (int): Number of pixels in the first dimension.
        npix2 (int): Number of pixels in the second dimension.
        readout_speed_khz (float): Readout speed in kHz.
        n_amplifiers (int): Number of amplifiers used for readout.

    Returns:
        float: Total readout time in seconds.
    """
    # Convert sampling rate from kHz to Hz
    sampling_rate_hz = readout_speed_khz * 1000.0
    total_pixels = float(npix1 * npix2)
    
    # Readout time = total pixels / (sampling rate per amplifier * number of amplifiers)[cite: 4, 6]
    return total_pixels / sampling_rate_hz / n_amplifiers

def calc_total_observation_time(exposure_time: float, readout_time: float) -> float:
    """
    Calculate the total telescope time required, including exposure and overhead.

    Args:
        exposure_time (float): The actual exposure/integration time in seconds.
        readout_time (float): The camera readout overhead in seconds.

    Returns:
        float: Total observation time in seconds.
    """
    return exposure_time + readout_time

def calc_total_noise_and_snr(
    source_count_rate: float,
    sky_count_rate: float,
    dark_count_rate: float,
    readout_noise: float,
    n_pix_aperture: float,
    exposure_time: float
) -> tuple[float, float]:
    """
    Calculate the total noise components and the final signal-to-noise ratio (SNR).

    Args:
        source_count_rate (float): Source count rate in e-/sec.
        sky_count_rate (float): Sky background count rate in e-/sec/pix.
        dark_count_rate (float): Dark current count rate in e-/sec/pix.
        readout_noise (float): Readout noise in e-/pix.
        n_pix_aperture (float): Number of pixels within the aperture.
        exposure_time (float): Exposure time in seconds.

    Returns:
        tuple[float, float]: A tuple containing (total_noise, snr).
    """
    signal = source_count_rate * exposure_time
    
    # Variance = Signal + Npix * (SkySignal + DarkSignal + ReadoutNoise^2)
    variance = (
        signal + 
        n_pix_aperture * (
            (sky_count_rate * exposure_time) + 
            (dark_count_rate * exposure_time) + 
            (readout_noise ** 2)
        )
    )
    total_noise = np.sqrt(variance)
    snr = signal / total_noise
    
    return total_noise, snr

def calc_exposure_time(
    source_count_rate: float,
    sky_count_rate: float,
    dark_count_rate: float,
    readout_noise: float,
    target_snr: float,
    n_pix_aperture: float
) -> float:
    """
    Reverse-calculate the required exposure time to achieve a target SNR 
    by solving a quadratic equation.

    Args:
        source_count_rate (float): Source count rate in e-/sec.
        sky_count_rate (float): Sky background count rate in e-/sec/pix.
        dark_count_rate (float): Dark current count rate in e-/sec/pix.
        readout_noise (float): Readout noise in e-/pix.
        target_snr (float): Requested signal-to-noise ratio.
        n_pix_aperture (float): Number of pixels within the aperture.

    Returns:
        float: Required exposure time in seconds.
    """
    # Coefficients for the quadratic equation: a*t^2 - b*t + c = 0
    a = source_count_rate ** 2
    b = (target_snr ** 2) * (source_count_rate + n_pix_aperture * (sky_count_rate + dark_count_rate))
    c = - (target_snr ** 2) * (readout_noise ** 2) * n_pix_aperture
    
    # Solve for t using the positive root of the quadratic formula[cite: 4, 6, 7]
    exposure_time = (b + np.sqrt(b**2 - 4 * a * c)) / (2 * a)
    
    return exposure_time
