from pydantic import BaseModel, Field, PositiveFloat, PositiveInt
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
