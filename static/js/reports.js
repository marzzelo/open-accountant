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
      <div class="max-w-6xl mx-auto px-5 sm:px-10 py-6">
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

  row: (cells, cls = '') => `<tr class="border-b border-dark-600/50 hover:bg-dark-700/40 ${cls}">
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

  _isZeroBalance(value) {
    return Math.abs(Number(value) || 0) < 0.005;
  },

  _filterBalanceGroups(groups) {
    if (State.showZeroBalanceItems) return groups;

    return groups
      .map(group => {
        const subgroups = group.subgroups
          .filter(subgroup => !this._isZeroBalance(subgroup.subtotal))
          .map(subgroup => ({
            ...subgroup,
            items: subgroup.items.filter(item => !this._isZeroBalance(item.balance)),
          }));

        return {
          ...group,
          subgroups,
        };
      })
      .filter(group => group.subgroups.length > 0 || !this._isZeroBalance(group.total));
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

  /* ── Balance General ──────────────────────────────────────────── */
  async balance() {
    const bs = await API.get('/reports/balance' + State.apiDateParams);
    const main = document.getElementById('main');
    const visibleGroups = this._filterBalanceGroups(bs.groups);

    const groupHtml = g => {
      const color = TYPE_COLORS[g.type_id] || '#fff';
      const rows = g.subgroups.flatMap(sg => [
        ...sg.items.map(i => R.row([
          { v: `<span class="pl-6 text-dark-400">${i.account_name}</span>` },
          { v: R.amt(i.balance), cls: 'text-right font-mono' },
        ])),
        R.row([
          { v: `<span class="pl-4 font-semibold text-blue-300">${sg.subtype_name}</span>` },
          { v: R.amt(sg.subtotal), cls: 'text-right font-mono font-semibold text-blue-300' },
        ], 'bg-dark-700/60'),
      ]).join('');

      return `
        <div class="bg-dark-800 border border-dark-600 rounded-xl overflow-hidden mb-4">
          <div class="px-4 py-2.5 text-xs font-bold uppercase tracking-wide border-b-2"
               style="color:${color};border-color:${color}33">
            ${_typeLabel(g.type_id, g.type_name).toUpperCase()}
          </div>
          ${R.table(
            [{label:t('report.col.account')}, {label:t('report.col.balance'), right:true}],
            rows + R.row([
              { v: `<span class="font-bold text-dark-100">TOTAL ${_typeLabel(g.type_id, g.type_name).toUpperCase()}</span>` },
              { v: R.amt(g.total), cls: 'text-right font-bold text-dark-100' },
            ], '!border-t-2 !border-dark-600 !bg-blue-600/5').replace('overflow-x-auto rounded-xl border border-dark-600','')
          )}
        </div>`;
    };

      const left  = visibleGroups.filter(g => [1, 4].includes(g.type_id));
      const right = visibleGroups.filter(g => [2, 3, 5].includes(g.type_id));

    const eqOk     = Math.abs(bs.equation_check) < 0.01;
    const resColor  = bs.resultado >= 0 ? 'text-ingreso' : 'text-pasivo';
    const eqColor   = eqOk ? 'text-ingreso' : 'text-pasivo';
    const expFrom   = State.filterFrom || `${new Date().getFullYear()}-01-01`;
    const expTo     = State.filterTo   || `${new Date().getFullYear()}-12-31`;

    const kpi = (label, val, cls) => `
      <div class="text-center min-w-[100px]">
        <div class="text-[10px] text-dark-400 uppercase tracking-wide mb-1">${label}</div>
        <div class="text-base font-bold ${cls}">${fmt(val)}</div>
      </div>`;

    main.innerHTML = R.view(`⚖️ ${t('report.balance')}`,
      t('report.period_range', { from: bs.period_from, to: bs.period_to }), `
      <label class="inline-flex items-center gap-2 mb-4 text-xs text-dark-300 select-none cursor-pointer">
        <input type="checkbox"
               class="h-3.5 w-3.5 rounded border-dark-500 bg-dark-700 text-blue-500 focus:ring-blue-500/40"
               ${State.showZeroBalanceItems ? 'checked' : ''}
           data-report-change="toggle-zero-balance">
        <span>${t('report.show_zero_balance_items')}</span>
      </label>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">
        <div>${left.map(groupHtml).join('')}</div>
        <div>${right.map(groupHtml).join('')}</div>
      </div>

      <div class="bg-dark-800 border border-dark-600 rounded-xl p-4 mb-5
                  flex gap-5 flex-wrap">
        ${kpi(t('report.total_assets'), bs.total_activo, 'text-activo')}
        ${kpi(t('report.total_liab'), bs.total_pasivo, 'text-pasivo')}
        ${kpi(t('report.total_equity'), bs.total_patrimonio, 'text-patrimonio')}
        ${kpi(t('report.result'), bs.resultado, resColor)}
        <div class="text-center min-w-[100px]">
          <div class="text-[10px] text-dark-400 uppercase tracking-wide mb-1">${t('report.equation')}</div>
          <div class="text-base font-bold ${eqColor}">${bs.equation_check.toFixed(2)}</div>
        </div>
      </div>

      <div class="flex gap-2 flex-wrap">
        ${R.btn('⬇ CSV', this._downloadUrl(`/reports/export/csv?report=balance&from=${expFrom}&to=${expTo}`), true)}
        ${R.btn('⬇ PDF', this._downloadUrl(`/reports/export/pdf?report=balance&from=${expFrom}&to=${expTo}`), true)}
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

  /* ── Libro Diario ─────────────────────────────────────────────── */
  async journal() {
    const data = await API.get('/reports/journal' + State.apiDateParams);
    const main = document.getElementById('main');
    const expFrom = State.filterFrom || `${new Date().getFullYear()}-01-01`;
    const expTo   = State.filterTo   || `${new Date().getFullYear()}-12-31`;
    const sorted = this._sortByDate(data, 'journal');

    const rows = sorted.map(r => R.row([
      { v: `<span class="font-mono text-xs">${r.date.slice(0,16)}</span>` },
      { v: escapeHtml(r.debit_name) },
      { v: `<span class="text-dark-400">${escapeHtml(r.credit_name)}</span>` },
      { v: R.amt(r.amount), cls: 'text-right' },
      { v: `<span class="text-dark-400">${escapeHtml(r.description || '')}</span>` },
      { v: R.actionBtn('🗑', 'text-xs px-2 py-1 border border-pasivo/30 rounded text-pasivo/60 hover:text-pasivo bg-transparent cursor-pointer font-sans', {
        'data-report-action': 'delete-tx',
        'data-tx-id': r.id,
      }) },
    ])).join('');

    main.innerHTML = R.view(`📒 ${t('report.journal')}`,
      t('report.journal_summary', { count: sorted.length, from: expFrom, to: expTo }),
      `<div class="flex gap-2 flex-wrap mb-4">
         ${this._sortToggleButton('journal')}
         ${R.btn('⬇ CSV', this._downloadUrl(`/reports/export/csv?report=journal&from=${expFrom}&to=${expTo}`), true)}
         ${R.btn('⬇ PDF', this._downloadUrl(`/reports/export/pdf?report=journal&from=${expFrom}&to=${expTo}`), true)}
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
    const data    = await API.get(`/reports/ledger/${accId}` + State.apiDateParams);
    const expFrom = State.filterFrom || `${new Date().getFullYear()}-01-01`;
    const expTo   = State.filterTo   || `${new Date().getFullYear()}-12-31`;
    const entries = this._sortByDate(data.entries, 'ledger');

    const rows = entries.map(e => R.row([
      { v: `<span class="font-mono text-xs">${e.date.slice(0,16)}</span>` },
      { v: escapeHtml(e.description || '') },
      { v: `<span class="text-dark-400">${escapeHtml(e.counterpart || '')}</span>` },
      { v: e.debit  ? R.amt(e.debit)  : '', cls: 'text-right' },
      { v: e.credit ? R.amt(e.credit) : '', cls: 'text-right' },
      { v: `<span class="font-semibold">${R.amt(e.balance)}</span>`, cls: 'text-right' },
    ])).join('');

    main.innerHTML = R.view(`📖 ${t('report.ledger')}`, t('report.ledger_summary', { count: entries.length }), `
      <div class="flex flex-wrap items-center gap-3 mb-4">
        <select ${htmlAttrs({
          'data-report-change': 'ledger-account',
          class: 'bg-dark-700 border border-dark-600 rounded-lg text-dark-300 text-sm px-3 py-2 font-sans outline-none focus:border-blue-500 cursor-pointer',
        })}>
          ${opts}
        </select>
        ${this._sortToggleButton('ledger')}
        <span class="text-sm text-dark-400">${t('report.opening')}: <strong class="text-dark-300">${fmt(data.opening_balance)}</strong></span>
        <span class="text-sm text-dark-400">${t('report.closing')}: <strong class="text-dark-300">${fmt(data.closing_balance)}</strong></span>
        ${R.btn('⬇ CSV', this._downloadUrl(`/reports/export/csv?report=ledger&account_id=${accId}&from=${expFrom}&to=${expTo}`), true)}
        ${R.btn('⬇ PDF', this._downloadUrl(`/reports/export/pdf?report=ledger&account_id=${accId}&from=${expFrom}&to=${expTo}`), true)}
      </div>` +
      R.table(
        [{label:t('report.col.date')},{label:t('report.col.description')},{label:t('report.col.account')},
         {label:t('report.col.debit'),right:true},{label:t('report.col.credit'),right:true},{label:t('report.col.balance'),right:true}],
        rows || `<tr><td colspan='6' class='text-center py-8 text-dark-500 text-xs'>${t('report.no_data')}</td></tr>`
      )
    );
  },

  /* ── Lista de transacciones ───────────────────────────────────── */
  async txlist() {
    const sep  = State.apiDateParams ? '&' : '?';
    const data = await API.get('/transactions' + State.apiDateParams + sep + 'limit=300');
    const main = document.getElementById('main');
    const sorted = this._sortByDate(data, 'txlist');

    const rows = sorted.map(tx => R.row([
      { v: `<span class="font-mono text-xs">${tx.date.slice(0,16)}</span>` },
      { v: escapeHtml(tx.debit_name) },
      { v: `<span class="text-dark-400">${escapeHtml(tx.credit_name)}</span>` },
      { v: R.amt(tx.amount), cls: 'text-right' },
      { v: `<span class="text-dark-400 text-xs">${escapeHtml(tx.description || '')}</span>` },
      { v: `
        ${R.actionBtn('✏️', 'text-xs px-2 py-1 border border-dark-600 rounded text-dark-400 hover:text-dark-300 bg-transparent cursor-pointer font-sans mr-1', {
          'data-report-action': 'edit-tx',
          'data-tx-id': tx.id,
        })}
        ${R.actionBtn('🗑', 'text-xs px-2 py-1 border border-pasivo/30 rounded text-pasivo/60 hover:text-pasivo bg-transparent cursor-pointer font-sans', {
          'data-report-action': 'delete-tx',
          'data-tx-id': tx.id,
        })}` }
    ])).join('');

    main.innerHTML = R.view(`🔁 ${t('nav.transactions')}`, t('report.txlist_summary', { count: sorted.length }),
      `<div class="flex gap-2 flex-wrap mb-4">${this._sortToggleButton('txlist')}</div>` +
      R.table(
        [{label:t('report.col.date')},{label:t('report.col.debited')},{label:t('report.col.credited')},
         {label:t('report.col.amount'),right:true},{label:t('report.col.description')},{label:''}],
        rows || `<tr><td colspan="6" class="text-center py-8 text-dark-500 text-xs">${t('report.no_transactions')}</td></tr>`
      )
    );
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
    case 'edit-tx':
      Reports._editTx(Number(action.dataset.txId));
      break;
    default:
      break;
  }
});

document.addEventListener('change', event => {
  const target = event.target.closest('[data-report-change]');
  if (!target) return;

  const main = document.getElementById('main');
  if (main && !main.contains(target)) return;

  switch (target.dataset.reportChange) {
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
