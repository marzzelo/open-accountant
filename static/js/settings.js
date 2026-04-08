/* settings.js — Open Accountant · Configuration Panel */
'use strict';

const Settings = {
  _tab:    'config',
  _config: {},
  _env:    [],
  _preferences: {},
  _configFormSnapshot: '',
  _syncingFinanceRate: false,

  /* ── Helpers ──────────────────────────────────────────────────────────────── */
  async _get(path)          { return API.get(path); },
  async _post(path, data)   { return API.post(path, data); },
  async _put(path, data)    { return API.put(path, data); },
  async _del(path)          { return API.del(path); },

  /* ── Load all settings data ───────────────────────────────────────────────── */
  async load() {
    try {
      const [config, env, preferences] = await Promise.all([
        this._get('/settings/config'),
        this._get('/settings/env'),
        this._get('/settings/preferences'),
      ]);
      this._config = config || {};
      this._env    = env    || [];
      this._preferences = preferences || {};
    } catch (e) {
      console.error('Settings.load error:', e);
      this._config = {};
      this._env    = [];
      this._preferences = {};
    }
  },

  /* ── Render full settings panel into #main ────────────────────────────────── */
  async render() {
    const main = document.getElementById('main');
    main.innerHTML = '<div class="spinner">⏳ Cargando...</div>';
    await this.load();
    main.innerHTML = this._buildHTML();
    this._attachHandlers();
  },

  _buildHTML() {
    return `
      <div class="flex-1 min-h-0 overflow-y-auto overscroll-y-contain">
        <div class="max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-5 xl:px-4 py-6 pb-24 sm:pb-8 w-full">
          <h2 class="text-xl font-semibold text-dark-200 mb-6">⚙️ ${t('settings.title')}</h2>

          <!-- Tab strip -->
          <div class="sticky top-0 z-10 flex gap-1 mb-0 border-b border-dark-600 bg-dark-900/95 backdrop-blur supports-[backdrop-filter]:bg-dark-900/80">
            ${['config','env'].map(tab => {
              const tabLabels = { config: t('settings.tab.config'), env: t('settings.tab.env') };
              return `<button id="stab-${tab}" onclick="Settings._switchTab('${tab}')"
                      class="stab-btn px-4 py-2 text-sm rounded-t-lg border border-dark-600 border-b-0
                             cursor-pointer transition-colors
                             ${this._tab === tab
                               ? 'bg-dark-700 text-dark-200 border-b-dark-700'
                               : 'bg-dark-800 text-dark-400 hover:text-dark-300'}">
                ${tabLabels[tab]}
              </button>`;
            }).join('')}
          </div>

          <!-- Panels -->
          <div class="bg-dark-800 border border-dark-600 border-t-0 rounded-b-xl rounded-tr-xl p-5">
            <div id="spanel-config" class="${this._tab !== 'config' ? 'hidden' : ''}">${this._configHTML()}</div>
            <div id="spanel-env"    class="${this._tab !== 'env'    ? 'hidden' : ''}">${this._envHTML()}</div>
          </div>
        </div>
      </div>`;
  },

  _attachHandlers() {
    // Config form submit
    document.getElementById('cfg-form')?.addEventListener('submit', e => {
      e.preventDefault(); this._saveConfig();
    });
    // Env form submit
    document.getElementById('env-form')?.addEventListener('submit', e => {
      e.preventDefault(); this._saveEnv();
    });

    this._financeManualRateIds().forEach(id => {
      document.getElementById(id)?.addEventListener('input', () => this._handleManualFinanceRateInput());
    });

    document.querySelectorAll('.cfg-input, .pref-input').forEach(el => {
      el.addEventListener('input', () => this._syncConfigSaveButton());
      el.addEventListener('change', () => this._syncConfigSaveButton());
    });

    this._configFormSnapshot = this._serializeConfigForm();
    this._syncConfigSaveButton();
  },

  _switchTab(tab) {
    this._tab = tab;
    ['config','env'].forEach(t => {
      const btn = document.getElementById(`stab-${t}`);
      const panel = document.getElementById(`spanel-${t}`);
      if (btn) btn.className =
        `stab-btn px-4 py-2 text-sm rounded-t-lg border border-dark-600 border-b-0
         cursor-pointer transition-colors ` +
        (t === tab
          ? 'bg-dark-700 text-dark-200'
          : 'bg-dark-800 text-dark-400 hover:text-dark-300');
      if (panel) panel.className = t === tab ? '' : 'hidden';
    });
  },

  /* ── CONFIG panel ─────────────────────────────────────────────────────────── */
  _configHTML() {
    if (!Object.keys(this._config).length) {
      return `<p class="text-dark-400 text-sm">${t('settings.config.no_config')}</p>`;
    }

    const sectionOrder = ['general', 'finance', 'app'];
    const orderedSections = [
      ...sectionOrder,
      ...Object.keys(this._config).filter(section => !sectionOrder.includes(section)),
    ];

    const cards = orderedSections
      .map(section => this._configSectionCard(section, this._config[section] || {}))
      .join('');

    return `
      <form id="cfg-form" class="flex flex-col gap-5">
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">${cards}</div>
        <div class="flex items-center gap-3 pt-1">
          <button id="cfg-save-btn" type="submit" disabled
                  class="px-5 py-2 text-sm rounded-lg border transition-colors duration-150
                         border-dark-600 bg-dark-800 text-dark-500 cursor-not-allowed opacity-60">
            ${t('btn.save_config')}
          </button>
          <span class="text-xs text-dark-500">${t('settings.config.restart')}</span>
        </div>
      </form>`;
  },

  _configSectionCard(section, values) {
    const fields = Object.entries(values)
      .filter(([key]) => !this._isHiddenConfigField(section, key))
      .map(([key, value]) => this._configFieldHTML(section, key, value))
      .join('');

    const extras = [];
    if (section === 'finance') extras.push(this._financeSectionHTML());
    if (section === 'app') extras.push(`
      <div class="flex flex-col gap-2">
        <label class="text-xs text-dark-400 uppercase tracking-wide">${t('settings.language')}</label>
        <div class="flex gap-2 flex-wrap">${I18n.langSelectorHTML()}</div>
      </div>
      <div class="flex flex-col gap-2">
        <label class="text-xs text-dark-400 uppercase tracking-wide">⚡ FX</label>
        <label class="flex items-center gap-3 cursor-pointer select-none text-sm text-dark-300">
          <input type="checkbox" id="pref-fx-sounds"
                 class="w-4 h-4 accent-blue-500"
                 ${this._preferences.fx_sounds_enabled !== false ? 'checked' : ''}
                 onchange="Settings._onFxSoundsChange(event)"/>
          Sonidos de arrastre (buzz + crash)
        </label>
      </div>`);

    return `
      <section class="bg-dark-750/40 border border-dark-700 rounded-xl p-4 flex flex-col gap-4 ${section === 'finance' ? 'xl:col-span-2' : ''}">
        <div>
          <h3 class="text-sm font-semibold text-dark-100">${this._configSectionTitle(section)}</h3>
        </div>
        ${extras.join('')}
        ${fields ? `<div class="flex flex-col gap-3">${fields}</div>` : ''}
      </section>`;
  },

  _configSectionTitle(section) {
    const titles = {
      general: t('settings.section.general'),
      finance: t('settings.section.finance'),
      app: t('settings.section.app'),
    };
    return titles[section] || section;
  },

  _isHiddenConfigField(section, key) {
    const hidden = {
      app: ['language'],
      finance: ['usd_official_buy_ars', 'usd_official_sell_ars', 'usd_blue_buy_ars', 'usd_blue_sell_ars', 'usd_card_ars', 'usd_official_last_update'],
    };
    return (hidden[section] || []).includes(key);
  },

  _configFieldHTML(section, key, value) {
    return `
      <label class="flex flex-col gap-1.5">
        <span class="text-xs text-dark-400 uppercase tracking-wide">${this._configFieldLabel(section, key)}</span>
        <input type="text" data-section="${section}" data-key="${key}" value="${escapeHtml(value)}"
               class="bg-dark-700 border border-dark-600 rounded-lg
                      text-dark-200 text-sm px-3 py-2 font-sans
                      focus:outline-none focus:border-blue-500/60 cfg-input"/>
      </label>`;
  },

  _configFieldLabel(section, key) {
    const labels = {
      general: {
        host: t('settings.config.field.general.host'),
        port: t('settings.config.field.general.port'),
      },
      app: {
        name: t('settings.config.field.app.name'),
      },
    };
    return labels[section]?.[key] || key;
  },

  _financeSectionHTML() {
    const rate = this._financeConfigValue('usd_official_buy_ars', '0.00');
    const officialSell = this._financeConfigValue('usd_official_sell_ars', '0.00');
    const blueBuy = this._financeConfigValue('usd_blue_buy_ars', '0.00');
    const blueSell = this._financeConfigValue('usd_blue_sell_ars', '0.00');
    const cardRate = this._calculateCardDollarRate(officialSell, this._financeConfigValue('usd_card_ars', '0.00'));
    const lastUpdate = this._financeConfigValue('usd_official_last_update', '');

    return `
      <div class="flex flex-col gap-3">
        <div class="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_auto] gap-3 items-end">
          <label class="flex flex-col gap-1.5 min-w-0">
            <span class="text-xs text-dark-400 uppercase tracking-wide">${t('settings.finance.official_usd_buy')}</span>
            <input id="cfg-finance-usd-official-buy-ars"
                   type="number" step="0.01" min="0"
                   data-section="finance" data-key="usd_official_buy_ars" value="${escapeHtml(rate)}"
                   class="bg-dark-700 border border-dark-600 rounded-lg
                          text-dark-200 text-sm px-3 py-2 font-sans
                     focus:outline-none focus:border-blue-500/60 cfg-input"/>
          </label>
          <button id="cfg-finance-fetch-rate" type="button" onclick="Settings.fetchOfficialDollarRate()"
                  class="tbtn px-4 py-2 text-sm whitespace-nowrap">${t('settings.finance.fetch_button')}</button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          <label class="flex flex-col gap-1.5 min-w-0">
            <span class="text-xs text-dark-400 uppercase tracking-wide">${t('settings.finance.official_usd_sell')}</span>
            <input id="cfg-finance-usd-official-sell-ars"
                   type="number" step="0.01" min="0"
                   data-section="finance" data-key="usd_official_sell_ars" value="${escapeHtml(officialSell)}"
                   class="bg-dark-700 border border-dark-600 rounded-lg
                          text-dark-200 text-sm px-3 py-2 font-sans
                     focus:outline-none focus:border-blue-500/60 cfg-input"/>
          </label>
          <label class="flex flex-col gap-1.5 min-w-0">
            <span class="text-xs text-dark-400 uppercase tracking-wide">${t('settings.finance.blue_usd_buy')}</span>
            <input id="cfg-finance-usd-blue-buy-ars"
                   type="number" step="0.01" min="0"
                   data-section="finance" data-key="usd_blue_buy_ars" value="${escapeHtml(blueBuy)}"
                   class="bg-dark-700 border border-dark-600 rounded-lg
                          text-dark-200 text-sm px-3 py-2 font-sans
                     focus:outline-none focus:border-blue-500/60 cfg-input"/>
          </label>
          <label class="flex flex-col gap-1.5 min-w-0">
            <span class="text-xs text-dark-400 uppercase tracking-wide">${t('settings.finance.blue_usd_sell')}</span>
            <input id="cfg-finance-usd-blue-sell-ars"
                   type="number" step="0.01" min="0"
                   data-section="finance" data-key="usd_blue_sell_ars" value="${escapeHtml(blueSell)}"
                   class="bg-dark-700 border border-dark-600 rounded-lg
                          text-dark-200 text-sm px-3 py-2 font-sans
                     focus:outline-none focus:border-blue-500/60 cfg-input"/>
          </label>
          <label class="flex flex-col gap-1.5 min-w-0">
            <span class="text-xs text-dark-400 uppercase tracking-wide">${t('settings.finance.card_usd')}</span>
            <input id="cfg-finance-usd-card-ars"
                   type="number" step="0.01" min="0" readonly
                   data-section="finance" data-key="usd_card_ars" value="${escapeHtml(cardRate)}"
                   class="bg-dark-800 border border-dark-700 rounded-lg
                          text-dark-300 text-sm px-3 py-2 font-sans
                     focus:outline-none cfg-input"/>
          </label>
        </div>
        <div class="text-xs text-dark-500">
          ${t('settings.finance.last_update')}: <span id="cfg-finance-last-update-label">${this._formatConfigTimestamp(lastUpdate)}</span>
        </div>
        <input id="cfg-finance-usd-official-last-update" type="hidden"
               data-section="finance" data-key="usd_official_last_update" value="${escapeHtml(lastUpdate)}"
               class="cfg-input"/>
      </div>`;
  },

  _financeConfigValue(key, fallback = '') {
    const financeConfig = this._config.finance || {};
    const value = financeConfig[key];
    if (value != null && value !== '') return String(value);
    return fallback;
  },

  _financeManualRateIds() {
    return [
      'cfg-finance-usd-official-buy-ars',
      'cfg-finance-usd-official-sell-ars',
      'cfg-finance-usd-blue-buy-ars',
      'cfg-finance-usd-blue-sell-ars',
    ];
  },

  _calculateCardDollarRate(officialSellValue, fallback = '') {
    const officialSell = parseFloat(officialSellValue);
    if (!Number.isFinite(officialSell) || officialSell <= 0) return fallback;
    return (officialSell * 1.30).toFixed(2);
  },

  _syncDerivedFinanceRates() {
    const officialSellInput = document.getElementById('cfg-finance-usd-official-sell-ars');
    const cardInput = document.getElementById('cfg-finance-usd-card-ars');
    if (!officialSellInput || !cardInput) return;
    cardInput.value = this._calculateCardDollarRate(officialSellInput.value, '');
  },

  _formatConfigTimestamp(value) {
    if (!value) return '—';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return escapeHtml(value);
    return parsed.toLocaleString();
  },

  _setFinanceLastUpdate(value) {
    const rawValue = value || '';
    const hiddenInput = document.getElementById('cfg-finance-usd-official-last-update');
    const label = document.getElementById('cfg-finance-last-update-label');
    if (hiddenInput) hiddenInput.value = rawValue;
    if (label) label.textContent = rawValue ? this._formatConfigTimestamp(rawValue) : '—';
    this._syncConfigSaveButton();
  },

  _serializeConfigForm() {
    const payload = [];

    document.querySelectorAll('.cfg-input').forEach(el => {
      payload.push([
        'cfg',
        el.dataset.section || '',
        el.dataset.key || '',
        el.value ?? '',
      ]);
    });

    document.querySelectorAll('.pref-input').forEach(el => {
      payload.push([
        'pref',
        el.dataset.prefKey || '',
        el.value ?? '',
      ]);
    });

    return JSON.stringify(payload.sort((a, b) => a.join('|').localeCompare(b.join('|'))));
  },

  _syncConfigSaveButton() {
    const button = document.getElementById('cfg-save-btn');
    if (!button) return;

    const dirty = this._serializeConfigForm() !== this._configFormSnapshot;
    button.disabled = !dirty;

    if (dirty) {
      button.className = 'px-5 py-2 text-sm rounded-lg border transition-colors duration-150 border-amber-300/70 bg-amber-500 text-dark-950 font-semibold shadow-[0_0_0_1px_rgba(251,191,36,0.12)] hover:bg-amber-400 cursor-pointer';
    } else {
      button.className = 'px-5 py-2 text-sm rounded-lg border transition-colors duration-150 border-dark-600 bg-dark-800 text-dark-500 cursor-not-allowed opacity-60';
    }
  },

  _handleManualFinanceRateInput() {
    if (this._syncingFinanceRate) return;
    this._syncDerivedFinanceRates();
    const hasValue = this._financeManualRateIds().some(id => {
      const input = document.getElementById(id);
      return input && input.value.trim() !== '';
    });
    this._setFinanceLastUpdate(hasValue ? new Date().toISOString() : '');
  },

  async fetchOfficialDollarRate() {
    const button = document.getElementById('cfg-finance-fetch-rate');
    const officialBuyInput = document.getElementById('cfg-finance-usd-official-buy-ars');
    const officialSellInput = document.getElementById('cfg-finance-usd-official-sell-ars');
    const blueBuyInput = document.getElementById('cfg-finance-usd-blue-buy-ars');
    const blueSellInput = document.getElementById('cfg-finance-usd-blue-sell-ars');
    const cardInput = document.getElementById('cfg-finance-usd-card-ars');
    if (!button || !officialBuyInput || !officialSellInput || !blueBuyInput || !blueSellInput || !cardInput) return;

    const previousLabel = button.textContent;
    button.disabled = true;
    button.textContent = t('settings.finance.fetching_button');

    try {
      const data = await this._get('/settings/finance/usd-rates');
      this._syncingFinanceRate = true;
      officialBuyInput.value = Number(data.official_buy || 0).toFixed(2);
      officialSellInput.value = Number(data.official_sell || 0).toFixed(2);
      blueBuyInput.value = Number(data.blue_buy || 0).toFixed(2);
      blueSellInput.value = Number(data.blue_sell || 0).toFixed(2);
      cardInput.value = Number(data.card || 0).toFixed(2);
      this._setFinanceLastUpdate(data.last_update || new Date().toISOString());
      Toast.show(t('msg.official_dollar_loaded'));
    } catch (e) {
      Toast.show(t('msg.error_generic', {msg: e.message}), 'error');
    } finally {
      this._syncingFinanceRate = false;
      button.disabled = false;
      button.textContent = previousLabel;
    }
  },

  async _saveConfig() {
    const data = {};
    document.querySelectorAll('.cfg-input').forEach(el => {
      const s = el.dataset.section, k = el.dataset.key;
      if (!data[s]) data[s] = {};
      data[s][k] = el.value;
    });

    const prefPatch = {};
    document.querySelectorAll('.pref-input').forEach(el => {
      const key = el.dataset.prefKey;
      if (key) prefPatch[key] = el.value;
    });

    try {
      if (Object.keys(data).length) {
        const response = await this._put('/settings/config', data);
        this._config = response.config || this._config;
        if (typeof State !== 'undefined') State.appConfig = this._config;
      }
      if (Object.keys(prefPatch).length) {
        this._preferences = await Preferences.save(prefPatch);
      }
      this._configFormSnapshot = this._serializeConfigForm();
      this._syncConfigSaveButton();
      Toast.show(t('msg.config_saved'));
    } catch (e) { Toast.show(t('msg.error_generic', {msg: e.message}), 'error'); }
  },

  /* ── ENV panel ────────────────────────────────────────────────────────────── */
  _envHTML() {
    if (!this._env.length) {
      return `<p class="text-dark-400 text-sm">${t('settings.env.no_env')}</p>`;
    }

    const rows = this._env.map((p, i) => `
      <div id="env-row-${i}" class="flex items-center gap-2">
        <input type="text" value="${p.key}" data-env-key="${i}"
               class="w-44 bg-dark-700 border border-dark-600 rounded-lg
                      text-dark-300 text-xs px-3 py-2 font-mono shrink-0
                      focus:outline-none focus:border-blue-500/60"/>
        <input type="${p.sensitive ? 'password' : 'text'}" value="${p.value}"
               data-env-val="${i}"
               class="flex-1 bg-dark-700 border border-dark-600 rounded-lg
                      text-dark-300 text-xs px-3 py-2 font-mono
                      focus:outline-none focus:border-blue-500/60"/>
        ${p.sensitive ? `
          <button type="button" onclick="Settings._toggleEnvVis(${i})"
            class="tbtn text-[11px] px-2 py-1.5" title="${escapeHtml(t('settings.env.toggle_visibility'))}">👁</button>` : ''}
        <button type="button" onclick="Settings._removeEnvRow(${i})"
          class="tbtn text-[11px] px-2 py-1.5 hover:!text-red-400" title="${escapeHtml(t('btn.delete'))}">✕</button>
      </div>`).join('');

    return `
      <form id="env-form" class="flex flex-col gap-3">
        <div id="env-rows" class="flex flex-col gap-2.5">${rows}</div>
        <div>
          <button type="button" onclick="Settings._addEnvRow()"
                  class="tbtn text-xs px-3 py-1.5">${t('btn.add_var')}</button>
        </div>
        <div class="flex items-center gap-3 pt-1 border-t border-dark-700">
          <button type="submit" class="tbtn px-5 py-2 text-sm">${t('btn.save_env')}</button>
          <span class="text-xs text-dark-500">
            ${t('settings.env.hint')}
          </span>
        </div>
      </form>`;
  },

  async _onFxSoundsChange(event) {
    const checked = event.target.checked;
    // Actualizar la copia local para que re-renders muestren el estado correcto
    this._preferences.fx_sounds_enabled = checked;
    // Guardar directamente (mismo patrón que otros toggles del panel)
    await Preferences.save({ fx_sounds_enabled: checked });
    // Reproducir preview de audio si se activó
    if (typeof FX !== 'undefined') FX.toggleSound(checked);
  },

  _toggleEnvVis(i) {
    const el = document.querySelector(`[data-env-val="${i}"]`);
    if (el) el.type = el.type === 'password' ? 'text' : 'password';
  },

  _removeEnvRow(i) {
    document.getElementById(`env-row-${i}`)?.remove();
  },

  _addEnvRow() {
    const container = document.getElementById('env-rows');
    if (!container) return;
    const i = `new_${Date.now()}`;
    const div = document.createElement('div');
    div.id = `env-row-${i}`;
    div.className = 'flex items-center gap-2';
    div.innerHTML = `
      <input type="text" placeholder="VARIABLE" data-env-key="${i}"
             class="w-44 bg-dark-700 border border-dark-600 rounded-lg
                    text-dark-300 text-xs px-3 py-2 font-mono shrink-0
                    focus:outline-none focus:border-blue-500/60"/>
      <input type="text" placeholder="valor" data-env-val="${i}"
             class="flex-1 bg-dark-700 border border-dark-600 rounded-lg
                    text-dark-300 text-xs px-3 py-2 font-mono
                    focus:outline-none focus:border-blue-500/60"/>
      <button type="button" onclick="Settings._removeEnvRow('${i}')"
              class="tbtn text-[11px] px-2 py-1.5 hover:!text-red-400">✕</button>`;
    container.appendChild(div);
    div.querySelector('input')?.focus();
  },

  async _saveEnv() {
    const pairs = [];
    document.getElementById('env-rows')?.querySelectorAll('[data-env-key]').forEach(keyEl => {
      const idx = keyEl.dataset.envKey;
      const valEl = document.querySelector(`[data-env-val="${idx}"]`);
      const k = keyEl.value.trim();
      if (k) pairs.push({ key: k, value: valEl?.value ?? '' });
    });
    try {
      await this._put('/settings/env', pairs);
      Toast.show(t('msg.env_saved'));
    } catch (e) { Toast.show(t('msg.env_save_error'), 'error'); }
  },
};
