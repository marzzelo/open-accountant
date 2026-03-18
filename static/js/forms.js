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

  _selectedFxRate() {
    const value = parseFloat(document.getElementById('f-fx-rate')?.value);
    return Number.isFinite(value) && value > 0 ? value : null;
  },

  _isDebitNormal(typeId) {
    return typeId === 1 || typeId === 4;
  },

  _accountBalanceSide(typeId, balance) {
    if (!Number.isFinite(balance) || Math.abs(balance) < 0.005) return 'zero';
    const normalSide = this._isDebitNormal(typeId) ? 'debit' : 'credit';
    if (balance > 0) return normalSide;
    return normalSide === 'debit' ? 'credit' : 'debit';
  },

  _sideLabel(side) {
    if (side === 'zero') return t('form.balance_side_zero');
    return t(`form.balance_side_${side}`);
  },

  _signedBalanceForSide(typeId, side, magnitude) {
    const normalizedMagnitude = Math.round(Math.abs(Number(magnitude) || 0) * 100) / 100;
    if (normalizedMagnitude === 0) return 0;
    const normalSide = this._isDebitNormal(typeId) ? 'debit' : 'credit';
    return Math.round(normalizedMagnitude * (side === normalSide ? 1 : -1) * 100) / 100;
  },

  _balanceDeltaSign(typeId, role) {
    if (role === 'debit') return this._isDebitNormal(typeId) ? 1 : -1;
    return this._isDebitNormal(typeId) ? -1 : 1;
  },

  _currentBalanceNote(account) {
    if (!account) return '';
    const balance = Number(account.balance) || 0;
    return t('form.force_balance_current', {
      name: account.name,
      side: this._sideLabel(this._accountBalanceSide(account.type_id, balance)),
      amount: fmt(Math.abs(balance)),
    });
  },

  _roundMoney(value) {
    return Math.round((Number(value) || 0) * 100) / 100;
  },

  _plainAmount(value) {
    return Math.abs(Number(value) || 0).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  },

  _currencyAmountLabel(currency, value) {
    if (currency === 'ARS') return fmt(value);
    return `${currency} ${this._plainAmount(value)}`;
  },

  _previewTransactionRate() {
    const currency = this._selectedAmountCurrency();
    if (currency === 'ARS') return 1;
    return this._selectedFxRate() || this._getCurrencyRate(currency);
  },

  _effectiveAmountPreviewField(opts = {}) {
    return `
      <div id="f-effective-amount-preview" ${htmlAttrs({
        'data-credit-id': opts.creditId,
        'data-debit-id': opts.debitId,
        class: 'mb-4 rounded-xl border border-emerald-900/30 bg-emerald-950/20 px-3 py-3',
      })}>
        <div class="text-[11px] font-semibold uppercase tracking-wide text-emerald-300/80 mb-1">${escapeHtml(t('form.effective_amount_title'))}</div>
        <div id="f-effective-amount-preview-body" class="text-sm text-dark-300">${escapeHtml(t('form.effective_amount_placeholder'))}</div>
      </div>`;
  },

  _previewAccountIds() {
    const preview = document.getElementById('f-effective-amount-preview');
    const creditId = Number.parseInt(preview?.dataset.creditId || document.getElementById('f-credit')?.value || '', 10);
    const debitId = Number.parseInt(preview?.dataset.debitId || document.getElementById('f-debit')?.value || '', 10);
    return { creditId, debitId };
  },

  _effectiveAmountPreviewState({ creditId = null, debitId = null } = {}) {
    const preview = {
      tone: 'muted',
      text: t('form.effective_amount_placeholder'),
    };
    const rawAmount = this._transactionInputAmount();
    const forceMode = this._selectedForceBalanceMode();
    const currency = this._selectedAmountCurrency();
    const meta = this._transactionCurrencyMeta(currency);
    const rate = this._previewTransactionRate();

    if (forceMode === 'invalid') {
      return { tone: 'err', text: t('msg.force_balance_single_option') };
    }

    if (!forceMode && (!Number.isFinite(rawAmount) || rawAmount <= 0)) return preview;
    if (forceMode && (!Number.isFinite(rawAmount) || rawAmount < 0)) return preview;

    if (currency !== 'ARS' && !(Number.isFinite(rate) && rate > 0)) {
      return {
        tone: 'err',
        text: t('form.effective_amount_rate_missing', { label: meta.label }),
      };
    }

    if (!forceMode) {
      const bookedAmount = currency === 'ARS' ? this._roundMoney(rawAmount) : this._roundMoney(rawAmount * rate);
      if (currency === 'ARS') {
        return {
          tone: 'ok',
          text: t('form.effective_amount_preview', { amount: fmt(bookedAmount) }),
        };
      }

      return {
        tone: 'ok',
        text: t('form.effective_amount_preview_fx', {
          amount: fmt(bookedAmount),
          original: this._currencyAmountLabel(meta.originalCurrency, rawAmount),
        }),
      };
    }

    const fallbackIds = this._previewAccountIds();
    const resolvedCreditId = creditId ?? fallbackIds.creditId;
    const resolvedDebitId = debitId ?? fallbackIds.debitId;
    const targetAccountId = forceMode === 'credit' ? resolvedCreditId : resolvedDebitId;
    const targetAccount = State.accounts.find(account => account.id === targetAccountId);
    if (!targetAccount) return preview;

    const targetBookedBalance = currency === 'ARS' ? this._roundMoney(rawAmount) : this._roundMoney(rawAmount * rate);
    const desiredBalance = this._signedBalanceForSide(targetAccount.type_id, forceMode, targetBookedBalance);
    const currentBalance = this._roundMoney(targetAccount.balance);
    const bookedAmount = this._roundMoney((desiredBalance - currentBalance) / this._balanceDeltaSign(targetAccount.type_id, forceMode));

    if (Math.abs(bookedAmount) < 0.005) {
      return { tone: 'muted', text: t('msg.force_balance_no_change') };
    }

    if (!Number.isFinite(bookedAmount) || bookedAmount < 0) {
      return { tone: 'err', text: t('msg.force_balance_conflict') };
    }

    if (currency === 'ARS') {
      return {
        tone: 'ok',
        text: t('form.effective_amount_preview_forced', {
          amount: fmt(bookedAmount),
          name: targetAccount.name,
          side: this._sideLabel(forceMode),
          target: fmt(targetBookedBalance),
        }),
      };
    }

    return {
      tone: 'ok',
      text: t('form.effective_amount_preview_forced_fx', {
        amount: fmt(bookedAmount),
        original: this._currencyAmountLabel(meta.originalCurrency, this._roundMoney(bookedAmount / rate)),
        name: targetAccount.name,
        side: this._sideLabel(forceMode),
        target: fmt(targetBookedBalance),
      }),
    };
  },

  _refreshTransactionEffectiveAmountNote({ creditId = null, debitId = null } = {}) {
    const wrapper = document.getElementById('f-effective-amount-preview');
    const body = document.getElementById('f-effective-amount-preview-body');
    if (!wrapper || !body) return;

    const forceMode = this._selectedForceBalanceMode();
    wrapper.classList.toggle('hidden', !forceMode);
    if (!forceMode) return;

    const preview = this._effectiveAmountPreviewState({ creditId, debitId });
    body.textContent = preview.text;

    wrapper.className = 'mb-4 rounded-xl border px-3 py-3';
    body.className = 'text-sm';

    if (preview.tone === 'err') {
      wrapper.classList.add('border-red-900/40', 'bg-red-950/20');
      body.classList.add('text-red-300');
      return;
    }

    if (preview.tone === 'ok') {
      wrapper.classList.add('border-emerald-900/30', 'bg-emerald-950/20');
      body.classList.add('text-emerald-200');
      return;
    }

    wrapper.classList.add('border-dark-600', 'bg-dark-800/50');
    body.classList.add('text-dark-400');
  },

  _forcedBalanceField(opts = {}) {
    return `
      <div class="mb-4 rounded-xl border border-dark-600 bg-dark-800/60 p-3">
        <div class="text-[11px] font-semibold uppercase tracking-wide text-dark-400 mb-3">${escapeHtml(t('form.force_balance_title'))}</div>
        <div class="space-y-3">
          <label class="flex items-start gap-3 rounded-lg border border-dark-600/70 bg-dark-700/40 px-3 py-3 cursor-pointer">
            <input id="f-force-credit-balance" type="checkbox" data-form-change="toggle-force-balance" data-target="credit"
              class="mt-0.5 h-4 w-4 rounded border-dark-500 bg-dark-800 text-blue-500 focus:ring-blue-500/40 cursor-pointer">
            <div class="min-w-0">
              <div class="text-sm font-semibold text-dark-100">${escapeHtml(t('form.force_credit_balance'))}</div>
              <div id="f-force-credit-balance-note" class="mt-1 text-[11px] text-dark-500">${escapeHtml(this._currentBalanceNote(opts.creditAccount))}</div>
            </div>
          </label>
          <label class="flex items-start gap-3 rounded-lg border border-dark-600/70 bg-dark-700/40 px-3 py-3 cursor-pointer">
            <input id="f-force-debit-balance" type="checkbox" data-form-change="toggle-force-balance" data-target="debit"
              class="mt-0.5 h-4 w-4 rounded border-dark-500 bg-dark-800 text-blue-500 focus:ring-blue-500/40 cursor-pointer">
            <div class="min-w-0">
              <div class="text-sm font-semibold text-dark-100">${escapeHtml(t('form.force_debit_balance'))}</div>
              <div id="f-force-debit-balance-note" class="mt-1 text-[11px] text-dark-500">${escapeHtml(this._currentBalanceNote(opts.debitAccount))}</div>
            </div>
          </label>
        </div>
      </div>`;
  },

  _selectedForceBalanceMode() {
    const creditChecked = !!document.getElementById('f-force-credit-balance')?.checked;
    const debitChecked = !!document.getElementById('f-force-debit-balance')?.checked;

    if (creditChecked && debitChecked) return 'invalid';
    if (creditChecked) return 'credit';
    if (debitChecked) return 'debit';
    return null;
  },

  _syncForceBalanceMode(target) {
    const creditCheckbox = document.getElementById('f-force-credit-balance');
    const debitCheckbox = document.getElementById('f-force-debit-balance');
    if (!creditCheckbox || !debitCheckbox) return;

    if (target === 'credit' && creditCheckbox.checked) debitCheckbox.checked = false;
    if (target === 'debit' && debitCheckbox.checked) creditCheckbox.checked = false;
  },

  _refreshForceBalanceNotes({ creditId = null, debitId = null } = {}) {
    const resolvedCreditId = creditId ?? Number.parseInt(document.getElementById('f-credit')?.value || '', 10);
    const resolvedDebitId = debitId ?? Number.parseInt(document.getElementById('f-debit')?.value || '', 10);
    const creditAccount = State.accounts.find(account => account.id === resolvedCreditId);
    const debitAccount = State.accounts.find(account => account.id === resolvedDebitId);
    const creditNote = document.getElementById('f-force-credit-balance-note');
    const debitNote = document.getElementById('f-force-debit-balance-note');

    if (creditNote) creditNote.textContent = this._currentBalanceNote(creditAccount);
    if (debitNote) debitNote.textContent = this._currentBalanceNote(debitAccount);
    this._refreshTransactionEffectiveAmountNote({ creditId: resolvedCreditId, debitId: resolvedDebitId });
  },

  _transactionInputAmount() {
    const rawValue = document.getElementById('f-amount')?.value;
    if (rawValue == null || rawValue === '') return Number.NaN;
    return Number.parseFloat(rawValue);
  },

  async _selectedTransactionRate() {
    const currency = this._selectedAmountCurrency();
    if (currency === 'ARS') return 1;
    return this._selectedFxRate() || await this._resolveCurrencyRate(currency);
  },

  _syncTransactionFxUi(currency, { preserveRate = false } = {}) {
    const meta = this._transactionCurrencyMeta(currency);
    const originalCurrencyDisplay = document.getElementById('f-original-currency-display');
    const fxRateGroup = document.getElementById('f-fx-rate-group');
    const fxRateInput = document.getElementById('f-fx-rate');
    const note = document.getElementById('f-amount-currency-note');
    const isBaseCurrency = meta.originalCurrency === 'ARS';

    if (originalCurrencyDisplay) originalCurrencyDisplay.textContent = meta.originalCurrency;
    if (fxRateGroup) fxRateGroup.classList.toggle('hidden', isBaseCurrency);

    if (fxRateInput) {
      fxRateInput.disabled = isBaseCurrency;
      if (isBaseCurrency) {
        fxRateInput.value = '1.00';
      } else if (!preserveRate) {
        const nextRate = this._getCurrencyRate(currency);
        fxRateInput.value = Number.isFinite(nextRate) && nextRate > 0 ? nextRate.toFixed(2) : '';
      }
    }

    if (note) note.textContent = this._amountCurrencyHelp(currency, this._selectedFxRate() || this._getCurrencyRate(currency));
  },

  _transactionFxEditor(opts = {}) {
    const selected = this._transactionCurrencyMeta(opts.currency || 'ARS');
    const rateValue = selected.originalCurrency === 'ARS'
      ? '1.00'
      : (opts.rate != null ? Number(opts.rate).toFixed(2) : '');

    return `
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
        <div>
          ${T.label(t('form.label.original_currency'))}
          <div id="f-original-currency-display" class="w-full bg-dark-700/50 border border-dark-600 rounded-lg text-dark-200 text-sm px-3 py-2.5 font-mono">${selected.originalCurrency}</div>
        </div>
        <div id="f-fx-rate-group" class="${selected.originalCurrency === 'ARS' ? 'hidden' : ''}">
          ${T.label(t('form.label.fx_rate'))}
          ${T.input('f-fx-rate', {
            type: 'number',
            step: '0.0001',
            min: '0.0001',
            val: rateValue,
            inputmode: 'decimal',
          })}
        </div>
      </div>`;
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
          type: 'number', step: '0.01', min: opts.min ?? '0.01', ph: t('form.placeholder.amount'), auto: opts.auto !== false,
        val: opts.value,
        inputmode: 'decimal',
          cls: `!text-[22px] !font-bold !text-center !text-ingreso !tracking-tight ${opts.hideSpin ? 'input-no-spin' : ''}`.trim()
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
    const amountInput = document.getElementById('f-amount');

    if (hiddenInput) hiddenInput.value = nextCurrency;

    this._transactionCurrencies().forEach(option => {
      const button = document.getElementById(this._transactionCurrencyButtonId(option.code));
      if (!button) return;
      const active = option.code === nextCurrency;
      button.className = this._currencyButtonClass(option.code, active);
      button.setAttribute('aria-pressed', String(active));
    });

    if (amountInput) amountInput.placeholder = this._currencyPlaceholder(nextCurrency);
    this._syncTransactionFxUi(nextCurrency);
    this._refreshTransactionEffectiveAmountNote();
  },

  async _primeAmountCurrencyHelp() {
    const currency = this._selectedAmountCurrency();
    const rate = this._selectedFxRate() || await this._resolveCurrencyRate(currency);
    const note = document.getElementById('f-amount-currency-note');
    if (!note) return;
    note.textContent = this._amountCurrencyHelp(currency, rate);
  },

  async _normalizeTransactionAmount(rawAmount, rate = null) {
    const currency = this._selectedAmountCurrency();
    if (currency === 'ARS') return rawAmount;

    const resolvedRate = rate || await this._selectedTransactionRate();
    if (!resolvedRate) {
      Toast.show(this._missingCurrencyRateMessage(currency), 'err');
      return null;
    }

    return Math.round(rawAmount * resolvedRate * 100) / 100;
  },

  async _resolveTransactionEntryAmount(rawAmount, { creditId, debitId }) {
    const forceMode = this._selectedForceBalanceMode();

    if (forceMode === 'invalid') {
      Toast.show(t('msg.force_balance_single_option'), 'err');
      return null;
    }

    if (!forceMode) {
      if (!Number.isFinite(rawAmount) || rawAmount <= 0) {
        Toast.show(t('msg.invalid_amount'), 'err');
        return null;
      }
      return rawAmount;
    }

    if (!Number.isFinite(rawAmount) || rawAmount < 0) {
      Toast.show(t('msg.invalid_amount'), 'err');
      return null;
    }

    const targetAccountId = forceMode === 'credit' ? creditId : debitId;
    const targetAccount = State.accounts.find(account => account.id === targetAccountId);
    if (!targetAccount) {
      Toast.show(t('msg.invalid_value'), 'err');
      return null;
    }

    const rate = await this._selectedTransactionRate();
    const targetMagnitude = await this._normalizeTransactionAmount(rawAmount, rate);
    if (targetMagnitude == null) return null;

    const desiredBalance = this._signedBalanceForSide(targetAccount.type_id, forceMode, targetMagnitude);
    const currentBalance = Math.round((Number(targetAccount.balance) || 0) * 100) / 100;
    const amount = Math.round(((desiredBalance - currentBalance) / this._balanceDeltaSign(targetAccount.type_id, forceMode)) * 100) / 100;

    if (!Number.isFinite(amount)) {
      Toast.show(t('msg.invalid_amount'), 'err');
      return null;
    }
    if (Math.abs(amount) < 0.005) {
      Toast.show(t('msg.force_balance_no_change'), 'err');
      return null;
    }
    if (amount < 0) {
      Toast.show(t('msg.force_balance_conflict'), 'err');
      return null;
    }
    if (this._selectedAmountCurrency() === 'ARS') return amount;

    return Math.round((amount / rate) * 100) / 100;
  },

  async _buildTransactionPayload(rawAmount) {
    const currency = this._selectedAmountCurrency();
    const meta = this._transactionCurrencyMeta(currency);
    const manualRate = this._selectedFxRate();

    if (meta.originalCurrency === 'ARS') {
      return {
        original_amount: rawAmount,
        original_currency: 'ARS',
        fx_rate: 1,
        fx_source: null,
      };
    }

    const rate = manualRate || await this._resolveCurrencyRate(currency);
    if (!rate) {
      Toast.show(this._missingCurrencyRateMessage(currency), 'err');
      return null;
    }

    return {
      original_amount: rawAmount,
      original_currency: meta.originalCurrency,
      fx_rate: rate,
      fx_source: meta.fxSource,
    };
  },

  _transactionSelectionFromTx(tx) {
    return tx.fx_source || tx.original_currency || 'ARS';
  },

  _focusTransactionAmount({ preserveRate = false } = {}) {
    const input = document.getElementById('f-amount');
    input?.focus();
    input?.select();
    this._syncTransactionFxUi(this._selectedAmountCurrency(), { preserveRate });
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
      ${T.group(`${t('form.label.amount')} *`, this._transactionAmountField({ hideSpin: true, min: '0' }))}
      ${T.group(t('form.label.description'), T.input('f-desc', { ph: t('form.placeholder.desc_tx'), val: description }))}
      ${T.group(t('form.label.date'), T.input('f-date', { type: 'datetime-local', val: now }))}
      ${this._forcedBalanceField({ creditAccount: credit, debitAccount: debit })}
      ${this._effectiveAmountPreviewField({ creditId, debitId })}
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true }) +
       T.btnSuccess(t('btn.register'), { 'data-form-action': 'save-transaction', 'data-credit-id': creditId, 'data-debit-id': debitId })));

    setTimeout(() => {
      this._focusTransactionAmount();
      this._refreshForceBalanceNotes({ creditId, debitId });
    }, 80);
  },

  /* ── FAB: transacción manual (mobile) ────────────────────────── */
  newTransactionFAB() {
    const opts = State.accounts.map(a =>
      `<option value="${a.id}">${escapeHtml(a.name)} (${escapeHtml(a.type_name)})</option>`).join('');
    const now = localNow();
    const [firstAccount] = State.accounts;

    Modal.open(T.modalShell(`💸 ${t('form.new_transaction')}`, `
      ${T.group(`${t('form.label.amount')} *`, this._transactionAmountField({ hideSpin: true, min: '0' }))}
      ${T.group(t('form.label.credit'), T.select('f-credit', opts, { 'data-form-change': 'refresh-force-balance' }))}
      ${T.group(t('form.label.debit'),  T.select('f-debit',  opts, { 'data-form-change': 'refresh-force-balance' }))}
      ${T.group(t('form.label.description'), T.input('f-desc', { ph: t('form.placeholder.desc_tx') }))}
      ${T.group(t('form.label.date'), T.input('f-date', { type: 'datetime-local', val: now }))}
      ${this._forcedBalanceField({ creditAccount: firstAccount || null, debitAccount: firstAccount || null })}
      ${this._effectiveAmountPreviewField()}
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true }) +
       T.btnSuccess(t('btn.register'), { 'data-form-action': 'save-transaction-fab' })));

    setTimeout(() => {
      this._focusTransactionAmount();
      this._refreshForceBalanceNotes();
    }, 80);
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

  _bindEditTransactionFxInputs() {
    const fxRateInput = document.getElementById('f-fx-rate');
    fxRateInput?.addEventListener('input', () => this._primeAmountCurrencyHelp());
  },

  /* ── Editar transacción ──────────────────────────────────────── */
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
      ${this._transactionFxEditor({ currency: selectedCurrency, rate: tx.fx_rate })}
      ${T.group(t('form.label.description'), T.input('f-desc', { val: tx.description || '' }))}
      ${T.group(t('form.label.date'), T.input('f-date', { type: 'datetime-local', val: dtLocal }))}
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true })
      + T.btnPrimary(t('btn.save'), { 'data-form-action': 'update-transaction', 'data-tx-id': tx.id })));

    setTimeout(() => {
      this._bindEditTransactionFxInputs();
      this._focusTransactionAmount({ preserveRate: true });
    }, 40);
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
    const rawAmount = this._transactionInputAmount();
    const desc   = document.getElementById('f-desc')?.value || '';
    const date   = document.getElementById('f-date')?.value?.replace('T', ' ');

    const entryAmount = await this._resolveTransactionEntryAmount(rawAmount, { creditId, debitId });
    if (entryAmount == null) return;

    const txPayload = await this._buildTransactionPayload(entryAmount);
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
    const rawAmount = this._transactionInputAmount();
    const creditId = parseInt(document.getElementById('f-credit')?.value);
    const debitId  = parseInt(document.getElementById('f-debit')?.value);
    const desc     = document.getElementById('f-desc')?.value || '';
    const date     = document.getElementById('f-date')?.value?.replace('T', ' ');
    if (creditId === debitId)    return Toast.show(t('msg.same_account'), 'err');

    const entryAmount = await this._resolveTransactionEntryAmount(rawAmount, { creditId, debitId });
    if (entryAmount == null) return;

    const txPayload = await this._buildTransactionPayload(entryAmount);
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

  switch (target.dataset.formChange) {
    case 'load-subtypes':
      Forms._loadSubtypes(target.value);
      break;
    case 'toggle-force-balance':
      Forms._syncForceBalanceMode(target.dataset.target);
      Forms._refreshTransactionEffectiveAmountNote();
      break;
    case 'refresh-force-balance':
      Forms._refreshForceBalanceNotes();
      break;
    default:
      break;
  }
});

document.addEventListener('input', event => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;

  const modalContent = document.getElementById('modal-content');
  if (modalContent && !modalContent.contains(target)) return;

  if (target.id === 'f-amount') {
    Forms._refreshTransactionEffectiveAmountNote();
  }
});
