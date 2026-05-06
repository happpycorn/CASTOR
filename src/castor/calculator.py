from pydantic import BaseModel, Field, PositiveFloat, model_validator
from typing import Optional
from castor.schema import TelescopeSchema, CameraSchema, FilterSchema
class ObservationRequest(BaseModel):
    """
    The complete contract for a CASTOR calculation request.
    This links hardware parameters with specific observation conditions.
    """
    # --- 1. Hardware Configuration ---
    telescope: TelescopeSchema
    camera: CameraSchema
    instrument_filter: FilterSchema

    # --- 2. Target Information ---
    target_mag: float = Field(
        ..., 
        description="The apparent magnitude of the target celestial object."
    )

    # --- 3. Observation Environment (Mandatory) ---
    sky_brightness_mag_arcsec2: float = Field(
        ..., 
        description="Sky background brightness in magnitude per square arcsecond (mag/arcsec^2)."
    )
    
    # --- 4. Environmental Variables (With Defaults) ---
    airmass: float = Field(
        1.0, 
        ge=1.0, 
        le=5.0, 
        description="Airmass of the observation (1.0 = Zenith)."
    )
    seeing_fwhm_arcsec: PositiveFloat = Field(
        1.5, 
        description="Atmospheric seeing FWHM in arcseconds. Used for PSF flux fraction."
    )
    extinction_coeff: Optional[float] = Field(
        None, 
        description="Atmospheric extinction coefficient. If None, use filter's default."
    )

    # --- 5. Calculation Logic Control ---
    # User must provide either exposure_time to get SNR, or target_snr to get time.
    exposure_time: Optional[PositiveFloat] = Field(
        None, 
        description="Exposure time in seconds. Input for SNR calculation."
    )
    target_snr: Optional[PositiveFloat] = Field(
        None, 
        description="Requested Signal-to-Noise Ratio. Input for time calculation."
    )

    # --- 6. Advanced Overrides & Settings ---
    gain_override: Optional[float] = Field(
        None, 
        gt=0, 
        description="Override the camera's hardware gain for specific scenarios (e.g., CMOS modes)."
    )
    aperture_radius_arcsec: Optional[PositiveFloat] = Field(
        None, 
        description="Software aperture radius in arcseconds. If None, the calculator will default to 1.5x seeing."
    )

    @model_validator(mode='after')
    def check_calculation_mode(self):
        """
        Ensure that exactly one of 'exposure_time' or 'target_snr' is provided.
        This enforces mutual exclusivity between the two calculation modes.
        """
        # (self.exposure_time is None) == (self.target_snr is None) 
        # is True if both are None or both are provided.
        if (self.exposure_time is None) == (self.target_snr is None):
            raise ValueError("Must provide either 'exposure_time' or 'target_snr', but not both.")
        return self

class CastorResponse(BaseModel):
    """
    Structured output from the CASTOR calculator.
    """
    # Primary Results
    snr: Optional[float] = None
    exposure_time: Optional[float] = None
    
    # Secondary Physics Metrics (For user verification)
    source_rate_e_sec: float = Field(..., description="Source signal rate.")
    sky_rate_e_sec_pix: float = Field(..., description="Sky background rate per pixel[cite: 1].")
    pixel_scale: float = Field(..., description="Arcsec per pixel[cite: 1].")
    total_noise_e: Optional[float] = None
    
    # Overhead & Safety
    readout_time_sec: float = Field(..., description="Time to read the CCD[cite: 1].")
    total_observation_time_sec: float = Field(..., description="Exposure + Readout[cite: 1].")
    is_saturated: bool = Field(False, description="True if the signal exceeds Full Well Capacity.")
    
    # Warnings (Optional)
    warnings: list[str] = []