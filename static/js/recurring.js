/* ── recurring.js — Monthly recurring transactions ── */
'use strict';

const Recurring = {
  filter: 'all',
  items: [],

  setFilter(filter, opts = {}) {
    this.filter = ['all', 'enabled', 'active'].includes(filter) ? filter : 'all';
    if (!opts.silent && View.current === 'recurring') this.render();
  },

  _accountOptions(selectedId = null) {
    return (State.accounts || []).map(account => `
      <option value="${account.id}" ${Number(account.id) === Number(selectedId) ? 'selected' : ''}>
        ${escapeHtml(account.name)} (${escapeHtml(account.type_name)})
      </option>`).join('');
  },

  _selectedTagIds() {
    return [...document.querySelectorAll('input[name="f-tag-ids"]:checked')].map(input => Number(input.value));
  },

  _status(item) {
    if (!item.enabled) return 'disabled';
    if (item.is_active) return 'active';
    return 'upcoming';
  },

  _statusLabel(item) {
    const status = this._status(item);
    if (status === 'active') return t('recurring.status.active');
    if (status === 'disabled') return t('recurring.status.disabled');
    return t('recurring.status.upcoming');
  },

  _currencyFromItem(item) {
    return item.fx_source || item.original_currency || 'ARS';
  },

  _tagBadges(item) {
    return (item.tags || []).map(tag => renderTagBadge(tag)).join('');
  },

  _dateUtcDay(value) {
    const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) return null;
    const [, year, month, day] = match.map(Number);
    return Date.UTC(year, month - 1, day);
  },

  _daysFromToday(value) {
    const scheduled = this._dateUtcDay(value);
    if (scheduled === null) return null;
    const now = new Date();
    const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.round((today - scheduled) / 86400000);
  },

  _scheduleOffsetLabel(item) {
    const status = this._status(item);
    if (status === 'disabled') return '';
    const daysFromScheduled = this._daysFromToday(item.effective_alert_date);
    if (daysFromScheduled === null) return '';

    if (status === 'active') {
      const count = Math.max(0, daysFromScheduled);
      return t(count === 1 ? 'recurring.days_overdue_one' : 'recurring.days_overdue_many', { count });
    }

    const count = Math.max(0, -daysFromScheduled);
    return t(count === 1 ? 'recurring.days_remaining_one' : 'recurring.days_remaining_many', { count });
  },

  _column(titleKey, items, toneClass) {
    return `
      <section class="min-w-0 rounded-lg border border-dark-600 bg-dark-800/55 flex flex-col overflow-hidden">
        <div class="px-3 py-2 border-b border-dark-600 flex items-center justify-between">
          <h3 class="text-xs font-bold uppercase tracking-wide ${toneClass}">${escapeHtml(t(titleKey))}</h3>
          <span class="text-[11px] text-dark-400">${items.length}</span>
        </div>
        <div class="p-3 space-y-3 overflow-y-auto">
          ${items.map(item => this._card(item)).join('') || `<div class="text-xs text-dark-500 py-8 text-center">${escapeHtml(t('recurring.empty_column'))}</div>`}
        </div>
      </section>`;
  },

  _card(item) {
    const status = this._status(item);
    const scheduleOffsetLabel = this._scheduleOffsetLabel(item);
    const statusClass = status === 'active'
      ? 'text-amber-300 bg-amber-500/10 border-amber-500/30'
      : status === 'disabled'
        ? 'text-dark-400 bg-dark-700/50 border-dark-600'
        : 'text-blue-300 bg-blue-500/10 border-blue-500/30';
    return `
      <article class="rounded-lg border border-dark-600 bg-dark-700/50 hover:bg-dark-700 cursor-pointer transition-colors"
               data-recurring-action="details" data-recurring-id="${item.id}">
        <div class="p-3">
          <div class="flex items-start justify-between gap-3 mb-2">
            <div class="min-w-0">
              <div class="text-sm font-semibold text-dark-100 truncate">${escapeHtml(item.description || t('recurring.untitled'))}</div>
              <div class="text-[11px] text-dark-400 truncate">${escapeHtml(item.credit_name)} → ${escapeHtml(item.debit_name)}</div>
            </div>
            <span class="shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusClass}">${escapeHtml(this._statusLabel(item))}</span>
          </div>
          <div class="flex items-end justify-between gap-3">
            <div>
              <div class="text-lg font-bold text-ingreso">${escapeHtml(fmt(item.amount))}</div>
              <div class="text-[11px] text-dark-500">${escapeHtml(item.original_currency)} ${Number(item.original_amount || 0).toFixed(2)}</div>
            </div>
            <div class="text-right text-[11px] text-dark-400">
              <div>${escapeHtml(t('recurring.alert_day_short', { day: item.alert_day }))}</div>
              <div>${escapeHtml(item.effective_alert_date || '')}</div>
              ${scheduleOffsetLabel ? `<div class="mt-1 font-semibold ${status === 'active' ? 'text-amber-300' : 'text-blue-300'}">${escapeHtml(scheduleOffsetLabel)}</div>` : ''}
            </div>
          </div>
          <div class="mt-2 flex flex-wrap gap-1.5">${this._tagBadges(item)}</div>
        </div>
      </article>`;
  },

  async render() {
    const main = document.getElementById('main');
    const query = encodeURIComponent(this.filter);
    this.items = await API.get(`/recurring-transactions?filter=${query}`);
    const activeItems = this.items.filter(item => this._status(item) === 'active');
    const upcomingItems = this.items.filter(item => this._status(item) === 'upcoming');
    const disabledItems = this.items.filter(item => this._status(item) === 'disabled');
    main.innerHTML = `
      <div class="h-full min-h-0 flex flex-col px-3 py-3 sm:px-5 sm:py-4 gap-3">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 class="text-xl font-bold text-dark-100">${escapeHtml(t('recurring.title'))}</h2>
            <p class="text-xs text-dark-400">${escapeHtml(t('recurring.subtitle'))}</p>
          </div>
          <div class="flex items-center gap-2 flex-wrap">
            ${['all', 'enabled', 'active'].map(filter => `
              <button type="button" data-recurring-action="filter" data-filter="${filter}"
                      class="tbtn text-xs px-3 py-2 ${this.filter === filter ? 'active' : ''}">
                ${escapeHtml(t(`recurring.filter.${filter}`))}
              </button>`).join('')}
            <button type="button" data-recurring-action="new"
                    class="tbtn !bg-blue-600 !text-white !border-blue-600 hover:!bg-blue-500 text-xs px-3 py-2">
              ${escapeHtml(t('recurring.new'))}
            </button>
          </div>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-3 flex-1 min-h-0">
          ${this._column('recurring.column.active', activeItems, 'text-amber-300')}
          ${this._column('recurring.column.upcoming', upcomingItems, 'text-blue-300')}
          ${this._column('recurring.column.disabled', disabledItems, 'text-dark-400')}
        </div>
      </div>`;
  },

  _form(item = null) {
    const isEdit = !!item;
    const selectedCurrency = item ? this._currencyFromItem(item) : 'ARS';
    Modal.open(T.modalShell(isEdit ? t('recurring.edit') : t('recurring.new'), `
      <div class="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] gap-3 items-end bg-dark-700 rounded-xl p-3 mb-5">
        <div>
          ${T.label(t('form.transaction.source'))}
          ${T.select('f-credit', this._accountOptions(item?.credit_account))}
        </div>
        <div class="flex items-center justify-center text-2xl text-gasto pb-2">→</div>
        <div>
          ${T.label(t('form.transaction.destination'))}
          ${T.select('f-debit', this._accountOptions(item?.debit_account))}
        </div>
      </div>
      ${T.group(`${t('form.label.amount')} *`, Forms._transactionAmountField({
        value: item?.original_amount ?? item?.amount ?? '',
        currency: selectedCurrency,
        rate: item?.fx_rate,
        hideSpin: true,
        min: '0',
      }))}
      ${Forms._transactionFxEditor({ currency: selectedCurrency, rate: item?.fx_rate })}
      ${T.group(t('form.label.description'), T.input('f-desc', { val: item?.description || '', ph: t('form.placeholder.desc_tx') }))}
      ${Forms._tagSelectionField((item?.tags || []).map(tag => Number(tag.id)))}
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
        <div>${T.label(t('recurring.alert_day'))}${T.input('f-alert-day', { type: 'number', min: '1', max: '31', step: '1', val: item?.alert_day || 1 })}</div>
        <label class="rounded-xl border border-dark-600 bg-dark-800/70 px-3 py-3 flex items-center gap-3 cursor-pointer">
          <input id="f-alert-active" type="checkbox" class="w-4 h-4 accent-blue-500" ${item?.alert_active === false ? '' : 'checked'}>
          <span class="text-sm text-dark-200">${escapeHtml(t('recurring.alert_active'))}</span>
        </label>
        <label class="rounded-xl border border-dark-600 bg-dark-800/70 px-3 py-3 flex items-center gap-3 cursor-pointer">
          <input id="f-enabled" type="checkbox" class="w-4 h-4 accent-blue-500" ${item?.enabled === false ? '' : 'checked'}>
          <span class="text-sm text-dark-200">${escapeHtml(t('recurring.enabled'))}</span>
        </label>
      </div>
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true }) +
       T.btnSuccess(isEdit ? t('btn.save') : t('btn.create'), {
         'data-recurring-action': isEdit ? 'update' : 'create',
         'data-recurring-id': item?.id,
       })));

    setTimeout(() => {
      Forms._bindEditTransactionFxInputs();
      Forms._focusTransactionAmount({ preserveRate: true });
    }, 40);
  },

  _detail(item) {
    const now = localNow();
    const selectedCurrency = this._currencyFromItem(item);
    Modal.open(T.modalShell(t('recurring.detail_title', { id: item.id }), `
      <div class="rounded-xl border border-dark-600 bg-dark-700/60 p-3 mb-4">
        <div class="text-sm font-semibold text-dark-100 mb-1">${escapeHtml(item.description || t('recurring.untitled'))}</div>
        <div class="text-xs text-dark-400">${escapeHtml(item.credit_name)} → ${escapeHtml(item.debit_name)}</div>
        <div class="mt-2 text-xs text-dark-400">${escapeHtml(t('recurring.next_alert', { date: item.effective_alert_date }))}</div>
      </div>
      ${T.group(`${t('form.label.amount')} *`, Forms._transactionAmountField({
        value: item.original_amount ?? item.amount,
        currency: selectedCurrency,
        rate: item.fx_rate,
        hideSpin: true,
        min: '0',
      }))}
      ${Forms._transactionFxEditor({ currency: selectedCurrency, rate: item.fx_rate })}
      ${T.group(t('form.label.description'), T.input('f-desc', { val: item.description || '' }))}
      ${T.group(t('form.label.date'), T.input('f-date', { type: 'datetime-local', val: now }))}
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true }) +
       T.btnPrimary(t('btn.edit'), { 'data-recurring-action': 'edit', 'data-recurring-id': item.id }) +
       T.btnGhost(t('btn.delete'), { 'data-recurring-action': 'delete', 'data-recurring-id': item.id }) +
       `<button ${htmlAttrs({
         type: 'button',
         'data-recurring-action': 'mark-done',
         'data-recurring-id': item.id,
         class: 'px-3 py-1.5 rounded-lg text-xs font-medium font-sans cursor-pointer transition-all border border-dark-600 text-dark-400 hover:text-dark-300 hover:bg-dark-700 bg-transparent',
       })}>${escapeHtml(t('recurring.mark_done'))}</button>` +
       T.btnSuccess(t('recurring.post'), { 'data-recurring-action': 'post', 'data-recurring-id': item.id })));

    setTimeout(() => {
      Forms._bindEditTransactionFxInputs();
      Forms._focusTransactionAmount({ preserveRate: true });
    }, 40);
  },

  async _payload() {
    const amountState = Forms._transactionAmountState();
    if (!amountState.isValid || amountState.value <= 0) {
      Toast.show(t('msg.invalid_amount'), 'err');
      return null;
    }
    const txPayload = await Forms._buildTransactionPayload(amountState.value);
    if (!txPayload) return null;
    const creditId = Number.parseInt(document.getElementById('f-credit')?.value || '', 10);
    const debitId = Number.parseInt(document.getElementById('f-debit')?.value || '', 10);
    if (!Number.isInteger(creditId) || !Number.isInteger(debitId)) {
      Toast.show(t('msg.invalid_value'), 'err');
      return null;
    }
    if (creditId === debitId) {
      Toast.show(t('msg.same_account'), 'err');
      return null;
    }
    const alertDay = Number.parseInt(document.getElementById('f-alert-day')?.value || '', 10);
    if (!Number.isInteger(alertDay) || alertDay < 1 || alertDay > 31) {
      Toast.show(t('recurring.invalid_alert_day'), 'err');
      return null;
    }
    return {
      credit_account: creditId,
      debit_account: debitId,
      tag_ids: this._selectedTagIds(),
      description: document.getElementById('f-desc')?.value || '',
      alert_day: alertDay,
      alert_active: !!document.getElementById('f-alert-active')?.checked,
      enabled: !!document.getElementById('f-enabled')?.checked,
      ...txPayload,
    };
  },

  async _create() {
    const payload = await this._payload();
    if (!payload) return;
    try {
      await API.post('/recurring-transactions', payload);
      Modal.close();
      Toast.show(t('recurring.created'));
      await API.reloadRecurringActiveCount();
      await this.render();
    } catch (e) {
      Toast.show(e.message, 'err');
    }
  },

  async _update(id) {
    const payload = await this._payload();
    if (!payload) return;
    try {
      await API.put(`/recurring-transactions/${id}`, payload);
      Modal.close();
      Toast.show(t('recurring.updated'));
      await API.reloadRecurringActiveCount();
      await this.render();
    } catch (e) {
      Toast.show(e.message, 'err');
    }
  },

  async _post(id) {
    const amountState = Forms._transactionAmountState();
    if (!amountState.isValid || amountState.value <= 0) {
      Toast.show(t('msg.invalid_amount'), 'err');
      return;
    }
    const txPayload = await Forms._buildTransactionPayload(amountState.value);
    if (!txPayload) return;
    try {
      const result = await API.post(`/recurring-transactions/${id}/post`, {
        description: document.getElementById('f-desc')?.value || '',
        date: document.getElementById('f-date')?.value?.replace('T', ' '),
        ...txPayload,
      });
      Modal.close();
      Toast.show(t('msg.tx_registered', { amount: fmt(result.transaction.amount) }));
      await View.refresh();
    } catch (e) {
      Toast.show(e.message, 'err');
    }
  },

  async _delete(id) {
    const item = this.items.find(candidate => Number(candidate.id) === Number(id))
      || await API.get(`/recurring-transactions/${id}`);
    const confirmed = await Dialog.confirm({
      title: t('btn.delete'),
      message: t('msg.confirm_delete', { name: item.description || t('recurring.untitled') }),
      confirmLabel: t('btn.delete'),
      cancelLabel: t('btn.cancel'),
      submitTone: 'danger',
    });
    if (!confirmed) return;
    try {
      await API.del(`/recurring-transactions/${id}`);
      Modal.close();
      Toast.show(t('recurring.deleted'));
      await API.reloadRecurringActiveCount();
      await this.render();
    } catch (e) {
      Toast.show(e.message, 'err');
    }
  },

  async _markDone(id) {
    try {
      await API.post(`/recurring-transactions/${id}/mark-done`, {});
      Modal.close();
      Toast.show(t('recurring.marked_done'));
      await View.refresh();
    } catch (e) {
      Toast.show(e.message, 'err');
    }
  },
};

window.Recurring = Recurring;

document.addEventListener('click', async event => {
  const action = event.target.closest('[data-recurring-action]');
  if (!action) return;
  event.preventDefault();

  const recurringId = Number(action.dataset.recurringId || 0);
  switch (action.dataset.recurringAction) {
    case 'filter':
      Recurring.setFilter(action.dataset.filter);
      break;
    case 'new':
      Recurring._form();
      break;
    case 'details': {
      const item = Recurring.items.find(candidate => Number(candidate.id) === recurringId)
        || await API.get(`/recurring-transactions/${recurringId}`);
      Recurring._detail(item);
      break;
    }
    case 'edit': {
      const item = await API.get(`/recurring-transactions/${recurringId}`);
      Recurring._form(item);
      break;
    }
    case 'create':
      await Recurring._create();
      break;
    case 'update':
      await Recurring._update(recurringId);
      break;
    case 'post':
      await Recurring._post(recurringId);
      break;
    case 'mark-done':
      await Recurring._markDone(recurringId);
      break;
    case 'delete':
      await Recurring._delete(recurringId);
      break;
    default:
      break;
  }
});
