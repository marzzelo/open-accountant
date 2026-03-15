/* ── forms.js — Modales con Tailwind ── */
'use strict';

/* ── Helpers de HTML reutilizables ── */
const T = {
  modalShell: (title, body, footer) => `
    <div class="flex items-center justify-between px-5 pt-5 pb-3 border-b border-dark-600">
      <span class="text-base font-bold text-dark-100">${title}</span>
      <button onclick="Modal.close()" class="text-dark-400 hover:text-dark-300 text-xl cursor-pointer border-0 bg-transparent">✕</button>
    </div>
    <div class="p-5">${body}</div>
    <div class="flex gap-2 justify-end px-5 pb-5 pt-3 border-t border-dark-600 flex-wrap">
      ${footer}
    </div>`,

  input: (id, opts = {}) => `
    <input id="${id}"
           class="w-full bg-dark-700 border border-dark-600 rounded-lg text-dark-300
                  text-sm px-3 py-2.5 font-sans outline-none
                  focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30
                  ${opts.cls || ''}"
           ${opts.type ? `type="${opts.type}"` : ''}
           ${opts.step ? `step="${opts.step}"` : ''}
           ${opts.min  ? `min="${opts.min}"` : ''}
           ${opts.ph   ? `placeholder="${opts.ph}"` : ''}
           ${opts.val  ? `value="${opts.val}"` : ''}
           ${opts.auto ? 'autofocus' : ''}
           ${opts.inputmode ? `inputmode="${opts.inputmode}"` : ''}>`,

  select: (id, opts, extra = '') => `
    <select id="${id}" ${extra}
            class="w-full bg-dark-700 border border-dark-600 rounded-lg text-dark-300
                   text-sm px-3 py-2.5 font-sans outline-none
                   focus:border-blue-500 cursor-pointer">
      ${opts}
    </select>`,

  label: txt => `<label class="block text-xs text-dark-400 mb-1.5">${txt}</label>`,
  group: (label, inner) => `<div class="mb-4">${T.label(label)}${inner}</div>`,
  row2:  (...cols) => `<div class="grid grid-cols-1 sm:grid-cols-${cols.length} gap-3 mb-4">
                         ${cols.map(c => `<div>${c}</div>`).join('')}
                       </div>`,

  btn: (label, cls, action) =>
    `<button onclick="${action}"
             class="px-5 py-2 rounded-lg text-sm font-medium font-sans cursor-pointer
                    transition-all border ${cls}">${label}</button>`,
  btnGhost:   (label, action) => T.btn(label, 'border-dark-600 text-dark-400 hover:text-dark-300 hover:bg-dark-700 bg-transparent', action),
  btnPrimary: (label, action) => T.btn(label, 'bg-blue-600 hover:bg-blue-500 text-white border-blue-600', action),
  btnSuccess: (label, action) => T.btn(label, 'bg-emerald-700 hover:bg-emerald-600 text-white border-emerald-700', action),
  btnDanger:  (label, action) => T.btn(label, 'bg-red-900/30 hover:bg-red-900/50 text-pasivo border-pasivo/30', action),
};

const Forms = {

  /* ── Nueva cuenta ─────────────────────────────────────────────── */
  newAccount() {
    const typeOpts = State.types.map(t =>
      `<option value="${t.id}">${t.name}</option>`).join('');
    Modal.open(T.modalShell(t('form.new_account'), `
      ${T.group(`${t('form.label.name')} *`, T.input('f-name', { ph: 'Ej: Banco Galicia', auto: true }))}
      ${T.row2(
        T.label(`${t('form.label.type')} *`) + T.select('f-type', `<option value="">${t('form.select_placeholder')}</option>` + typeOpts, 'onchange="Forms._loadSubtypes()"'),
        T.label(t('form.label.subtype'))  + T.select('f-subtype', `<option value="">${t('form.select_type')}</option>`)
      )}
      ${T.group(t('form.label.initial_bal'), T.input('f-initial', { type: 'number', step: '0.01', val: '0' }))}
      ${T.group(t('form.label.description'), T.input('f-desc', { ph: 'Opcional' }))}
    `, T.btnGhost('Cancelar', 'Modal.close()') + T.btnSuccess('Crear cuenta', 'Forms._saveAccount()')));
  },

  /* ── Editar cuenta ────────────────────────────────────────────── */
  async editAccount(accId) {
    const acc  = State.accounts.find(a => a.id === accId);
    if (!acc) return;
    const subs = State.subtypes.filter(s => s.type_id === acc.type_id);
    const subOpts = `<option value="">${t('form.no_subtype')}</option>` +
      subs.map(s => `<option value="${s.id}" ${s.id === acc.subtype_id ? 'selected' : ''}>${s.name}</option>`).join('');

    Modal.open(T.modalShell(`✏️ Editar — ${acc.name}`, `
      ${T.group(t('form.label.name'), T.input('f-name', { val: acc.name }))}
      ${T.row2(
        T.label(t('form.label.type')) + `<input value="${acc.type_name}" disabled
                 class="w-full bg-dark-700/50 border border-dark-600 rounded-lg text-dark-500
                        text-sm px-3 py-2.5 cursor-not-allowed">`,
        T.label('Subtipo') + T.select('f-subtype', subOpts)
      )}
      ${T.group(t('form.label.description'), T.input('f-desc', { val: acc.description || '' }))}
    `, T.btnGhost('Cancelar', 'Modal.close()') + T.btnPrimary('Guardar', `Forms._updateAccount(${accId})`)));
  },

  /* ── Saldo inicial ────────────────────────────────────────────── */
  async initialBalance(accId) {
    const acc = State.accounts.find(a => a.id === accId);
    if (!acc) return;
    Modal.open(T.modalShell(`💰 ${t('form.initial_balance')} — ${acc.name}`, `
      <p class="text-dark-400 text-sm mb-4">
        El saldo inicial es el punto de partida antes de registrar transacciones.
      </p>
      ${T.group(t('form.label.initial_bal'), T.input('f-initial', {
        type: 'number', step: '0.01', val: acc.initial_balance,
        cls: '!text-2xl !font-bold !text-center !text-ingreso !tracking-tight'
      }))}
    `, T.btnGhost('Cancelar', 'Modal.close()') + T.btnPrimary('Guardar', `Forms._saveInitialBalance(${accId})`)));
  },

  /* ── Eliminar cuenta ──────────────────────────────────────────── */
  deleteAccount(accId) {
    const acc = State.accounts.find(a => a.id === accId);
    if (!acc) return;
    Modal.open(T.modalShell('<span class="text-pasivo">🗑 Eliminar Cuenta</span>', `
      <p class="text-sm mb-2">¿Eliminar la cuenta <strong class="text-dark-100">${acc.name}</strong>?</p>
      <p class="text-dark-400 text-xs">Solo se puede eliminar si no tiene transacciones registradas.</p>
    `, T.btnGhost('Cancelar', 'Modal.close()') + T.btnDanger('Eliminar', `Forms._deleteAccount(${accId})`)));
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
          <div class="text-[10px] text-dark-400 uppercase tracking-wide mb-1">Origen (acreditada)</div>
          <div class="text-sm font-semibold text-dark-100 truncate">${credit.name}</div>
          <div class="text-[11px] text-dark-400">${credit.type_name}</div>
        </div>
        <div class="text-2xl text-gasto shrink-0">→</div>
        <div class="flex-1 text-center min-w-0">
          <div class="text-[10px] text-dark-400 uppercase tracking-wide mb-1">Destino (debitada)</div>
          <div class="text-sm font-semibold text-dark-100 truncate">${debit.name}</div>
          <div class="text-[11px] text-dark-400">${debit.type_name}</div>
        </div>
      </div>
      ${T.group(`${t('form.label.amount')} *`, T.input('f-amount', {
        type: 'number', step: '0.01', min: '0.01', ph: '0.00', auto: true,
        inputmode: 'decimal',
        cls: '!text-[22px] !font-bold !text-center !text-ingreso !tracking-tight'
      }))}
      ${T.group(t('form.label.description'), T.input('f-desc', { ph: 'Opcional', val: description }))}
      ${T.group(t('form.label.date'), T.input('f-date', { type: 'datetime-local', val: now }))}
    `, T.btnGhost('Cancelar', 'Modal.close()') +
       T.btnSuccess(t('btn.register'), `Forms._saveTransaction(${creditId},${debitId})`)));

    setTimeout(() => { const i = document.getElementById('f-amount'); i?.focus(); i?.select(); }, 80);
  },

  /* ── FAB: transacción manual (mobile) ────────────────────────── */
  newTransactionFAB() {
    const opts = State.accounts.map(a =>
      `<option value="${a.id}">${a.name} (${a.type_name})</option>`).join('');
    const now = localNow();

    Modal.open(T.modalShell('💸 Nueva Transacción', `
      ${T.group(`${t('form.label.amount')} *`, T.input('f-amount', {
        type: 'number', step: '0.01', min: '0.01', ph: '0.00', auto: true,
        inputmode: 'decimal',
        cls: '!text-[22px] !font-bold !text-center !text-ingreso !tracking-tight'
      }))}
      ${T.group(t('form.label.credit'), T.select('f-credit', opts))}
      ${T.group(t('form.label.debit'),  T.select('f-debit',  opts))}
      ${T.group(t('form.label.description'), T.input('f-desc', { ph: 'Opcional' }))}
      ${T.group(t('form.label.date'), T.input('f-date', { type: 'datetime-local', val: now }))}
    `, T.btnGhost('Cancelar', 'Modal.close()') +
       T.btnSuccess(t('btn.register'), 'Forms._saveTransactionFAB()')));
  },

  /* ── Gestión de subtipos ──────────────────────────────────────── */
  async subtypeModal() {
    const typeOpts = State.types.map(t => `<option value="${t.id}">${t.name}</option>`).join('');
    const rows = State.subtypes.map(s => `
      <tr class="border-b border-dark-600/60 hover:bg-dark-700/50">
        <td class="px-4 py-3 text-sm text-dark-400 w-[28%]">${s.type_name}</td>
        <td class="px-4 py-3 text-sm text-dark-100">${s.name}</td>
        <td class="px-4 py-3 text-right whitespace-nowrap w-[120px]">
          <button onclick="Forms._editSubtype(${s.id})"
                  class="inline-flex items-center gap-1 text-xs px-3 py-1.5 border border-dark-600
                         rounded-md text-dark-400 hover:text-dark-100 hover:bg-dark-600
                         bg-transparent cursor-pointer font-sans mr-2">
            ✏️ Editar
          </button>
          <button onclick="Forms._deleteSubtype(${s.id})"
                  class="inline-flex items-center gap-1 text-xs px-3 py-1.5 border border-red-900/40
                         rounded-md text-red-400/70 hover:text-red-400 hover:bg-red-900/20
                         bg-transparent cursor-pointer font-sans">
            🗑 Borrar
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
        <p class="text-xs text-dark-400 mb-3 font-semibold uppercase tracking-wide">＋ Agregar subtipo</p>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          ${T.select('new-st-type', typeOpts)}
          ${T.input('new-st-name', { ph: t('form.placeholder.name'), auto: true })}
        </div>
      </div>
    `, T.btnGhost('Cerrar', 'Modal.close()') + T.btnSuccess('＋ Agregar', 'Forms._addSubtype()')), { wide: true });
  },

  /* ── Editar transacción (desde txlist) ───────────────────────── */
  editTransaction(tx) {
    const dtLocal = tx.date.replace(' ', 'T').slice(0, 16);
    Modal.open(T.modalShell(`✏️ Transacción #${tx.id}`, `
      <div class="flex items-center gap-3 bg-dark-700 rounded-xl p-3 mb-5">
        <div class="flex-1 text-center"><div class="text-xs text-dark-400 mb-1">Acreditada</div>
          <div class="text-sm font-semibold text-dark-100">${tx.credit_name}</div></div>
        <div class="text-2xl text-gasto">→</div>
        <div class="flex-1 text-center"><div class="text-xs text-dark-400 mb-1">Debitada</div>
          <div class="text-sm font-semibold text-dark-100">${tx.debit_name}</div></div>
      </div>
      ${T.group(t('form.label.amount'), T.input('f-amount', {
        type: 'number', step: '0.01', val: tx.amount,
        cls: '!text-[22px] !font-bold !text-center !text-ingreso !tracking-tight'
      }))}
      ${T.group(t('form.label.description'), T.input('f-desc', { val: tx.description || '' }))}
      ${T.group(t('form.label.date'), T.input('f-date', { type: 'datetime-local', val: dtLocal }))}
    `, T.btnGhost('Cancelar', 'Modal.close()') + T.btnPrimary('Guardar', `Forms._updateTransaction(${tx.id})`)));
  },

  /* ── Helpers privados ─────────────────────────────────────────── */
  _loadSubtypes(typeId) {
    const sel = document.getElementById('f-subtype');
    if (!sel) return;
    const tid  = typeId || document.getElementById('f-type')?.value;
    const subs = State.subtypes.filter(s => s.type_id == tid);
    sel.innerHTML = `<option value="">${t('form.no_subtype')}</option>` +
      subs.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
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
    const amount = parseFloat(document.getElementById('f-amount')?.value);
    const desc   = document.getElementById('f-desc')?.value || '';
    const date   = document.getElementById('f-date')?.value?.replace('T', ' ');
    if (!amount || amount <= 0) return Toast.show(t('msg.invalid_amount'), 'err');
    try {
      await API.post('/transactions', { debit_account: debitId, credit_account: creditId, amount, description: desc, date });
      State.recordUsage(creditId); State.recordUsage(debitId);
      Modal.close(); Toast.show(t('msg.tx_registered', {amount: fmt(amount)})); await View.refresh();
    } catch (e) { Toast.show(e.message, 'err'); }
  },

  async _saveTransactionFAB() {
    const amount   = parseFloat(document.getElementById('f-amount')?.value);
    const creditId = parseInt(document.getElementById('f-credit')?.value);
    const debitId  = parseInt(document.getElementById('f-debit')?.value);
    const desc     = document.getElementById('f-desc')?.value || '';
    const date     = document.getElementById('f-date')?.value?.replace('T', ' ');
    if (!amount || amount <= 0)  return Toast.show('Ingrese un monto válido', 'err');
    if (creditId === debitId)    return Toast.show(t('msg.same_account'), 'err');
    try {
      await API.post('/transactions', { debit_account: debitId, credit_account: creditId, amount, description: desc, date });
      State.recordUsage(creditId); State.recordUsage(debitId);
      Modal.close(); Toast.show(`Registrada: ${fmt(amount)}`); await View.refresh();
    } catch (e) { Toast.show(e.message, 'err'); }
  },

  async _updateTransaction(txId) {
    const amount = parseFloat(document.getElementById('f-amount')?.value);
    const desc   = document.getElementById('f-desc')?.value;
    const date   = document.getElementById('f-date')?.value?.replace('T', ' ');
    try {
      await API.put(`/transactions/${txId}`, { amount, description: desc, date });
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
    const name = prompt('Nuevo nombre:', st.name);
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
    if (!st || !confirm(`¿Eliminar "${st.name}"?`)) return;
    try {
      await API.del(`/subtypes/${stId}`);
      State.subtypes = await API.get('/subtypes');
      Toast.show(t('msg.subtype_deleted'));
      await this.subtypeModal();
    } catch (e) { Toast.show(e.message, 'err'); }
  },
};
