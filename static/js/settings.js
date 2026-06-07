/* settings.js — Open Accountant · Configuration Panel */
'use strict';

const Settings = {
  _tab:    'config',
  _config: {},
  _env:    [],
  _users:  [],
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
      const usersPromise = State.currentUser?.is_admin
        ? this._get('/auth/users').catch(error => {
          console.error('Settings.load users error:', error);
          return [];
        })
        : Promise.resolve([]);

      const [config, env, preferences, users] = await Promise.all([
        this._get('/settings/config'),
        this._get('/settings/env'),
        this._get('/settings/preferences'),
        usersPromise,
      ]);
      this._config = config || {};
      this._env    = env    || [];
      this._users  = users  || [];
      this._preferences = preferences || {};
    } catch (e) {
      console.error('Settings.load error:', e);
      this._config = {};
      this._env    = [];
      this._users  = [];
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
    const tabs = ['config', 'env', ...(State.currentUser?.is_admin ? ['users'] : [])];
    const tabLabels = {
      config: t('settings.tab.config'),
      env: t('settings.tab.env'),
      users: t('settings.tab.users'),
    };

    return `
      <div class="flex-1 min-h-0 overflow-y-auto overscroll-y-contain">
        <div class="max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-5 xl:px-4 py-6 pb-24 sm:pb-8 w-full">
          <h2 class="text-xl font-semibold text-dark-200 mb-6">⚙️ ${t('settings.title')}</h2>

          <!-- Tab strip -->
          <div class="sticky top-0 z-10 flex gap-1 mb-0 border-b border-dark-600 bg-dark-900/95 backdrop-blur supports-[backdrop-filter]:bg-dark-900/80">
            ${tabs.map(tab => {
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
            ${State.currentUser?.is_admin ? `<div id="spanel-users" class="${this._tab !== 'users' ? 'hidden' : ''}">${this._usersHTML()}</div>` : ''}
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
    document.getElementById('cfg-backup-export')?.addEventListener('click', () => this._downloadBackup());
    document.getElementById('cfg-backup-restore')?.addEventListener('click', () => this._openRestoreBackupPicker());
    document.getElementById('cfg-backup-file')?.addEventListener('change', e => this._restoreBackupFromFile(e));

    this._financeManualRateIds().forEach(id => {
      document.getElementById(id)?.addEventListener('input', () => this._handleManualFinanceRateInput());
    });

    document.querySelectorAll('.cfg-input, .pref-input').forEach(el => {
      el.addEventListener('input', () => this._syncConfigSaveButton());
      el.addEventListener('change', () => this._syncConfigSaveButton());
    });

    this._syncFinanceRateValidation();
    this._configFormSnapshot = this._serializeConfigForm();
    this._syncConfigSaveButton();
  },

  _switchTab(tab) {
    this._tab = tab;
    ['config','env','users'].forEach(t => {
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

    const cards = [];
    orderedSections.forEach(section => {
      cards.push(this._configSectionCard(section, this._config[section] || {}));
      if (section === 'general' && State.currentUser?.is_admin) {
        cards.push(this._backupSectionCard());
      }
    });

    return `
      <form id="cfg-form" class="flex flex-col gap-5">
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">${cards.join('')}</div>
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

  _backupSectionCard() {
    return `
      <section class="bg-dark-750/40 border border-dark-700 rounded-xl p-4 flex flex-col gap-4">
        <div>
          <h3 class="text-sm font-semibold text-dark-100">${t('settings.section.backup')}</h3>
          <p class="text-xs text-dark-500 mt-1">${t('settings.backup.scope_hint')}</p>
        </div>
        <div class="flex flex-col gap-2">
          <button id="cfg-backup-export" type="button" class="tbtn px-4 py-2 text-sm text-left">${t('settings.backup.export_button')}</button>
          <button id="cfg-backup-restore" type="button" class="tbtn px-4 py-2 text-sm text-left hover:!text-amber-300">${t('settings.backup.restore_button')}</button>
        </div>
        <p class="text-[11px] text-dark-500">${t('settings.backup.restore_warning')}</p>
        <input id="cfg-backup-file" type="file" accept="application/json,.json" class="hidden"/>
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
                   type="text" step="0.01" min="0" inputmode="decimal"
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
                   type="text" step="0.01" min="0" inputmode="decimal"
                   data-section="finance" data-key="usd_official_sell_ars" value="${escapeHtml(officialSell)}"
                   class="bg-dark-700 border border-dark-600 rounded-lg
                          text-dark-200 text-sm px-3 py-2 font-sans
                     focus:outline-none focus:border-blue-500/60 cfg-input"/>
          </label>
          <label class="flex flex-col gap-1.5 min-w-0">
            <span class="text-xs text-dark-400 uppercase tracking-wide">${t('settings.finance.blue_usd_buy')}</span>
            <input id="cfg-finance-usd-blue-buy-ars"
                   type="text" step="0.01" min="0" inputmode="decimal"
                   data-section="finance" data-key="usd_blue_buy_ars" value="${escapeHtml(blueBuy)}"
                   class="bg-dark-700 border border-dark-600 rounded-lg
                          text-dark-200 text-sm px-3 py-2 font-sans
                     focus:outline-none focus:border-blue-500/60 cfg-input"/>
          </label>
          <label class="flex flex-col gap-1.5 min-w-0">
            <span class="text-xs text-dark-400 uppercase tracking-wide">${t('settings.finance.blue_usd_sell')}</span>
            <input id="cfg-finance-usd-blue-sell-ars"
                   type="text" step="0.01" min="0" inputmode="decimal"
                   data-section="finance" data-key="usd_blue_sell_ars" value="${escapeHtml(blueSell)}"
                   class="bg-dark-700 border border-dark-600 rounded-lg
                          text-dark-200 text-sm px-3 py-2 font-sans
                     focus:outline-none focus:border-blue-500/60 cfg-input"/>
          </label>
          <label class="flex flex-col gap-1.5 min-w-0">
            <span class="text-xs text-dark-400 uppercase tracking-wide">${t('settings.finance.card_usd')}</span>
            <input id="cfg-finance-usd-card-ars"
                   type="text" step="0.01" min="0" readonly
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

  _financeRateState(inputOrId) {
    const input = typeof inputOrId === 'string' ? document.getElementById(inputOrId) : inputOrId;
    const parsed = parseMoneyInput(input?.value);
    if (parsed.isEmpty) return { isEmpty: true, isValid: true, value: null, normalized: '' };
    if (!parsed.isValid || !Number.isFinite(parsed.value) || parsed.value < 0) {
      return { isEmpty: false, isValid: false, value: Number.NaN, normalized: '' };
    }

    const rounded = Math.round(parsed.value * 100) / 100;
    return {
      isEmpty: false,
      isValid: true,
      value: rounded,
      normalized: rounded.toFixed(2),
    };
  },

  _setFinanceInputInvalid(input, invalid) {
    if (!input) return;
    input.classList.toggle('border-red-500/70', invalid);
    input.classList.toggle('focus:border-red-500/70', invalid);
    input.classList.toggle('focus:ring-red-500/20', invalid);
  },

  _syncFinanceRateValidation() {
    let hasInvalid = false;
    this._financeManualRateIds().forEach(id => {
      const input = document.getElementById(id);
      const state = this._financeRateState(input);
      const invalid = !state.isEmpty && !state.isValid;
      this._clearFieldValidation(id);
      this._setFinanceInputInvalid(input, invalid);
      if (invalid) hasInvalid = true;
    });
    return !hasInvalid;
  },

  _normalizedFinanceConfigValues() {
    const normalized = {};

    for (const id of this._financeManualRateIds()) {
      const input = document.getElementById(id);
      const key = input?.dataset.key;
      if (!input || !key) continue;

      const state = this._financeRateState(input);
      if (!state.isValid) {
        this._setFinanceInputInvalid(input, true);
        this._setFieldValidation(id, t('msg.invalid_money_input'));
        return null;
      }

      this._clearFieldValidation(id);
      this._setFinanceInputInvalid(input, false);
      normalized[key] = state.normalized;
    }

    normalized.usd_card_ars = this._calculateCardDollarRate(normalized.usd_official_sell_ars, '');
    return normalized;
  },

  _applyNormalizedFinanceValues(values = {}) {
    Object.entries(values).forEach(([key, value]) => {
      const input = document.querySelector(`.cfg-input[data-section="finance"][data-key="${key}"]`);
      if (input) input.value = value ?? '';
    });
  },

  _calculateCardDollarRate(officialSellValue, fallback = '') {
    const officialSellState = this._financeRateState({ value: officialSellValue });
    if (!officialSellState.isValid || officialSellState.isEmpty || officialSellState.value <= 0) return fallback;
    return (officialSellState.value * 1.30).toFixed(2);
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

  _backupFilename() {
    const stamp = new Date().toISOString().replace(/[.:]/g, '-');
    return `open-accountant-backup-${stamp}.json`;
  },

  async _downloadBackup() {
    const button = document.getElementById('cfg-backup-export');
    if (button) button.disabled = true;
    try {
      const payload = await this._get('/settings/backup/export');
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = this._backupFilename();
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      Toast.show(t('msg.settings_backup_exported'));
    } catch (e) {
      Toast.show(t('msg.error_generic', { msg: e.message }), 'error');
    } finally {
      if (button) button.disabled = false;
    }
  },

  _openRestoreBackupPicker() {
    const input = document.getElementById('cfg-backup-file');
    if (!input) return;
    input.value = '';
    input.click();
  },

  async _restoreBackupFromFile(event) {
    const input = event?.target;
    const file = input?.files?.[0];
    if (!file) return;

    const confirmed = await Dialog.confirm({
      title: t('settings.backup.restore_confirm_title'),
      message: t('settings.backup.restore_confirm_message'),
      confirmLabel: t('settings.backup.restore_button'),
      cancelLabel: t('btn.cancel'),
      submitTone: 'danger',
    });
    if (!confirmed) return;

    const restoreButton = document.getElementById('cfg-backup-restore');
    if (restoreButton) restoreButton.disabled = true;
    try {
      const rawText = await file.text();
      let backup;
      try {
        backup = JSON.parse(rawText);
      } catch {
        throw new Error(t('settings.backup.invalid_json'));
      }

      const response = await this._post('/settings/backup/restore', { backup });
      await API.loadAll().catch(() => null);
      await this.render();
      Toast.show(t('msg.settings_backup_restored', { count: response.restored_total_rows ?? 0 }));
    } catch (e) {
      Toast.show(t('msg.error_generic', { msg: e.message }), 'error');
    } finally {
      if (input) input.value = '';
      if (restoreButton) restoreButton.disabled = false;
    }
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
    const isValid = this._syncFinanceRateValidation();
    this._syncDerivedFinanceRates();
    const hasValue = this._financeManualRateIds().some(id => {
      const input = document.getElementById(id);
      return input && input.value.trim() !== '';
    });
    if (isValid) this._setFinanceLastUpdate(hasValue ? new Date().toISOString() : '');
  },

  _financeValuesFromRateResponse(data = {}) {
    const lastUpdate = data.last_update || new Date().toISOString();
    return {
      usd_official_buy_ars: Number(data.official_buy || 0).toFixed(2),
      usd_official_sell_ars: Number(data.official_sell || 0).toFixed(2),
      usd_blue_buy_ars: Number(data.blue_buy || 0).toFixed(2),
      usd_blue_sell_ars: Number(data.blue_sell || 0).toFixed(2),
      usd_card_ars: Number(data.card || 0).toFixed(2),
      usd_official_last_update: lastUpdate,
    };
  },

  _applyFetchedFinanceValues(values = {}) {
    this._syncingFinanceRate = true;
    this._applyNormalizedFinanceValues(values);
    this._syncDerivedFinanceRates();
    this._syncFinanceRateValidation();
    this._setFinanceLastUpdate(values.usd_official_last_update || '');
    this._syncingFinanceRate = false;
  },

  _setRefreshRatesActionBusy(isBusy) {
    document.querySelectorAll('[data-action="refresh-usd-rates"]').forEach(button => {
      button.disabled = isBusy;
      button.classList.toggle('opacity-60', isBusy);
      button.classList.toggle('cursor-not-allowed', isBusy);
    });
  },

  async fetchOfficialDollarRate() {
    const button = document.getElementById('cfg-finance-fetch-rate');
    if (!button) return;

    const previousLabel = button.textContent;
    button.disabled = true;
    button.textContent = t('settings.finance.fetching_button');

    try {
      const data = await this._get('/settings/finance/usd-rates');
      this._applyFetchedFinanceValues(this._financeValuesFromRateResponse(data));
      Toast.show(t('msg.official_dollar_loaded'));
    } catch (e) {
      Toast.show(t('msg.error_generic', {msg: e.message}), 'error');
    } finally {
      button.disabled = false;
      button.textContent = previousLabel;
    }
  },

  async refreshAndSaveDollarRates() {
    this._setRefreshRatesActionBusy(true);
    try {
      const rates = await this._get('/settings/finance/usd-rates');
      const financeValues = this._financeValuesFromRateResponse(rates);
      if (document.getElementById('cfg-form')) {
        this._applyFetchedFinanceValues(financeValues);
        await this._saveConfig({ successMessage: t('msg.official_dollar_saved') });
      } else {
        const response = await this._put('/settings/config', { finance: financeValues });
        this._config = response.config || this._config;
        if (typeof State !== 'undefined') State.appConfig = this._config;
        Toast.show(t('msg.official_dollar_saved'));
      }
    } catch (e) {
      Toast.show(t('msg.error_generic', { msg: e.message }), 'error');
    } finally {
      this._setRefreshRatesActionBusy(false);
    }
  },

  async _saveConfig({ successMessage } = {}) {
    const financeValues = this._normalizedFinanceConfigValues();
    if (financeValues == null) {
      Toast.show(t('msg.invalid_money_input'), 'error');
      return;
    }

    const data = {};
    document.querySelectorAll('.cfg-input').forEach(el => {
      const s = el.dataset.section, k = el.dataset.key;
      if (!data[s]) data[s] = {};
      data[s][k] = s === 'finance' && Object.prototype.hasOwnProperty.call(financeValues, k)
        ? financeValues[k]
        : el.value;
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
        this._applyNormalizedFinanceValues(financeValues);
        this._syncDerivedFinanceRates();
      }
      if (Object.keys(prefPatch).length) {
        this._preferences = await Preferences.save(prefPatch);
      }
      this._configFormSnapshot = this._serializeConfigForm();
      this._syncConfigSaveButton();
      Toast.show(successMessage || t('msg.config_saved'));
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

  _usersHTML() {
    if (!State.currentUser?.is_admin) {
      return `<p class="text-dark-400 text-sm">${t('settings.users.admin_only')}</p>`;
    }

    const rows = this._users.length
      ? this._users.map(user => {
        const isCurrent = State.currentUser?.id === user.id;
        const statusClass = user.is_active ? 'text-ingreso' : 'text-pasivo';
        const statusLabel = user.is_active ? t('settings.users.status_active') : t('settings.users.status_inactive');
        return `
          <div class="rounded-2xl border border-dark-700 bg-dark-900/50 px-4 py-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <h3 class="text-base font-semibold text-dark-100">${escapeHtml(user.username)}</h3>
                ${user.is_admin ? `<span class="inline-flex items-center rounded-full border border-blue-500/30 bg-blue-500/15 px-2 py-0.5 text-[11px] font-medium text-blue-300">${t('settings.users.role_admin')}</span>` : `<span class="inline-flex items-center rounded-full border border-dark-600 px-2 py-0.5 text-[11px] font-medium text-dark-400">${t('settings.users.role_member')}</span>`}
                ${isCurrent ? `<span class="inline-flex items-center rounded-full border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-[11px] font-medium text-amber-300">${t('settings.users.current_session')}</span>` : ''}
              </div>
              <div class="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-dark-500">
                <span class="${statusClass}">${escapeHtml(statusLabel)}</span>
                <span>${t('settings.users.created_at')}: ${new Date(user.created_at).toLocaleString()}</span>
              </div>
            </div>
            <div class="flex flex-wrap gap-2">
              <button type="button" onclick="Settings._openEditUserModal(${user.id})" class="tbtn text-xs px-3 py-1.5">${t('btn.edit')}</button>
              <button type="button" onclick="Settings._openPasswordModal(${user.id})" class="tbtn text-xs px-3 py-1.5">${t('settings.users.change_password')}</button>
              <button type="button" onclick="Settings._toggleUserActive(${user.id}, ${user.is_active ? 'false' : 'true'})" class="tbtn text-xs px-3 py-1.5 ${user.is_active ? 'hover:!text-red-400' : 'hover:!text-green-400'}">${user.is_active ? t('btn.deactivate') : t('btn.activate')}</button>
              ${isCurrent ? '' : `<button type="button" onclick="Settings._deleteUser(${user.id})" class="tbtn text-xs px-3 py-1.5 hover:!text-red-400">${t('settings.users.delete_user')}</button>`}
            </div>
          </div>`;
      }).join('')
      : `<p class="text-dark-400 text-sm">${t('settings.users.empty')}</p>`;

    return `
      <div class="flex flex-col gap-4">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 class="text-sm font-semibold text-dark-100">${t('settings.users.title')}</h3>
            <p class="text-xs text-dark-500 mt-1">${t('settings.users.subtitle')}</p>
          </div>
          <button type="button" onclick="Settings._openCreateUserModal()" class="tbtn px-4 py-2 text-sm">${t('settings.users.add_user')}</button>
        </div>
        <div class="flex flex-col gap-3">${rows}</div>
      </div>`;
  },

  _findUser(userId) {
    return this._users.find(user => Number(user.id) === Number(userId)) || null;
  },

  async _reloadUsers() {
    if (!State.currentUser?.is_admin) return;
    this._users = await this._get('/auth/users');
  },

  _userValidationRules() {
    return {
      minUsername: 3,
      maxUsername: 120,
      minPassword: 8,
    };
  },

  _validateUsername(username) {
    const value = String(username || '').trim();
    const { minUsername, maxUsername } = this._userValidationRules();
    if (!value) return t('settings.users.validation.username_required');
    if (value.length < minUsername) return t('settings.users.validation.username_short', { min: minUsername });
    if (value.length > maxUsername) return t('settings.users.validation.username_long', { max: maxUsername });
    return '';
  },

  _validatePassword(password) {
    const value = String(password || '');
    const { minPassword } = this._userValidationRules();
    if (!value) return t('settings.users.validation.password_required');
    if (value.length < minPassword) return t('settings.users.validation.password_short', { min: minPassword });
    return '';
  },

  _validateUserCreateForm({ username, password }) {
    return this._validateUsername(username) || this._validatePassword(password);
  },

  _validateUserEditForm({ username }) {
    return this._validateUsername(username);
  },

  _validatePasswordChangeForm({ password, confirmation }) {
    return this._validatePassword(password)
      || (!confirmation ? t('settings.users.validation.confirmation_required') : '')
      || (password !== confirmation ? t('settings.users.password_mismatch') : '');
  },

  _setFieldValidation(inputId, message) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.setCustomValidity(message || '');
    input.reportValidity();
  },

  _clearFieldValidation(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.setCustomValidity('');
  },

  _openCreateUserModal() {
    Modal.open(`
      <form data-modal-submit-form class="p-5 space-y-4">
        <p data-modal-description class="text-sm text-dark-400">${escapeHtml(t('settings.users.create_help'))}</p>
        <label class="flex flex-col gap-1.5">
          <span class="text-xs text-dark-400 uppercase tracking-wide">${t('settings.users.username')}</span>
          <input id="settings-user-create-username" type="text" data-modal-autofocus
                 class="bg-dark-700 border border-dark-600 rounded-lg text-dark-200 text-sm px-3 py-2 font-sans outline-none focus:border-blue-500/60">
        </label>
        <label class="flex flex-col gap-1.5">
          <span class="text-xs text-dark-400 uppercase tracking-wide">${t('settings.users.password')}</span>
          <input id="settings-user-create-password" type="password"
                 class="bg-dark-700 border border-dark-600 rounded-lg text-dark-200 text-sm px-3 py-2 font-sans outline-none focus:border-blue-500/60">
        </label>
        <label class="flex items-center gap-3 cursor-pointer select-none text-sm text-dark-300">
          <input id="settings-user-create-admin" type="checkbox" class="w-4 h-4 accent-blue-500">
          <span>${t('settings.users.make_admin')}</span>
        </label>
      </form>`, {
      title: t('settings.users.create_title'),
      submitLabel: t('btn.create'),
      onSubmit: async () => {
        const username = document.getElementById('settings-user-create-username')?.value?.trim() || '';
        const password = document.getElementById('settings-user-create-password')?.value || '';
        const isAdmin = !!document.getElementById('settings-user-create-admin')?.checked;
        this._clearFieldValidation('settings-user-create-username');
        this._clearFieldValidation('settings-user-create-password');
        const validationMessage = this._validateUserCreateForm({ username, password });
        if (validationMessage) {
          const targetId = !username || username.length < this._userValidationRules().minUsername
            ? 'settings-user-create-username'
            : 'settings-user-create-password';
          this._setFieldValidation(targetId, validationMessage);
          Toast.show(validationMessage, 'error');
          return false;
        }
        try {
          const created = await this._post('/auth/users', { username, password, is_admin: isAdmin });
          await this._reloadUsers();
          this._tab = 'users';
          await this.render();
          Toast.show(t('settings.users.created', { user: created.username }));
          return true;
        } catch (e) {
          Toast.show(t('msg.error_generic', { msg: e.message }), 'error');
          return false;
        }
      },
    });
  },

  _openEditUserModal(userId) {
    const user = this._findUser(userId);
    if (!user) return;

    Modal.open(`
      <form data-modal-submit-form class="p-5 space-y-4">
        <p data-modal-description class="text-sm text-dark-400">${escapeHtml(t('settings.users.edit_help', { user: user.username }))}</p>
        <label class="flex flex-col gap-1.5">
          <span class="text-xs text-dark-400 uppercase tracking-wide">${t('settings.users.username')}</span>
          <input id="settings-user-edit-username" type="text" data-modal-autofocus value="${escapeHtml(user.username)}"
                 class="bg-dark-700 border border-dark-600 rounded-lg text-dark-200 text-sm px-3 py-2 font-sans outline-none focus:border-blue-500/60">
        </label>
        <label class="flex items-center gap-3 cursor-pointer select-none text-sm text-dark-300">
          <input id="settings-user-edit-admin" type="checkbox" class="w-4 h-4 accent-blue-500" ${user.is_admin ? 'checked' : ''}>
          <span>${t('settings.users.make_admin')}</span>
        </label>
      </form>`, {
      title: t('settings.users.edit_title', { user: user.username }),
      submitLabel: t('btn.save'),
      onSubmit: async () => {
        const username = document.getElementById('settings-user-edit-username')?.value?.trim() || '';
        const isAdmin = !!document.getElementById('settings-user-edit-admin')?.checked;
        this._clearFieldValidation('settings-user-edit-username');
        const validationMessage = this._validateUserEditForm({ username });
        if (validationMessage) {
          this._setFieldValidation('settings-user-edit-username', validationMessage);
          Toast.show(validationMessage, 'error');
          return false;
        }

        if (username === user.username && isAdmin === !!user.is_admin) {
          Toast.show(t('settings.users.validation.no_changes'), 'error');
          return false;
        }

        try {
          const updated = await this._put(`/auth/users/${user.id}`, { username, is_admin: isAdmin });
          if (State.currentUser?.id === updated.id) {
            State.currentUser = { ...State.currentUser, username: updated.username, is_admin: updated.is_admin };
            Auth.renderSessionUi();
          }
          await this._reloadUsers();
          this._tab = 'users';
          await this.render();
          Toast.show(t('settings.users.updated', { user: updated.username }));
          return true;
        } catch (e) {
          Toast.show(t('msg.error_generic', { msg: e.message }), 'error');
          return false;
        }
      },
    });
  },

  _openPasswordModal(userId) {
    const user = this._findUser(userId);
    if (!user) return;

    Modal.open(`
      <form data-modal-submit-form class="p-5 space-y-4">
        <p data-modal-description class="text-sm text-dark-400">${escapeHtml(t('settings.users.password_help', { user: user.username }))}</p>
        <label class="flex flex-col gap-1.5">
          <span class="text-xs text-dark-400 uppercase tracking-wide">${t('settings.users.new_password')}</span>
          <input id="settings-user-password" type="password" data-modal-autofocus
                 class="bg-dark-700 border border-dark-600 rounded-lg text-dark-200 text-sm px-3 py-2 font-sans outline-none focus:border-blue-500/60">
        </label>
        <label class="flex flex-col gap-1.5">
          <span class="text-xs text-dark-400 uppercase tracking-wide">${t('settings.users.confirm_password')}</span>
          <input id="settings-user-password-confirm" type="password"
                 class="bg-dark-700 border border-dark-600 rounded-lg text-dark-200 text-sm px-3 py-2 font-sans outline-none focus:border-blue-500/60">
        </label>
      </form>`, {
      title: t('settings.users.change_password_title', { user: user.username }),
      submitLabel: t('settings.users.change_password'),
      onSubmit: async () => {
        const password = document.getElementById('settings-user-password')?.value || '';
        const confirmation = document.getElementById('settings-user-password-confirm')?.value || '';
        this._clearFieldValidation('settings-user-password');
        this._clearFieldValidation('settings-user-password-confirm');
        const validationMessage = this._validatePasswordChangeForm({ password, confirmation });
        if (validationMessage) {
          const targetId = !password || password.length < this._userValidationRules().minPassword
            ? 'settings-user-password'
            : 'settings-user-password-confirm';
          this._setFieldValidation(targetId, validationMessage);
          Toast.show(validationMessage, 'error');
          return false;
        }

        try {
          await this._put(`/auth/users/${user.id}/password`, { password });
          Toast.show(t('settings.users.password_updated', { user: user.username }));
          if (State.currentUser?.id === user.id) {
            await Auth.logout();
          }
          return true;
        } catch (e) {
          Toast.show(t('msg.error_generic', { msg: e.message }), 'error');
          return false;
        }
      },
    });
  },

  async _toggleUserActive(userId, nextActive) {
    const user = this._findUser(userId);
    if (!user) return;

    const confirmed = await Dialog.confirm({
      title: nextActive ? t('settings.users.activate_title', { user: user.username }) : t('settings.users.deactivate_title', { user: user.username }),
      message: nextActive ? t('settings.users.activate_confirm', { user: user.username }) : t('settings.users.deactivate_confirm', { user: user.username }),
      confirmLabel: nextActive ? t('btn.activate') : t('btn.deactivate'),
      cancelLabel: t('btn.cancel'),
      submitTone: nextActive ? 'primary' : 'danger',
    });
    if (!confirmed) return;

    try {
      await this._put(`/auth/users/${user.id}/status`, { is_active: !!nextActive });
      await this._reloadUsers();
      this._tab = 'users';
      await this.render();
      Toast.show(nextActive ? t('settings.users.activated', { user: user.username }) : t('settings.users.deactivated', { user: user.username }));
    } catch (e) {
      Toast.show(t('msg.error_generic', { msg: e.message }), 'error');
    }
  },

  async _deleteUser(userId) {
    const user = this._findUser(userId);
    if (!user) return;

    const confirmed = await Dialog.confirm({
      title: t('settings.users.delete_title', { user: user.username }),
      message: t('settings.users.delete_confirm', { user: user.username }),
      confirmLabel: t('settings.users.delete_user'),
      cancelLabel: t('btn.cancel'),
      submitTone: 'danger',
    });
    if (!confirmed) return;

    try {
      await this._del(`/auth/users/${user.id}`);
      await this._reloadUsers();
      this._tab = 'users';
      await this.render();
      Toast.show(t('settings.users.deleted', { user: user.username }));
    } catch (e) {
      Toast.show(t('msg.error_generic', { msg: e.message }), 'error');
    }
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

window.Settings = Settings;
