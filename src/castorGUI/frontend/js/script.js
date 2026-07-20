// ==========================================
// 1. UI 狀態控制器 (UIController)
// ==========================================
class UIController {
    constructor() {
        // 取代原本寫死的字典，改為空物件準備接收 API 資料
        this.presets = null;
        this.bindEvents();
    }

    // 新增：向後端請求 JSON 檔案，並初始化下拉選單
    async loadPresets() {
        try {
            const response = await fetch('/api/presets');
            if (!response.ok) throw new Error('無法取得預設硬體參數');
            this.presets = await response.json();

            // 將資料注入到剛剛改好的三個下拉選單
            this.populateSelect('telescope-template', this.presets.telescopes);
            this.populateSelect('camera-template', this.presets.cameras);
            this.populateSelect('filter-template', this.presets.filters);

        } catch (error) {
            console.error(error);
            alert("載入硬體預設檔失敗，請確認後端已啟動。");
        }
    }

    // 新增：動態生成 <option> 並掛載
    populateSelect(elementId, presetCategory) {
        const select = document.getElementById(elementId);
        select.innerHTML = ''; // 清空 'Loading...'

        for (const key in presetCategory) {
            const option = document.createElement('option');
            option.value = key;
            option.textContent = key.replace(/_/g, ' '); // 把底線換成空白，稍微美化一下顯示
            select.appendChild(option);
        }

        // 加入自訂選項
        const customOption = document.createElement('option');
        customOption.value = 'CUSTOM';
        customOption.textContent = 'Custom Parameters';
        select.appendChild(customOption);

        // 預設選取第一個，並觸發數值填寫
        if (Object.keys(presetCategory).length > 0) {
            const firstKey = Object.keys(presetCategory)[0];
            select.value = firstKey;
            
            // 找出這個選單對應的是 telescopes, cameras 還是 filters
            const categoryMap = {
                'telescope-template': 'telescopes',
                'camera-template': 'cameras',
                'filter-template': 'filters'
            };
            this.applyPreset(categoryMap[elementId], firstKey);
        }
    }

    bindEvents() {
        // 把原本的 updateHardwarePresets 拆解成三組，並呼叫通用的 applyPreset 方法
        document.getElementById('telescope-template').addEventListener('change', (e) => {
            this.applyPreset('telescopes', e.target.value);
        });

        document.getElementById('camera-template').addEventListener('change', (e) => {
            this.applyPreset('cameras', e.target.value);
        });

        document.getElementById('filter-template').addEventListener('change', (e) => {
            this.applyPreset('filters', e.target.value);
        });

        // 以下保留原本的邏輯
        document.getElementById('target-type').addEventListener('change', (e) => this.toggleTargetMode(e.target.value));
        document.getElementById('calc-mode').addEventListener('change', (e) => this.toggleCalcMode(e.target.value));
        document.getElementById('toggle-array-mode').addEventListener('change', (e) => this.toggleArrayMode(e.target.checked));
    }

    // 將原本的 updateHardwarePresets 改寫為通用的資料綁定器
    applyPreset(category, templateName) {
        if (templateName === 'CUSTOM') return; 
        if (!this.presets || !this.presets[category]) return;

        const presetData = this.presets[category][templateName];
        if (!presetData) return;

        // 走訪 JSON 欄位，自動對應 HTML name
        for (const [inputName, value] of Object.entries(presetData)) {
            // 如果遇到 null (例如 ESO_Reference 裡面預留的空位)，就跳過不處理
            if (value === null) continue;

            const inputElement = document.querySelector(`input[name="${inputName}"]`);
            if (inputElement) {
                inputElement.value = value;
                
                // 保留閃爍特效提示使用者
                inputElement.style.transition = 'background-color 0.3s';
                inputElement.style.backgroundColor = 'rgba(197, 160, 89, 0.3)';
                setTimeout(() => {
                    inputElement.style.backgroundColor = '';
                }, 400);
            }
        }
    }

    toggleTargetMode(mode) { /* 保持原樣不變 */
        const magGroup = document.getElementById('target-mag-group');
        const sbGroup = document.getElementById('target-sb-group');
        if (mode === 'point') { magGroup.hidden = false; sbGroup.hidden = true; } 
        else if (mode === 'extended') { magGroup.hidden = true; sbGroup.hidden = false; }
    }

    toggleCalcMode(mode) { /* 保持原樣不變 */
        const label = document.getElementById('label-calc-values');
        if (mode === 'solve_snr') { label.textContent = 'Exposure Time (sec): '; } 
        else if (mode === 'solve_time') { label.textContent = 'Target SNR: '; }
    }

    toggleArrayMode(isArray) { /* 保持原樣不變 */
        const singleInput = document.getElementById('calc-values');
        const arrayGroup = document.getElementById('array-input-group');
        if (isArray) {
            singleInput.hidden = true;
            singleInput.required = false; 
            arrayGroup.hidden = false;
        } else {
            singleInput.hidden = false;
            singleInput.required = true;
            arrayGroup.hidden = true;
        }
    }

    setLoadingState(isLoading) { /* 保持原樣不變 */
        const btn = document.getElementById('btn-submit');
        if (isLoading) {
            btn.disabled = true;
            btn.textContent = 'Calculating...';
            btn.style.opacity = '0.7';
            btn.style.cursor = 'not-allowed';
        } else {
            btn.disabled = false;
            btn.textContent = 'Run Simulation';
            btn.style.opacity = '1';
            btn.style.cursor = 'pointer';
        }
    }
}

// ==========================================
// 2. 資料打包器 (PayloadBuilder)
// ==========================================
class PayloadBuilder {
    
    // 工具函式：從畫面上取得數值並轉型
    static getVal(name, type = 'float') {
        const input = document.querySelector(`input[name="${name}"], select[name="${name}"]`);
        if (!input || input.value.trim() === '') return null;
        
        const val = input.value;
        if (type === 'float') return parseFloat(val);
        if (type === 'int') return parseInt(val, 10);
        if (type === 'string') return val;
        return val;
    }

    static build() {
        return {
            instrument: this._buildInstrument(),
            target: this._buildTarget(),
            environment: this._buildEnvironment(),
            options: this._buildOptions()
        };
    }

    static _buildInstrument() {
        return {
            telescope: {
                diameter_m: this.getVal('telescope-diameter_m'),
                focal_length_m: this.getVal('telescope-focal_length_m'),
                m1_reflectance: this.getVal('telescope-m1_reflectance'),
                m2_reflectance: this.getVal('telescope-m2_reflectance'),
                glass_transmission: this.getVal('telescope-glass_transmission'),
                central_obstruction_linear_ratio: this.getVal('telescope-central_obstruction_linear_ratio'),
                additional_throughput: this.getVal('telescope-additional_throughput')
            },
            camera: {
                pixel_size_micron: this.getVal('camera-pixel_size_micron'),
                resolution_x: this.getVal('camera-resolution_x', 'int'),
                resolution_y: this.getVal('camera-resolution_y', 'int'),
                read_noise_e: this.getVal('camera-read_noise_e'),
                dark_current_e_per_sec: this.getVal('camera-dark_current_e_per_sec'),
                quantum_efficiency: this.getVal('camera-quantum_efficiency'),
                binning_x: this.getVal('camera-binning_x', 'int'),
                binning_y: this.getVal('camera-binning_y', 'int'),
                readout_speed_khz: this.getVal('camera-readout_speed_khz'),
                n_amplifiers: this.getVal('camera-n_amplifiers', 'int'),
                gain: this.getVal('camera-gain'),
                shutter_overhead_sec: this.getVal('camera-shutter_overhead_sec'),
                full_well_capacity_e: this.getVal('camera-full_well_capacity_e') || null
            },
            optic_filter: {
                name: this.getVal('filter-name', 'string'),
                central_wavelength_nm: this.getVal('filter-central_wavelength_nm'),
                fwhm_nm: this.getVal('filter-fwhm_nm'),
                peak_transmission: this.getVal('filter-peak_transmission'),
                zero_mag_flux: this.getVal('filter-zero_mag_flux'),
                default_extinction: this.getVal('filter-default_extinction')
            }
        };
    }

    static _buildTarget() {
        const targetType = this.getVal('target-type', 'string');
        const sedType = this.getVal('target-sed_type', 'string');
        
        // 1. 處理基礎屬性
        const baseTarget = {
            type: targetType,
            sed_type: sedType,
            redshift: this.getVal('target-redshift'),
        };

        // 處理黑體輻射溫度 (只有黑體才帶溫度)
        if (sedType === 'blackbody') {
            baseTarget.temperature_k = this.getVal('target-temperature_k');
        }

        // 處理天球座標 (組裝成 Tuple [float, float, float] 或 null)
        const raH = this.getVal('target-ra_h');
        if (raH !== null) {
            baseTarget.ra = [raH, this.getVal('target-ra_m') || 0, this.getVal('target-ra_s') || 0];
        }
        const decD = this.getVal('target-dec_d');
        if (decD !== null) {
            baseTarget.dec = [decD, this.getVal('target-dec_m') || 0, this.getVal('target-dec_s') || 0];
        }

        // 2. 處理多態屬性 (Polymorphic)
        if (targetType === 'point') {
            baseTarget.target_mag = this.getVal('target-target_mag');
        } else if (targetType === 'extended') {
            baseTarget.surface_brightness = this.getVal('target-surface_brightness');
        }

        return baseTarget;
    }

    static _buildEnvironment() {
        const env = {
            type: "manual",
            seeing_fwhm_arcsec: this.getVal('environment-seeing_fwhm_arcsec'),
            airmass: this.getVal('environment-airmass'),
            sky_brightness_mag_arcsec2: this.getVal('environment-sky_brightness_mag_arcsec2')
        };

        // Optional: 自訂消光
        const ext = this.getVal('environment-extinction_coeff');
        if (ext !== null) env.extinction_coeff = ext;

        // Optional: 動態星曆時間
        const obsTime = this.getVal('environment-observing_time', 'string');
        if (obsTime) env.observing_time = obsTime + ":00Z"; // 簡單加上秒數與 UTC 標籤對齊 datetime

        // Optional: 天文台座標 Tuple
        const lat = this.getVal('environment-obs_lat');
        if (lat !== null) {
            env.observatory_position = [lat, this.getVal('environment-obs_lon') || 0, this.getVal('environment-obs_elev') || 0];
        }

        return env;
    }

    static _buildOptions() {
        const optType = this.getVal('options-type', 'string'); // solve_snr 或 solve_time
        const isArrayMode = document.getElementById('toggle-array-mode').checked;
        
        let inputValueObj = {};

        // 判斷是單一數值還是陣列
        if (isArrayMode) {
            const arrayStr = this.getVal('options-values-array', 'string');
            // 把 "10, 30, 60" 字串切開、去除空白、轉成 float 的陣列
            const valArray = arrayStr.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
            inputValueObj = { type: "array", values: valArray };
        } else {
            const singleVal = this.getVal('options-values-single');
            inputValueObj = { type: "single", value: singleVal };
        }

        // 根據策略將 input 賦值給不同的 key
        if (optType === 'solve_snr') {
            return { type: optType, exposure_time: inputValueObj };
        } else {
            return { type: optType, target_snr: inputValueObj };
        }
    }
}

// ==========================================
// 3. API 客戶端 (CastorAPI)
// ==========================================
class CastorAPI {
    static async calculate(payload) {
        try {
            // 請將這裡的 URL 換成你 FastAPI 實際的路由端點
            const response = await fetch('/api/calculate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                // 攔截 FastAPI (Pydantic) 丟回來的 422 格式錯誤或其他 HTTP 錯誤
                const errorData = await response.json();
                console.error("API 錯誤細節:", errorData);
                
                // 嘗試解析 Pydantic 的 detail 陣列，讓錯誤訊息對人類友善一點
                const errorMsg = errorData.detail 
                    ? JSON.stringify(errorData.detail, null, 2) 
                    : "未知伺服器錯誤";
                
                throw new Error(errorMsg);
            }

            // 回傳成功解析的 CastorResponse 物件
            return await response.json();
        } catch (error) {
            throw error;
        }
    }
}

// ==========================================
// 4. 結果渲染器 (ResultRenderer)
// ==========================================
class ResultRenderer {
    static render(data, isArrayMode) {
        // 1. 切換結果區塊顯示狀態
        document.getElementById('results-placeholder').hidden = true;
        document.getElementById('results-container').hidden = false;

        // 2. 處理過曝與系統警告
        this._renderWarnings(data.warnings, data.is_saturated);

        // 3. 填入物理常數 (標量)
        // 使用 toFixed(2) 確保小數點後兩位，畫面才不會被超長浮點數撐破
        document.getElementById('res-source-rate').textContent = data.source_rate_e_sec.toFixed(2);
        document.getElementById('res-sky-rate').textContent = data.sky_rate_e_sec_pix.toFixed(2);
        document.getElementById('res-pixel-scale').textContent = data.pixel_scale.toFixed(2);
        document.getElementById('res-readout-time').textContent = data.readout_time_sec.toFixed(2);

        // 4. 渲染核心解答卡片 (Hero Metric)
        this._renderPrimary(data);

        // 5. 處理陣列圖表與表格
        const plotArea = document.getElementById('plot-area');
        const tableArea = document.getElementById('table-area');

        if (isArrayMode) {
            plotArea.hidden = false;
            tableArea.hidden = false;
            this._renderPlot(data);
            this._renderTable(data);
        } else {
            plotArea.hidden = true;
            tableArea.hidden = true;
        }
    }

    static _renderPrimary(data) {
        const labelEl = document.getElementById('primary-result-label');
        const valueEl = document.getElementById('primary-result-value');
        const descEl = document.getElementById('primary-result-desc');

        // 判斷回應型別，並抓取陣列的第 [0] 個值作為卡片代表
        if (data.type === 'snr_result') {
            labelEl.textContent = 'Signal-to-Noise Ratio(SNR)';
            valueEl.textContent = data.calculated_snr[0].toFixed(2);
            descEl.textContent = `Exposure Time: ${data.input_exposure_time[0]} Sec`;
        } else {
            labelEl.textContent = 'Required Exposure Time';
            valueEl.textContent = `${data.calculated_exposure_time[0].toFixed(2)} Sec`;
            descEl.textContent = `Target SNR: ${data.input_target_snr[0]}`;
        }
    }

    static _renderWarnings(warnings, isSaturatedArr) {
        const alertContainer = document.getElementById('alert-container');
        const warningList = document.getElementById('warning-list');
        warningList.innerHTML = ''; // 清空舊警告

        let hasWarning = false;

        // 檢查是否有任何一點過曝
        if (isSaturatedArr && isSaturatedArr.includes(true)) {
            hasWarning = true;
            const li = document.createElement('li');
            // li.textContent = '警告：部分曝光時間將導致感光元件像素過曝 (超過滿井容量 Full Well Capacity)。';
            warningList.appendChild(li);
        }

        // 寫入後端自訂警告
        if (warnings && warnings.length > 0) {
            hasWarning = true;
            warnings.forEach(w => {
                const li = document.createElement('li');
                li.textContent = w;
                warningList.appendChild(li);
            });
        }

        alertContainer.hidden = !hasWarning;
    }

    static _renderPlot(data) {
        let xValues, yValues, xLabel, yLabel, title;

        // 動態翻轉 XY 軸
        if (data.type === 'snr_result') {
            xValues = data.input_exposure_time;
            yValues = data.calculated_snr;
            xLabel = 'Exposure Time (s)';
            yLabel = 'Signal-to-Noise Ratio (SNR)';
            title = 'SNR vs Exposure Time';
        } else {
            xValues = data.input_target_snr;
            yValues = data.calculated_exposure_time;
            xLabel = 'Target SNR';
            yLabel = 'Required Exposure Time (s)';
            title = 'Required Time vs Target SNR';
        }

        const trace = {
            x: xValues,
            y: yValues,
            type: 'scatter',
            mode: 'lines+markers',
            line: { color: '#C5A059', width: 3 }, // 鹿林金黃色
            marker: { size: 8, color: '#C5A059' }
        };

        const layout = {
            title: { text: title, font: { color: '#f3f4f6' } },
            xaxis: { title: xLabel, gridcolor: 'rgba(255,255,255,0.1)', zerolinecolor: 'rgba(255,255,255,0.2)', tickfont: {color: '#9ca3af'} },
            yaxis: { title: yLabel, gridcolor: 'rgba(255,255,255,0.1)', zerolinecolor: 'rgba(255,255,255,0.2)', tickfont: {color: '#9ca3af'} },
            paper_bgcolor: 'rgba(0,0,0,0)', // 透明背景，讓 CSS 的毛玻璃透出來
            plot_bgcolor: 'rgba(0,0,0,0)',
            margin: { t: 40, b: 40, l: 50, r: 20 }
        };

        Plotly.newPlot('plot-area', [trace], layout, { responsive: true, displayModeBar: false });
    }

    static _renderTable(data) {
        const tbody = document.getElementById('res-table-body');
        tbody.innerHTML = ''; // 清空舊資料

        const length = data.total_noise_e.length;
        for (let i = 0; i < length; i++) {
            const tr = document.createElement('tr');
            
            let expTime, snr;
            if (data.type === 'snr_result') {
                expTime = data.input_exposure_time[i];
                snr = data.calculated_snr[i];
            } else {
                expTime = data.calculated_exposure_time[i];
                snr = data.input_target_snr[i];
            }

            const isSat = data.is_saturated[i];
            // 過曝標紅字，正常標綠字
            const statusText = isSat 
                ? '<span style="color: #ef4444; font-weight: 600;">Saturated</span>' 
                : '<span style="color: #10b981;">OK</span>';

            tr.innerHTML = `
                <td>${expTime.toFixed(2)}</td>
                <td>${snr.toFixed(2)}</td>
                <td>${data.total_noise_e[i].toFixed(2)}</td>
                <td>${data.total_observation_time_sec[i].toFixed(2)}</td>
                <td>${statusText}</td>
            `;
            tbody.appendChild(tr);
        }
    }
}

// ==========================================
// 🚀 主程式進入點 (Main Execution)
// ==========================================
document.addEventListener('DOMContentLoaded', async () => {
    // 啟動 UI 監聽與載入預設值
    const ui = new UIController();
    
    // 新增：等待後端回傳 presets.json 並渲染選單
    await ui.loadPresets();

    // 攔截表單發射事件 (保持不變)
    document.getElementById('castor-form').addEventListener('submit', async (e) => {
        e.preventDefault(); 
        
        ui.setLoadingState(true);

        try {
            const payload = PayloadBuilder.build();
            console.log("Payload ready:", payload);
            
            const resultData = await CastorAPI.calculate(payload);
            console.log("Response received:", resultData);
            
            const isArrayMode = document.getElementById('toggle-array-mode').checked;
            ResultRenderer.render(resultData, isArrayMode);

        } catch (error) {
            alert(`Run Fail! \n\nReason: ${error.message}`);
        } finally {
            ui.setLoadingState(false);
        }
    });
});