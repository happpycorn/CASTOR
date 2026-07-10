from pydantic import BaseModel, Field, PositiveFloat, PositiveInt, model_validator
from typing import Literal, Optional, Union, Annotated
from datetime import datetime

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
    additional_throughput: float = Field(
        1.0,
        ge=0,
        le=1,
        description="Combined optical transmission efficiency (0.0 to 1.0) of any auxiliary optics not explicitly covered, such as focal reducers, field flatteners, or a tertiary mirror (M3)."
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
    binning_x: PositiveInt = Field(
        1,
        description="Hardware pixel binning factor along the X dimension (width). Combines adjacent pixels to increase signal-to-noise ratio (SNR) at the cost of spatial resolution."
    )
    binning_y: PositiveInt = Field(
        1,
        description="Hardware pixel binning factor along the Y dimension (height). Combines adjacent pixels to increase signal-to-noise ratio (SNR) at the cost of spatial resolution."
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
    shutter_overhead_sec: float = Field(
        0.0,
        ge=0,
        description="Mechanical shutter opening/closing overhead or readout initialization delay in seconds per single exposure. Crucial for total observation time calculation."
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

class InstrumentProfile(BaseModel):
    """
    The static hardware configuration of the observatory, combining optics, 
    sensor electronics, and the filter bandpass.
    """
    telescope: TelescopeSchema = Field(
        ...,
        description="Optical and structural parameters of the telescope assembly (e.g., aperture, focal length, throughput modifiers)."
    )
    camera: CameraSchema = Field(
        ...,
        description="Electronic and geometric properties of the detector sensor (e.g., pixel size, read noise, quantum efficiency, binning modes)."
    )
    optic_filter: FilterSchema = Field(
        ...,
        description="Characteristics of the selected optical filter band, defining the wavelength window and zero-magnitude flux reference."
    )

class BaseTarget(BaseModel):
    """
    Shared astrophysical properties for all target types.
    Handles common parameters like SED models and cosmological modifiers.
    """
    sed_type: Literal["flat", "blackbody"] = Field(
        "flat", 
        description="Spectral Energy Distribution model. 'flat' assumes constant flux across the band; 'blackbody' uses Planck's law."
    )
    temperature_k: Optional[PositiveFloat] = Field(
        None, 
        description="Blackbody temperature in Kelvin. Required if sed_type is 'blackbody'."
    )
    redshift: float = Field(
        0.0, 
        ge=0.0, 
        description="Cosmological redshift (z) of the target. Default is 0.0 (local)."
    )
    ra: tuple[float, float, float] | None = Field(
        None, 
        description="Right Ascension in hours, minutes, seconds (RA_h, RA_m, RA_s)."
    )
    dec: tuple[float, float, float] | None = Field(
        None,
        description="Declination in degrees, arcminutes, arcseconds (Dec_d, Dec_m, Dec_s)."
    )

    @model_validator(mode='after')
    def validate_sed_configuration(self):
        """
        Ensure that temperature is provided when blackbody SED is selected.
        """
        if self.sed_type == "blackbody" and self.temperature_k is None:
            raise ValueError("Field 'temperature_k' must be provided when 'sed_type' is 'blackbody'.")
        return self


class PointTarget(BaseTarget):
    """
    Data contract for point-source celestial objects (e.g., stars, unresolved quasars).
    """
    type: Literal["point"] = Field(
        "point", 
        description="Target morphology identifier."
    )
    target_mag: float = Field(
        ..., 
        description="The apparent magnitude of the point source in the observed band."
    )

class ExtendedTarget(BaseTarget):
    """
    Data contract for extended celestial objects (e.g., galaxies, nebulae, comets).
    """
    type: Literal["extended"] = Field(
        "extended", 
        description="Target morphology identifier."
    )
    surface_brightness: float = Field(
        ..., 
        description="Surface brightness of the extended source in mag/arcsec^2."
    )

TargetProfile = Annotated[
    Union[PointTarget, ExtendedTarget], 
    Field(discriminator="type")
]

class ManualEnvironment(BaseModel):
    """
    MVP: Manual environmental conditions provided directly by the caller.
    Future versions can introduce 'DynamicEnvironment' to calculate these 
    from RA/Dec and timestamps.
    """
    type: Literal["manual"] = Field(
        "manual",
        description="Environment condition identifier. 'manual' requires direct input of atmospheric parameters."
    )
    seeing_fwhm_arcsec: PositiveFloat = Field(
        1.5,
        description="Atmospheric seeing Full Width at Half Maximum (FWHM) in arcseconds. Crucial for resolving point source PSF."
    )
    airmass: float = Field(
        1.0,
        ge=1.0,
        description="Airmass of the observation (1.0 = Zenith). Determines the path length of light through the atmosphere."
    )
    extinction_coeff: Optional[float] = Field(
        None,
        description="Atmospheric extinction coefficient (mag/airmass). If None, the engine will fallback to the filter's default extinction."
    )
    sky_brightness_mag_arcsec2: float = Field(
        ...,
        description="Base dark sky background brightness in magnitude per square arcsecond (mag/arcsec^2) assuming no moonlight."
    )

    observing_time: datetime | None = Field(
        None,
        description="UTC timestamp of the observation. Required for dynamic calculations like moon phase and position."
    )
    observatory_position: tuple[float, float, float] | None = Field(
        None,
        description="Observatory geodetic coordinates as (latitude_deg, longitude_deg, elevation_m). Required for accurate celestial calculations."
    )

EnvironmentCondition = ManualEnvironment

class SingleInput(BaseModel):
    type: Literal["single"] = "single"
    value: PositiveFloat

class ArrayInput(BaseModel):
    type: Literal["array"] = "array"
    values: list[PositiveFloat]

InputValue = Annotated[
    Union[SingleInput, ArrayInput], 
    Field(discriminator="type")
]

class SolveForSNR(BaseModel):
    """
    Strategy: Provide exposure time to calculate SNR.
    """
    type: Literal["solve_snr"] = "solve_snr"
    exposure_time: InputValue

class SolveForTime(BaseModel):
    """
    Strategy: Provide target SNR to calculate required exposure time.
    """
    type: Literal["solve_time"] = "solve_time"
    target_snr: InputValue

CalculationOptions = Annotated[
    Union[SolveForSNR, SolveForTime], 
    Field(discriminator="type")
]

class ObservationRequest(BaseModel):
    """
    The root contract for a CASTOR calculation request.
    Strictly aggregates the four domain pillars: Instrument, Target, Environment, and Options.
    """
    instrument: InstrumentProfile = Field(
        ...,
        description="Static hardware configuration of the observatory (telescope, camera, filter)."
    )
    
    target: TargetProfile = Field(
        ...,
        description="Intrinsic physical properties of the celestial source (polymorphic: point or extended)."
    )
    
    environment: EnvironmentCondition = Field(
        ...,
        description="Atmospheric and situational context (MVP: manual input of seeing, airmass, etc.)."
    )
    
    options: CalculationOptions = Field(
        ...,
        description="Software control interface defining the calculation strategy (polymorphic: solve_snr or solve_time)."
    )

class BaseMetrics(BaseModel):
    """
    Secondary diagnostics and physical constants calculated during the run.
    Contains both scalar constants for the run and array metrics that map 1:1 with the input length.
    """
    source_rate_e_sec: float = Field(..., description="Source signal rate (e-/sec).")
    sky_rate_e_sec_pix: float = Field(..., description="Sky background rate per pixel (e-/sec/pix).")
    pixel_scale: float = Field(..., description="Spatial resolution in arcseconds per pixel.")
    readout_time_sec: float = Field(..., description="Fixed mechanical/electronic time to read the sensor.")

    total_noise_e: list[float] = Field(..., description="Total noise in electrons for each calculated point.")
    is_saturated: list[bool] = Field(..., description="True if the cumulative signal exceeds Full Well Capacity.")
    total_observation_time_sec: list[float] = Field(..., description="Total elapsed time (Exposure + Readout Overhead) per point.")
    
    warnings: list[str] = Field(default_factory=list, description="Array of domain-specific warnings (e.g., 'Target too close to horizon').")


class SNRResponse(BaseMetrics):
    """
    Output contract when the strategy was to solve for SNR.
    """
    type: Literal["snr_result"] = Field("snr_result", description="Response type identifier.")
    
    calculated_snr: list[float] = Field(
        ..., 
        description="The resolved Signal-to-Noise Ratio(s)."
    )
    input_exposure_time: list[float] = Field(
        ..., 
        description="The original exposure time(s) passed to the engine, normalized to a 1D array."
    )


class TimeResponse(BaseMetrics):
    """
    Output contract when the strategy was to solve for Exposure Time.
    """
    type: Literal["time_result"] = Field("time_result", description="Response type identifier.")
    
    calculated_exposure_time: list[float] = Field(
        ..., 
        description="The resolved required exposure time(s) in seconds."
    )
    input_target_snr: list[float] = Field(
        ..., 
        description="The original target SNR(s) passed to the engine, normalized to a 1D array."
    )


# --- The Flat Polymorphic Response ---
CastorResponse = Annotated[
    Union[SNRResponse, TimeResponse], 
    Field(discriminator="type")
]