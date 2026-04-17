/* ── reports.js — Reports & tables ── */
const TYPE_I18N = {
  1: 'account.type.asset',
  2: 'account.type.liability',
  3: 'account.type.income',
  4: 'account.type.expense',
  5: 'account.type.equity',
};
function _typeLabel(typeId, typeName) {
  return typeId && TYPE_I18N[typeId] ? t(TYPE_I18N[typeId]) : typeName;
}
/* ── reports.js — Balance, Diario, Mayor, TxList, Subtypes ── */
'use strict';

/* ── Shared HTML helpers ── */
const R = {
  view: (title, sub, body) => `
    <div class="flex-1 overflow-y-auto">
      <div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-5 xl:px-4 py-6">
        <h1 class="text-xl font-bold text-dark-100 mb-1">${title}</h1>
        <p class="text-xs text-dark-400 mb-5">${sub}</p>
        ${body}
      </div>
    </div>`,

  table: (head, rows) => `
    <div class="overflow-x-auto rounded-xl border border-dark-600">
      <table class="w-full text-sm border-collapse min-w-[480px]">
        <thead class="bg-dark-700">
          <tr>${head.map(h => `<th class="px-3 py-2.5 text-left text-xs text-blue-400
                                          font-semibold uppercase tracking-wide
                                          ${h.right ? 'text-right' : ''}">${h.label}</th>`).join('')}</tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`,

  row: (cells, cls = '', attrs = {}) => `<tr ${htmlAttrs({
    class: `border-b border-dark-600/50 hover:bg-dark-700/40 ${cls}`.trim(),
    ...attrs,
  })}>
    ${cells.map(c => `<td class="px-3 py-2.5 ${c.cls || ''}">${c.v}</td>`).join('')}
  </tr>`,

  btn: (label, href, download = false) => `
    <a href="${href}" ${download ? 'download' : ''}
       class="inline-flex items-center gap-1.5 px-4 py-2 border border-dark-600 rounded-lg
              text-dark-400 hover:text-dark-300 hover:bg-dark-700 text-xs font-sans
              no-underline transition-all cursor-pointer">
      ${label}
    </a>`,

  actionBtn: (label, cls, attrs = {}) => `<button ${htmlAttrs({
    type: 'button',
    class: cls,
    ...attrs,
  })}>${label}</button>`,

  amt: v => `<span class="font-mono">${fmt(v)}</span>`,
  tags: tags => (tags || []).map(tag => renderTagBadge(tag)).join(''),
};

const TYPE_COLORS = {
  1: '#4fc3f7', 2: '#ef5350', 3: '#66bb6a', 4: '#ffd54f', 5: '#ce93d8'
};

const Reports = {
  dateSort: {
    journal: 'desc',
    ledger: 'desc',
    txlist: 'desc',
  },
  _downloadUrl(path) {
    return buildApiUrl(path);
  },

  _reportQuery(extra = {}) {
    return State.buildReportQuery(extra);
  },

  _balanceQueryParams(fromDate = null, toDate = null) {
    const params = new URLSearchParams();
    if (fromDate) params.set('from', fromDate);
    if (toDate) params.set('to', toDate);
    if (State.hasTagFilter) params.set('tag_ids', State.tagFilterIds.join(','));
    params.set('hide_accounts', String(State.hideBalanceAccounts));
    params.set('show_zero_balance', String(State.showZeroBalanceItems));
    params.set('type_ids', this._selectedBalanceTypeIds().join(','));
    return params.toString();
  },

  _balanceApiPath() {
    const query = this._balanceQueryParams(State.filterFrom, State.filterTo);
    return `/reports/balance${query ? `?${query}` : ''}`;
  },

  _balanceExportQuery(fromDate, toDate) {
    const params = new URLSearchParams(this._balanceQueryParams(fromDate, toDate));
    params.set('report', 'balance');
    return params.toString();
  },

  _allBalanceTypeIds() {
    return [1, 2, 3, 4, 5];
  },

  _selectedBalanceTypeIds() {
    const selected = Array.isArray(State.balanceTypeFilter) ? State.balanceTypeFilter : [];
    return this._allBalanceTypeIds().filter(typeId => selected.includes(typeId));
  },

  _balanceTypeFilterButtons() {
    return this._allBalanceTypeIds().map(typeId => {
      const active = this._selectedBalanceTypeIds().includes(typeId);
      const accent = TYPE_COLORS[typeId] || '#c9d1d9';
      return `<button ${htmlAttrs({
        type: 'button',
        'data-report-action': 'toggle-balance-type',
        'data-type-id': typeId,
        'aria-pressed': String(active),
        class: `px-3 py-2 rounded-lg border text-xs font-semibold transition-colors ${active
          ? 'text-dark-950 shadow-sm'
          : 'text-dark-400 hover:text-dark-200 bg-transparent border-dark-600 hover:bg-dark-700'}`,
        style: active ? `background:${accent};border-color:${accent};` : null,
      })}>${escapeHtml(_typeLabel(typeId, ''))}</button>`;
    }).join('');
  },

  async toggleBalanceType(typeId) {
    const nextSelected = new Set(this._selectedBalanceTypeIds());
    if (nextSelected.has(typeId)) {
      nextSelected.delete(typeId);
    } else {
      nextSelected.add(typeId);
    }
    State.balanceTypeFilter = this._allBalanceTypeIds().filter(id => nextSelected.has(id));
    await this.balance();
  },

  _fxSourceLabel(source) {
    const labels = {
      USD_CARD: t('report.fx.source.usd_card'),
      USD_BUY: t('report.fx.source.usd_buy'),
      USD_SELL: t('report.fx.source.usd_sell'),
      BLUE_BUY: t('report.fx.source.blue_buy'),
      BLUE_SELL: t('report.fx.source.blue_sell'),
    };
    if (!source) return t('report.fx.source.direct');
    return labels[source] || source;
  },

  _fmtPlainAmount(value) {
    return Number(value || 0).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  },

  _fxCell(tx) {
    const originalCurrency = tx.original_currency || 'ARS';
    const originalAmount = tx.original_amount ?? tx.amount;
    const fxRate = tx.fx_rate ?? 1;

    return `
      <div class="leading-4 min-w-[132px]">
        <div class="font-mono text-xs text-dark-200">${escapeHtml(originalCurrency)} ${this._fmtPlainAmount(originalAmount)}</div>
        <div class="text-[11px] text-dark-400">${escapeHtml(this._fxSourceLabel(tx.fx_source))} · ${t('report.fx.rate_short')}: ${fmt(fxRate)}</div>
      </div>`;
  },

  _isForeignCurrencyTx(tx) {
    return (tx.original_currency || 'ARS') !== 'ARS';
  },

  _txDetailBody(tx) {
    return `
      <div class="p-5 space-y-5">
        <p data-modal-description class="text-sm text-dark-400">${t('report.tx_detail.subtitle')}</p>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div class="rounded-xl border border-dark-600 bg-dark-700/50 p-4">
            <div class="text-[11px] uppercase tracking-wide text-dark-500 mb-1">${t('report.col.debited')}</div>
            <div class="text-sm font-semibold text-dark-100">${escapeHtml(tx.debit_name)}</div>
          </div>
          <div class="rounded-xl border border-dark-600 bg-dark-700/50 p-4">
            <div class="text-[11px] uppercase tracking-wide text-dark-500 mb-1">${t('report.col.credited')}</div>
            <div class="text-sm font-semibold text-dark-100">${escapeHtml(tx.credit_name)}</div>
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div class="rounded-xl border border-dark-600 p-4">
            <div class="text-[11px] uppercase tracking-wide text-dark-500 mb-1">${t('report.tx_detail.booked_amount')}</div>
            <div class="font-mono text-lg font-semibold text-dark-100">${fmt(tx.amount)}</div>
          </div>
          <div class="rounded-xl border border-dark-600 p-4">
            <div class="text-[11px] uppercase tracking-wide text-dark-500 mb-1">${t('report.tx_detail.original_amount')}</div>
            <div class="font-mono text-lg font-semibold text-dark-100">${escapeHtml(tx.original_currency || 'ARS')} ${this._fmtPlainAmount(tx.original_amount ?? tx.amount)}</div>
          </div>
          <div class="rounded-xl border border-dark-600 p-4">
            <div class="text-[11px] uppercase tracking-wide text-dark-500 mb-1">${t('report.tx_detail.fx_rate')}</div>
            <div class="font-mono text-base font-semibold text-dark-100">${fmt(tx.fx_rate ?? 1)}</div>
          </div>
          <div class="rounded-xl border border-dark-600 p-4">
            <div class="text-[11px] uppercase tracking-wide text-dark-500 mb-1">${t('report.tx_detail.fx_source')}</div>
            <div class="text-sm font-semibold text-dark-100">${escapeHtml(this._fxSourceLabel(tx.fx_source))}</div>
          </div>
        </div>

        <div class="rounded-xl border border-dark-600 p-4 space-y-2">
          <div>
            <div class="text-[11px] uppercase tracking-wide text-dark-500 mb-1">${t('report.col.date')}</div>
            <div class="text-sm text-dark-100 font-mono">${escapeHtml((tx.date || '').slice(0, 16))}</div>
          </div>
          <div>
            <div class="text-[11px] uppercase tracking-wide text-dark-500 mb-1">${t('report.col.description')}</div>
            <div class="text-sm text-dark-300">${escapeHtml(tx.description || '—')}</div>
          </div>
          <div>
            <div class="text-[11px] uppercase tracking-wide text-dark-500 mb-1">${t('report.col.tags')}</div>
            <div class="flex flex-wrap gap-2">${tx.tags?.length ? R.tags(tx.tags) : '<span class="text-sm text-dark-500">—</span>'}</div>
          </div>
        </div>

        <div class="flex justify-end pt-1 border-t border-dark-600">
          <button type="button" data-modal-close class="tbtn px-4 py-2 text-sm">${t('btn.close')}</button>
        </div>
      </div>`;
  },

  async _viewTx(txId) {
    try {
      const tx = await API.get(`/transactions/${txId}`);
      Modal.open(this._txDetailBody(tx), {
        title: `${t('report.tx_detail.title')} #${tx.id}`,
      });
    } catch (e) {
      Toast.show(e.message, 'err');
    }
  },

  _balanceGroupRows(group) {
    return group.subgroups.flatMap(subgroup => {
      const subgroupRow = R.row([
        { v: `<span class="pl-4 font-bold text-blue-200 text-sm">${subgroup.subtype_name}</span>` },
        { v: R.amt(subgroup.subtotal), cls: 'text-right font-mono font-bold text-blue-200' },
      ], 'bg-dark-700/60');

      if (!subgroup.items.length) return [subgroupRow];

      return [
        ...subgroup.items.map(item => R.row([
          { v: `<span class="pl-6 text-dark-300">${item.account_name}</span>` },
          { v: R.amt(item.balance), cls: 'text-right font-mono' },
        ], 'cursor-pointer hover:!bg-blue-600/10', {
          'data-report-action': 'open-ledger',
          'data-account-id': item.account_id,
          tabindex: '0',
          role: 'button',
          title: t('report.open_ledger_account', { account: item.account_name }),
          'aria-label': t('report.open_ledger_account', { account: item.account_name }),
        })),
        subgroupRow,
      ];
    }).join('');
  },

  _sortToggleButton(view) {
    const dir = this.dateSort[view] || 'desc';
    const arrow = dir === 'asc' ? '↑' : '↓';
    return `<button ${htmlAttrs({
                    type: 'button',
                    'data-report-action': 'toggle-sort',
                    'data-view': view,
                    class: 'tbtn px-3 py-2 text-xs',
                    title: `${t('report.col.date')} ${arrow}`,
                    'aria-label': `${t('report.col.date')} ${arrow}`,
                  })}>
              ${t('report.col.date')} ${arrow}
            </button>`;
  },

  _sortByDate(items, view, dateField = 'date') {
    const dir = this.dateSort[view] || 'desc';
    return [...items].sort((left, right) => {
      const dateCmp = String(left[dateField] || '').localeCompare(String(right[dateField] || ''));
      if (dateCmp !== 0) return dir === 'asc' ? dateCmp : -dateCmp;

      const leftId = Number(left.id || left.tx_id || 0);
      const rightId = Number(right.id || right.tx_id || 0);
      return dir === 'asc' ? leftId - rightId : rightId - leftId;
    });
  },

  _selectedTagNames() {
    const selected = new Set((State.tagFilterIds || []).map(Number));
    return (State.tags || []).filter(tag => selected.has(Number(tag.id))).map(tag => tag.name);
  },

  _tagFilterBar() {
    if (!State.tags?.length) return '';

    const selectedNames = this._selectedTagNames();
    return `
      <div class="rounded-xl border border-dark-600 bg-dark-800/70 px-3 py-3 mb-4">
        <div class="flex items-center justify-between gap-2 mb-3 flex-wrap">
          <div>
            <div class="text-[11px] font-semibold uppercase tracking-wide text-dark-400">${escapeHtml(t('report.filter_tags'))}</div>
            <div class="text-[11px] text-dark-500 mt-1">${escapeHtml(selectedNames.length ? t('report.filter_tags_active', { count: selectedNames.length, tags: selectedNames.join(', ') }) : t('report.filter_tags_none'))}</div>
          </div>
          ${State.hasTagFilter ? `<button ${htmlAttrs({ type: 'button', 'data-report-action': 'clear-tag-filters', class: 'text-xs px-3 py-1.5 rounded-lg border border-dark-600 text-dark-300 hover:bg-dark-700 cursor-pointer' })}>${t('filter.clear')}</button>` : ''}
        </div>
        <div class="flex flex-wrap gap-2">
          ${(State.tags || []).map(tag => {
            const active = (State.tagFilterIds || []).includes(Number(tag.id));
            const color = normalizeTagColor(tag.color);
            return `<button ${htmlAttrs({
              type: 'button',
              'data-report-action': 'toggle-tag-filter',
              'data-tag-id': tag.id,
              'aria-pressed': String(active),
              class: `inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${active ? 'text-dark-950 shadow-sm' : 'text-dark-300 hover:bg-dark-700'}`,
              style: active ? `background:${color};border-color:${color};` : `border-color:${color}55;color:${color};background:${color}12;`,
            })}><span class="h-2 w-2 rounded-full" style="background:${color}"></span>${escapeHtml(tag.name)}</button>`;
          }).join('')}
        </div>
      </div>`;
  },

  async toggleTagFilter(tagId) {
    const next = new Set((State.tagFilterIds || []).map(Number));
    if (next.has(tagId)) next.delete(tagId);
    else next.add(tagId);
    State.tagFilterIds = [...next];

    if (View.current === 'stats' && typeof Charts !== 'undefined') {
      await Charts.stats();
      return;
    }

    if (typeof this[View.current] === 'function') {
      await this[View.current]();
    }
  },

  async clearTagFilters() {
    State.tagFilterIds = [];

    if (View.current === 'stats' && typeof Charts !== 'undefined') {
      await Charts.stats();
      return;
    }

    if (typeof this[View.current] === 'function') {
      await this[View.current]();
    }
  },

  async toggleDateSort(view) {
    const previous = this.dateSort[view] || 'desc';
    const next = previous === 'asc' ? 'desc' : 'asc';
    this.dateSort[view] = next;

    try {
      await Preferences.save({ report_sort_directions: { ...this.dateSort } });
      await this[view]();
    } catch (error) {
      this.dateSort[view] = previous;
      Toast.show(t('msg.error_generic', {msg: error.message}), 'error');
    }
  },

  openLedger(accountId) {
    if (!accountId) return;
    State._ledgerAccount = accountId;
    View.show('ledger');
  },

  /* ── Balance General ──────────────────────────────────────────── */
  async balance() {
    const bs = await API.get(this._balanceApiPath());
    const main = document.getElementById('main');
    const visibleGroups = bs.groups;

    const groupHtml = g => {
      const color = TYPE_COLORS[g.type_id] || '#fff';
      const rows = this._balanceGroupRows(g);

      return `
        <div class="bg-dark-800 border border-dark-600 rounded-xl overflow-hidden mb-4">
          <div class="px-4 py-3 text-sm sm:text-base font-bold uppercase tracking-[0.12em] border-b-2 text-center"
               style="color:${color};border-color:${color}33">
            ${_typeLabel(g.type_id, g.type_name).toUpperCase()}
          </div>
          ${R.table(
            [{label:t('report.col.category')}, {label:t('report.col.balance'), right:true}],
            rows + R.row([
              { v: `<span class="font-bold text-dark-100">TOTAL ${_typeLabel(g.type_id, g.type_name).toUpperCase()}</span>` },
              { v: R.amt(g.total), cls: 'text-right font-bold text-dark-100' },
            ], '!border-t-2 !border-dark-600 !bg-blue-600/5').replace('overflow-x-auto rounded-xl border border-dark-600','')
          )}
        </div>`;
    };

    const left  = visibleGroups.filter(g => [1, 4].includes(g.type_id));
    const right = visibleGroups.filter(g => [2, 3, 5].includes(g.type_id));

    const eqOk        = Math.abs(bs.equation_check) < 0.01;
    const resColor    = bs.resultado >= 0 ? 'text-ingreso' : 'text-pasivo';
    const eqColor     = eqOk ? 'text-ingreso' : 'text-pasivo';
    const expFrom     = State.filterFrom || `${new Date().getFullYear()}-01-01`;
    const expTo       = State.filterTo   || `${new Date().getFullYear()}-12-31`;
    const hasFilter   = !!(State.filterFrom || State.filterTo);

    const kpi = (label, val, cls, toneClass) => `
      <div class="rounded-xl border ${toneClass} bg-dark-800 p-4 sm:p-5 min-w-0">
        <div class="text-[10px] text-dark-400 uppercase tracking-[0.12em] mb-2">${label}</div>
        <div class="text-xl sm:text-2xl font-bold ${cls}">${fmt(val)}</div>
      </div>`;

    main.innerHTML = R.view(`⚖️ ${t('report.balance')}`,
      t('report.period_range', { from: bs.period_from, to: bs.period_to }), `
      ${this._tagFilterBar()}
      <div class="flex flex-col gap-4 mb-5">
        <div class="flex flex-wrap gap-2">
          ${this._balanceTypeFilterButtons()}
        </div>

        <div class="flex flex-wrap gap-4">
        <label class="inline-flex items-center gap-2 text-xs text-dark-300 select-none cursor-pointer">
          <input type="checkbox"
                 class="h-3.5 w-3.5 rounded border-dark-500 bg-dark-700 text-blue-500 focus:ring-blue-500/40"
                 ${State.hideBalanceAccounts ? 'checked' : ''}
                 data-report-change="toggle-hide-balance-accounts">
          <span>${t('report.hide_accounts')}</span>
        </label>

        <label class="inline-flex items-center gap-2 text-xs text-dark-300 select-none cursor-pointer">
          <input type="checkbox"
                 class="h-3.5 w-3.5 rounded border-dark-500 bg-dark-700 text-blue-500 focus:ring-blue-500/40"
                 ${State.showZeroBalanceItems ? 'checked' : ''}
                 data-report-change="toggle-zero-balance">
          <span>${t('report.show_zero_balance_items')}</span>
        </label>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-5">
        ${kpi(hasFilter ? t('report.incr_assets')  : t('report.total_assets'),  bs.total_activo,     'text-activo',     'border-activo/30')}
        ${kpi(hasFilter ? t('report.incr_liab')    : t('report.total_liab'),    bs.total_pasivo,     'text-pasivo',     'border-pasivo/30')}
        ${kpi(hasFilter ? t('report.incr_equity')  : t('report.total_equity'),  bs.total_patrimonio, 'text-patrimonio', 'border-patrimonio/30')}
        ${kpi(hasFilter ? t('report.period_result'): t('report.result'),        bs.resultado,        resColor,          bs.resultado >= 0 ? 'border-ingreso/30' : 'border-pasivo/30')}
      </div>

      ${visibleGroups.length ? `
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">
        <div>${left.map(groupHtml).join('')}</div>
        <div>${right.map(groupHtml).join('')}</div>
      </div>` : `
      <div class="bg-dark-800 border border-dark-600 rounded-xl px-4 py-10 text-center text-sm text-dark-400 mb-5">
        ${t('report.no_data')}
      </div>`}

      <div class="bg-dark-800 border border-dark-600 rounded-xl p-4 mb-5 flex justify-center">
        <div class="text-center min-w-[140px]">
          <div class="text-[10px] text-dark-400 uppercase tracking-wide mb-1">${t('report.equation')}</div>
          <div class="text-base font-bold ${eqColor}">${bs.equation_check.toFixed(2)}</div>
        </div>
      </div>

      <div class="flex gap-2 flex-wrap">
        ${R.btn('⬇ CSV', this._downloadUrl(`/reports/export/csv?${this._balanceExportQuery(expFrom, expTo)}`), true)}
        ${R.btn('⬇ PDF', this._downloadUrl(`/reports/export/pdf?${this._balanceExportQuery(expFrom, expTo)}`), true)}
      </div>`
    );
  },

  async toggleZeroBalanceItems(checked) {
    const previous = State.showZeroBalanceItems;
    State.showZeroBalanceItems = checked;

    try {
      await Preferences.save({ show_zero_balance_accounts: checked });
      await this.balance();
    } catch (error) {
      State.showZeroBalanceItems = previous;
      Toast.show(t('msg.error_generic', {msg: error.message}), 'error');
    }
  },

  async toggleHideBalanceAccounts(checked) {
    const previous = State.hideBalanceAccounts;
    State.hideBalanceAccounts = checked;

    try {
      await Preferences.save({ hide_balance_accounts: checked });
      await this.balance();
    } catch (error) {
      State.hideBalanceAccounts = previous;
      Toast.show(t('msg.error_generic', {msg: error.message}), 'error');
    }
  },

  /* ── Libro Diario ─────────────────────────────────────────────── */
  async journal() {
    const data = await API.get('/reports/journal' + this._reportQuery());
    const main = document.getElementById('main');
    const expFrom = State.filterFrom || `${new Date().getFullYear()}-01-01`;
    const expTo   = State.filterTo   || `${new Date().getFullYear()}-12-31`;
    const sorted = this._sortByDate(data, 'journal');

    const rows = sorted.map(r => R.row([
      { v: `<span class="font-mono text-xs">${r.date.slice(0,16)}</span>` },
      { v: escapeHtml(r.debit_name) },
      { v: `<span class="text-dark-400">${escapeHtml(r.credit_name)}</span>` },
      { v: R.amt(r.amount), cls: 'text-right' },
      { v: `<div class="flex flex-col gap-2"><span class="text-dark-400">${escapeHtml(r.description || '')}</span>${r.tags?.length ? `<div class="flex flex-wrap gap-1.5">${R.tags(r.tags)}</div>` : ''}</div>` },
      { v: `<div class="flex items-center justify-end gap-1.5 whitespace-nowrap">
        ${this._isForeignCurrencyTx(r) ? `<span class="inline-flex items-center justify-center text-sm text-gasto" title="${escapeHtml(t('report.tx_foreign_currency'))}" aria-label="${escapeHtml(t('report.tx_foreign_currency'))}">💱</span>` : ''}
        ${R.actionBtn('👁', 'text-xs px-2 py-1 border border-dark-600 rounded text-dark-300 hover:text-dark-100 bg-transparent cursor-pointer font-sans', {
          'data-report-action': 'view-tx',
          'data-tx-id': r.id,
          title: t('btn.view'),
          'aria-label': t('btn.view'),
        })}
        ${R.actionBtn('✏️', 'text-xs px-2 py-1 border border-dark-600 rounded text-dark-400 hover:text-dark-300 bg-transparent cursor-pointer font-sans', {
          'data-report-action': 'edit-tx',
          'data-tx-id': r.id,
          title: t('btn.edit'),
          'aria-label': t('btn.edit'),
        })}
        ${R.actionBtn('🗑️', 'text-xs px-2 py-1 border border-pasivo/30 rounded text-pasivo/60 hover:text-pasivo bg-transparent cursor-pointer font-sans', {
          'data-report-action': 'delete-tx',
          'data-tx-id': r.id,
          title: t('btn.delete'),
          'aria-label': t('btn.delete'),
        })}</div>` },
    ])).join('');

    main.innerHTML = R.view(`📒 ${t('report.journal')}`,
      t('report.journal_summary', { count: sorted.length, from: expFrom, to: expTo }),
      `${this._tagFilterBar()}<div class="flex gap-2 flex-wrap mb-4">
         ${this._sortToggleButton('journal')}
         ${R.btn('⬇ CSV', this._downloadUrl(`/reports/export/csv${this._reportQuery({ report: 'journal' })}`), true)}
         ${R.btn('⬇ PDF', this._downloadUrl(`/reports/export/pdf${this._reportQuery({ report: 'journal' })}`), true)}
       </div>` +
      R.table(
        [{label:t('report.col.date')},{label:t('report.col.debit')},{label:t('report.col.credit')},
         {label:t('report.col.amount'),right:true},{label:t('report.col.description')},{label:''}],
        rows || `<tr><td colspan='6' class='text-center py-8 text-dark-500 text-xs'>${t('report.no_data')}</td></tr>`
      )
    );
  },

  /* ── Libro Mayor ──────────────────────────────────────────────── */
  async ledger() {
    const main  = document.getElementById('main');
    const accId = State._ledgerAccount || State.accounts[0]?.id;
    if (!accId) { main.innerHTML = `<div class="text-dark-500 text-center py-16">${t('report.no_accounts')}</div>`; return; }

    const opts    = State.accounts.map(a =>
      `<option value="${a.id}" ${a.id === accId ? 'selected' : ''}>${escapeHtml(a.name)} (${escapeHtml(a.type_name)})</option>`
    ).join('');
    const data    = await API.get(`/reports/ledger/${accId}` + this._reportQuery());
    const expFrom = State.filterFrom || `${new Date().getFullYear()}-01-01`;
    const expTo   = State.filterTo   || `${new Date().getFullYear()}-12-31`;
    const entries = this._sortByDate(data.entries, 'ledger');

    const counterpartCell = entry => {
      if (!entry.counterpart_id) {
        return `<span class="text-dark-400">${escapeHtml(entry.counterpart || '')}</span>`;
      }

      return `<button ${htmlAttrs({
        type: 'button',
        class: 'text-left text-blue-300 hover:text-blue-200 underline-offset-2 hover:underline cursor-pointer',
        'data-report-action': 'open-ledger',
        'data-account-id': entry.counterpart_id,
        title: t('report.open_ledger_account', { account: entry.counterpart || '' }),
        'aria-label': t('report.open_ledger_account', { account: entry.counterpart || '' }),
      })}>${escapeHtml(entry.counterpart || '')}</button>`;
    };

    const rows = entries.map(e => R.row([
      { v: `<span class="font-mono text-xs">${e.date.slice(0,16)}</span>` },
      { v: `<div class="flex flex-col gap-2"><span>${escapeHtml(e.description || '')}</span>${e.tags?.length ? `<div class="flex flex-wrap gap-1.5">${R.tags(e.tags)}</div>` : ''}</div>` },
      { v: counterpartCell(e) },
      { v: e.debit  ? R.amt(e.debit)  : '', cls: 'text-right' },
      { v: e.credit ? R.amt(e.credit) : '', cls: 'text-right' },
      { v: `<span class="font-semibold">${R.amt(e.balance)}</span>`, cls: 'text-right' },
      { v: `<div class="flex items-center justify-end gap-1.5 whitespace-nowrap">
        ${this._isForeignCurrencyTx(e) ? `<span class="inline-flex items-center justify-center text-sm text-gasto" title="${escapeHtml(t('report.tx_foreign_currency'))}" aria-label="${escapeHtml(t('report.tx_foreign_currency'))}">💱</span>` : ''}
        ${R.actionBtn('👁', 'text-xs px-2 py-1 border border-dark-600 rounded text-dark-300 hover:text-dark-100 bg-transparent cursor-pointer font-sans', {
          'data-report-action': 'view-tx',
          'data-tx-id': e.id,
          title: t('btn.view'),
          'aria-label': t('btn.view'),
        })}
        ${R.actionBtn('✏️', 'text-xs px-2 py-1 border border-dark-600 rounded text-dark-400 hover:text-dark-300 bg-transparent cursor-pointer font-sans', {
          'data-report-action': 'edit-tx',
          'data-tx-id': e.id,
          title: t('btn.edit'),
          'aria-label': t('btn.edit'),
        })}
        ${R.actionBtn('🗑️', 'text-xs px-2 py-1 border border-pasivo/30 rounded text-pasivo/60 hover:text-pasivo bg-transparent cursor-pointer font-sans', {
          'data-report-action': 'delete-tx',
          'data-tx-id': e.id,
          title: t('btn.delete'),
          'aria-label': t('btn.delete'),
        })}</div>` },
    ])).join('');

    main.innerHTML = R.view(
      `<span class="block w-full text-center text-3xl sm:text-5xl lg:text-4xl font-black tracking-tight leading-none">${escapeHtml(data.account_name)}</span>`,
      `<span class="block w-full text-center text-sm text-dark-400">📖 ${escapeHtml(t('report.ledger'))} · ${escapeHtml(t('report.ledger_summary', { count: entries.length }))}</span>`,
      `
      ${this._tagFilterBar()}
      <div class="flex flex-wrap items-center gap-3 mb-4">
        <select ${htmlAttrs({
          'data-report-change': 'ledger-account',
          class: 'bg-dark-700 border border-dark-600 rounded-lg text-dark-300 text-sm px-3 py-2 font-sans outline-none focus:border-blue-500 cursor-pointer',
        })}>
          ${opts}
        </select>
        ${this._sortToggleButton('ledger')}
        <span class="text-base font-bold text-activo">${t('report.closing')}: <strong class="text-lg">${fmt(data.closing_balance)}</strong></span>
        ${R.btn('⬇ CSV', this._downloadUrl(`/reports/export/csv${this._reportQuery({ report: 'ledger', account_id: accId })}`), true)}
        ${R.btn('⬇ PDF', this._downloadUrl(`/reports/export/pdf${this._reportQuery({ report: 'ledger', account_id: accId })}`), true)}
      </div>` +
      R.table(
        [{label:t('report.col.date')},{label:t('report.col.description')},{label:t('report.col.account')},
         {label:t('report.col.debit'),right:true},{label:t('report.col.credit'),right:true},{label:t('report.col.balance'),right:true},{label:''}],
        rows || `<tr><td colspan='7' class='text-center py-8 text-dark-500 text-xs'>${t('report.no_data')}</td></tr>`
      )
    );
  },

  /* ── Lista de transacciones ───────────────────────────────────── */
  async txlist() {
    return this.journal();
  },

  /* ── Subtipos (re-usa Forms) ──────────────────────────────────── */
  async subtypes() {
    await View.show('board');
    setTimeout(() => Forms.subtypeModal(), 30);
  },

  /* ── Privados ─────────────────────────────────────────────────── */
  async _deleteTx(txId) {
    const confirmed = await Dialog.confirm({
      title: t('btn.delete'),
      message: t('msg.confirm_delete', { name: `#${txId}` }),
      confirmLabel: t('btn.delete'),
      cancelLabel: t('btn.cancel'),
      submitTone: 'danger',
    });
    if (!confirmed) return;

    try {
      await API.del(`/transactions/${txId}`);
      Toast.show(t('msg.tx_deleted')); await View.refresh();
    } catch (e) { Toast.show(e.message, 'err'); }
  },

  async _editTx(txId) {
    const tx = await API.get(`/transactions/${txId}`);
    Forms.editTransaction(tx);
  },
};

document.addEventListener('click', event => {
  const action = event.target.closest('[data-report-action]');
  if (!action) return;

  const main = document.getElementById('main');
  if (main && !main.contains(action)) return;

  switch (action.dataset.reportAction) {
    case 'toggle-sort':
      Reports.toggleDateSort(action.dataset.view);
      break;
    case 'delete-tx':
      Reports._deleteTx(Number(action.dataset.txId));
      break;
    case 'view-tx':
      Reports._viewTx(Number(action.dataset.txId));
      break;
    case 'edit-tx':
      Reports._editTx(Number(action.dataset.txId));
      break;
    case 'toggle-balance-type':
      Reports.toggleBalanceType(Number(action.dataset.typeId));
      break;
    case 'toggle-tag-filter':
      Reports.toggleTagFilter(Number(action.dataset.tagId));
      break;
    case 'clear-tag-filters':
      Reports.clearTagFilters();
      break;
    case 'open-ledger':
      Reports.openLedger(Number(action.dataset.accountId));
      break;
    default:
      break;
  }
});

window.Reports = Reports;

document.addEventListener('keydown', event => {
  if (event.key !== 'Enter' && event.key !== ' ') return;

  const action = event.target.closest('[data-report-action="open-ledger"]');
  if (!action) return;

  const main = document.getElementById('main');
  if (main && !main.contains(action)) return;

  event.preventDefault();
  Reports.openLedger(Number(action.dataset.accountId));
});

document.addEventListener('change', event => {
  const target = event.target.closest('[data-report-change]');
  if (!target) return;

  const main = document.getElementById('main');
  if (main && !main.contains(target)) return;

  switch (target.dataset.reportChange) {
    case 'toggle-hide-balance-accounts':
      Reports.toggleHideBalanceAccounts(target.checked);
      break;
    case 'toggle-zero-balance':
      Reports.toggleZeroBalanceItems(target.checked);
      break;
    case 'ledger-account':
      State._ledgerAccount = parseInt(target.value, 10);
      Reports.ledger();
      break;
    default:
      break;
  }
});
