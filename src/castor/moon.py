from skyfield.api import load, wgs84, Star, Timescale
from skyfield.almanac import fraction_illuminated
import numpy as np

from castor.schema import ObservationRequest

# moon.py

def calc_moonlight_background(
    request: ObservationRequest, 
) -> float | None:
    
    if request.target.ra is None or request.target.dec is None:
        return None 
    
    if request.environment.observatory_position is None:
        return None 
    
    if request.environment.observing_time is None:
        return None 
    
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

    moon_phase = fraction_illuminated(eph, 'moon', t) 

    target_observation = obs_position.at(t).observe(target_star).apparent()
    moon_target_separation_deg = target_observation.separation_from(moon_observation).degrees

    return calc_moonlight_environment(
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
