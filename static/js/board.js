/* ── board.js — Card board, drag & drop ── */
'use strict';

let _activeTab = 0; // índice de COLUMNS
const MOBILE_SWIPE_DISTANCE = 56;
const MOBILE_SWIPE_VERTICAL_TOLERANCE = 48;

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
  return found ? found.name : t(`account.type.${['', 'asset', 'liability', 'income', 'expense', 'equity'][typeId]}`);
}

// Definición de columnas del tablero — fácil de reordenar o fusionar
// COLUMNS.label is computed at render time from DB type names
const COLUMNS = [
  {
    id: 'asset',
    types: [1],
    iconSrc: '/images/asset.png',
    iconAlt: t('board.tab.asset'),
    labelKey: 'board.col.asset',
    typeIds: [1],
    hdr: 'bg-[#0d2233] text-[#4fc3f7] border border-[#4fc3f722]',
    accent: '#4fc3f7',
  },
  {
    id: 'expense',
    types: [4],
    iconSrc: '/images/expense.png',
    iconAlt: t('board.tab.expense'),
    labelKey: 'board.col.expense',
    typeIds: [4],
    hdr: 'bg-[#2a2000] text-[#ffd54f] border border-[#ffd54f22]',
    accent: '#ffd54f',
  },
  {
    id: 'income',
    types: [3],
    iconSrc: '/images/income.png',
    iconAlt: t('board.tab.income'),
    labelKey: 'board.col.income',
    typeIds: [3],
    hdr: 'bg-[#0e2a0e] text-[#66bb6a] border border-[#66bb6a22]',
    accent: '#66bb6a',
  },
  {
    id: 'liability-equity',
    types: [2, 5],
    iconSrc: '/images/liability.png',
    iconAlt: t('board.tab.liab_eq'),
    labelKey: 'board.col.liab_eq',
    typeIds: [2, 5],
    hdr: 'bg-[#2a0e1e] text-[#ef5350] border border-[#ef535022]',
    accent: '#ef5350',
  },
];

// Column header label from i18n (UI label, not DB data)
function _colLabel(col) {
  return `<span class="inline-flex items-center gap-2 min-w-0">
    <img src="${col.iconSrc}" alt="${escapeHtml(col.iconAlt)}" class="board-col-icon" draggable="false">
    <span class="truncate">${t(col.labelKey).toUpperCase()}</span>
  </span>`;
}

let drag = { active: false, sourceId: null, sourceEl: null, pointerId: null };

const LONG_PRESS_MS = 450;
const POINTER_MOVE_TOLERANCE = 8;
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
      Toast.show(t('msg.error_generic', { msg: error.message }), 'error');
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
  _eventsBound: false,
  _press: null,
  _swipe: null,
  _swipeIgnoreUntil: 0,
  _pendingCredit: { accountId: null, cardEl: null },
  _suppressedClick: { accountId: null, until: 0 },

  _pendingCreditAccount() {
    if (!this._pendingCredit.accountId) return null;
    return State.accounts.find(account => account.id === this._pendingCredit.accountId) || null;
  },

  _refreshPendingCreditHint() {
    const hint = document.getElementById('board-pending-credit-hint');
    if (!hint) return;

    const account = this._pendingCreditAccount();
    if (!account) {
      hint.classList.add('hidden');
      hint.innerHTML = '';
      return;
    }

    hint.classList.remove('hidden');
    hint.innerHTML = `
      <div class="flex items-center justify-between gap-3 rounded-xl border border-blue-500/25 bg-blue-500/10 px-3 py-2 text-sm text-blue-100">
        <div class="min-w-0">
          <div class="text-[10px] font-semibold uppercase tracking-wide text-blue-300">${escapeHtml(t('board.pending_credit_title'))}</div>
          <div class="truncate">${escapeHtml(t('board.pending_credit_hint', { name: account.name }))}</div>
        </div>
        <button type="button" class="shrink-0 rounded-lg border border-blue-400/20 px-2 py-1 text-xs text-blue-200 hover:bg-blue-400/10"
                onclick="Board.clearPendingCreditHint()">${escapeHtml(t('btn.cancel'))}</button>
      </div>`;
  },

  clearPendingCreditHint() {
    this._clearPendingCredit();
  },

  _isCardActionTarget(target) {
    return Boolean(target.closest('.card-ctx-menu') || target.closest('button'));
  },

  _clearPress() {
    if (!this._press) return;
    clearTimeout(this._press.timerId);
    this._press = null;
  },

  _clearSwipe() {
    this._swipe = null;
  },

  _suppressNextClick(accountId) {
    this._suppressedClick = { accountId, until: Date.now() + 500 };
  },

  _shouldSuppressClick(accountId) {
    if (this._suppressedClick.accountId !== accountId) return false;
    if (Date.now() > this._suppressedClick.until) {
      this._suppressedClick = { accountId: null, until: 0 };
      return false;
    }
    return true;
  },

  _clearPendingCredit() {
    this._pendingCredit.cardEl?.classList.remove('credit-selected');
    this._pendingCredit = { accountId: null, cardEl: null };
    this._refreshPendingCreditHint();
  },

  _setPendingCredit(accountId, cardEl) {
    this._clearPendingCredit();
    cardEl.classList.add('credit-selected');
    this._pendingCredit = { accountId, cardEl };
    this._suppressNextClick(accountId);
    this._refreshPendingCreditHint();
  },

  _resetDragState() {
    const ghost = document.getElementById('ghost');
    ghost?.classList.add('hidden');
    drag.sourceEl?.classList.remove('dragging');
    document.querySelectorAll('.card.drag-over').forEach(card => card.classList.remove('drag-over'));
    drag = { active: false, sourceId: null, sourceEl: null, pointerId: null };
  },

  _startDrag(card, accountId, clientX, clientY, pointerId) {
    const ghost = document.getElementById('ghost');
    if (!ghost) return;

    drag = { active: true, sourceId: accountId, sourceEl: card, pointerId };
    ghost.innerHTML = '<img src="images/dollars.png" alt="" class="ghost-image">';
    ghost.style.cssText = `left:${clientX}px;top:${clientY}px`;
    ghost.classList.remove('hidden');
    card.classList.add('dragging');
  },

  _updateDrag(clientX, clientY) {
    if (!drag.active) return;

    const ghost = document.getElementById('ghost');
    if (!ghost) return;

    ghost.style.left = clientX + 'px';
    ghost.style.top = clientY + 'px';
    document.querySelectorAll('.card.drag-over').forEach(card => card.classList.remove('drag-over'));

    const el = document.elementFromPoint(clientX, clientY);
    const target = el?.closest('.card');
    if (target && parseInt(target.dataset.accountId, 10) !== drag.sourceId)
      target.classList.add('drag-over');
  },

  _finishDrag(clientX, clientY) {
    if (!drag.active) return;

    const sourceId = drag.sourceId;
    this._resetDragState();

    const el = document.elementFromPoint(clientX, clientY);
    const target = el?.closest('.card');
    if (target && parseInt(target.dataset.accountId, 10) !== sourceId)
      Forms.newTransaction(sourceId, parseInt(target.dataset.accountId, 10));
  },

  _handlePointerDown(e) {
    if (e.pointerType === 'touch' && isMobile()) {
      this._swipe = {
        pointerId: e.pointerId,
        startX: e.clientX,
        startY: e.clientY,
        handled: false,
      };
    }

    if (e.pointerType === 'mouse' && e.button !== 0) return;

    const card = e.target.closest('.card');
    if (!card || this._isCardActionTarget(e.target)) return;

    const accountId = parseInt(card.dataset.accountId, 10);
    if (Number.isNaN(accountId)) return;

    this._clearPress();
    this._press = {
      pointerId: e.pointerId,
      pointerType: e.pointerType,
      accountId,
      cardEl: card,
      startX: e.clientX,
      startY: e.clientY,
      timerId: setTimeout(() => {
        if (!this._press || this._press.pointerId !== e.pointerId) return;
        this._setPendingCredit(accountId, card);
        this._clearPress();
      }, LONG_PRESS_MS),
    };
  },

  _handlePointerMove(e) {
    if (this._swipe && this._swipe.pointerId === e.pointerId && !this._swipe.handled) {
      const deltaX = e.clientX - this._swipe.startX;
      const deltaY = e.clientY - this._swipe.startY;
      if (Math.abs(deltaY) <= MOBILE_SWIPE_VERTICAL_TOLERANCE && Math.abs(deltaX) >= MOBILE_SWIPE_DISTANCE) {
        e.preventDefault();
        this._swipe.handled = true;
        this._swipeIgnoreUntil = Date.now() + 350;
        this._clearPress();
        this.selectRelativeTab(deltaX > 0 ? -1 : 1);
        return;
      }
      if (Math.abs(deltaY) > MOBILE_SWIPE_VERTICAL_TOLERANCE) this._swipe.handled = true;
    }

    if (drag.active) {
      if (drag.pointerId === e.pointerId) this._updateDrag(e.clientX, e.clientY);
      return;
    }

    if (!this._press || this._press.pointerId !== e.pointerId) return;

    const moved = Math.hypot(e.clientX - this._press.startX, e.clientY - this._press.startY);
    if (moved < POINTER_MOVE_TOLERANCE) return;

    const press = this._press;
    this._clearPress();

    if (press.pointerType !== 'mouse' || this._pendingCredit.accountId) return;

    e.preventDefault();
    this._startDrag(press.cardEl, press.accountId, e.clientX, e.clientY, e.pointerId);
  },

  _handlePointerUp(e) {
    if (this._swipe && this._swipe.pointerId === e.pointerId) this._clearSwipe();

    if (drag.active && drag.pointerId === e.pointerId) {
      this._finishDrag(e.clientX, e.clientY);
      return;
    }

    if (this._press && this._press.pointerId === e.pointerId) this._clearPress();
  },

  _handleCardClick(e) {
    if (Date.now() < this._swipeIgnoreUntil) return;

    const card = e.target.closest('.card');
    if (!card || this._isCardActionTarget(e.target)) return;

    const accountId = parseInt(card.dataset.accountId, 10);
    if (Number.isNaN(accountId)) return;

    if (this._shouldSuppressClick(accountId)) return;
    if (!this._pendingCredit.accountId) return;

    const creditId = this._pendingCredit.accountId;
    this._clearPendingCredit();

    if (creditId === accountId) return;
    Forms.newTransaction(creditId, accountId);
  },

  async render() {
    const main = document.getElementById('main');

    this._clearPress();
    this._clearPendingCredit();
    this._resetDragState();

    const typeTotals = {};
    State.accounts.forEach(a => { typeTotals[a.type_id] = (typeTotals[a.type_id] || 0) + a.balance; });

    const shell = document.createElement('div');
    shell.className = 'flex flex-col h-full min-h-0';

    const shortcutsPanel = await CommonTx.renderPanel();
    shell.appendChild(shortcutsPanel);

    const pendingHint = document.createElement('div');
    pendingHint.id = 'board-pending-credit-hint';
    pendingHint.className = 'hidden px-2 pb-2 sm:px-3 lg:px-8 xl:px-64';
    shell.appendChild(pendingHint);

    const boardHost = document.createElement('div');
    boardHost.className = 'flex-1 min-h-0 px-2 sm:px-3 lg:px-8 xl:px-64 pb-2';

    const board = document.createElement('div');
    board.className = 'board';

    COLUMNS.forEach((col_cfg, colIdx) => {
      const accs = col_cfg.types.flatMap(tid => State.sortedAccounts(tid));
      const colTotal = col_cfg.types.reduce((sum, tid) => sum + (typeTotals[tid] || 0), 0);

      const col = document.createElement('div');
      col.className = 'column';
      col.dataset.colIdx = colIdx;
      if (colIdx === _activeTab) col.classList.add('mobile-active');

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
    this._refreshPendingCreditHint();
  },

  buildCard(acc, cfg) {
    const card = document.createElement('div');
    card.className = 'card bg-dark-800 border border-dark-600 rounded-xl p-3.5';
    card.dataset.accountId = acc.id;
    card.style.setProperty('--card-accent', cfg.accent);

    const balClass = acc.balance < 0
      ? 'text-pasivo'
      : 'text-[var(--card-accent)]';

    const bars = this._buildBars(acc.monthly_history, cfg.accent);
    const movs = acc.last_movements.length
      ? acc.last_movements.map(m => {
          const isPos = (acc.type_id === 1 || acc.type_id === 4)
            ? m.role === 'debit'
            : m.role === 'credit';
          const amtCls = isPos ? 'text-ingreso' : 'text-pasivo';
          const sign = isPos ? '+' : '−';
          const desc = m.description || m.counterpart || '—';
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
    const max = Math.max(...vals, 1);
    const bars = history.map((h, i) => {
      const pct = Math.max(vals[i] / max, 0.05);
      const isLast = i === history.length - 1;
      return `<div class="hbar flex-1 rounded-sm"
               style="height:${Math.round(pct * 100)}%;background:${accent};${isLast ? 'opacity:.75' : 'opacity:.22'}"
               title="${h.month}: ${fmtSigned(h.net)}"></div>`;
    }).join('');
    return `<div class="history-bars">${bars}</div>`;
  },

  ctxMenu(e, accId) {
    e.stopPropagation();
    document.querySelectorAll('.card-ctx-menu').forEach(menu => menu.remove());
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

  showLedger(accId) {
    State._ledgerAccount = accId;
    View.show('ledger');
  },

  selectRelativeTab(offset) {
    const total = COLUMNS.length;
    this.selectTab((_activeTab + offset + total) % total);
  },

  selectTab(colIdx) {
    _activeTab = colIdx;
    const cfg = COLUMNS[colIdx];
    document.querySelectorAll('.mttab').forEach(tab => {
      const active = parseInt(tab.dataset.col, 10) === colIdx;
      tab.classList.toggle('active', active);
      tab.style.setProperty('--tab-accent', active ? cfg.accent : '');
    });
    document.querySelectorAll('.column').forEach(col => {
      col.classList.toggle('mobile-active', parseInt(col.dataset.colIdx, 10) === colIdx);
    });
  },

  initDrag() {
    if (this._eventsBound) return;

    const main = document.getElementById('main');
    if (!main) return;

    this._eventsBound = true;

    main.addEventListener('pointerdown', e => this._handlePointerDown(e));
    main.addEventListener('click', e => this._handleCardClick(e));

    document.addEventListener('pointermove', e => this._handlePointerMove(e));
    document.addEventListener('pointerup', e => this._handlePointerUp(e));
    document.addEventListener('pointercancel', () => {
      this._clearSwipe();
      this._clearPress();
      this._resetDragState();
    });
  },
};