from pydantic import BaseModel, Field, PositiveFloat, PositiveInt, model_validator
from typing import Optional

class TelescopeSchema(BaseModel):
    """
    Physical and optical parameters of the telescope gathering system.
    """
    diameter_m: PositiveFloat = Field(
        ..., 
        description="Diameter of the primary mirror in meters (m)."
    )
    focal_length_m: PositiveFloat = Field(
        ..., 
        description="Effective focal length of the telescope in meters (m)."
    )
    m1_reflectance: float = Field(
        0.92, 
        ge=0, 
        le=1, 
        description="Reflectance of the primary mirror (M1)."
    )
    m2_reflectance: float = Field(
        0.92, 
        ge=0, 
        le=1, 
        description="Reflectance of the secondary mirror (M2)."
    )
    glass_transmission: float = Field(
        0.95, 
        ge=0, 
        le=1, 
        description="Transmission rate of any corrective glass or dewar window."
    )
    central_obstruction_linear_ratio: float = Field(
        0.0,
        ge=0,
        le=1,
        description="Linear ratio of the central obstruction (secondary mirror diameter / primary mirror diameter)."
    )

class CameraSchema(BaseModel):
    """
    Physical and operational parameters of the camera (CCD/CMOS).
    """
    # 1. Geometry & Scale
    pixel_size_micron: PositiveFloat = Field(
        ..., 
        description="Physical size of a single pixel in microns (μm)."
    )
    resolution_x: PositiveInt = Field(
        ..., 
        description="Number of pixels in the X dimension (width)."
    )
    resolution_y: PositiveInt = Field(
        ..., 
        description="Number of pixels in the Y dimension (height)."
    )

    # 2. Noise & Efficiency (Required by calc_total_noise_and_snr)
    read_noise_e: float = Field(
        ..., 
        ge=0, 
        description="Readout noise in electrons per pixel (e-/pix)."
    )
    dark_current_e_per_sec: float = Field(
        0.1, 
        ge=0, 
        description="Dark current rate in electrons per second per pixel (e-/sec/pix)."
    )
    quantum_efficiency: float = Field(
        ..., 
        ge=0, 
        le=1, 
        description="Quantum efficiency (QE) of the detector at the observed band."
    )

    # 3. Readout Electronics (Required by calc_readout_time)
    readout_speed_khz: float = Field(
        100.0, 
        gt=0, 
        description="The sampling rate of the readout electronics in kHz."
    )
    n_amplifiers: PositiveInt = Field(
        1, 
        description="Number of amplifiers used during the readout process."
    )
    gain: float = Field(
        1.0, 
        gt=0, 
        description="Conversion gain from electrons to ADU (e-/ADU)."
    )

    # 4. Safety & Quality Control (Optional but Recommended)
    full_well_capacity_e: Optional[PositiveFloat] = Field(
        None, 
        description="Maximum electron capacity per pixel before saturation (e-)."
    )

class FilterSchema(BaseModel):
    """
    Characteristics of the optical filter band.
    """
    name: str = Field(
        ..., 
        description="Name of the filter band (e.g., 'V', 'R', 'I', 'Ha')."
    )
    central_wavelength_nm: PositiveFloat = Field(
        ..., 
        description="The central wavelength of the filter in nanometers (nm)."
    )
    fwhm_nm: PositiveFloat = Field(
        ..., 
        description="Full Width at Half Maximum of the filter passband in nanometers (nm)."
    )
    peak_transmission: float = Field(
        0.9, 
        ge=0, 
        le=1, 
        description="The maximum transmission ratio of the filter (0.0 to 1.0)."
    )
    zero_mag_flux: float = Field(
        ..., 
        description="The flux of a 0-magnitude star for this band (W m^-2 m^-1)."
    )
    default_extinction: float = Field(
        0.15, 
        description="Default atmospheric extinction coefficient for this band (mag/airmass)."
    )

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
    exposure_time: Optional[list[PositiveFloat]] = Field(
        None, 
        description="Exposure time in seconds. Input for SNR calculation."
    )
    target_snr: Optional[list[PositiveFloat]] = Field(
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
    Each list item corresponds to the respective input in the request.
    """
    # Primary Results (Arrays)
    snr: Optional[list[float]] = None
    exposure_time: Optional[list[float]] = None
    
    # Secondary Physics Metrics (Arrays for each calculated point)
    total_noise_e: Optional[list[float]] = None
    is_saturated: list[bool] = Field(
        default_factory=list, 
        description="True if the signal exceeds Full Well Capacity at each point."
    )
    total_observation_time_sec: list[float] = Field(
        default_factory=list, 
        description="Exposure + Readout for each point."
    )

    # Constant Metrics (Single values for the whole request)
    source_rate_e_sec: float = Field(..., description="Source signal rate.")
    sky_rate_e_sec_pix: float = Field(..., description="Sky background rate per pixel.")
    pixel_scale: float = Field(..., description="Arcsec per pixel.")
    readout_time_sec: float = Field(..., description="Fixed time to read the CCD.")
    
    # Information
    warnings: list[str] = Field(default_factory=list)