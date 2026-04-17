/* i18n.js — Open Accountant · Internationalization
 *
 * Usage:
 *   t('nav.board')               → "Board" or "Tablero"
 *   t('msg.book_created', {name: 'home'}) → "Book 'home' created"
 *   I18n.setLanguage('es')       → switch to Spanish + re-render
 */
'use strict';

const I18n = {
  _dict:    {},
  _lang:    'en',
  _langs:   [],        // [{code, name}]

  /* ── Bootstrap (called once at app startup) ──────────────────────── */
  async init() {
    // Load available languages list
    try {
      this._langs = await window.API.get('/settings/languages');
    } catch (_) {}

    // Determine language: config.ini → fallback 'en'
    try {
      const cfg = await window.API.get('/settings/language');
      this._lang = cfg.language || 'en';
    } catch (_) { this._lang = 'en'; }

    await this._loadDict(this._lang);
    this._applyStatic();
  },

  /* ── Load translation dictionary ─────────────────────────────────── */
  async _loadDict(lang) {
    try {
      this._dict = await window.API.get(`/settings/translations/${lang}`);
      this._lang = lang;
    } catch (_) {
      console.warn(`[i18n] Could not load '${lang}', keeping current.`);
    }
  },

  /* ── Apply translations to static data-i18n elements ─────────────── */
  _applyStatic() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.dataset.i18n;
      const val = this.get(key);
      if (val) {
        if (el.tagName === 'INPUT' && el.placeholder !== undefined) {
          el.placeholder = val;
        } else {
          el.textContent = val;
        }
      }
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      const key = el.dataset.i18nTitle;
      const val = this.get(key);
      if (val) {
        el.title = val;
        el.setAttribute('aria-label', val);
      }
    });
    document.documentElement.lang = this._lang;
    if (window.StatusBar?.refresh) window.StatusBar.refresh();
  },

  /* ── Public: get translation (with optional interpolation) ────────── */
  get(key, vars = {}) {
    const raw = this._dict[key] || key;
    return raw.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? `{${k}}`);
  },

  /* ── Switch language ──────────────────────────────────────────────── */
  async setLanguage(lang) {
    if (lang === this._lang) return;
    await this._loadDict(lang);
    // Persist to config.ini via API
    try {
      await window.API.put('/settings/language', { language: lang });
    } catch (_) {}
    this._applyStatic();
    // Re-render current view
    await window.View.refresh();
    // Update language buttons
    document.querySelectorAll('[data-lang-btn]').forEach(btn => {
      btn.classList.toggle('!bg-blue-600/20', btn.dataset.langBtn === lang);
      btn.classList.toggle('!border-blue-500/50', btn.dataset.langBtn === lang);
      btn.classList.toggle('!text-blue-300', btn.dataset.langBtn === lang);
    });
  },

  /* ── Available languages ──────────────────────────────────────────── */
  availableLanguages() { return this._langs; },
  currentLanguage()    { return this._lang; },

  /* ── Language selector HTML ───────────────────────────────────────── */
  langSelectorHTML() {
    return this._langs.map(l => `
      <button data-lang-btn="${l.code}"
              onclick="I18n.setLanguage('${l.code}')"
              class="tbtn text-sm px-4 py-2
                     ${l.code === this._lang
                       ? '!bg-blue-600/20 !border-blue-500/50 !text-blue-300'
                       : ''}">
        ${l.name}
      </button>`).join('');
  },
};

/* Global shorthand */
function t(key, vars = {}) { return I18n.get(key, vars); }

window.I18n = I18n;
window.t = t;
