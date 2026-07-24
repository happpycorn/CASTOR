// ==========================================
// 1. UI 狀態控制器 (UIController)
// ==========================================
class UIController {
    constructor() {
        this.presets = null;
        this.bindEvents();
        this.initUI();
    }

    async loadPresets() {
        try {
            const response = await fetch('/api/presets');
            if (!response.ok) throw new Error('無法取得預設硬體參數');
            this.presets = await response.json();

            this.populateSelect('telescope-template', this.presets.telescopes, 'telescopes');
            this.populateSelect('camera-template', this.presets.cameras, 'cameras');
            this.populateSelect('filter-template', this.presets.filters, 'filters');
        } catch (error) {
            console.error(error);
            console.warn("載入硬體預設檔失敗，可能是後端未啟動或找不到 presets.json。");
        }
    }

    populateSelect(elementId, presetCategory, categoryName) {
        const select = document.getElementById(elementId);
        select.innerHTML = ''; 

        for (const key in presetCategory) {
            const option = document.createElement('option');
            option.value = key;
            option.textContent = key.replace(/_/g, ' '); 
            select.appendChild(option);
        }

        const customOption = document.createElement('option');
        customOption.value = 'CUSTOM';
        customOption.textContent = 'Custom Parameters';
        select.appendChild(customOption);

        if (Object.keys(presetCategory).length > 0) {
            const firstKey = Object.keys(presetCategory)[0];
            select.value = firstKey;
            this.applyPreset(categoryName, firstKey);
        }
        
        // 初始載入時，執行一次顯示/隱藏的判定
        this.toggleCustomDetails(select);
    }

    bindEvents() {
        // 硬體預設切換，加上了 toggleCustomDetails 聯動
        document.getElementById('telescope-template').addEventListener('change', (e) => {
            this.applyPreset('telescopes', e.target.value);
            this.toggleCustomDetails(e.target);
        });
        document.getElementById('camera-template').addEventListener('change', (e) => {
            this.applyPreset('cameras', e.target.value);
            this.toggleCustomDetails(e.target);
        });
        document.getElementById('filter-template').addEventListener('change', (e) => {
            this.applyPreset('filters', e.target.value);
            this.toggleCustomDetails(e.target);
        });

        // 漸進式揭露 UI 切換
        document.getElementById('target-brightness-type').addEventListener('change', (e) => this.toggleBrightnessUI(e.target.value));
        document.getElementById('sed-type').addEventListener('change', (e) => this.toggleSedUI(e.target.value));
        document.getElementById('calc-mode-type').addEventListener('change', (e) => this.toggleCalcStrategyUI(e.target.value));
    }

    initUI() {
        // 頁面載入時初始化一次 UI 狀態
        this.toggleBrightnessUI(document.getElementById('target-brightness-type').value);
        this.toggleSedUI(document.getElementById('sed-type').value);
        this.toggleCalcStrategyUI(document.getElementById('calc-mode-type').value);
    }

    // 處理 preset 鍵值對應到 HTML 表單
    applyPreset(category, templateName) {
        if (templateName === 'CUSTOM') return; 
        if (!this.presets || !this.presets[category]) return;

        const presetData = this.presets[category][templateName];
        if (!presetData) return;

        for (const [inputName, value] of Object.entries(presetData)) {
            const inputElement = document.querySelector(`input[name="${inputName}"]`);
            if (inputElement && value !== null) {
                inputElement.value = value;
                // 閃爍特效
                inputElement.style.transition = 'background-color 0.3s';
                inputElement.style.backgroundColor = 'rgba(197, 160, 89, 0.3)';
                setTimeout(() => inputElement.style.backgroundColor = '', 400);
            }
        }
    }

    // 控制「自訂參數區塊」的顯示與隱藏
    toggleCustomDetails(selectElement) {
        const customDetailsDiv = selectElement.closest('.instrument-group').querySelector('.custom-details');
        if (selectElement.value === 'CUSTOM') {
            customDetailsDiv.classList.remove('hidden-detail');
        } else {
            customDetailsDiv.classList.add('hidden-detail');
        }
    }

    toggleBrightnessUI(type) {
        document.getElementById('group-target-mag').hidden = !['vega_mag', 'ab_mag'].includes(type);
        document.getElementById('group-zero-point-flux').hidden = (type !== 'vega_mag');
        document.getElementById('group-flux-value').hidden = !['jansky_flux', 'wavelength_flux'].includes(type);
    }

    toggleSedUI(type) {
        document.getElementById('group-temperature').hidden = (type !== 'Temp');
    }

    toggleCalcStrategyUI(type) {
        document.getElementById('group-solve-snr').hidden = (type !== 'solve_snr');
        document.getElementById('group-solve-time').hidden = (type !== 'solve_time');
    }

    setLoadingState(isLoading) {
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
// 2. 智慧資料打包器 (PayloadBuilder)
// ==========================================
class PayloadBuilder {
    static build() {
        const payload = {};
        const formElements = document.getElementById('castor-form').elements;

        // 1. 自動遍歷所有表單元素，利用 . 拆分路徑自動建構巢狀 JSON
        for (let el of formElements) {
            if (!el.name || el.name.startsWith('preset_') || el.id === 'toggle-array-mode') continue;
            
            // 【打包 JSON 邏輯】：只略過真正二選一沒選到的動態欄位，把隱藏的 custom 數值一起打包！
            if (el.closest('.dynamic-group[hidden]')) {
                continue; 
            }

            const value = this._parseValue(el);
            if (value === null || value === '') continue;

            this._setNestedValue(payload, el.name.split('.'), value);
        }

        // 2. 特殊格式處理 (將當地時間轉換為後端需要的標準 UTC ISO 8601)
        if (payload.environment && payload.environment.observing_time_utc) {
            const localTimeString = payload.environment.observing_time_utc;
            const dateObj = new Date(localTimeString);
            payload.environment.observing_time_utc = dateObj.toISOString();
        }

        return payload;
    }

    static _parseValue(el) {
        if (el.type === 'number') {
            return el.value === '' ? null : parseFloat(el.value);
        }
        return el.value;
    }

    static _setNestedValue(obj, pathArray, value) {
        let current = obj;
        for (let i = 0; i < pathArray.length - 1; i++) {
            const part = pathArray[i];
            if (!current[part]) current[part] = {};
            current = current[part];
        }
        current[pathArray[pathArray.length - 1]] = value;
    }
}

// ==========================================
// 3. API 客戶端 (CastorAPI)
// ==========================================
class CastorAPI {
    static async calculate(payload) {
        try {
            const response = await fetch('/api/calculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json();
                const errorMsg = errorData.detail 
                    ? JSON.stringify(errorData.detail, null, 2) 
                    : JSON.stringify(errorData);
                throw new Error(errorMsg);
            }

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
        document.getElementById('results-placeholder').hidden = true;
        document.getElementById('results-container').hidden = false;

        this._renderWarnings(data.flags.warnings, data.flags.is_saturated);

        // --- 1. Signal & Noise Budget ---
        document.getElementById('res-source-rate').textContent = data.budget.source_count_rate.toFixed(2);
        document.getElementById('res-sky-rate').textContent = data.budget.sky_count_rate.toFixed(2);
        document.getElementById('res-peak-rate').textContent = data.budget.peak_pixel_rate.toFixed(2);
        document.getElementById('res-single-snr').textContent = data.core.single_snr.toFixed(2);

        // --- 2. Physical Diagnostics ---
        document.getElementById('res-total-fwhm').textContent = data.diagnostics.total_fwhm.toFixed(2);
        document.getElementById('res-pixel-scale').textContent = data.diagnostics.pixel_scale.toFixed(3);
        document.getElementById('res-eff-area').textContent = data.diagnostics.effective_area.toFixed(3);
        document.getElementById('res-throughput').textContent = (data.diagnostics.total_throughput * 100).toFixed(1);
        document.getElementById('res-enclosed-flux').textContent = (data.diagnostics.enclosed_flux_fraction * 100).toFixed(1);
        document.getElementById('res-num-pixels').textContent = data.diagnostics.num_pixels_aperture.toFixed(1);

        // --- 3. Limits ---
        document.getElementById('res-sat-time').textContent = data.core.saturation_time_limit.toFixed(2);

        // --- 4. Hero Result ---
        this._renderPrimary(data);

        const plotArea = document.getElementById('plot-area');
        if (isArrayMode) {
            plotArea.hidden = false;
        } else {
            plotArea.hidden = true;
        }
    }

    static _renderPrimary(data) {
        const labelEl = document.getElementById('primary-result-label');
        const valueEl = document.getElementById('primary-result-value');
        const descEl = document.getElementById('primary-result-desc');

        if (data.core.required_exposures === null || data.core.required_exposures === undefined) {
            labelEl.textContent = 'Signal-to-Noise Ratio (SNR)';
            valueEl.textContent = data.core.total_snr.toFixed(2);
            descEl.textContent = `Calculated based on provided exposure time.`;
        } else {
            labelEl.textContent = 'Required Exposures';
            valueEl.textContent = `${data.core.required_exposures} Frames`;
            descEl.textContent = `Target SNR Achieved: ${data.core.total_snr.toFixed(2)}`;
        }
    }

    static _renderWarnings(warnings, isSaturated) {
        const alertContainer = document.getElementById('alert-container');
        const warningList = document.getElementById('warning-list');
        warningList.innerHTML = ''; 

        let hasWarning = false;

        if (isSaturated) {
            hasWarning = true;
            const li = document.createElement('li');
            li.textContent = 'WARNING: The single exposure time exceeds the saturation limit (Full Well Capacity reached).';
            warningList.appendChild(li);
        }

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
}

// ==========================================
// 5. 步驟化表單控制器 (StepperController)
// ==========================================
class StepperController {
    constructor() {
        this.currentStep = 0;
        this.steps = Array.from(document.querySelectorAll('.step-content'));
        this.indicators = document.querySelectorAll('.stepper-indicator .step');
        
        this.btnNext = document.getElementById('btn-next');
        this.btnPrev = document.getElementById('btn-prev');
        this.btnSubmit = document.getElementById('btn-submit');

        this.bindEvents();
        this.updateUI(); // 確保初始狀態正確
    }

    bindEvents() {
        this.btnNext.addEventListener('click', () => this.nextStep());
        this.btnPrev.addEventListener('click', () => this.prevStep());
    }

    nextStep() {
        const currentSection = this.steps[this.currentStep];
        const inputs = currentSection.querySelectorAll('input, select');
        
        let isValid = true;
        for (let input of inputs) {
            // 【UI 驗證邏輯】：只要是隱藏的動態群組，或是收合的 custom 欄位，統統不做必填檢查！
            if (input.closest('.dynamic-group[hidden]') || input.closest('.hidden-detail')) {
                continue; 
            }

            if (!input.checkValidity()) {
                input.reportValidity(); // 彈出瀏覽器內建的警告
                isValid = false;
                break;
            }
        }

        if (!isValid) return;

        if (this.currentStep < this.steps.length - 1) {
            this.currentStep++;
            this.updateUI();
        }
    }

    prevStep() {
        if (this.currentStep > 0) {
            this.currentStep--;
            this.updateUI();
        }
    }

    updateUI() {
        this.steps.forEach((step, index) => {
            step.hidden = (index !== this.currentStep);
        });

        this.indicators.forEach((ind, index) => {
            if (index === this.currentStep) {
                ind.classList.add('active');
                ind.classList.remove('completed');
            } else if (index < this.currentStep) {
                ind.classList.remove('active');
                ind.classList.add('completed');
            } else {
                ind.classList.remove('active', 'completed');
            }
        });

        this.btnPrev.hidden = (this.currentStep === 0);
        
        if (this.currentStep === this.steps.length - 1) {
            this.btnNext.hidden = true;
            this.btnSubmit.hidden = false;
        } else {
            this.btnNext.hidden = false;
            this.btnSubmit.hidden = true;
        }
    }
}

// ==========================================
// 🚀 主程式進入點 (Main Execution)
// ==========================================
document.addEventListener('DOMContentLoaded', async () => {
    const ui = new UIController();
    await ui.loadPresets();

    // 啟動步驟化表單
    const stepper = new StepperController();

    document.getElementById('castor-form').addEventListener('submit', async (e) => {
        e.preventDefault(); 
        
        ui.setLoadingState(true);

        try {
            const payload = PayloadBuilder.build();
            console.log("JSON Payload to Send:", payload); 
            
            const resultData = await CastorAPI.calculate(payload);
            console.log("Response Received:", resultData);
            
            const isArrayMode = document.getElementById('toggle-array-mode').checked;
            ResultRenderer.render(resultData, isArrayMode);

        } catch (error) {
            alert(`Calculation Failed! \n\nReason: \n${error.message}`);
        } finally {
            ui.setLoadingState(false);
        }
    });
});