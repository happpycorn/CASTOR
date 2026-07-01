# example.py
from schema import TelescopeSchema, CameraSchema, FilterSchema, ObservationRequest

# 1. 鹿林一米鏡 (LOT) 真實數據
lot_telescope = TelescopeSchema(
    diameter_m=1.0,           
    focal_length_m=8.0,       
    m1_reflectance=0.92,
    m2_reflectance=0.92,
    glass_transmission=0.95,
    central_obstruction_linear_ratio=0.3 
)

# 2. LOT 使用的 SOPHIA 相機真實數據
lot_camera = CameraSchema(
    pixel_size_micron=15.0,   
    resolution_x=2048,        
    resolution_y=2048,        
    read_noise_e=5.0,         
    dark_current_e_per_sec=0.01,
    quantum_efficiency=0.85,  
    readout_speed_khz=100.0,
    n_amplifiers=2,
    gain=1.5
)

# 3. V Band 濾鏡數據
v_band = FilterSchema(
    name="V",
    central_wavelength_nm=550.0,
    fwhm_nm=89.0,
    peak_transmission=0.9,
    zero_mag_flux=3.63e-11,    
    default_extinction=0.15
)

# 4. 把所有硬體跟觀測條件打包成一個 Request
try:
    test_request = ObservationRequest(
        telescope=lot_telescope,
        camera=lot_camera,
        instrument_filter=v_band,
        target_mag=15.0,                     
        sky_brightness_mag_arcsec2=21.0,     
        airmass=1.2,
        seeing_fwhm_arcsec=1.5,
        exposure_time=[10.0, 30.0, 60.0]     
    )
    print("✅ 成功！資料符合 schema 規範，測試資料準備完成！")
    print(f"目前準備的望遠鏡口徑是：{test_request.telescope.diameter_m} 公尺")
    print(f"相機的像素大小是：{test_request.camera.pixel_size_micron} µm")
except Exception as e:
    print("❌ 填寫的資料有錯，被 schema 擋下來了：", e)