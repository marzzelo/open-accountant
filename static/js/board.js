/* ── board.js — Card board, drag & drop ── */
'use strict';

let _activeTab = 0; // índice de COLUMNS

const TYPE_CFG = {
  // type_name comes from the database (always English after seed migration)
  // accent colors only — name resolved at render time from State.types
  1: { accent: '#4fc3f7' },
  2: { accent: '#ef5350' },
  3: { accent: '#66bb6a' },
  4: { accent: '#ffd54f' },
  5: { accent: '#ce93d8' },
};
// Helper: resolve type name from State (DB) — fallback to t() key
function _typeName(typeId) {
  const found = (State.types || []).find(ty => ty.id === typeId);
  return found ? found.name : t(`account.type.${['','asset','liability','income','expense','equity'][typeId]}`);
}

// Definición de columnas del tablero — fácil de reordenar o fusionar
// COLUMNS.label is computed at render time from DB type names
const COLUMNS = [
  {
    id:     'asset',
    types:  [1],
    emoji:  '🏦',
    labelKey: 'board.col.asset',
    typeIds: [1],
    hdr:    'bg-[#0d2233] text-[#4fc3f7] border border-[#4fc3f722]',
    accent: '#4fc3f7',
  },
  {
    id:     'expense',
    types:  [4],
    emoji:  '🧾',
    labelKey: 'board.col.expense',
    typeIds: [4],
    hdr:    'bg-[#2a2000] text-[#ffd54f] border border-[#ffd54f22]',
    accent: '#ffd54f',
  },
  {
    id:     'income',
    types:  [3],
    emoji:  '📈',
    labelKey: 'board.col.income',
    typeIds: [3],
    hdr:    'bg-[#0e2a0e] text-[#66bb6a] border border-[#66bb6a22]',
    accent: '#66bb6a',
  },
  {
    id:     'liability-equity',
    types:  [2, 5],                                         // ← fusionados
    emoji:  '💳',
    labelKey: 'board.col.liab_eq',
    typeIds: [2, 5],
    hdr:    'bg-[#2a0e1e] text-[#ef5350] border border-[#ef535022]',
    accent: '#ef5350',
  },
];
// Column header label from i18n (UI label, not DB data)
function _colLabel(col) {
  return `${col.emoji} ${t(col.labelKey).toUpperCase()}`;
}

let drag = { active: false, sourceId: null, sourceEl: null };

const COMMON_TX_STORAGE_KEY = 'acct_common_tx_pins_v1';
const COMMON_TX_MAX_VISIBLE = 20;

const CommonTx = {
  _cache: new Map(),
  _pinnedStore: {},
  _legacyPinsChecked: false,

  _isExpanded() {
    return false;
  },

  _setExpanded() {},

  applyPinnedStore(items) {
    this._pinnedStore = items && typeof items === 'object' ? { ...items } : {};
  },

  _loadLegacyPinned() {
    try {
      return JSON.parse(localStorage.getItem(COMMON_TX_STORAGE_KEY) || '{}');
    } catch (_) {
      return {};
    }
  },

  async migrateLegacyPins() {
    if (this._legacyPinsChecked) return;
    this._legacyPinsChecked = true;

    const legacyPins = this._loadLegacyPinned();
    if (Object.keys(this._pinnedStore).length || !Object.keys(legacyPins).length) return;

    this.applyPinnedStore(legacyPins);
    try {
      await Preferences.save({ common_transactions_pins: legacyPins });
      localStorage.removeItem(COMMON_TX_STORAGE_KEY);
    } catch (_) {
      this._legacyPinsChecked = false;
    }
  },

  _signature(tx) {
    return [
      tx.credit_account,
      tx.debit_account,
      (tx.description || '').trim().toLowerCase(),
    ].join('|');
  },

  _formatLastDate(dateValue) {
    const [datePart = ''] = String(dateValue || '').split(' ');
    const [, month = '--', day = '--'] = datePart.split('-');
    return `${Number(day) || '--'}-${month}`;
  },

  _toShortcut(tx) {
    return {
      signature: this._signature(tx),
      creditId: tx.credit_account,
      creditName: tx.credit_name,
      debitId: tx.debit_account,
      debitName: tx.debit_name,
      description: (tx.description || '').trim(),
      lastDate: tx.date,
      pinned: false,
    };
  },

  _hydratePinned(saved) {
    const credit = State.accounts.find(acc => acc.id === saved.creditId);
    const debit = State.accounts.find(acc => acc.id === saved.debitId);
    if (!credit || !debit) return null;
    return {
      ...saved,
      creditName: credit.name,
      debitName: debit.name,
      pinned: true,
    };
  },

  async list() {
    await this.migrateLegacyPins();
    const recentTx = await API.get('/transactions?limit=120');
    const bySignature = new Map();

    recentTx.forEach(tx => {
      const shortcut = this._toShortcut(tx);
      if (!bySignature.has(shortcut.signature)) bySignature.set(shortcut.signature, shortcut);
    });

    const pinnedStore = this._pinnedStore;
    Object.entries(pinnedStore).forEach(([signature, saved]) => {
      const hydrated = this._hydratePinned(saved);
      if (!hydrated) return;
      const live = bySignature.get(signature);
      bySignature.set(signature, { ...hydrated, ...live, signature, pinned: true });
    });

    const all = [...bySignature.values()]
      .filter(item => item.creditId && item.debitId)
      .sort((left, right) => {
        if (left.pinned !== right.pinned) return left.pinned ? -1 : 1;
        return String(right.lastDate || '').localeCompare(String(left.lastDate || ''));
      });

    const visible = all.slice(0, COMMON_TX_MAX_VISIBLE);
    this._cache = new Map(visible.map(item => [item.signature, item]));
    return visible;
  },

  _card(shortcut) {
    const card = document.createElement('article');
    card.className = `common-tx-card${shortcut.pinned ? ' pinned' : ''}`;
    card.tabIndex = 0;
    card.setAttribute('role', 'button');
    card.setAttribute('aria-label', `${shortcut.creditName} → ${shortcut.debitName}`);
    card.addEventListener('click', () => this.use(shortcut.signature));
    card.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        this.use(shortcut.signature);
      }
    });

    const top = document.createElement('div');
    top.className = 'common-tx-top';

    const pinBtn = document.createElement('button');
    pinBtn.type = 'button';
    pinBtn.className = 'common-tx-pin';
    pinBtn.textContent = shortcut.pinned ? t('common.unpin') : t('common.pin');
    pinBtn.title = shortcut.pinned ? t('common.unpin') : t('common.pin');
    pinBtn.addEventListener('click', event => {
      event.stopPropagation();
      this.togglePin(shortcut.signature);
    });
    top.appendChild(pinBtn);

    if (shortcut.pinned) {
      const badge = document.createElement('span');
      badge.className = 'common-tx-badge';
      badge.textContent = t('common.pinned');
      top.appendChild(badge);
    }

    const title = document.createElement('div');
    title.className = 'common-tx-title';
    title.textContent = `${shortcut.creditName} → ${shortcut.debitName}`;

    const meta = document.createElement('div');
    meta.className = 'common-tx-meta';
    meta.textContent = `${t('common.last')}: ${this._formatLastDate(shortcut.lastDate)}`;

    card.appendChild(top);
    card.appendChild(title);

    if (shortcut.description) {
      const desc = document.createElement('div');
      desc.className = 'common-tx-desc';
      desc.textContent = shortcut.description;
      card.appendChild(desc);
    }

    card.appendChild(meta);
    return card;
  },

  async _populateList(listEl) {
    try {
      const shortcuts = await this.list();
      listEl.innerHTML = '';
      if (!shortcuts.length) {
        listEl.innerHTML = `<div class="common-tx-empty">${t('common.empty')}</div>`;
        return;
      }
      shortcuts.forEach(shortcut => listEl.appendChild(this._card(shortcut)));
    } catch (_) {
      listEl.innerHTML = `<div class="common-tx-empty">${t('common.empty')}</div>`;
    }
  },

  async togglePanel(button, content, forceExpanded = null) {
    const expanded = forceExpanded ?? !content.classList.contains('hidden');
    const nextExpanded = forceExpanded ?? !expanded;
    content.classList.toggle('hidden', !nextExpanded);
    button.setAttribute('aria-expanded', String(nextExpanded));
    button.title = nextExpanded ? t('common.collapse') : t('common.expand');
    this._setExpanded(nextExpanded);

    if (nextExpanded && !content.dataset.loaded) {
      content.dataset.loaded = '1';
      await this._populateList(content.querySelector('.common-tx-list'));
    }
  },

  async renderPanel() {
    const expanded = this._isExpanded();
    const section = document.createElement('section');
    section.className = `common-tx-panel${expanded ? ' is-open' : ''}`;
    section.innerHTML = `
      <div class="common-tx-shell">
        <button type="button" class="common-tx-toggle" aria-expanded="${expanded}"
                title="${expanded ? t('common.collapse') : t('common.expand')}">
          <span class="common-tx-heading">${t('common.title')}</span>
          <span class="common-tx-chevron" aria-hidden="true">${expanded ? '▾' : '▸'}</span>
        </button>
        <div class="common-tx-content${expanded ? '' : ' hidden'}">
          <p class="common-tx-subtitle">${t('common.subtitle')}</p>
          <div class="common-tx-list"></div>
        </div>
      </div>`;

    const toggleBtn = section.querySelector('.common-tx-toggle');
    const contentEl = section.querySelector('.common-tx-content');
    const chevronEl = section.querySelector('.common-tx-chevron');

    toggleBtn.addEventListener('click', async () => {
      await this.togglePanel(toggleBtn, contentEl);
      const isOpen = !contentEl.classList.contains('hidden');
      section.classList.toggle('is-open', isOpen);
      chevronEl.textContent = isOpen ? '▾' : '▸';
    });

    if (expanded) {
      contentEl.dataset.loaded = '1';
      await this._populateList(section.querySelector('.common-tx-list'));
    }

    return section;
  },

  async togglePin(signature) {
    const item = this._cache.get(signature);
    if (!item) return;

    const pinnedStore = { ...this._pinnedStore };
    const pinning = !pinnedStore[signature];

    if (!pinning) {
      delete pinnedStore[signature];
    } else {
      pinnedStore[signature] = {
        signature,
        creditId: item.creditId,
        creditName: item.creditName,
        debitId: item.debitId,
        debitName: item.debitName,
        description: item.description,
        lastDate: item.lastDate,
        pinned: true,
      };
    }

    this.applyPinnedStore(pinnedStore);

    try {
      await Preferences.save({ common_transactions_pins: pinnedStore });
      Toast.show(t(pinning ? 'common.pinned_saved' : 'common.unpinned'));
      await View.show('board');
    } catch (error) {
      Toast.show(t('msg.error_generic', {msg: error.message}), 'error');
    }
  },

  use(signature) {
    const item = this._cache.get(signature);
    if (!item) return;

    const credit = State.accounts.find(acc => acc.id === item.creditId);
    const debit = State.accounts.find(acc => acc.id === item.debitId);
    if (!credit || !debit) {
      Toast.show(t('common.account_missing'), 'err');
      return;
    }

    Forms.newTransaction(item.creditId, item.debitId, { description: item.description });
  },
};

const Board = {

  async render() {
    const main = document.getElementById('main');

    // Total por tipo y por columna (puede agrupar múltiples tipos)
    const typeTotals = {};
    State.accounts.forEach(a => { typeTotals[a.type_id] = (typeTotals[a.type_id] || 0) + a.balance; });

    const shell = document.createElement('div');
    shell.className = 'flex flex-col h-full min-h-0';

    const shortcutsPanel = await CommonTx.renderPanel();
    shell.appendChild(shortcutsPanel);

    const boardHost = document.createElement('div');
    boardHost.className = 'flex-1 min-h-0';

    const board = document.createElement('div');
    board.className = 'board';

    COLUMNS.forEach((col_cfg, colIdx) => {
      // Cuentas de todos los tipos de esta columna, ordenadas por uso reciente
      const accs = col_cfg.types
        .flatMap(tid => State.sortedAccounts(tid));

      // Total sumado de todos los tipos de la columna
      const colTotal = col_cfg.types.reduce((s, tid) => s + (typeTotals[tid] || 0), 0);

      const col = document.createElement('div');
      col.className = 'column';
      col.dataset.colIdx = colIdx;
      if (colIdx === _activeTab) col.classList.add('mobile-active');

      // Column header
      const hdr = document.createElement('div');
      hdr.className = `${col_cfg.hdr} flex items-center justify-between
                       px-3 py-2 rounded-xl text-xs font-bold uppercase tracking-wide
                       sticky top-0 z-10 shrink-0`;
      hdr.innerHTML = `<span>${_colLabel(col_cfg)}</span>
                       <span class="font-normal opacity-80 text-[11px]">${fmt(colTotal)}</span>`;
      col.appendChild(hdr);

      if (accs.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'text-dark-500 text-center py-8 text-xs';
        empty.textContent = t('board.empty');
        col.appendChild(empty);
      } else {
        accs.forEach(acc => {
          const typeCfg = TYPE_CFG[acc.type_id];
          col.appendChild(this.buildCard(acc, { accent: typeCfg.accent }));
        });
      }

      board.appendChild(col);
    });

    main.innerHTML = '';
    boardHost.appendChild(board);
    shell.appendChild(boardHost);
    main.appendChild(shell);
    this.initDrag();
    this.selectTab(_activeTab);
  },

  buildCard(acc, cfg) {
    const card = document.createElement('div');
    card.className = `card bg-dark-800 border border-dark-600 rounded-xl p-3.5`;
    card.dataset.accountId = acc.id;
    card.style.setProperty('--card-accent', cfg.accent);

    const balClass = acc.balance < 0
      ? 'text-pasivo'
      : 'text-[var(--card-accent)]';

    const bars = this._buildBars(acc.monthly_history, cfg.accent);
    const movs = acc.last_movements.length
      ? acc.last_movements.map(m => {
          const isPos = (acc.type_id === 1 || acc.type_id === 4)
            ? m.role === 'debit' : m.role === 'credit';
          const amtCls = isPos ? 'text-ingreso' : 'text-pasivo';
          const sign   = isPos ? '+' : '−';
          const desc   = m.description || m.counterpart || '—';
          return `<div class="flex justify-between text-[11px] mb-0.5">
            <span class="text-dark-400 truncate max-w-[60%]" title="${desc}">${desc}</span>
            <span class="font-semibold ${amtCls} shrink-0">${sign}${fmt(m.amount)}</span>
          </div>`;
        }).join('')
      : `<div class='text-[11px] text-dark-500'>${t('board.no_movements')}</div>`;

    card.innerHTML = `
      <div class="flex items-start justify-between mb-1">
        <span class="text-xl font-bold tracking-tight leading-tight text-dark-100 pr-2">${acc.name}</span>
        <button class="text-dark-400 hover:text-dark-300 text-lg px-0.5 shrink-0 border-0 bg-transparent cursor-pointer"
                onclick="Board.ctxMenu(event,${acc.id})">⋯</button>
      </div>
      <div class="text-[11px] text-dark-400 mb-3">${acc.type_name} · ${acc.subtype_name || '—'}</div>
      <div class="text-[22px] font-bold ${balClass} text-center my-2 tracking-tight">
        ${fmt(acc.balance)}
      </div>
      ${bars}
      <div class="mt-2 pt-2 border-t border-dark-600">
        <div class='text-[9px] text-dark-500 uppercase tracking-wide mb-1.5'>${t('board.last_movements').toUpperCase()}</div>
        ${movs}
      </div>`;

    return card;
  },

  _buildBars(history, accent) {
    if (!history?.length) return '';
    const vals = history.map(h => Math.abs(h.net));
    const max  = Math.max(...vals, 1);
    const bars = history.map((h, i) => {
      const pct    = Math.max(vals[i] / max, 0.05);
      const isLast = i === history.length - 1;
      return `<div class="hbar flex-1 rounded-sm"
               style="height:${Math.round(pct*100)}%;background:${accent};${isLast ? 'opacity:.75' : 'opacity:.22'}"
               title="${h.month}: ${fmtSigned(h.net)}"></div>`;
    }).join('');
    return `<div class="history-bars">${bars}</div>`;
  },

  ctxMenu(e, accId) {
    e.stopPropagation();
    document.querySelectorAll('.card-ctx-menu').forEach(m => m.remove());
    const menu = document.createElement('div');
    menu.className = 'card-ctx-menu';
    menu.innerHTML = `
      <button onclick="Forms.editAccount(${accId})">✏️ Editar cuenta</button>
      <button onclick="Forms.initialBalance(${accId})">💰 Saldo inicial</button>
      <button onclick="Board.showLedger(${accId})">📖 Libro mayor</button>
      <button class="danger" onclick="Forms.deleteAccount(${accId})">🗑 Eliminar</button>`;
    e.currentTarget.closest('.card').appendChild(menu);
    setTimeout(() => document.addEventListener('click', () => menu.remove(), { once: true }), 0);
  },

  showLedger(accId) { State._ledgerAccount = accId; View.show('ledger'); },

  selectTab(colIdx) {
    _activeTab = colIdx;
    const cfg = COLUMNS[colIdx];
    document.querySelectorAll('.mttab').forEach(t => {
      const active = parseInt(t.dataset.col) === colIdx;
      t.classList.toggle('active', active);
      t.style.setProperty('--tab-accent', active ? cfg.accent : '');
    });
    document.querySelectorAll('.column').forEach(col => {
      col.classList.toggle('mobile-active', parseInt(col.dataset.colIdx) === colIdx);
    });
  },

  initDrag() {
    const ghost = document.getElementById('ghost');
    const main  = document.getElementById('main');

    main.addEventListener('mousedown', e => {
      const card = e.target.closest('.card');
      if (!card || e.target.closest('.card-ctx-menu') || e.target.closest('button')) return;
      e.preventDefault();
      const acc = State.accounts.find(a => a.id === parseInt(card.dataset.accountId));
      if (!acc) return;
      drag = { active: true, sourceId: acc.id, sourceEl: card };
      ghost.innerHTML = `<span>💵</span><span>${acc.name}</span>`;
      ghost.style.cssText = `left:${e.clientX+14}px;top:${e.clientY+14}px`;
      ghost.classList.remove('hidden');
      card.classList.add('dragging');
    });

    document.addEventListener('mousemove', e => {
      if (!drag.active) return;
      ghost.style.left = e.clientX + 14 + 'px';
      ghost.style.top  = e.clientY + 14 + 'px';
      document.querySelectorAll('.card.drag-over').forEach(c => c.classList.remove('drag-over'));
      const el = document.elementFromPoint(e.clientX, e.clientY);
      const target = el?.closest('.card');
      if (target && parseInt(target.dataset.accountId) !== drag.sourceId)
        target.classList.add('drag-over');
    });

    document.addEventListener('mouseup', e => {
      if (!drag.active) return;
      ghost.classList.add('hidden');
      drag.sourceEl?.classList.remove('dragging');
      document.querySelectorAll('.card.drag-over').forEach(c => c.classList.remove('drag-over'));
      const el     = document.elementFromPoint(e.clientX, e.clientY);
      const target = el?.closest('.card');
      if (target && parseInt(target.dataset.accountId) !== drag.sourceId)
        Forms.newTransaction(drag.sourceId, parseInt(target.dataset.accountId));
      drag = { active: false, sourceId: null, sourceEl: null };
    });
  },
};
