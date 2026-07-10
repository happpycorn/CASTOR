import sys
import os
# 導航魔法：讓 Python 退後一步找到 castor 防潮箱
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from castor.calculator import CastorCalculator
from castor.schema import (
    TelescopeSchema, CameraSchema, FilterSchema, InstrumentProfile,
    PointTarget, ManualEnvironment, SolveForSNR, ArrayInput, ObservationRequest
)

# ==========================================
# 1. 組裝鹿林一米鏡硬體 (Instrument)
# ==========================================
lot_telescope = TelescopeSchema(
    diameter_m=1.0, focal_length_m=8.0, m1_reflectance=0.92, m2_reflectance=0.92, 
    glass_transmission=0.95, central_obstruction_linear_ratio=0.3
)
lot_camera = CameraSchema(
    pixel_size_micron=15.0, resolution_x=2048, resolution_y=2048,
    read_noise_e=5.0, dark_current_e_per_sec=0.01, quantum_efficiency=0.85,
    readout_speed_khz=100.0, n_amplifiers=2, gain=1.5
)
v_band = FilterSchema(
    name="V", central_wavelength_nm=550.0, fwhm_nm=89.0,
    peak_transmission=0.9, zero_mag_flux=3.63e-11, default_extinction=0.15
)
instrument = InstrumentProfile(telescope=lot_telescope, camera=lot_camera, optic_filter=v_band)

# ==========================================
# 2. 鎖定拍攝目標 (Target)
# ==========================================
target = PointTarget(target_mag=15.0)

# ==========================================
# 3. 填寫今晚的觀測環境 (Environment) - 滿月來襲！
# ==========================================
environment = ManualEnvironment(
    seeing_fwhm_arcsec=1.5,
    airmass=1.2,
    sky_brightness_mag_arcsec2=21.0,
    # --- 你剛加上的月光魔王參數 ---
    moon_phase=1.0,                  # 今晚是 100% 滿月
    moon_target_separation_deg=30.0, # 目標離滿月只有 30 度 (超亮)
    moon_zenith_angle_deg=45.0       # 月亮仰角 45 度
)

# ==========================================
# 4. 指定計算選項 (Options)
# ==========================================
options = SolveForSNR(
    exposure_time=ArrayInput(values=[10.0, 30.0, 60.0])
)

# ==========================================
# 5. 打包並送入計算機
# ==========================================
test_request = ObservationRequest(
    instrument=instrument,
    target=target,
    environment=environment,
    options=options
)

calculator = CastorCalculator()
print("🚀 啟動 CASTOR 核心引擎...")
result = calculator.calculate(test_request)

print("\n🎉 計算完成！結果如下：")
print(f"每像素的天空背景雜訊 (e-/sec/pix): {result.sky_rate_e_sec_pix:.2f}")
print(f"最終算出的 SNR 陣列: {result.calculated_snr}")

from skyfield.api import load, wgs84, Star
from skyfield.almanac import fraction_illuminated

# ==========================================
# 1. 準備器材：載入星曆表與時間
# ==========================================
# 這會下載一個小小的星曆檔 (de421.bsp) 到你的資料夾，以後就可以 100% 離線使用！
eph = load('de421.bsp')
earth, moon, sun = eph['earth'], eph['moon'], eph['sun']

ts = load.timescale()
# 設定觀測時間（以 UTC 時間為準，這裡是舉例）
t = ts.utc(2026, 7, 2, 14, 0, 0) 

# ==========================================
# 2. 架設望遠鏡：設定鹿林天文台的真實座標
# ==========================================
# 鹿林天文台大約在 北緯 23.47度，東經 120.87度，海拔 2862 公尺
lulin_observatory = earth + wgs84.latlon(23.47, 120.87, elevation_m=2862)

# ==========================================
# 3. 開始計算三大核心參數！
# ==========================================

# 參數 A：計算「月亮天頂角」
# 讓鹿林的望遠鏡在 t 時間看向月亮
moon_observation = lulin_observatory.at(t).observe(moon).apparent()
alt, az, distance = moon_observation.altaz()
# 天頂角 = 90度 - 仰角 (Altitude)
moon_zenith_angle_deg = 90.0 - alt.degrees

# 參數 B：計算「月相」
# fraction_illuminated 會算出 0.0 (新月) 到 1.0 (滿月) 的比例
# 我們把它乘上 100 轉成百分比，符合你們 schema.py 的設計
moon_phase = fraction_illuminated(eph, 'moon', t) * 100.0

# 參數 C：計算「月亮與目標的角距離」
# 假設我們今晚的拍攝目標是天狼星 (Sirius)，先設定它的 RA/Dec 座標
target_star = Star(ra_hours=(6, 45, 8.9), dec_degrees=(-16, 42, 58))
target_observation = lulin_observatory.at(t).observe(target_star).apparent()

# 直接算出目標與月亮的夾角 (Separation)
moon_target_separation_deg = target_observation.separation_from(moon_observation).degrees

# ==========================================
# 4. 印出結果
# ==========================================
print(f"=== 鹿林天文台 月光狀態報告 ===")
print(f"月相 (0-100): {moon_phase:.1f}%")
print(f"月亮天頂角: {moon_zenith_angle_deg:.1f} 度")
print(f"目標與月亮角距離: {moon_target_separation_deg:.1f} 度")