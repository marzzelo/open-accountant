/* ── forms.js — Modales con Tailwind ── */
'use strict';

/* ── Helpers de HTML reutilizables ── */
const T = {
  modalShell: (title, body, footer) => `
    <div class="flex items-center justify-between px-5 pt-5 pb-3 border-b border-dark-600">
      <span data-modal-title class="text-base font-bold text-dark-100">${title}</span>
      <button type="button" data-modal-close aria-label="${escapeHtml(t('dialog.close'))}" class="text-dark-400 hover:text-dark-300 text-xl cursor-pointer border-0 bg-transparent">✕</button>
    </div>
    <div class="p-5">${body}</div>
    <div class="flex gap-2 justify-end px-5 pb-5 pt-3 border-t border-dark-600 flex-wrap">
      ${footer}
    </div>`,

  input: (id, opts = {}) => `<input ${htmlAttrs({
    id,
    type: opts.type,
    step: opts.step,
    min: opts.min,
    placeholder: opts.ph,
    value: opts.val,
    autofocus: opts.auto || null,
    inputmode: opts.inputmode,
    class: `w-full bg-dark-700 border border-dark-600 rounded-lg text-dark-300 text-sm px-3 py-2.5 font-sans outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 ${opts.cls || ''}`.trim(),
  })}>`,

  select: (id, opts, attrs = {}) => `
    <select ${htmlAttrs({
      id,
      class: 'w-full bg-dark-700 border border-dark-600 rounded-lg text-dark-300 text-sm px-3 py-2.5 font-sans outline-none focus:border-blue-500 cursor-pointer',
      ...attrs,
    })}>
      ${opts}
    </select>`,

  label: txt => `<label class="block text-xs text-dark-400 mb-1.5">${escapeHtml(txt)}</label>`,
  group: (label, inner) => `<div class="mb-4">${T.label(label)}${inner}</div>`,
  row2:  (...cols) => `<div class="grid grid-cols-1 sm:grid-cols-${cols.length} gap-3 mb-4">
                         ${cols.map(c => `<div>${c}</div>`).join('')}
                       </div>`,

  btn: (label, cls, attrs = {}) =>
    `<button ${htmlAttrs({
      type: 'button',
      class: `px-5 py-2 rounded-lg text-sm font-medium font-sans cursor-pointer transition-all border ${cls}`,
      ...attrs,
    })}>${label}</button>`,
  btnGhost:   (label, attrs) => T.btn(label, 'border-dark-600 text-dark-400 hover:text-dark-300 hover:bg-dark-700 bg-transparent', attrs),
  btnPrimary: (label, attrs) => T.btn(label, 'bg-blue-600 hover:bg-blue-500 text-white border-blue-600', attrs),
  btnSuccess: (label, attrs) => T.btn(label, 'bg-emerald-700 hover:bg-emerald-600 text-white border-emerald-700', attrs),
  btnDanger:  (label, attrs) => T.btn(label, 'bg-red-900/30 hover:bg-red-900/50 text-pasivo border-pasivo/30', attrs),
};

const Forms = {
  _transactionCurrencies() {
    return [
      { code: 'ARS', label: 'AR$', rateKey: null, originalCurrency: 'ARS', fxSource: null },
      { code: 'USD_CARD', label: 'USD CARD', rateKey: 'usd_card_ars', originalCurrency: 'USD', fxSource: 'USD_CARD' },
      { code: 'USD_BUY', label: 'USD BUY', rateKey: 'usd_official_buy_ars', originalCurrency: 'USD', fxSource: 'USD_BUY' },
      { code: 'USD_SELL', label: 'USD SELL', rateKey: 'usd_official_sell_ars', originalCurrency: 'USD', fxSource: 'USD_SELL' },
      { code: 'BLUE_BUY', label: 'BLUE BUY', rateKey: 'usd_blue_buy_ars', originalCurrency: 'USD', fxSource: 'BLUE_BUY' },
      { code: 'BLUE_SELL', label: 'BLUE SELL', rateKey: 'usd_blue_sell_ars', originalCurrency: 'USD', fxSource: 'BLUE_SELL' },
    ];
  },

  _transactionCurrencyMeta(currency) {
    return this._transactionCurrencies().find(option => option.code === currency)
      || this._transactionCurrencies()[0];
  },

  _transactionCurrencyButtonId(currency) {
    return `f-currency-${currency.toLowerCase().replace(/_/g, '-')}`;
  },

  _transactionAmountField(opts = {}) {
    const selected = this._transactionCurrencyMeta(opts.currency || 'ARS').code;
    const buttons = this._transactionCurrencies().map(option => `
      <button ${htmlAttrs({
        type: 'button',
        id: this._transactionCurrencyButtonId(option.code),
        'data-form-action': 'set-amount-currency',
        'data-currency': option.code,
        'aria-pressed': option.code === selected,
        class: `flex-1 rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${option.code === selected
          ? 'bg-blue-600 text-white shadow-sm'
          : 'text-dark-400 hover:text-dark-200 hover:bg-dark-700/80'}`,
      })}>
        ${option.label}
      </button>`).join('');

    return `
      <div class="mb-2">
        <div class="w-full rounded-xl border border-dark-600 bg-dark-800/80 p-1">
          <div class="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-1">
            ${buttons}
          </div>
        </div>
        <input id="f-amount-currency" type="hidden" value="${selected}">
      </div>
      ${T.input('f-amount', {
        type: 'number', step: '0.01', min: '0.01', ph: t('form.placeholder.amount'), auto: opts.auto !== false,
        val: opts.value,
        inputmode: 'decimal',
        cls: '!text-[22px] !font-bold !text-center !text-ingreso !tracking-tight'
      })}
      <div id="f-amount-currency-note" class="mt-2 text-[11px] text-dark-500">
        ${escapeHtml(this._amountCurrencyHelp(selected, opts.rate))}
      </div>`;
  },

  _selectedAmountCurrency() {
    return document.getElementById('f-amount-currency')?.value || 'ARS';
  },

  _getCurrencyRate(currency) {
    const { rateKey } = this._transactionCurrencyMeta(currency);
    if (!rateKey) return null;
    const configRate = parseFloat(State.appConfig?.finance?.[rateKey]);
    if (Number.isFinite(configRate) && configRate > 0) return configRate;
    return null;
  },

  async _resolveCurrencyRate(currency) {
    const liveRate = this._getCurrencyRate(currency);
    if (liveRate) return liveRate;

    try {
      await API.reloadConfig();
      return this._getCurrencyRate(currency);
    } catch (_) {}

    return null;
  },

  _amountCurrencyHelp(currency, rate = this._getCurrencyRate(currency)) {
    const meta = this._transactionCurrencyMeta(currency);
    if (meta.code === 'ARS') return t('form.amount_currency_help_ars');
    if (rate) return t('form.amount_currency_help_rate', { label: meta.label, rate: fmt(rate) });
    return t('form.amount_currency_help_rate_missing', { label: meta.label });
  },

  _currencyButtonClass(currency, active) {
    const activeClass = currency === 'ARS'
      ? 'bg-blue-600 text-white shadow-sm'
      : 'bg-emerald-600 text-white shadow-sm';
    const inactiveClass = 'text-dark-400 hover:text-dark-200 hover:bg-dark-700/80';
    return `flex-1 rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${active ? activeClass : inactiveClass}`;
  },

  _currencyPlaceholder(currency) {
    const meta = this._transactionCurrencyMeta(currency);
    return meta.code === 'ARS' ? '0.00' : `0.00 ${meta.label}`;
  },

  _missingCurrencyRateMessage(currency) {
    const meta = this._transactionCurrencyMeta(currency);
    return t('msg.currency_rate_missing', { label: meta.label });
  },

  _setAmountCurrency(currency) {
    const nextCurrency = this._transactionCurrencyMeta(currency).code;
    const hiddenInput = document.getElementById('f-amount-currency');
    const note = document.getElementById('f-amount-currency-note');
    const amountInput = document.getElementById('f-amount');

    if (hiddenInput) hiddenInput.value = nextCurrency;

    this._transactionCurrencies().forEach(option => {
      const button = document.getElementById(this._transactionCurrencyButtonId(option.code));
      if (!button) return;
      const active = option.code === nextCurrency;
      button.className = this._currencyButtonClass(option.code, active);
      button.setAttribute('aria-pressed', String(active));
    });

    if (note) note.textContent = this._amountCurrencyHelp(nextCurrency);
    if (amountInput) amountInput.placeholder = this._currencyPlaceholder(nextCurrency);
  },

  async _primeAmountCurrencyHelp() {
    const currency = this._selectedAmountCurrency();
    const rate = await this._resolveCurrencyRate(currency);
    const note = document.getElementById('f-amount-currency-note');
    if (!note) return;
    note.textContent = this._amountCurrencyHelp(currency, rate);
  },

  async _normalizeTransactionAmount(rawAmount) {
    const currency = this._selectedAmountCurrency();
    if (currency === 'ARS') return rawAmount;

    const rate = await this._resolveCurrencyRate(currency);
    if (!rate) {
      Toast.show(this._missingCurrencyRateMessage(currency), 'err');
      return null;
    }

    return Math.round(rawAmount * rate * 100) / 100;
  },

  async _buildTransactionPayload(rawAmount) {
    const currency = this._selectedAmountCurrency();
    const meta = this._transactionCurrencyMeta(currency);

    if (meta.originalCurrency === 'ARS') {
      return {
        original_amount: rawAmount,
        original_currency: 'ARS',
        fx_source: null,
      };
    }

    const rate = await this._resolveCurrencyRate(currency);
    if (!rate) {
      Toast.show(this._missingCurrencyRateMessage(currency), 'err');
      return null;
    }

    return {
      original_amount: rawAmount,
      original_currency: meta.originalCurrency,
      fx_source: meta.fxSource,
    };
  },

  _transactionSelectionFromTx(tx) {
    return tx.fx_source || tx.original_currency || 'ARS';
  },

  _focusTransactionAmount() {
    const input = document.getElementById('f-amount');
    input?.focus();
    input?.select();
    this._setAmountCurrency(this._selectedAmountCurrency());
    this._primeAmountCurrencyHelp();
  },

  /* ── Nueva cuenta ─────────────────────────────────────────────── */
  newAccount() {
    const typeOpts = State.types.map(type =>
      `<option value="${type.id}">${escapeHtml(type.name)}</option>`).join('');
    Modal.open(T.modalShell(t('form.new_account'), `
      ${T.group(`${t('form.label.name')} *`, T.input('f-name', { ph: t('form.placeholder.name'), auto: true }))}
      ${T.row2(
        T.label(`${t('form.label.type')} *`) + T.select('f-type', `<option value="">${t('form.select_placeholder')}</option>` + typeOpts, { 'data-form-change': 'load-subtypes' }),
        T.label(t('form.label.subtype'))  + T.select('f-subtype', `<option value="">${t('form.select_type')}</option>`)
      )}
      ${T.group(t('form.label.initial_bal'), T.input('f-initial', { type: 'number', step: '0.01', val: '0' }))}
      ${T.group(t('form.label.description'), T.input('f-desc', { ph: t('form.placeholder.desc') }))}
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true })
      + T.btnSuccess(t('btn.create'), { 'data-form-action': 'save-account' })));
  },

  /* ── Editar cuenta ────────────────────────────────────────────── */
  async editAccount(accId) {
    const acc  = State.accounts.find(a => a.id === accId);
    if (!acc) return;
    const subs = State.subtypes.filter(s => s.type_id === acc.type_id);
    const subOpts = `<option value="">${t('form.no_subtype')}</option>` +
      subs.map(s => `<option value="${s.id}" ${s.id === acc.subtype_id ? 'selected' : ''}>${escapeHtml(s.name)}</option>`).join('');

    Modal.open(T.modalShell(`✏️ ${t('form.edit_account')} — ${escapeHtml(acc.name)}`, `
      ${T.group(t('form.label.name'), T.input('f-name', { val: acc.name }))}
      ${T.row2(
        T.label(t('form.label.type')) + `<input value="${escapeHtml(acc.type_name)}" disabled
                 class="w-full bg-dark-700/50 border border-dark-600 rounded-lg text-dark-500
                        text-sm px-3 py-2.5 cursor-not-allowed">`,
        T.label(t('form.label.subtype')) + T.select('f-subtype', subOpts)
      )}
      ${T.group(t('form.label.description'), T.input('f-desc', { val: acc.description || '' }))}
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true })
      + T.btnPrimary(t('btn.save'), { 'data-form-action': 'update-account', 'data-account-id': accId })));
  },

  /* ── Saldo inicial ────────────────────────────────────────────── */
  async initialBalance(accId) {
    const acc = State.accounts.find(a => a.id === accId);
    if (!acc) return;
    Modal.open(T.modalShell(`💰 ${t('form.initial_balance')} — ${escapeHtml(acc.name)}`, `
      <p data-modal-description class="text-dark-400 text-sm mb-4">
        ${t('form.initial_balance_help')}
      </p>
      ${T.group(t('form.label.initial_bal'), T.input('f-initial', {
        type: 'number', step: '0.01', val: acc.initial_balance,
        cls: '!text-2xl !font-bold !text-center !text-ingreso !tracking-tight'
      }))}
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true })
      + T.btnPrimary(t('btn.save'), { 'data-form-action': 'save-initial-balance', 'data-account-id': accId })));
  },

  /* ── Eliminar cuenta ──────────────────────────────────────────── */
  async deleteAccount(accId) {
    const acc = State.accounts.find(a => a.id === accId);
    if (!acc) return;
    const confirmed = await Dialog.confirm({
      title: t('form.delete_account'),
      message: t('form.delete_account_confirm', { name: acc.name }),
      confirmLabel: t('btn.delete'),
      cancelLabel: t('btn.cancel'),
      submitTone: 'danger',
    });
    if (!confirmed) return;
    await this._deleteAccount(accId);
  },

  /* ── Nueva transacción (drag & drop) ─────────────────────────── */
  newTransaction(creditId, debitId, preset = {}) {
    const credit = State.accounts.find(a => a.id === creditId);
    const debit  = State.accounts.find(a => a.id === debitId);
    if (!credit || !debit) return;
    const now = localNow();
    const description = preset.description || '';

    Modal.open(T.modalShell(`💸 ${t('form.new_transaction')}`, `
      <div class="flex items-center gap-3 bg-dark-700 rounded-xl p-3 mb-5">
        <div class="flex-1 text-center min-w-0">
          <div class="text-[10px] text-dark-400 uppercase tracking-wide mb-1">${t('form.transaction.source')}</div>
          <div class="text-sm font-semibold text-dark-100 truncate">${escapeHtml(credit.name)}</div>
          <div class="text-[11px] text-dark-400">${escapeHtml(credit.type_name)}</div>
        </div>
        <div class="text-2xl text-gasto shrink-0">→</div>
        <div class="flex-1 text-center min-w-0">
          <div class="text-[10px] text-dark-400 uppercase tracking-wide mb-1">${t('form.transaction.destination')}</div>
          <div class="text-sm font-semibold text-dark-100 truncate">${escapeHtml(debit.name)}</div>
          <div class="text-[11px] text-dark-400">${escapeHtml(debit.type_name)}</div>
        </div>
      </div>
      ${T.group(`${t('form.label.amount')} *`, this._transactionAmountField())}
      ${T.group(t('form.label.description'), T.input('f-desc', { ph: t('form.placeholder.desc_tx'), val: description }))}
      ${T.group(t('form.label.date'), T.input('f-date', { type: 'datetime-local', val: now }))}
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true }) +
       T.btnSuccess(t('btn.register'), { 'data-form-action': 'save-transaction', 'data-credit-id': creditId, 'data-debit-id': debitId })));

    setTimeout(() => this._focusTransactionAmount(), 80);
  },

  /* ── FAB: transacción manual (mobile) ────────────────────────── */
  newTransactionFAB() {
    const opts = State.accounts.map(a =>
      `<option value="${a.id}">${escapeHtml(a.name)} (${escapeHtml(a.type_name)})</option>`).join('');
    const now = localNow();

    Modal.open(T.modalShell(`💸 ${t('form.new_transaction')}`, `
      ${T.group(`${t('form.label.amount')} *`, this._transactionAmountField())}
      ${T.group(t('form.label.credit'), T.select('f-credit', opts))}
      ${T.group(t('form.label.debit'),  T.select('f-debit',  opts))}
      ${T.group(t('form.label.description'), T.input('f-desc', { ph: t('form.placeholder.desc_tx') }))}
      ${T.group(t('form.label.date'), T.input('f-date', { type: 'datetime-local', val: now }))}
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true }) +
       T.btnSuccess(t('btn.register'), { 'data-form-action': 'save-transaction-fab' })));

    setTimeout(() => this._focusTransactionAmount(), 80);
  },

  /* ── Gestión de subtipos ──────────────────────────────────────── */
  async subtypeModal() {
    const typeOpts = State.types.map(type => `<option value="${type.id}">${escapeHtml(type.name)}</option>`).join('');
    const rows = State.subtypes.map(s => `
      <tr class="border-b border-dark-600/60 hover:bg-dark-700/50">
        <td class="px-4 py-3 text-sm text-dark-400 w-[28%]">${escapeHtml(s.type_name)}</td>
        <td class="px-4 py-3 text-sm text-dark-100">${escapeHtml(s.name)}</td>
        <td class="px-4 py-3 text-right whitespace-nowrap w-[120px]">
          <button ${htmlAttrs({
            type: 'button',
            'data-form-action': 'edit-subtype',
            'data-subtype-id': s.id,
            class: 'inline-flex items-center gap-1 text-xs px-3 py-1.5 border border-dark-600 rounded-md text-dark-400 hover:text-dark-100 hover:bg-dark-600 bg-transparent cursor-pointer font-sans mr-2',
          })}
            ${t('btn.edit')}
          </button>
          <button ${htmlAttrs({
            type: 'button',
            'data-form-action': 'delete-subtype',
            'data-subtype-id': s.id,
            class: 'inline-flex items-center gap-1 text-xs px-3 py-1.5 border border-red-900/40 rounded-md text-red-400/70 hover:text-red-400 hover:bg-red-900/20 bg-transparent cursor-pointer font-sans',
          })}>
            ${t('btn.delete')}
          </button>
        </td>
      </tr>`).join('');

    Modal.open(T.modalShell(`🏷 ${t('nav.subtypes')}`, `
      <div class="overflow-x-auto rounded-xl border border-dark-600 mb-6">
        <table class="w-full text-sm" style="min-width:560px">
          <thead class="bg-dark-700">
            <tr>
              <th class="px-4 py-3 text-left text-xs text-blue-400 font-semibold uppercase tracking-wide w-[28%]">${t('form.label.type')}</th>
              <th class="px-4 py-3 text-left text-xs text-blue-400 font-semibold uppercase tracking-wide">${t('form.label.name')}</th>
              <th class="px-4 py-3 w-[120px]"></th>
            </tr>
          </thead>
          <tbody>
            ${rows || `<tr><td colspan='3' class='text-center py-8 text-dark-500 text-xs'>${t('form.no_subtype_registered')}</td></tr>`}
          </tbody>
        </table>
      </div>

      <div class="bg-dark-700/50 rounded-xl p-4 border border-dark-600/60">
        <p class="text-xs text-dark-400 mb-3 font-semibold uppercase tracking-wide">${t('form.subtype.add_title')}</p>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          ${T.select('new-st-type', typeOpts)}
          ${T.input('new-st-name', { ph: t('form.placeholder.name'), auto: true })}
        </div>
      </div>
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true })
      + T.btnSuccess(t('btn.add'), { 'data-form-action': 'add-subtype' })), { wide: true });
  },

  /* ── Editar transacción (desde txlist) ───────────────────────── */
  editTransaction(tx) {
    const dtLocal = tx.date.replace(' ', 'T').slice(0, 16);
    const selectedCurrency = this._transactionSelectionFromTx(tx);
    Modal.open(T.modalShell(`${t('form.edit_transaction')} #${tx.id}`, `
      <div class="flex items-center gap-3 bg-dark-700 rounded-xl p-3 mb-5">
        <div class="flex-1 text-center"><div class="text-xs text-dark-400 mb-1">${t('report.col.credited')}</div>
          <div class="text-sm font-semibold text-dark-100">${escapeHtml(tx.credit_name)}</div></div>
        <div class="text-2xl text-gasto">→</div>
        <div class="flex-1 text-center"><div class="text-xs text-dark-400 mb-1">${t('report.col.debited')}</div>
          <div class="text-sm font-semibold text-dark-100">${escapeHtml(tx.debit_name)}</div></div>
      </div>
      ${T.group(t('form.label.amount'), this._transactionAmountField({
        value: tx.original_amount ?? tx.amount,
        currency: selectedCurrency,
        rate: tx.fx_rate,
      }))}
      ${T.group(t('form.label.description'), T.input('f-desc', { val: tx.description || '' }))}
      ${T.group(t('form.label.date'), T.input('f-date', { type: 'datetime-local', val: dtLocal }))}
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true })
      + T.btnPrimary(t('btn.save'), { 'data-form-action': 'update-transaction', 'data-tx-id': tx.id })));
  },

  /* ── Helpers privados ─────────────────────────────────────────── */
  _loadSubtypes(typeId) {
    const sel = document.getElementById('f-subtype');
    if (!sel) return;
    const tid  = typeId || document.getElementById('f-type')?.value;
    const subs = State.subtypes.filter(s => s.type_id == tid);
    sel.innerHTML = `<option value="">${t('form.no_subtype')}</option>` +
      subs.map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('');
  },

  async _saveAccount() {
    const name    = document.getElementById('f-name')?.value.trim();
    const typeId  = parseInt(document.getElementById('f-type')?.value);
    const subId   = document.getElementById('f-subtype')?.value;
    const initial = parseFloat(document.getElementById('f-initial')?.value) || 0;
    const desc    = document.getElementById('f-desc')?.value || '';
    if (!name || !typeId) return Toast.show(t('msg.name_type_required'), 'err');
    try {
      await API.post('/accounts', { name, type_id: typeId,
        subtype_id: subId ? parseInt(subId) : null, initial_balance: initial, description: desc });
      Modal.close(); Toast.show(t('msg.account_created', {name})); await View.refresh();
    } catch (e) { Toast.show(e.message, 'err'); }
  },

  async _updateAccount(accId) {
    const name  = document.getElementById('f-name')?.value.trim();
    const subId = document.getElementById('f-subtype')?.value;
    const desc  = document.getElementById('f-desc')?.value || '';
    try {
      await API.put(`/accounts/${accId}`, { name, subtype_id: subId ? parseInt(subId) : null, description: desc });
      Modal.close(); Toast.show(t('msg.account_updated')); await View.refresh();
    } catch (e) { Toast.show(e.message, 'err'); }
  },

  async _saveInitialBalance(accId) {
    const initial = parseFloat(document.getElementById('f-initial')?.value) || 0;
    try {
      await API.put(`/accounts/${accId}`, { initial_balance: initial });
      Modal.close(); Toast.show(t('msg.balance_updated')); await View.refresh();
    } catch (e) { Toast.show(e.message, 'err'); }
  },

  async _deleteAccount(accId) {
    try {
      await API.del(`/accounts/${accId}`);
      Modal.close(); Toast.show(t('msg.account_deleted')); await View.refresh();
    } catch (e) { Toast.show(e.message, 'err'); }
  },

  async _saveTransaction(creditId, debitId) {
    const rawAmount = parseFloat(document.getElementById('f-amount')?.value);
    const desc   = document.getElementById('f-desc')?.value || '';
    const date   = document.getElementById('f-date')?.value?.replace('T', ' ');
    if (!rawAmount || rawAmount <= 0) return Toast.show(t('msg.invalid_amount'), 'err');

    const txPayload = await this._buildTransactionPayload(rawAmount);
    if (!txPayload) return;

    try {
      const created = await API.post('/transactions', {
        debit_account: debitId,
        credit_account: creditId,
        description: desc,
        date,
        ...txPayload,
      });
      State.recordUsage(creditId); State.recordUsage(debitId);
      Modal.close(); Toast.show(t('msg.tx_registered', { amount: fmt(created.amount) })); await View.refresh();
    } catch (e) { Toast.show(e.message, 'err'); }
  },

  async _saveTransactionFAB() {
    const rawAmount = parseFloat(document.getElementById('f-amount')?.value);
    const creditId = parseInt(document.getElementById('f-credit')?.value);
    const debitId  = parseInt(document.getElementById('f-debit')?.value);
    const desc     = document.getElementById('f-desc')?.value || '';
    const date     = document.getElementById('f-date')?.value?.replace('T', ' ');
    if (!rawAmount || rawAmount <= 0)  return Toast.show(t('msg.invalid_amount'), 'err');
    if (creditId === debitId)    return Toast.show(t('msg.same_account'), 'err');

    const txPayload = await this._buildTransactionPayload(rawAmount);
    if (!txPayload) return;

    try {
      const created = await API.post('/transactions', {
        debit_account: debitId,
        credit_account: creditId,
        description: desc,
        date,
        ...txPayload,
      });
      State.recordUsage(creditId); State.recordUsage(debitId);
      Modal.close(); Toast.show(t('msg.tx_registered', { amount: fmt(created.amount) })); await View.refresh();
    } catch (e) { Toast.show(e.message, 'err'); }
  },

  async _updateTransaction(txId) {
    const rawAmount = parseFloat(document.getElementById('f-amount')?.value);
    const desc   = document.getElementById('f-desc')?.value;
    const date   = document.getElementById('f-date')?.value?.replace('T', ' ');
    if (!rawAmount || rawAmount <= 0) return Toast.show(t('msg.invalid_amount'), 'err');

    const txPayload = await this._buildTransactionPayload(rawAmount);
    if (!txPayload) return;

    try {
      await API.put(`/transactions/${txId}`, { description: desc, date, ...txPayload });
      Modal.close(); Toast.show(t('msg.tx_updated')); await View.refresh();
    } catch (e) { Toast.show(e.message, 'err'); }
  },

  async _addSubtype() {
    const typeId = parseInt(document.getElementById('new-st-type')?.value);
    const name   = document.getElementById('new-st-name')?.value.trim();
    if (!name) return Toast.show(t('msg.enter_name'), 'err');
    try {
      await API.post('/subtypes', { name, type_id: typeId });
      State.subtypes = await API.get('/subtypes');
      Toast.show(t('msg.subtype_added', {name}));
      await this.subtypeModal();
    } catch (e) { Toast.show(e.message, 'err'); }
  },

  async _editSubtype(stId) {
    const st = State.subtypes.find(s => s.id === stId);
    if (!st) return;
    const name = await Dialog.prompt({
      title: t('btn.rename'),
      label: t('form.label.name'),
      value: st.name,
      placeholder: t('form.placeholder.name'),
      confirmLabel: t('btn.save'),
      cancelLabel: t('btn.cancel'),
      validate: nextValue => nextValue.trim() ? true : t('msg.enter_name'),
    });
    if (!name?.trim() || name.trim() === st.name) return;
    try {
      await API.put(`/subtypes/${stId}`, { name: name.trim() });
      State.subtypes = await API.get('/subtypes');
      Toast.show(t('msg.subtype_updated'));
      await this.subtypeModal();
    } catch (e) { Toast.show(e.message, 'err'); }
  },

  async _deleteSubtype(stId) {
    const st = State.subtypes.find(s => s.id === stId);
    if (!st) return;

    const confirmed = await Dialog.confirm({
      title: t('btn.delete'),
      message: t('msg.confirm_delete', { name: st.name }),
      confirmLabel: t('btn.delete'),
      cancelLabel: t('btn.cancel'),
      submitTone: 'danger',
    });
    if (!confirmed) return;

    try {
      await API.del(`/subtypes/${stId}`);
      State.subtypes = await API.get('/subtypes');
      Toast.show(t('msg.subtype_deleted'));
      await this.subtypeModal();
    } catch (e) { Toast.show(e.message, 'err'); }
  },
};

document.addEventListener('click', event => {
  const action = event.target.closest('[data-form-action]');
  if (!action) return;

  const modalContent = document.getElementById('modal-content');
  if (modalContent && !modalContent.contains(action)) return;

  switch (action.dataset.formAction) {
    case 'set-amount-currency':
      Forms._setAmountCurrency(action.dataset.currency);
      break;
    case 'save-account':
      Forms._saveAccount();
      break;
    case 'update-account':
      Forms._updateAccount(Number(action.dataset.accountId));
      break;
    case 'save-initial-balance':
      Forms._saveInitialBalance(Number(action.dataset.accountId));
      break;
    case 'delete-account':
      Forms._deleteAccount(Number(action.dataset.accountId));
      break;
    case 'save-transaction':
      Forms._saveTransaction(Number(action.dataset.creditId), Number(action.dataset.debitId));
      break;
    case 'save-transaction-fab':
      Forms._saveTransactionFAB();
      break;
    case 'add-subtype':
      Forms._addSubtype();
      break;
    case 'edit-subtype':
      Forms._editSubtype(Number(action.dataset.subtypeId));
      break;
    case 'delete-subtype':
      Forms._deleteSubtype(Number(action.dataset.subtypeId));
      break;
    case 'update-transaction':
      Forms._updateTransaction(Number(action.dataset.txId));
      break;
    default:
      break;
  }
});

document.addEventListener('change', event => {
  const target = event.target.closest('[data-form-change]');
  if (!target) return;

  const modalContent = document.getElementById('modal-content');
  if (modalContent && !modalContent.contains(target)) return;

  if (target.dataset.formChange === 'load-subtypes') {
    Forms._loadSubtypes(target.value);
  }
});
