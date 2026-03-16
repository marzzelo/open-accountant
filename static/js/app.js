/* ── app.js — State, API client, View router, Filter, Modal, Toast ── */

'use strict';

/* ─── CONFIG ─────────────────────────────────────────────────────── */
// Resuelve automáticamente contra el host que sirvió la página
// → funciona tanto en localhost como desde dispositivos remotos en la red
const API_BASE = `${window.location.origin}/api`;

/* ─── LOCAL DATETIME HELPER ──────────────────────────────────────── */
// toISOString() siempre devuelve UTC. Ajustamos con el offset local del browser.
function localNow() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16); // "YYYY-MM-DDTHH:MM" en hora local
}

/* ─── CURRENCY FORMATTER ─────────────────────────────────────────── */
function fmt(v) {
  if (v == null) return '$ 0.00';
  const abs = Math.abs(v);
  const str = abs.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `$ ${str}`;
}
function fmtSigned(v) {
  if (v == null) return '$ 0.00';
  return (v < 0 ? '-' : '+') + fmt(v);
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[char]));
}

/* ─── STATE ──────────────────────────────────────────────────────── */
const State = {
  accounts:   [],
  types:      [],
  subtypes:   [],
  appVersion: null,
  filterFrom: null,
  filterTo:   null,
  userPreferences: {},
  showZeroBalanceItems: false,
  usageOrder: JSON.parse(localStorage.getItem('acct_usage') || '{}'), // {id: timestamp}

  get filtered() { return !!(this.filterFrom && this.filterTo); },

  get currentYear() { return new Date().getFullYear(); },

  get apiDateParams() {
    if (this.filtered) return `?from=${this.filterFrom}&to=${this.filterTo}`;
    return '';
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
    const r = await fetch(API_BASE + path, {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
    });
    if (!r.ok) {
      const msg = await r.text().catch(() => 'Unknown error');
      throw new Error(msg);
    }
    if (r.status === 204) return null;
    return r.json();
  },

  get(path)         { return this._fetch(path); },
  post(path, data)  { return this._fetch(path, { method: 'POST',   body: JSON.stringify(data) }); },
  put(path, data)   { return this._fetch(path, { method: 'PUT',    body: JSON.stringify(data) }); },
  del(path)         { return this._fetch(path, { method: 'DELETE' }); },

  async loadAll() {
    const [accounts, types, subtypes, version, preferences] = await Promise.all([
      this.get('/accounts' + State.apiDateParams),
      this.get('/types'),
      this.get('/subtypes'),
      this.get('/version'),
      this.get('/settings/preferences'),
    ]);
    State.accounts = accounts;
    State.types    = types;
    State.subtypes = subtypes;
    State.appVersion = version;
    State.userPreferences = preferences || {};
    StatusBar.refresh();
  },

  async reloadAccounts() {
    State.accounts = await this.get('/accounts' + State.apiDateParams);
    StatusBar.refresh();
  },

  async reloadPreferences() {
    State.userPreferences = await this.get('/settings/preferences');
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
    State.showZeroBalanceItems = !!prefs.show_zero_balance_accounts;

    if (typeof Reports !== 'undefined') {
      const persistedSort = prefs.report_sort_directions;
      if (persistedSort && typeof persistedSort === 'object') {
        Reports.dateSort = { ...Reports.dateSort, ...persistedSort };
      }
    }

    if (typeof CommonTx !== 'undefined') {
      CommonTx.applyPinnedStore(prefs.common_transactions_pins || {});
      await CommonTx.migrateLegacyPins();
    }
  },
};

function applyAppVersion() {
  const version = State.appVersion;
  if (!version) return;

  document.title = version.full_title;

  const headerTitle = document.getElementById('app-title');
  if (headerTitle) headerTitle.textContent = version.full_title;

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

  _isCurrentAsset(account) {
    if (account.type_id !== 1) return false;
    const subtypeName = String(account.subtype_name || '').toLowerCase();
    return account.subtype_id === 1 || subtypeName === 'current asset';
  },

  _metrics() {
    const currentAssets = this._sumAccounts(account => this._isCurrentAsset(account));
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

    const main = document.getElementById('main');
    main.innerHTML = '<div class="spinner">⏳ Cargando...</div>';

    try {
      switch (name) {
        case 'board':    await Board.render();   break;
        case 'balance':  await Reports.balance(); break;
        case 'journal':  await Reports.journal(); break;
        case 'ledger':   await Reports.ledger();  break;
        case 'stats':    await Charts.stats();    break;
        case 'subtypes':  await Reports.subtypes();  break;
        case 'txlist':    await Reports.txlist();    break;
        case 'settings':  await Settings.render(); break;
        case 'about':     await About.render();    break;
        default: main.innerHTML = '<div class="empty">Vista no encontrada</div>';
      }
    } catch (e) {
      main.innerHTML = `<div class="empty" style="color:#ef5350">Error: ${e.message}</div>`;
    }
  },

  async refresh() {
    await API.reloadAccounts();
    await API.reloadPreferences();
    await Preferences.applyLoaded();
    await this.show(this.current);
  },
};

/* ─── FILTER ─────────────────────────────────────────────────────── */
const Filter = {

  /* ── Aplicar rango arbitrario ── */
  setRange(from, to, label) {
    State.filterFrom = from;
    State.filterTo   = to;

    // Sincronizar ambos sets de inputs (desktop + mobile drawer)
    ['filter-from','filter-from-m'].forEach(id => {
      const el = document.getElementById(id); if (el) el.value = from;
    });
    ['filter-to','filter-to-m'].forEach(id => {
      const el = document.getElementById(id); if (el) el.value = to;
    });

    document.getElementById('filter-text').textContent = label;
    document.getElementById('filter-banner').classList.remove('hidden');

    // Resaltar el botón activo
    document.querySelectorAll('.qfilter-btn').forEach(b =>
      b.classList.toggle('qfilter-active',
                         b.dataset.label === label));
    View.refresh();
  },

  /* ── Atajos de período ── */
  setCurrentYear() {
    const y = new Date().getFullYear();
    this.setRange(`${y}-01-01`, `${y}-12-31`, t('filter.current_year'));
  },

  setCurrentMonth() {
    const now = new Date();
    const y   = now.getFullYear();
    const m   = now.getMonth() + 1;                           // 1-based
    const last = new Date(y, m, 0).getDate();                 // último día del mes
    const mm  = String(m).padStart(2, '0');
    const dd  = String(last).padStart(2, '0');
    this.setRange(`${y}-${mm}-01`, `${y}-${mm}-${dd}`, t('filter.current_month'));
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
    this.setRange(`${y}-${mm}-01`, `${y}-${mm}-${dd}`, t('filter.prev_month'));
  },

  apply() {
    const from = document.getElementById('filter-from').value;
    const to   = document.getElementById('filter-to').value;
    if (from && to) {
      State.filterFrom = from;
      State.filterTo   = to;
      document.getElementById('filter-text').textContent = `${from} → ${to}`;
      document.getElementById('filter-banner').classList.remove('hidden');
      // Limpiar resaltado de atajos si el usuario editó manualmente
      document.querySelectorAll('.qfilter-btn').forEach(b =>
        b.classList.remove('qfilter-active'));
    }
    View.refresh();
  },

  clear() {
    State.filterFrom = null;
    State.filterTo   = null;
    document.getElementById('filter-from').value = '';
    document.getElementById('filter-to').value   = '';
    document.getElementById('filter-text').textContent = t('filter.no_filter');
    document.getElementById('filter-banner').classList.add('hidden');
    View.refresh();
  },
};

/* ─── MODAL ──────────────────────────────────────────────────────── */
const Modal = {
  _onSubmit: null,

  open(html, { wide = false, title = '', onSubmit = null, submitLabel = 'Confirmar', cancelLabel = 'Cancelar' } = {}) {
    this._onSubmit = onSubmit;
    const box = document.getElementById('modal-box');
    box.style.maxWidth = wide ? '860px' : '540px';

    const header = title
      ? `<div class="flex items-center justify-between px-5 py-4 border-b border-dark-600">
           <h3 class="text-base font-semibold text-dark-200">${title}</h3>
           <button onclick="Modal.close()" class="text-dark-400 hover:text-dark-300 text-xl leading-none">✕</button>
         </div>`
      : '';

    const footer = onSubmit
      ? `<div class="flex justify-end gap-2 px-5 py-4 border-t border-dark-600">
           <button onclick="Modal.close()"
                   class="tbtn px-4 py-2 text-sm">${cancelLabel}</button>
           <button onclick="Modal._submit()"
                   class="tbtn px-4 py-2 text-sm !bg-blue-600/20 !border-blue-500/50 !text-blue-300
                          hover:!bg-blue-600/40">${submitLabel}</button>
         </div>`
      : '';

    document.getElementById('modal-content').innerHTML = header + html + footer;
    document.getElementById('modal-overlay').classList.remove('hidden');
  },

  async _submit() {
    if (!this._onSubmit) return;
    const result = await this._onSubmit();
    if (result !== false) this.close();
  },

  close() {
    this._onSubmit = null;
    document.getElementById('modal-overlay').classList.add('hidden');
    document.getElementById('modal-content').innerHTML = '';
  },

  overlayClick(e) {
    if (e.target === document.getElementById('modal-overlay')) this.close();
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
    if (action === 'new-account') { Forms.newAccount(); return; }
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
  document.getElementById('filter-text').textContent = t('filter.no_filter');
  document.getElementById('filter-banner').classList.add('hidden');
  document.querySelectorAll('.qfilter-btn').forEach(b =>
    b.classList.remove('qfilter-active'));
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

/* ─── INIT ───────────────────────────────────────────────────────── */
async function _initBookBadge() {
  try {
    const books = await API.get('/books');
    const cur = (books || []).find(b => b.current);
    if (cur) {
      ['current-book-badge', 'current-book-badge-m'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = cur.name;
      });
    }
  } catch (_) { /* non-critical */ }
}

document.addEventListener('DOMContentLoaded', async () => {
  try {
    await API.loadAll();
    await Preferences.applyLoaded();
    applyAppVersion();
    await I18n.init();         // load translations + apply static labels
    await _initBookBadge();
    StatusBar.startClock();
    StatusBar.refresh();
    await View.show('board');
  } catch (e) {
    document.getElementById('main').innerHTML =
      `<div class="empty" style="color:#ef5350">
        ⚠️ No se puede conectar al backend.<br>
        <small>Asegúrese de que el servidor corre en localhost:5001</small>
      </div>`;
  }
});
