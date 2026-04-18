/* ── app.js — State, API client, View router, Filter, Modal, Toast ── */

import {
  BOARD_IMAGE_DEFAULT_URL,
  BOARD_IMAGE_MIME_TYPES,
  BOARD_IMAGE_NORMALIZED_SIZE,
  BOARD_VIEW_MODE_DEFAULT,
  accountBoardImageUrl,
  buildApiUrl,
  escapeHtml,
  fmt,
  fmtSigned,
  formatApiError,
  hasCustomBoardImageUrl,
  htmlAttrs,
  localNow,
  normalizeBoardViewMode,
  normalizeTagColor,
  parseMoneyInput,
  renderTagBadge,
} from './core/app-shared.js';

const t = (...args) => window.t(...args);
const getBoard = () => window.Board;
const getReports = () => window.Reports;
const getCharts = () => window.Charts;
const getProjections = () => window.Projections;
const getSettings = () => window.Settings;
const getAbout = () => window.About;
const getForms = () => window.Forms;
const getCommonTx = () => window.CommonTx;
const getFX = () => window.FX;

/* ─── STATE ──────────────────────────────────────────────────────── */
const State = {
  accounts:   [],
  types:      [],
  subtypes:   [],
  tags:       [],
  appConfig:  {},
  appVersion: null,
  filterFrom: null,
  filterTo:   null,
  tagFilterIds: [],
  userPreferences: {},
  hideBalanceAccounts: false,
  showZeroBalanceItems: false,
  boardViewMode: BOARD_VIEW_MODE_DEFAULT,
  balanceTypeFilter: [1, 2, 3, 4, 5],
  isAuthenticated: false,
  currentUser: null,
  sessionExpiresAt: null,
  usageOrder: JSON.parse(localStorage.getItem('acct_usage') || '{}'), // {id: timestamp}

  get filtered() { return !!(this.filterFrom && this.filterTo); },

  get currentYear() { return new Date().getFullYear(); },

  get hasTagFilter() { return Array.isArray(this.tagFilterIds) && this.tagFilterIds.length > 0; },

  get apiDateParams() {
    if (this.filtered) return `?from=${this.filterFrom}&to=${this.filterTo}`;
    return '';
  },

  syncTagFilters() {
    const validIds = new Set((this.tags || []).map(tag => Number(tag.id)));
    this.tagFilterIds = (this.tagFilterIds || []).map(Number).filter(tagId => validIds.has(tagId));
  },

  buildReportQuery(extra = {}) {
    const params = new URLSearchParams();
    if (this.filtered) {
      params.set('from', this.filterFrom);
      params.set('to', this.filterTo);
    }
    if (this.hasTagFilter) params.set('tag_ids', this.tagFilterIds.join(','));
    Object.entries(extra).forEach(([key, value]) => {
      if (value == null || value === '') return;
      params.set(key, String(value));
    });
    const query = params.toString();
    return query ? `?${query}` : '';
  },

  recordUsage(accountId) {
    this.usageOrder[accountId] = Date.now();
    localStorage.setItem('acct_usage', JSON.stringify(this.usageOrder));
  },

  sortedAccounts(typeId) {
    return this.accounts
      .filter(a => a.type_id === typeId)
      .sort((a, b) => (this.usageOrder[b.id] || 0) - (this.usageOrder[a.id] || 0));
  },
};

/* ─── API CLIENT ─────────────────────────────────────────────────── */
const API = {
  async _fetch(path, opts = {}) {
    const { skipAuthRedirect = false, headers: customHeaders = {}, ...fetchOpts } = opts;
    const r = await fetch(buildApiUrl(path), {
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', ...customHeaders },
      ...fetchOpts,
    });
    const parseError = async () => {
      const raw = await r.text().catch(() => 'Unknown error');
      try {
        const payload = JSON.parse(raw);
        return formatApiError(payload, raw || 'Unknown error');
      } catch {
        return raw || 'Unknown error';
      }
    };
    if ((r.status === 401 || r.status === 403) && !skipAuthRedirect) {
      const msg = await parseError();
      Auth.handleUnauthorized(msg);
      const error = new Error(msg);
      error.code = 'AUTH_REQUIRED';
      throw error;
    }
    if (!r.ok) {
      throw new Error(await parseError());
    }
    if (r.status === 204) return null;
    return r.json();
  },

  get(path, opts = {})         { return this._fetch(path, opts); },
  post(path, data, opts = {})  { return this._fetch(path, { method: 'POST', body: JSON.stringify(data), ...opts }); },
  put(path, data, opts = {})   { return this._fetch(path, { method: 'PUT', body: JSON.stringify(data), ...opts }); },
  del(path, opts = {})         { return this._fetch(path, { method: 'DELETE', ...opts }); },

  async loadVersion({ force = false } = {}) {
    if (State.appVersion && !force) return State.appVersion;
    State.appVersion = await this.get('/version', { skipAuthRedirect: true });
    return State.appVersion;
  },

  async loadAll() {
    const [accounts, types, subtypes, tags, version, config, preferences] = await Promise.all([
      this.get('/accounts' + State.apiDateParams),
      this.get('/types'),
      this.get('/subtypes'),
      this.get('/tags'),
      this.loadVersion({ force: true }),
      this.get('/settings/config'),
      this.get('/settings/preferences'),
    ]);
    State.accounts = accounts;
    State.types    = types;
    State.subtypes = subtypes;
    State.tags     = tags;
    State.appVersion = version;
    State.appConfig = config || {};
    State.userPreferences = preferences || {};
    State.syncTagFilters();
    StatusBar.refresh();
  },

  async reloadAccounts() {
    State.accounts = await this.get('/accounts' + State.apiDateParams);
    StatusBar.refresh();
  },

  async reloadTags() {
    State.tags = await this.get('/tags');
    State.syncTagFilters();
  },

  async reloadPreferences() {
    State.userPreferences = await this.get('/settings/preferences');
  },

  async reloadConfig() {
    State.appConfig = await this.get('/settings/config');
  },
};

const AppShell = {
  _booted: false,

  async bootstrap() {
    await API.loadAll();
    await Preferences.applyLoaded();
    applyAppVersion();
    await window.I18n.init();
    StatusBar.startClock();
    StatusBar.refresh();
    Filter._syncUi();
    Auth.renderSessionUi();
    await View.show('board');
    getFX()?.init?.();
    this._booted = true;
  },

  reset() {
    this._booted = false;
    State.accounts = [];
    State.types = [];
    State.subtypes = [];
    State.tags = [];
    State.appConfig = {};
    State.userPreferences = {};
  },
};

const Auth = {
  rememberedUserKey: 'oacc_remembered_username',
  _bound: false,

  _overlay() {
    return document.getElementById('auth-overlay');
  },

  _errorBox() {
    return document.getElementById('auth-error');
  },

  _submitButton() {
    return document.getElementById('auth-submit');
  },

  bindUi() {
    if (this._bound) return;
    document.getElementById('auth-form')?.addEventListener('submit', event => {
      event.preventDefault();
      this.login();
    });
    this._bound = true;
  },

  _setBusy(busy) {
    const submit = this._submitButton();
    if (!submit) return;
    submit.disabled = busy;
    submit.textContent = busy ? 'Signing in...' : 'Sign in';
  },

  _setError(message = '') {
    const errorBox = this._errorBox();
    if (!errorBox) return;
    errorBox.textContent = message;
    errorBox.classList.toggle('hidden', !message);
  },

  _rememberedUsername() {
    return localStorage.getItem(this.rememberedUserKey) || '';
  },

  _persistRememberedUsername(username, rememberMe) {
    if (rememberMe && username) {
      localStorage.setItem(this.rememberedUserKey, username);
      return;
    }
    localStorage.removeItem(this.rememberedUserKey);
  },

  _setSession(session) {
    State.isAuthenticated = !!session?.authenticated;
    State.currentUser = session?.user || null;
    State.sessionExpiresAt = session?.expires_at || null;
  },

  clearSessionState() {
    this._setSession(null);
    AppShell.reset();
    this.renderSessionUi();
  },

  showLogin(message = '') {
    const overlay = this._overlay();
    if (!overlay) return;
    const usernameInput = document.getElementById('auth-username');
    const passwordInput = document.getElementById('auth-password');
    const rememberInput = document.getElementById('auth-remember');
    if (usernameInput && !usernameInput.value) usernameInput.value = this._rememberedUsername();
    if (passwordInput) passwordInput.value = '';
    if (rememberInput) rememberInput.checked = !!this._rememberedUsername();
    this._setError(message || '');
    overlay.classList.remove('hidden');
    requestAnimationFrame(() => usernameInput?.focus());
  },

  hideLogin() {
    this._overlay()?.classList.add('hidden');
    this._setError('');
  },

  renderSessionUi() {
    const username = State.currentUser?.username || '';
    [
      { label: document.getElementById('session-user'), button: document.getElementById('session-logout') },
      { label: document.getElementById('session-user-mobile'), button: document.getElementById('session-logout-mobile') },
    ].forEach(({ label, button }) => {
      if (label) {
        label.textContent = username ? `Signed in as ${username}` : '';
        label.classList.toggle('hidden', !username);
      }
      if (button) button.classList.toggle('hidden', !username);
    });

    const board = getBoard();
    if (typeof board?.syncGlobalControls === 'function') board.syncGlobalControls();
  },

  async restoreSession() {
    const session = await API.get('/auth/session', { skipAuthRedirect: true });
    if (!session?.authenticated) {
      this.clearSessionState();
      this.showLogin(session?.message || '');
      return false;
    }
    this._setSession(session);
    this.hideLogin();
    this.renderSessionUi();
    return true;
  },

  async login() {
    const username = document.getElementById('auth-username')?.value?.trim() || '';
    const password = document.getElementById('auth-password')?.value || '';
    const rememberMe = !!document.getElementById('auth-remember')?.checked;

    this._setBusy(true);
    this._setError('');
    try {
      const session = await API.post('/auth/login', {
        username,
        password,
        remember_me: rememberMe,
      }, { skipAuthRedirect: true });
      this._persistRememberedUsername(username, rememberMe);
      this._setSession(session);
      this.hideLogin();
      this.renderSessionUi();
      await AppShell.bootstrap();
    } catch (error) {
      this.showLogin(error.message || 'Unable to sign in');
    } finally {
      this._setBusy(false);
    }
  },

  async logout() {
    try {
      await API.post('/auth/logout', {}, { skipAuthRedirect: true });
    } catch {
      // best-effort logout; client state is cleared regardless
    }
    Nav.close();
    this.clearSessionState();
    this.showLogin('Session closed.');
    const main = document.getElementById('main');
    if (main) main.innerHTML = '';
  },

  handleUnauthorized(message = 'Session expired. Please sign in again.') {
    if (!State.isAuthenticated && !State.currentUser) return;
    this.clearSessionState();
    this.showLogin(message);
    const main = document.getElementById('main');
    if (main) main.innerHTML = '';
  },
};

const Preferences = {
  async save(patch) {
    const previous = { ...State.userPreferences };
    State.userPreferences = { ...State.userPreferences, ...patch };

    try {
      const response = await API.put('/settings/preferences', patch);
      State.userPreferences = response.preferences || State.userPreferences;
      await this.applyLoaded();
      return State.userPreferences;
    } catch (error) {
      State.userPreferences = previous;
      throw error;
    }
  },

  async applyLoaded() {
    const prefs = State.userPreferences || {};
    State.hideBalanceAccounts = !!prefs.hide_balance_accounts;
    State.showZeroBalanceItems = !!prefs.show_zero_balance_accounts;
    State.boardViewMode = normalizeBoardViewMode(prefs.board_view_mode);

    const reports = getReports();
    if (reports) {
      const persistedSort = prefs.report_sort_directions;
      if (persistedSort && typeof persistedSort === 'object') {
        reports.dateSort = { ...reports.dateSort, ...persistedSort };
      }
    }

    const commonTx = getCommonTx();
    if (commonTx) {
      commonTx.applyPinnedStore(prefs.common_transactions_pins || {});
      await commonTx.migrateLegacyPins();
    }

    const board = getBoard();
    if (typeof board?.syncGlobalControls === 'function') board.syncGlobalControls();
  },
};

function applyAppVersion() {
  const version = State.appVersion;
  if (!version) return;

  document.title = version.full_title;

  ['app-title', 'app-title-mobile', 'auth-app-title'].forEach(id => {
    const headerTitle = document.getElementById(id);
    if (headerTitle) headerTitle.textContent = version.full_title;
  });

  const drawerTitle = document.getElementById('drawer-app-title');
  if (drawerTitle) drawerTitle.textContent = `💰 ${version.full_title}`;
}

const StatusBar = {
  _timer: null,

  _sumAccounts(predicate) {
    return State.accounts
      .filter(predicate)
      .reduce((total, account) => total + (Number(account.balance) || 0), 0);
  },

  _isDisponibilidad(account) {
    if (account.type_id !== 1) return false;
    const subtypeName = String(account.subtype_name || '').toLowerCase();
    return account.subtype_id === 1 || account.subtype_id === 2
      || subtypeName === 'current asset' || subtypeName === 'bank';
  },

  _metrics() {
    const currentAssets = this._sumAccounts(account => this._isDisponibilidad(account));
    const totalAssets = this._sumAccounts(account => account.type_id === 1);
    const totalLiabilities = this._sumAccounts(account => account.type_id === 2);
    const totalIncome = this._sumAccounts(account => account.type_id === 3);
    const totalExpense = this._sumAccounts(account => account.type_id === 4);
    const netResult = totalIncome - totalExpense;

    return [
      { label: t('status.current_assets'), value: fmt(currentAssets), cls: 'text-activo' },
      { label: t('status.total_assets'), value: fmt(totalAssets), cls: 'text-activo' },
      { label: t('status.total_liabilities'), value: fmt(totalLiabilities), cls: 'text-pasivo' },
      { label: t('status.net_result'), value: fmt(netResult), cls: netResult >= 0 ? 'text-ingreso' : 'text-pasivo' },
    ];
  },

  render() {
    const metricsEl = document.getElementById('status-metrics');
    const datetimeEl = document.getElementById('status-datetime');
    if (!metricsEl || !datetimeEl) return;

    metricsEl.innerHTML = this._metrics().map(item => `
      <span class="inline-flex items-center gap-1.5 shrink-0">
        <span class="text-dark-500">${escapeHtml(item.label)}:</span>
        <strong class="font-semibold ${item.cls}">${escapeHtml(item.value)}</strong>
      </span>`).join('<span class="text-dark-600 shrink-0">|</span>');

    this._renderClock();
  },

  _renderClock() {
    const datetimeEl = document.getElementById('status-datetime');
    if (!datetimeEl) return;

    const locale = document.documentElement.lang || 'en';
    const now = new Date();
    const date = now.toLocaleDateString(locale, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
    const time = now.toLocaleTimeString(locale, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });

    datetimeEl.textContent = `${date} ${time}`;
  },

  refresh() {
    this.render();
  },

  startClock() {
    if (this._timer) clearInterval(this._timer);
    this._renderClock();
    this._timer = setInterval(() => this._renderClock(), 1000);
  },
};

/* ─── VIEW ROUTER ────────────────────────────────────────────────── */
const View = {
  current: 'board',

  async show(name) {
    this.current = name;

    // Update toolbar active state
    document.querySelectorAll('.tbtn[data-view]').forEach(b => {
      b.classList.toggle('active', b.dataset.view === name);
    });

    const board = getBoard();
    if (typeof board?.syncGlobalControls === 'function') board.syncGlobalControls();

    const main = document.getElementById('main');
    main.innerHTML = '<div class="spinner">⏳ Cargando...</div>';

    try {
      const board = getBoard();
      const reports = getReports();
      const charts = getCharts();
      const projections = getProjections();
      const settings = getSettings();
      const about = getAbout();
      switch (name) {
        case 'board':    await board.render();   break;
        case 'balance':  await reports.balance(); break;
        case 'journal':  await reports.journal(); break;
        case 'ledger':   await reports.ledger();  break;
        case 'indicadores': await charts.panel(); break;
        case 'stats':    await charts.stats();    break;
        case 'proyecciones': await projections.render(); break;
        case 'subtypes':  await reports.subtypes();  break;
        case 'txlist':    await reports.journal();   break;
        case 'settings':  await settings.render(); break;
        case 'about':     await about.render();    break;
        default: main.innerHTML = '<div class="empty">Vista no encontrada</div>';
      }
    } catch (e) {
      main.innerHTML = `<div class="empty" style="color:#ef5350">Error: ${e.message}</div>`;
    }
  },

  async refresh() {
    await API.reloadAccounts();
    await API.reloadTags();
    await API.reloadPreferences();
    await Preferences.applyLoaded();
    await this.show(this.current);
  },
};

/* ─── FILTER ─────────────────────────────────────────────────────── */
const Filter = {
  activePresetKey: null,

  _syncUi() {
    const filterText = document.getElementById('filter-text');
    if (filterText) {
      filterText.textContent = State.filtered
        ? `${State.filterFrom} → ${State.filterTo}`
        : t('filter.no_filter');
    }

    ['tl-filter', 'mobile-filter-panel'].forEach(id => {
      document.getElementById(id)?.classList.toggle('filter-controls-active', State.filtered);
    });

    document.querySelectorAll('.qfilter-btn').forEach(button => {
      button.classList.toggle('filter-active', State.filtered);
      button.classList.toggle('qfilter-active',
        State.filtered && !!this.activePresetKey && button.dataset.filterKey === this.activePresetKey);
    });
  },

  /* ── Aplicar rango arbitrario ── */
  setRange(from, to, label, presetKey = null) {
    State.filterFrom = from;
    State.filterTo   = to;
    this.activePresetKey = presetKey;

    // Sincronizar ambos sets de inputs (desktop + mobile drawer)
    ['filter-from','filter-from-m'].forEach(id => {
      const el = document.getElementById(id); if (el) el.value = from;
    });
    ['filter-to','filter-to-m'].forEach(id => {
      const el = document.getElementById(id); if (el) el.value = to;
    });

    this._syncUi();
    View.refresh();
  },

  /* ── Atajos de período ── */
  setToday() {
    const now = new Date();
    const d = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
    this.setRange(d, d, t('filter.today'), 'filter.today');
  },

  setCurrentYear() {
    const y = new Date().getFullYear();
    this.setRange(`${y}-01-01`, `${y}-12-31`, t('filter.current_year'), 'filter.current_year');
  },

  setCurrentMonth() {
    const now = new Date();
    const y   = now.getFullYear();
    const m   = now.getMonth() + 1;                           // 1-based
    const last = new Date(y, m, 0).getDate();                 // último día del mes
    const mm  = String(m).padStart(2, '0');
    const dd  = String(last).padStart(2, '0');
    this.setRange(`${y}-${mm}-01`, `${y}-${mm}-${dd}`, t('filter.current_month'), 'filter.current_month');
  },

  setPrevMonth() {
    const now = new Date();
    let y  = now.getFullYear();
    let m0 = now.getMonth() - 1;                              // 0-based mes anterior
    if (m0 < 0) { m0 = 11; y--; }                            // enero → diciembre año anterior
    const m1   = m0 + 1;                                     // 1-based
    const last = new Date(y, m1, 0).getDate();
    const mm   = String(m1).padStart(2, '0');
    const dd   = String(last).padStart(2, '0');
    this.setRange(`${y}-${mm}-01`, `${y}-${mm}-${dd}`, t('filter.prev_month'), 'filter.prev_month');
  },

  apply() {
    const from = document.getElementById('filter-from').value;
    const to   = document.getElementById('filter-to').value;
    if (from && to) {
      State.filterFrom = from;
      State.filterTo   = to;
      this.activePresetKey = null;
    }
    this._syncUi();
    View.refresh();
  },

  clear() {
    State.filterFrom = null;
    State.filterTo   = null;
    this.activePresetKey = null;
    document.getElementById('filter-from').value = '';
    document.getElementById('filter-to').value   = '';
    this._syncUi();
    View.refresh();
  },
};

/* ─── MODAL ──────────────────────────────────────────────────────── */
const Modal = {
  _onSubmit: null,
  _onClose: null,
  _bound: false,
  _lastFocused: null,
  _labelSeq: 0,

  _submitClass(tone) {
    const variants = {
      primary: 'tbtn px-4 py-2 text-sm !bg-blue-600/20 !border-blue-500/50 !text-blue-300 hover:!bg-blue-600/40',
      danger: 'tbtn px-4 py-2 text-sm !bg-red-900/30 !border-pasivo/40 !text-pasivo hover:!bg-red-900/45',
    };
    return variants[tone] || variants.primary;
  },

  _isOpen() {
    const overlay = document.getElementById('modal-overlay');
    return !!overlay && !overlay.classList.contains('hidden');
  },

  _focusables(container) {
    if (!container) return [];
    return [...container.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')]
      .filter(el => !el.hasAttribute('hidden') && (el.offsetParent !== null || el === document.activeElement));
  },

  _focusInitial() {
    const box = document.getElementById('modal-box');
    const modalContent = document.getElementById('modal-content');
    if (!box || !modalContent) return;

    const preferred = modalContent.querySelector('[data-modal-autofocus], [autofocus]');
    if (preferred instanceof HTMLElement) {
      preferred.focus();
      preferred.select?.();
      return;
    }

    const [firstFocusable] = this._focusables(box);
    if (firstFocusable) {
      firstFocusable.focus();
      firstFocusable.select?.();
      return;
    }

    box.focus();
  },

  _trapFocus(event) {
    const box = document.getElementById('modal-box');
    const focusable = this._focusables(box);
    if (!focusable.length) {
      event.preventDefault();
      box?.focus();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
      return;
    }

    if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  },

  _applyAccessibility(title) {
    const box = document.getElementById('modal-box');
    const modalContent = document.getElementById('modal-content');
    if (!box || !modalContent) return;

    const titleEl = modalContent.querySelector('[data-modal-title]');
    if (titleEl) {
      if (!titleEl.id) titleEl.id = `modal-title-${++this._labelSeq}`;
      box.setAttribute('aria-labelledby', titleEl.id);
      box.removeAttribute('aria-label');
    } else if (title) {
      box.setAttribute('aria-label', String(title).replace(/<[^>]*>/g, '').trim());
      box.removeAttribute('aria-labelledby');
    } else {
      box.removeAttribute('aria-label');
      box.removeAttribute('aria-labelledby');
    }

    const descriptionEl = modalContent.querySelector('[data-modal-description]');
    if (descriptionEl) {
      if (!descriptionEl.id) descriptionEl.id = `modal-description-${++this._labelSeq}`;
      box.setAttribute('aria-describedby', descriptionEl.id);
    } else {
      box.removeAttribute('aria-describedby');
    }
  },

  _restoreFocus() {
    if (this._lastFocused instanceof HTMLElement) this._lastFocused.focus();
    this._lastFocused = null;
  },

  _bindEvents() {
    if (this._bound) return;

    document.addEventListener('click', event => {
      const closeButton = event.target.closest('[data-modal-close]');
      if (closeButton) {
        event.preventDefault();
        this.close();
        return;
      }

      const submitButton = event.target.closest('[data-modal-submit]');
      if (submitButton) {
        event.preventDefault();
        this._submit();
      }
    });

    document.addEventListener('submit', event => {
      const form = event.target.closest('form[data-modal-submit-form]');
      if (!form) return;
      event.preventDefault();
      this._submit();
    });

    document.addEventListener('keydown', event => {
      if (!this._isOpen()) return;
      if (event.key === 'Escape') {
        this.close();
        return;
      }
      if (event.key === 'Tab') this._trapFocus(event);
    });

    const overlay = document.getElementById('modal-overlay');
    overlay?.addEventListener('click', event => {
      if (event.target === overlay) this.close();
    });

    this._bound = true;
  },

  open(html, {
    wide = false,
    title = '',
    onSubmit = null,
    onClose = null,
    submitLabel = t('btn.confirm'),
    cancelLabel = t('btn.cancel'),
    submitTone = 'primary'
  } = {}) {
    this._bindEvents();
    this._onSubmit = onSubmit;
    this._onClose = onClose;
    this._lastFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const box = document.getElementById('modal-box');
    box.style.maxWidth = wide ? '860px' : '540px';
    box.setAttribute('tabindex', '-1');

    const header = title
      ? `<div class="flex items-center justify-between px-5 py-4 border-b border-dark-600">
           <h3 data-modal-title class="text-base font-semibold text-dark-200">${title}</h3>
           <button type="button" data-modal-close aria-label="${escapeHtml(t('dialog.close'))}" class="text-dark-400 hover:text-dark-300 text-xl leading-none">✕</button>
         </div>`
      : '';

    const footer = onSubmit
      ? `<div class="flex justify-end gap-2 px-5 py-4 border-t border-dark-600">
           <button type="button" data-modal-close
                   class="tbtn px-4 py-2 text-sm">${cancelLabel}</button>
           <button type="button" data-modal-submit
                   class="${this._submitClass(submitTone)}">${submitLabel}</button>
         </div>`
      : '';

    document.getElementById('modal-content').innerHTML = header + html + footer;
    this._applyAccessibility(title);
    document.getElementById('modal-overlay').classList.remove('hidden');
    requestAnimationFrame(() => this._focusInitial());
  },

  async _submit() {
    if (!this._onSubmit) return;
    const result = await this._onSubmit();
    if (result !== false) this.close();
  },

  close() {
    const onClose = this._onClose;
    this._onSubmit = null;
    this._onClose = null;
    document.getElementById('modal-overlay').classList.add('hidden');
    document.getElementById('modal-content').innerHTML = '';
    onClose?.();
    this._restoreFocus();
  },

  overlayClick(e) {
    if (e.target === document.getElementById('modal-overlay')) this.close();
  },
};

const Dialog = {
  confirm({ title = '', message = '', confirmLabel = t('btn.confirm'), cancelLabel = t('btn.cancel'), submitTone = 'primary' } = {}) {
    return new Promise(resolve => {
      let settled = false;

      Modal.open(`
        <div class="p-5">
          <p data-modal-description class="text-sm text-dark-300 whitespace-pre-line">${escapeHtml(message)}</p>
        </div>`, {
        title,
        submitLabel: confirmLabel,
        cancelLabel,
        submitTone,
        onSubmit: () => {
          settled = true;
          resolve(true);
          return true;
        },
        onClose: () => {
          if (!settled) resolve(false);
        },
      });
    });
  },

  prompt({
    title = '',
    label = '',
    value = '',
    placeholder = '',
    confirmLabel = t('btn.confirm'),
    cancelLabel = t('btn.cancel'),
    submitTone = 'primary',
    validate = null,
  } = {}) {
    const inputId = 'dialog-prompt-input';
    const errorId = 'dialog-prompt-error';

    return new Promise(resolve => {
      let settled = false;

      const setError = message => {
        const input = document.getElementById(inputId);
        const error = document.getElementById(errorId);
        if (input) {
          input.setAttribute('aria-invalid', message ? 'true' : 'false');
        }
        if (error) {
          error.textContent = message || '';
          error.classList.toggle('hidden', !message);
        }
      };

      Modal.open(`
        <form data-modal-submit-form class="p-5">
          <label class="block text-xs text-dark-400 mb-1.5" for="${inputId}">${escapeHtml(label)}</label>
          <input id="${inputId}" type="text"
                 value="${escapeHtml(value)}"
                 placeholder="${escapeHtml(placeholder)}"
                 data-modal-autofocus
                 aria-describedby="${errorId}"
                 class="w-full bg-dark-700 border border-dark-600 rounded-lg text-dark-300
                        text-sm px-3 py-2.5 font-sans outline-none
                        focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30">
          <p id="${errorId}" class="mt-2 hidden text-xs text-pasivo"></p>
        </form>`, {
        title,
        submitLabel: confirmLabel,
        cancelLabel,
        submitTone,
        onSubmit: () => {
          const nextValue = document.getElementById(inputId)?.value ?? '';
          const validationResult = validate ? validate(nextValue) : true;
          if (validationResult !== true) {
            setError(validationResult || t('msg.invalid_value'));
            document.getElementById(inputId)?.focus();
            document.getElementById(inputId)?.select?.();
            return false;
          }

          setError('');
          settled = true;
          resolve(nextValue);
          return true;
        },
        onClose: () => {
          if (!settled) resolve(null);
        },
      });
    });
  },
};

/* ─── TOAST ──────────────────────────────────────────────────────── */
const Toast = {
  _t: null,
  show(msg, type = 'ok') {
    const el = document.getElementById('toast');
    el.textContent = type === 'ok' ? '✅ ' + msg : '❌ ' + msg;
    el.className = `toast ${type}`;
    el.classList.remove('hidden');
    clearTimeout(this._t);
    this._t = setTimeout(() => el.classList.add('hidden'), 3000);
  },
};

/* ─── NAV DRAWER (mobile) ────────────────────────────────────────── */
const Nav = {
  toggle() {
    document.getElementById('nav-drawer').classList.toggle('hidden');
  },
  close() {
    document.getElementById('nav-drawer').classList.add('hidden');
  },
  async go(action) {
    this.close();
    const forms = getForms();
    if (action === 'new-account') { forms?.newAccount(); return; }
    if (action === 'tags') { forms?.tagModal(); return; }
    await View.show(action);
  },
};

/* ─── FILTER (mobile sync) ───────────────────────────────────────── */
const _FilterApply = Filter.apply.bind(Filter);
Filter.applyMobile = function () {
  const from = document.getElementById('filter-from-m').value;
  const to   = document.getElementById('filter-to-m').value;
  if (from && to) {
    // sync desktop fields too
    const df = document.getElementById('filter-from');
    const dt = document.getElementById('filter-to');
    if (df) df.value = from;
    if (dt) dt.value = to;
  }
  this.apply();
};
const _FilterClear = Filter.clear.bind(Filter);
Filter.clear = function () {
  ['filter-from', 'filter-to', 'filter-from-m', 'filter-to-m'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  State.filterFrom = null;
  State.filterTo   = null;
  this.activePresetKey = null;
  this._syncUi();
  View.refresh();
};

/* ─── MOBILE TABS + FAB VISIBILITY (inline style, sin conflictos CSS) ─── */
const isMobile = () => window.innerWidth < 1024;

const _ViewShow = View.show.bind(View);
View.show = async function (name) {
  const tabs = document.getElementById('mobile-type-tabs');
  const fab  = document.getElementById('fab');
  const show = (name === 'board') && isMobile();
  if (tabs) tabs.style.display = show ? 'flex' : 'none';
  if (fab)  fab.style.display  = show ? 'flex' : 'none';
  return _ViewShow(name);
};

Object.assign(window, {
  BOARD_IMAGE_DEFAULT_URL,
  BOARD_IMAGE_MIME_TYPES,
  BOARD_IMAGE_NORMALIZED_SIZE,
  BOARD_VIEW_MODE_DEFAULT,
  accountBoardImageUrl,
  buildApiUrl,
  escapeHtml,
  fmt,
  fmtSigned,
  formatApiError,
  hasCustomBoardImageUrl,
  htmlAttrs,
  localNow,
  normalizeBoardViewMode,
  normalizeTagColor,
  parseMoneyInput,
  renderTagBadge,
  State,
  API,
  AppShell,
  Auth,
  Preferences,
  StatusBar,
  View,
  Filter,
  Modal,
  Dialog,
  Toast,
  Nav,
});

document.addEventListener('DOMContentLoaded', async () => {
  Auth.bindUi();
  try {
    await API.loadVersion();
    applyAppVersion();
  } catch {
    // Keep static fallback title if version metadata is temporarily unavailable.
  }
  try {
    const hasSession = await Auth.restoreSession();
    if (!hasSession) return;
    await AppShell.bootstrap();
  } catch (e) {
    const backendOrigin = window.location.origin;
    document.getElementById('main').innerHTML =
      `<div class="empty" style="color:#ef5350">
        ⚠️ No se puede conectar al backend.<br>
        <small>Asegúrese de que el servidor corre en ${backendOrigin}</small>
      </div>`;
  }
});
