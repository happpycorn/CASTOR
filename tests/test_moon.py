# import pytest
# from datetime import datetime, timezone
# from castor.calculator import CastorCalculator

# class TestMoonlightImpact:
    
#     def test_moonlight_impact_on_snr(self, base_request):
#         """驗證月光對背景雜訊與 SNR 的相對影響 (Delta Testing)"""
#         calc = CastorCalculator()

#         # ==========================================
#         # 1. 沒被影響的數值 (Baseline: 無月光)
#         # ==========================================
#         # 我們刻意把 observing_time 設為 None，
#         # 這樣 moon.py 就會直接 return，採用預設的暗夜背景 (21.0 等)
#         base_request.environment.observing_time = None 
        
#         baseline_response = calc.calculate(base_request)
#         baseline_snr = baseline_response.calculated_snr[0]
#         baseline_sky_rate = baseline_response.sky_rate_e_sec_pix

#         # ==========================================
#         # 2. 有被影響的數值 (Affected: 滿月轟炸)
#         # ==========================================
#         # 塞入一個真實存在的滿月時間 (例如 2026-06-30)
#         base_request.environment.observing_time = datetime(2026, 6, 30, 14, 0, tzinfo=timezone.utc)
        
#         affected_response = calc.calculate(base_request)
#         affected_snr = affected_response.calculated_snr[0]
#         affected_sky_rate = affected_response.sky_rate_e_sec_pix

#         # ==========================================
#         # 3. 計算差異是否等於影響 (Assert the Delta)
#         # ==========================================
        
#         # 斷言 A：月光一定會帶來額外的光子，所以背景電子數 (sky_rate) 絕對會上升
#         assert affected_sky_rate > baseline_sky_rate, "月光沒有增加背景電子數！"

#         # 斷言 B：因為背景雜訊變大了，所以最終的 SNR 絕對會下降
#         assert affected_snr < baseline_snr, "月光干擾下 SNR 竟然沒有下降！"

#         # 斷言 C (進階)：驗證影響的「量級」是否合理
#         # 例如：我們預期滿月造成的影響非常劇烈，SNR 至少要掉 30% 以上
#         snr_drop_ratio = (baseline_snr - affected_snr) / baseline_snr
#         assert snr_drop_ratio > 0.30, f"滿月的影響太小了，SNR 只掉了 {snr_drop_ratio:.1%}"