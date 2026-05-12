/* ── forms.js — Modales con Tailwind ── */
'use strict';

const { T } = window.UI;

const Forms = {
  _accountPropertiesDraft: {},
  _accountEditorTypeId: null,

  _sortedTags() {
    return [...(State.tags || [])].sort((left, right) => String(left.name || '').localeCompare(String(right.name || '')));
  },

  _selectedTagIds() {
    return [...document.querySelectorAll('input[name="f-tag-ids"]:checked')].map(input => Number(input.value));
  },

  _tagSelectionField(selectedIds = []) {
    const selected = new Set((selectedIds || []).map(Number));
    const tags = this._sortedTags();

    if (!tags.length) {
      return `
        <div class="mb-4 rounded-xl border border-dashed border-dark-600 bg-dark-800/50 px-3 py-3 text-xs text-dark-400">
          ${escapeHtml(t('form.tags_empty'))}
        </div>`;
    }

    return `
      <div class="mb-4 rounded-xl border border-dark-600 bg-dark-800/60 px-3 py-3">
        <div class="mb-3">
          <div>
            <div class="text-[11px] font-semibold uppercase tracking-wide text-dark-400">${escapeHtml(t('form.label.tags'))}</div>
            <div class="text-[11px] text-dark-500 mt-1">${escapeHtml(t('form.tags_help'))}</div>
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-44 overflow-y-auto pr-1">
          ${tags.map(tag => `
            <label class="flex items-center gap-2 rounded-lg border border-dark-600 bg-dark-700/50 px-3 py-2 cursor-pointer">
              <input type="checkbox" name="f-tag-ids" value="${tag.id}" ${selected.has(Number(tag.id)) ? 'checked' : ''}
                class="h-4 w-4 rounded border-dark-500 bg-dark-800 text-blue-500 focus:ring-blue-500/40 cursor-pointer">
              <span class="h-2.5 w-2.5 rounded-full shrink-0" style="background:${normalizeTagColor(tag.color)}"></span>
              <span class="text-sm text-dark-200 truncate">${escapeHtml(tag.name)}</span>
            </label>`).join('')}
        </div>
      </div>`;
  },

  tagModal() {
    const rows = this._sortedTags().map(tag => `
      <tr class="border-b border-dark-600/60 hover:bg-dark-700/50">
        <td class="px-4 py-3">
          <div class="flex items-center gap-2">${renderTagBadge(tag)}</div>
        </td>
        <td class="px-4 py-3 text-sm text-dark-400">${tag.transaction_count || 0}</td>
        <td class="px-4 py-3 text-right whitespace-nowrap w-[120px]">
          <button ${htmlAttrs({
            type: 'button',
            'data-form-action': 'edit-tag',
            'data-tag-id': tag.id,
            class: 'inline-flex items-center justify-center text-base w-9 h-9 border border-dark-600 rounded-md text-dark-400 hover:text-dark-100 hover:bg-dark-600 bg-transparent cursor-pointer font-sans mr-2',
            title: t('btn.edit'),
            'aria-label': t('btn.edit'),
          })}>✏️</button>
          <button ${htmlAttrs({
            type: 'button',
            'data-form-action': 'delete-tag',
            'data-tag-id': tag.id,
            class: 'inline-flex items-center justify-center text-base w-9 h-9 border border-red-900/40 rounded-md text-red-400/70 hover:text-red-400 hover:bg-red-900/20 bg-transparent cursor-pointer font-sans',
            title: t('btn.delete'),
            'aria-label': t('btn.delete'),
          })}>🗑️</button>
        </td>
      </tr>`).join('');

    Modal.open(T.modalShell(`🎯 ${t('tag.title')}`, `
      <div class="overflow-x-auto rounded-xl border border-dark-600 mb-6">
        <table class="w-full text-sm" style="min-width:540px">
          <thead class="bg-dark-700">
            <tr>
              <th class="px-4 py-3 text-left text-xs text-blue-400 font-semibold uppercase tracking-wide">${t('form.label.tags')}</th>
              <th class="px-4 py-3 text-left text-xs text-blue-400 font-semibold uppercase tracking-wide">${t('tag.transactions')}</th>
              <th class="px-4 py-3 w-[120px]"></th>
            </tr>
          </thead>
          <tbody>
            ${rows || `<tr><td colspan='3' class='text-center py-8 text-dark-500 text-xs'>${t('tag.empty')}</td></tr>`}
          </tbody>
        </table>
      </div>

      <div class="bg-dark-700/50 rounded-xl p-4 border border-dark-600/60">
        <div class="flex items-center justify-between gap-2 mb-3">
          <p class="text-xs text-dark-400 font-semibold uppercase tracking-wide">${t('tag.add_title')}</p>
          <button type="button" data-form-action="show-add-tag" class="text-xs px-3 py-1.5 rounded-lg border border-dark-600 text-dark-300 hover:bg-dark-700 cursor-pointer">${t('btn.add')}</button>
        </div>
        <p class="text-xs text-dark-500">${escapeHtml(t('tag.help'))}</p>
      </div>
    `, T.btnGhost(t('btn.close'), { 'data-modal-close': true })), { wide: true });
  },

  _tagEditor(tag = null) {
    const isEdit = !!tag;
    const title = isEdit ? t('tag.edit_title') : t('tag.create_title');
    const submitAction = isEdit ? 'update-tag' : 'create-tag';

    Modal.open(T.modalShell(`🎯 ${title}`, `
      ${T.group(t('form.label.name'), T.input('f-tag-name', { val: tag?.name || '', ph: t('tag.name_placeholder'), auto: true }))}
      <div class="mb-4">
        ${T.label(t('tag.color'))}
        <div class="flex items-center gap-3">
          <input id="f-tag-color" type="color" value="${escapeHtml(normalizeTagColor(tag?.color))}" class="h-11 w-16 bg-transparent border border-dark-600 rounded-lg cursor-pointer">
          <div class="text-xs text-dark-400">${escapeHtml(t('tag.color_help'))}</div>
        </div>
      </div>
    `, T.btnGhost(t('btn.cancel'), { 'data-form-action': 'back-to-tags' })
      + T.btnSuccess(isEdit ? t('btn.save') : t('btn.create'), {
        'data-form-action': submitAction,
        'data-tag-id': tag?.id,
      })));
  },

  async _createTag() {
    const name = document.getElementById('f-tag-name')?.value.trim();
    const color = document.getElementById('f-tag-color')?.value || '#3B82F6';
    if (!name) return Toast.show(t('msg.enter_name'), 'err');

    try {
      await API.post('/tags', { name, color });
      await API.reloadTags();
      Toast.show(t('msg.tag_created', { name }));
      this.tagModal();
    } catch (e) {
      Toast.show(e.message, 'err');
    }
  },

  async _updateTag(tagId) {
    const name = document.getElementById('f-tag-name')?.value.trim();
    const color = document.getElementById('f-tag-color')?.value || '#3B82F6';
    if (!name) return Toast.show(t('msg.enter_name'), 'err');

    try {
      await API.put(`/tags/${tagId}`, { name, color });
      await API.reloadTags();
      Toast.show(t('msg.tag_updated'));
      this.tagModal();
    } catch (e) {
      Toast.show(e.message, 'err');
    }
  },

  async _deleteTag(tagId) {
    const tag = State.tags.find(item => Number(item.id) === Number(tagId));
    if (!tag) return;

    const confirmed = await Dialog.confirm({
      title: t('btn.delete'),
      message: t('msg.confirm_delete', { name: tag.name }),
      confirmLabel: t('btn.delete'),
      cancelLabel: t('btn.cancel'),
      submitTone: 'danger',
    });
    if (!confirmed) return;

    try {
      await API.del(`/tags/${tagId}`);
      await API.reloadTags();
      Toast.show(t('msg.tag_deleted'));
      this.tagModal();
    } catch (e) {
      Toast.show(e.message, 'err');
    }
  },

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

  _selectedFxRateState() {
    return parseMoneyInput(document.getElementById('f-fx-rate')?.value, { maxFractionDigits: 4 });
  },

  _selectedFxRate() {
    const rateState = this._selectedFxRateState();
    return rateState.isValid && rateState.value > 0 ? rateState.value : null;
  },

  _hasInvalidManualFxRate() {
    const rateState = this._selectedFxRateState();
    return !rateState.isEmpty && (!rateState.isValid || !Number.isFinite(rateState.value) || rateState.value <= 0);
  },

  _isDebitNormal(typeId) {
    return typeId === 1 || typeId === 4;
  },

  _balanceDeltaSign(typeId, role) {
    if (role === 'debit') return this._isDebitNormal(typeId) ? 1 : -1;
    return this._isDebitNormal(typeId) ? -1 : 1;
  },

  _currentBalanceNote(account) {
    if (!account) return '';
    return t('form.force_balance_current', {
      amount: fmt(account.balance),
    });
  },

  _forceBalanceLabel(account) {
    return t('form.force_account_balance', { name: account?.name || '' });
  },

  _roundMoney(value) {
    return Math.round((Number(value) || 0) * 100) / 100;
  },

  _copyAccountProperties(properties = {}) {
    try {
      return JSON.parse(JSON.stringify(properties && typeof properties === 'object' ? properties : {}));
    } catch (_) {
      return {};
    }
  },

  _resetAccountEditorState(properties = {}, typeId = null) {
    this._accountPropertiesDraft = this._copyAccountProperties(properties);
    const numericTypeId = Number.parseInt(typeId ?? '', 10);
    this._accountEditorTypeId = Number.isNaN(numericTypeId) ? null : numericTypeId;
  },

  _accountEditorProperties() {
    return this._copyAccountProperties(this._accountPropertiesDraft);
  },

  _setAccountEditorProperties(properties = {}) {
    this._accountPropertiesDraft = this._copyAccountProperties(properties);
  },

  _currentAccountEditorTypeId(typeId = null) {
    const selectedTypeId = Number.parseInt(document.getElementById('f-type')?.value || '', 10);
    if (!Number.isNaN(selectedTypeId)) {
      this._accountEditorTypeId = selectedTypeId;
      return selectedTypeId;
    }

    const explicitTypeId = Number.parseInt(typeId ?? '', 10);
    if (!Number.isNaN(explicitTypeId)) {
      this._accountEditorTypeId = explicitTypeId;
      return explicitTypeId;
    }

    return this._accountEditorTypeId;
  },

  _accountImageField(properties = {}) {
    const imageUrl = accountBoardImageUrl(properties);
    const customImage = hasCustomBoardImageUrl(properties);

    return `
      <div class="mb-4 rounded-xl border border-dark-600 bg-dark-800/70 px-3 py-3">
        <div class="text-[11px] font-semibold uppercase tracking-wide text-dark-400 mb-2">${escapeHtml(t('form.account_image.title'))}</div>
        <div class="text-xs text-dark-400 mb-3">${escapeHtml(t('form.account_image.help'))}</div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 items-start">
          <div class="account-image-preview-panel">
            <div class="account-image-preview-stage transparent-preview-bg">
              <img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(t('form.account_image.preview_alt'))}" class="account-image-preview-media" draggable="false">
            </div>
          </div>
          <div class="min-w-0 space-y-3">
            <div class="text-[11px] text-dark-500">${escapeHtml(t(customImage ? 'form.account_image.custom_active' : 'form.account_image.default_active'))}</div>
            <input id="f-account-image-file" type="file" accept="image/png,image/webp" data-form-change="account-image-file"
                   class="block w-full rounded-lg border border-dark-600 bg-dark-700/60 px-3 py-2.5 text-xs text-dark-300 cursor-pointer">
            <div class="text-[11px] leading-relaxed text-dark-500">${escapeHtml(t('form.account_image.spec'))}</div>
            ${customImage
              ? `<button type="button" data-form-action="clear-account-image"
                   class="inline-flex items-center rounded-lg border border-dark-600 px-3 py-2 text-xs font-medium text-dark-300 hover:bg-dark-700 cursor-pointer bg-transparent">${escapeHtml(t('form.account_image.reset'))}</button>`
              : ''}
          </div>
        </div>
      </div>`;
  },

  _readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error(t('msg.account_image_read_error')));
      reader.readAsDataURL(file);
    });
  },

  _loadImageFromDataUrl(dataUrl) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error(t('msg.account_image_processing_error')));
      image.src = dataUrl;
    });
  },

  async _normalizeAccountImageFile(file) {
    if (!file) return null;
    if (!BOARD_IMAGE_MIME_TYPES.includes(file.type)) {
      throw new Error(t('msg.account_image_invalid_type'));
    }

    const sourceDataUrl = await this._readFileAsDataUrl(file);
    const image = await this._loadImageFromDataUrl(sourceDataUrl);
    const canvas = document.createElement('canvas');
    const size = BOARD_IMAGE_NORMALIZED_SIZE;
    canvas.width = size;
    canvas.height = size;

    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error(t('msg.account_image_processing_error'));

    const drawScale = Math.min(size / image.naturalWidth, size / image.naturalHeight);
    const drawWidth = Math.max(1, Math.round(image.naturalWidth * drawScale));
    const drawHeight = Math.max(1, Math.round(image.naturalHeight * drawScale));
    const offsetX = Math.round((size - drawWidth) / 2);
    const offsetY = Math.round((size - drawHeight) / 2);

    ctx.clearRect(0, 0, size, size);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(image, offsetX, offsetY, drawWidth, drawHeight);
    return canvas.toDataURL('image/png');
  },

  async _handleAccountImageSelection(file) {
    if (!file) return;

    try {
      const normalizedImageUrl = await this._normalizeAccountImageFile(file);
      const nextProperties = this._accountEditorProperties();
      nextProperties.board_image_url = normalizedImageUrl;
      this._setAccountEditorProperties(nextProperties);
      this._renderAccountPropertiesFields(this._currentAccountEditorTypeId(), nextProperties);
    } catch (error) {
      const input = document.getElementById('f-account-image-file');
      if (input) input.value = '';
      Toast.show(error.message || t('msg.account_image_processing_error'), 'err');
    }
  },

  _clearAccountImage() {
    const nextProperties = this._accountEditorProperties();
    delete nextProperties.board_image_url;
    this._setAccountEditorProperties(nextProperties);
    this._renderAccountPropertiesFields(this._currentAccountEditorTypeId(), nextProperties);
  },

  _accountPropertyOptions(typeId, selected = {}) {
    if (typeId === 1) {
      return {
        id: 'f-liquidity-profile',
        label: t('form.classification.asset_liquidity'),
        value: selected.liquidity_profile || '',
        options: [
          { value: '', label: t('form.classification.auto') },
          { value: 'quick', label: t('form.classification.asset_quick') },
          { value: 'current', label: t('form.classification.asset_current') },
          { value: 'non_current', label: t('form.classification.asset_non_current') },
          { value: 'fixed', label: t('form.classification.asset_fixed') },
        ],
      };
    }
    if (typeId === 2) {
      return {
        id: 'f-liability-term',
        label: t('form.classification.liability_term'),
        value: selected.liability_term || '',
        options: [
          { value: '', label: t('form.classification.auto') },
          { value: 'current', label: t('form.classification.liability_current') },
          { value: 'long_term', label: t('form.classification.liability_long_term') },
        ],
      };
    }
    if (typeId === 4) {
      return {
        id: 'f-expense-profile',
        label: t('form.classification.expense_profile'),
        value: selected.expense_profile || '',
        options: [
          { value: '', label: t('form.classification.auto') },
          { value: 'essential', label: t('form.classification.expense_essential') },
          { value: 'discretionary', label: t('form.classification.expense_discretionary') },
        ],
      };
    }
    return null;
  },

  _accountPropertiesFields(typeId, properties = {}) {
    const imageField = this._accountImageField(properties);
    const definition = this._accountPropertyOptions(typeId, properties);
    if (!definition) return imageField;

    const options = definition.options.map(option =>
      `<option value="${option.value}" ${option.value === definition.value ? 'selected' : ''}>${escapeHtml(option.label)}</option>`
    ).join('');

    return `
      ${imageField}
      <div class="mb-4 rounded-xl border border-dark-600 bg-dark-800/70 px-3 py-3">
        <div class="text-[11px] font-semibold uppercase tracking-wide text-dark-400 mb-2">${escapeHtml(t('form.classification.title'))}</div>
        <div class="text-xs text-dark-400 mb-3">${escapeHtml(t('form.classification.help'))}</div>
        ${T.group(definition.label, T.select(definition.id, options))}
      </div>`;
  },

  _renderAccountPropertiesFields(typeId, properties = null) {
    const container = document.getElementById('f-account-properties');
    if (!container) return;
    const resolvedTypeId = this._currentAccountEditorTypeId(typeId);
    if (properties && typeof properties === 'object') this._setAccountEditorProperties(properties);
    container.innerHTML = this._accountPropertiesFields(resolvedTypeId, this._accountEditorProperties());
  },

  _readAccountProperties(typeId) {
    const numericTypeId = Number(typeId);
    const properties = this._accountEditorProperties();

    delete properties.liquidity_profile;
    delete properties.liability_term;
    delete properties.expense_profile;

    if (numericTypeId === 1) {
      const liquidity = document.getElementById('f-liquidity-profile')?.value || '';
      if (liquidity) properties.liquidity_profile = liquidity;
    } else if (numericTypeId === 2) {
      const liabilityTerm = document.getElementById('f-liability-term')?.value || '';
      if (liabilityTerm) properties.liability_term = liabilityTerm;
    } else if (numericTypeId === 4) {
      const expenseProfile = document.getElementById('f-expense-profile')?.value || '';
      if (expenseProfile) properties.expense_profile = expenseProfile;
    }

    if (properties.board_image_url === BOARD_IMAGE_DEFAULT_URL || !properties.board_image_url) {
      delete properties.board_image_url;
    }

    this._setAccountEditorProperties(properties);

    return JSON.stringify(properties);
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
    const rateState = this._selectedFxRateState();
    if (!rateState.isEmpty) {
      return rateState.isValid ? rateState.value : Number.NaN;
    }
    return this._getCurrencyRate(currency);
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

  _forceBalanceAccounts({ creditId = null, debitId = null } = {}) {
    const fallbackIds = this._previewAccountIds();
    const resolvedCreditId = creditId ?? fallbackIds.creditId;
    const resolvedDebitId = debitId ?? fallbackIds.debitId;
    const creditAccount = State.accounts.find(account => account.id === resolvedCreditId) || null;
    const debitAccount = State.accounts.find(account => account.id === resolvedDebitId) || null;

    return {
      creditId: resolvedCreditId,
      debitId: resolvedDebitId,
      creditAccount,
      debitAccount,
    };
  },

  _forcedBalanceComputation(rawAmount, { creditId = null, debitId = null, rate = null } = {}) {
    const forceMode = this._selectedForceBalanceMode();
    if (!forceMode || forceMode === 'invalid') return null;

    const { creditAccount, debitAccount } = this._forceBalanceAccounts({ creditId, debitId });
    const targetAccount = forceMode === 'credit' ? creditAccount : debitAccount;
    const otherAccount = forceMode === 'credit' ? debitAccount : creditAccount;
    if (!targetAccount || !otherAccount) return null;

    const currency = this._selectedAmountCurrency();
    const targetBalance = currency === 'ARS'
      ? this._roundMoney(rawAmount)
      : this._roundMoney(rawAmount * rate);
    const currentTargetBalance = this._roundMoney(targetAccount.balance);
    const bookedAmount = this._roundMoney(
      (targetBalance - currentTargetBalance) / this._balanceDeltaSign(targetAccount.type_id, forceMode)
    );
    const otherRole = forceMode === 'credit' ? 'debit' : 'credit';
    const otherFinalBalance = this._roundMoney(
      this._roundMoney(otherAccount.balance)
      + bookedAmount * this._balanceDeltaSign(otherAccount.type_id, otherRole)
    );

    return {
      targetAccount,
      otherAccount,
      targetBalance,
      otherFinalBalance,
      bookedAmount,
      originalAmount: currency === 'ARS' || !Number.isFinite(rate) || rate <= 0
        ? bookedAmount
        : this._roundMoney(bookedAmount / rate),
    };
  },

  _effectiveAmountPreviewState({ creditId = null, debitId = null } = {}) {
    const preview = {
      tone: 'muted',
      text: t('form.effective_amount_placeholder'),
    };
    const amountState = this._transactionAmountState();
    const rawAmount = amountState.value;
    const forceMode = this._selectedForceBalanceMode();
    const currency = this._selectedAmountCurrency();
    const meta = this._transactionCurrencyMeta(currency);
    const rate = this._previewTransactionRate();

    if (forceMode === 'invalid') {
      return { tone: 'err', text: t('msg.force_balance_single_option') };
    }

    if (!amountState.isEmpty && !amountState.isValid) {
      return { tone: 'err', text: t('msg.invalid_amount') };
    }

    if (currency !== 'ARS' && this._hasInvalidManualFxRate()) {
      return { tone: 'err', text: t('msg.invalid_money_input') };
    }

    if (!forceMode && (amountState.isEmpty || !Number.isFinite(rawAmount) || rawAmount <= 0)) return preview;
    if (forceMode && (amountState.isEmpty || !Number.isFinite(rawAmount))) return preview;

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

    const computation = this._forcedBalanceComputation(rawAmount, { creditId, debitId, rate });
    if (!computation) return preview;

    const {
      targetAccount,
      otherAccount,
      targetBalance,
      otherFinalBalance,
      bookedAmount,
      originalAmount,
    } = computation;

    if (Math.abs(bookedAmount) < 0.005) {
      return { tone: 'muted', text: t('msg.force_balance_no_change') };
    }

    if (!Number.isFinite(bookedAmount) || bookedAmount < 0) {
      return { tone: 'err', text: t('msg.force_balance_conflict') };
    }

    const lines = [
      currency === 'ARS'
        ? t('form.effective_amount_preview_forced_amount_line', { amount: fmt(bookedAmount) })
        : t('form.effective_amount_preview_forced_amount_line_fx', {
          amount: fmt(bookedAmount),
          original: this._currencyAmountLabel(meta.originalCurrency, originalAmount),
        }),
      t('form.effective_amount_preview_forced_balance_line', {
        name: targetAccount.name,
        amount: fmt(targetBalance),
      }),
      t('form.effective_amount_preview_forced_balance_line', {
        name: otherAccount.name,
        amount: fmt(otherFinalBalance),
      }),
    ];

    return {
      tone: 'ok',
      text: lines.join('\n'),
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
    body.className = 'text-sm whitespace-pre-line';

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
              <div id="f-force-credit-balance-label" class="text-sm font-semibold text-dark-100">${escapeHtml(this._forceBalanceLabel(opts.creditAccount))}</div>
              <div id="f-force-credit-balance-note" class="mt-1 text-[11px] text-dark-500">${escapeHtml(this._currentBalanceNote(opts.creditAccount))}</div>
            </div>
          </label>
          <label class="flex items-start gap-3 rounded-lg border border-dark-600/70 bg-dark-700/40 px-3 py-3 cursor-pointer">
            <input id="f-force-debit-balance" type="checkbox" data-form-change="toggle-force-balance" data-target="debit"
              class="mt-0.5 h-4 w-4 rounded border-dark-500 bg-dark-800 text-blue-500 focus:ring-blue-500/40 cursor-pointer">
            <div class="min-w-0">
              <div id="f-force-debit-balance-label" class="text-sm font-semibold text-dark-100">${escapeHtml(this._forceBalanceLabel(opts.debitAccount))}</div>
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
    const creditLabel = document.getElementById('f-force-credit-balance-label');
    const debitLabel = document.getElementById('f-force-debit-balance-label');
    const creditNote = document.getElementById('f-force-credit-balance-note');
    const debitNote = document.getElementById('f-force-debit-balance-note');

    if (creditNote) creditNote.textContent = this._currentBalanceNote(creditAccount);
    if (debitNote) debitNote.textContent = this._currentBalanceNote(debitAccount);
    if (creditLabel) creditLabel.textContent = this._forceBalanceLabel(creditAccount);
    if (debitLabel) debitLabel.textContent = this._forceBalanceLabel(debitAccount);
    this._syncTransactionAmountConstraints();
    this._refreshTransactionEffectiveAmountNote({ creditId: resolvedCreditId, debitId: resolvedDebitId });
  },

  _syncTransactionAmountConstraints() {
    const amountInput = document.getElementById('f-amount');
    if (!amountInput) return;

    if (this._selectedForceBalanceMode()) {
      amountInput.removeAttribute('min');
      return;
    }

    amountInput.setAttribute('min', '0');
  },

  _evaluateTransactionAmount(rawValue) {
    const parsedAmount = parseMoneyInput(rawValue, { allowExpression: true });
    if (parsedAmount.isEmpty) return { isEmpty: true, isValid: false, value: Number.NaN };
    if (!parsedAmount.isValid) return { isEmpty: false, isValid: false, value: Number.NaN };

    return {
      isEmpty: false,
      isValid: true,
      value: this._roundMoney(parsedAmount.value),
    };
  },

  _transactionAmountState() {
    return this._evaluateTransactionAmount(document.getElementById('f-amount')?.value);
  },

  _transactionInputAmount() {
    return this._transactionAmountState().value;
  },

  async _selectedTransactionRate() {
    const currency = this._selectedAmountCurrency();
    if (currency === 'ARS') return 1;
    const rateState = this._selectedFxRateState();
    if (!rateState.isEmpty) {
      return rateState.isValid && rateState.value > 0 ? rateState.value : null;
    }
    return await this._resolveCurrencyRate(currency);
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
            type: 'text',
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
          type: 'text', step: '0.01', min: opts.min ?? '0.01', ph: t('form.placeholder.amount'), auto: opts.auto !== false,
        val: opts.value,
        inputmode: 'text',
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
    const note = document.getElementById('f-amount-currency-note');
    if (!note) return;
    if (currency !== 'ARS' && this._hasInvalidManualFxRate()) {
      note.textContent = t('msg.invalid_money_input');
      return;
    }
    const rate = this._selectedFxRate() || await this._resolveCurrencyRate(currency);
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

  async _resolveTransactionEntryAmount(rawAmount, { creditId, debitId, silent = false }) {
    const amountState = this._transactionAmountState();
    const forceMode = this._selectedForceBalanceMode();

    if (forceMode === 'invalid') {
      if (!silent) Toast.show(t('msg.force_balance_single_option'), 'err');
      return null;
    }

    if (!amountState.isEmpty && !amountState.isValid) {
      if (!silent) Toast.show(t('msg.invalid_amount'), 'err');
      return null;
    }

    if (this._selectedAmountCurrency() !== 'ARS' && this._hasInvalidManualFxRate()) {
      if (!silent) Toast.show(t('msg.invalid_money_input'), 'err');
      return null;
    }

    if (!forceMode) {
      if (!Number.isFinite(rawAmount) || rawAmount <= 0) {
        if (!silent) Toast.show(t('msg.invalid_amount'), 'err');
        return null;
      }
      return rawAmount;
    }

    if (!Number.isFinite(rawAmount)) {
      if (!silent) Toast.show(t('msg.invalid_amount'), 'err');
      return null;
    }

    const rate = await this._selectedTransactionRate();
    if (this._selectedAmountCurrency() !== 'ARS' && !(Number.isFinite(rate) && rate > 0)) {
      if (!silent) Toast.show(this._missingCurrencyRateMessage(this._selectedAmountCurrency()), 'err');
      return null;
    }

    const computation = this._forcedBalanceComputation(rawAmount, { creditId, debitId, rate });
    if (!computation) {
      if (!silent) Toast.show(t('msg.invalid_value'), 'err');
      return null;
    }

    const { bookedAmount, originalAmount } = computation;

    if (!Number.isFinite(bookedAmount)) {
      if (!silent) Toast.show(t('msg.invalid_amount'), 'err');
      return null;
    }
    if (Math.abs(bookedAmount) < 0.005) {
      if (!silent) Toast.show(t('msg.force_balance_no_change'), 'err');
      return null;
    }
    if (bookedAmount < 0) {
      if (!silent) Toast.show(t('msg.force_balance_conflict'), 'err');
      return null;
    }
    if (this._selectedAmountCurrency() === 'ARS') return bookedAmount;

    return originalAmount;
  },

  async _buildTransactionPayload(rawAmount, { silent = false } = {}) {
    const currency = this._selectedAmountCurrency();
    const meta = this._transactionCurrencyMeta(currency);
    const manualRate = this._selectedFxRate();

    if (meta.originalCurrency !== 'ARS' && this._hasInvalidManualFxRate()) {
      if (!silent) Toast.show(t('msg.invalid_money_input'), 'err');
      return null;
    }

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
      if (!silent) Toast.show(this._missingCurrencyRateMessage(currency), 'err');
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

  _recurringButtonContext() {
    const button = document.getElementById('f-make-recurring-btn');
    if (!button) return null;
    return {
      mode: button.dataset.recurringMode || '',
      creditId: Number.parseInt(button.dataset.creditId || '', 10),
      debitId: Number.parseInt(button.dataset.debitId || '', 10),
      txId: Number.parseInt(button.dataset.txId || '', 10),
    };
  },

  _transactionAlertDayPreset() {
    const dateValue = document.getElementById('f-date')?.value || '';
    const match = dateValue.match(/^\d{4}-\d{2}-(\d{2})/);
    if (match) {
      const day = Number.parseInt(match[1], 10);
      if (Number.isInteger(day) && day >= 1 && day <= 31) return day;
    }
    return new Date().getDate();
  },

  async _buildRecurringPayloadFromCurrentForm({ silent = false } = {}) {
    const context = this._recurringButtonContext();
    if (!context) return null;

    const rawAmount = this._transactionInputAmount();
    const desc = document.getElementById('f-desc')?.value || '';
    let creditId = context.creditId;
    let debitId = context.debitId;

    if (context.mode === 'fab' || context.mode === 'edit') {
      creditId = Number.parseInt(document.getElementById('f-credit')?.value || '', 10);
      debitId = Number.parseInt(document.getElementById('f-debit')?.value || '', 10);
    }

    if (!Number.isInteger(creditId) || !Number.isInteger(debitId)) {
      if (!silent) Toast.show(t('msg.invalid_value'), 'err');
      return null;
    }
    if (creditId === debitId) {
      if (!silent) Toast.show(t('msg.same_account'), 'err');
      return null;
    }

    const entryAmount = await this._resolveTransactionEntryAmount(rawAmount, {
      creditId,
      debitId,
      silent,
    });
    if (entryAmount == null) return null;

    const txPayload = await this._buildTransactionPayload(entryAmount, { silent });
    if (!txPayload) return null;

    return {
      credit_account: creditId,
      debit_account: debitId,
      tag_ids: this._selectedTagIds(),
      description: desc,
      alert_active: true,
      enabled: true,
      ...txPayload,
    };
  },

  async _syncRecurringButtonState() {
    const button = document.getElementById('f-make-recurring-btn');
    if (!button) return;
    const payload = await this._buildRecurringPayloadFromCurrentForm({ silent: true });
    button.disabled = !payload;
  },

  async _makeRecurringFromTransactionForm() {
    const payload = await this._buildRecurringPayloadFromCurrentForm();
    if (!payload) return;

    const presetDay = this._transactionAlertDayPreset();
    const alertDayInput = window.prompt(
      t('recurring.make_from_transaction_alert_prompt'),
      String(presetDay)
    );
    if (alertDayInput == null) return;

    const alertDay = Number.parseInt(String(alertDayInput).trim(), 10);
    if (!Number.isInteger(alertDay) || alertDay < 1 || alertDay > 31) {
      Toast.show(t('recurring.invalid_alert_day'), 'err');
      return;
    }

    try {
      const similar = await API.get(`/recurring-transactions/find-similar?credit_account=${encodeURIComponent(payload.credit_account)}&debit_account=${encodeURIComponent(payload.debit_account)}&description=${encodeURIComponent(payload.description)}`);
      const recurringPayload = { ...payload, alert_day: alertDay };

      if (similar?.id) {
        const overwrite = window.confirm(
          t('recurring.make_from_transaction_duplicate', { id: similar.id })
        );
        if (!overwrite) return;
        await API.put(`/recurring-transactions/${similar.id}`, recurringPayload);
        Toast.show(t('recurring.make_from_transaction_overwritten'));
      } else {
        await API.post('/recurring-transactions', recurringPayload);
        Toast.show(t('recurring.make_from_transaction_created'));
      }

      await API.reloadRecurringActiveCount();
    } catch (e) {
      Toast.show(e.message, 'err');
    }
  },

  _focusTransactionAmount({ preserveRate = false } = {}) {
    const input = document.getElementById('f-amount');
    input?.focus();
    input?.select();
    this._syncTransactionFxUi(this._selectedAmountCurrency(), { preserveRate });
    this._syncTransactionAmountConstraints();
    this._primeAmountCurrencyHelp();
  },

  /* ── Nueva cuenta ─────────────────────────────────────────────── */
  newAccount() {
    this._resetAccountEditorState();
    const typeOpts = State.types.map(type =>
      `<option value="${type.id}">${escapeHtml(type.name)}</option>`).join('');
    Modal.open(T.modalShell(t('form.new_account'), `
      ${T.group(`${t('form.label.name')} *`, T.input('f-name', { ph: t('form.placeholder.name'), auto: true }))}
      ${T.row2(
        T.label(`${t('form.label.type')} *`) + T.select('f-type', `<option value="">${t('form.select_placeholder')}</option>` + typeOpts, { 'data-form-change': 'load-subtypes' }),
        T.label(t('form.label.subtype'))  + T.select('f-subtype', `<option value="">${t('form.select_type')}</option>`)
      )}
      ${T.group(t('form.label.initial_bal'), T.input('f-initial', { type: 'text', step: '0.01', val: '0', inputmode: 'decimal' }))}
      ${T.group(t('form.label.description'), T.input('f-desc', { ph: t('form.placeholder.desc') }))}
      <div id="f-account-properties"></div>
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true })
      + T.btnSuccess(t('btn.create'), { 'data-form-action': 'save-account' })));
    this._renderAccountPropertiesFields(document.getElementById('f-type')?.value, this._accountEditorProperties());
  },

  /* ── Editar cuenta ────────────────────────────────────────────── */
  async editAccount(accId) {
    const acc  = State.accounts.find(a => a.id === accId);
    if (!acc) return;
    this._resetAccountEditorState(acc.properties || {}, acc.type_id);
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
      <div id="f-account-properties">${this._accountPropertiesFields(acc.type_id, acc.properties || {})}</div>
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
        type: 'text', step: '0.01', val: acc.initial_balance, inputmode: 'decimal',
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

  _transactionAccountOptions(selectedId = null) {
    return State.accounts.map(account =>
      `<option value="${account.id}" ${selectedId != null && Number(account.id) === Number(selectedId) ? 'selected' : ''}>${escapeHtml(account.name)} (${escapeHtml(account.type_name)})</option>`
    ).join('');
  },

  _makeRecurringButtonAttrs(context = {}) {
    return {
      id: 'f-make-recurring-btn',
      'data-form-action': 'make-recurring-transaction',
      'data-recurring-mode': context.mode || '',
      'data-credit-id': context.creditId ?? '',
      'data-debit-id': context.debitId ?? '',
      'data-tx-id': context.txId ?? '',
      disabled: true,
    };
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
      ${this._tagSelectionField(preset.tag_ids || [])}
      ${T.group(t('form.label.date'), T.input('f-date', { type: 'datetime-local', val: now }))}
      ${this._forcedBalanceField({ creditAccount: credit, debitAccount: debit })}
      ${this._effectiveAmountPreviewField({ creditId, debitId })}
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true }) +
       T.btnGhost(t('btn.make_recurring'), this._makeRecurringButtonAttrs({
         mode: 'pair',
         creditId,
         debitId,
       })) +
       T.btnSuccess(t('btn.register'), { 'data-form-action': 'save-transaction', 'data-credit-id': creditId, 'data-debit-id': debitId })));

    setTimeout(() => {
      this._focusTransactionAmount();
      this._refreshForceBalanceNotes({ creditId, debitId });
      void this._syncRecurringButtonState();
    }, 80);
  },

  /* ── FAB: transacción manual (mobile) ────────────────────────── */
  newTransactionFAB() {
    const opts = this._transactionAccountOptions();
    const now = localNow();
    const [firstAccount] = State.accounts;

    Modal.open(T.modalShell(`💸 ${t('form.new_transaction')}`, `
      ${T.group(`${t('form.label.amount')} *`, this._transactionAmountField({ hideSpin: true, min: '0' }))}
      ${T.group(t('form.label.credit'), T.select('f-credit', opts, { 'data-form-change': 'refresh-force-balance' }))}
      ${T.group(t('form.label.debit'),  T.select('f-debit',  opts, { 'data-form-change': 'refresh-force-balance' }))}
      ${T.group(t('form.label.description'), T.input('f-desc', { ph: t('form.placeholder.desc_tx') }))}
      ${this._tagSelectionField()}
      ${T.group(t('form.label.date'), T.input('f-date', { type: 'datetime-local', val: now }))}
      ${this._forcedBalanceField({ creditAccount: firstAccount || null, debitAccount: firstAccount || null })}
      ${this._effectiveAmountPreviewField()}
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true }) +
       T.btnGhost(t('btn.make_recurring'), this._makeRecurringButtonAttrs({ mode: 'fab' })) +
       T.btnSuccess(t('btn.register'), { 'data-form-action': 'save-transaction-fab' })));

    setTimeout(() => {
      this._focusTransactionAmount();
      this._refreshForceBalanceNotes();
      void this._syncRecurringButtonState();
    }, 80);
  },

  /* ── Gestión de subtipos ──────────────────────────────────────── */
  async subtypeModal() {
    const typeOpts = State.types.map(type => `<option value="${type.id}">${escapeHtml(type.name)}</option>`).join('');
    const rows = State.subtypes.map(s => `
      <tr class="border-b border-dark-600/60 hover:bg-dark-700/50">
        <td class="px-4 py-3 text-sm text-dark-400 w-[28%]">${escapeHtml(s.type_name)}</td>
        <td class="px-4 py-3 text-sm text-dark-100">${escapeHtml(s.name)}</td>
        <td class="px-4 py-3 text-right whitespace-nowrap w-[88px]">
          <button ${htmlAttrs({
            type: 'button',
            'data-form-action': 'edit-subtype',
            'data-subtype-id': s.id,
            title: t('btn.edit'),
            'aria-label': t('btn.edit'),
            class: 'inline-flex items-center justify-center text-base w-9 h-9 border border-dark-600 rounded-md text-dark-400 hover:text-dark-100 hover:bg-dark-600 bg-transparent cursor-pointer font-sans mr-2',
          })}>✏️</button>
          <button ${htmlAttrs({
            type: 'button',
            'data-form-action': 'delete-subtype',
            'data-subtype-id': s.id,
            title: t('btn.delete'),
            'aria-label': t('btn.delete'),
            class: 'inline-flex items-center justify-center text-base w-9 h-9 border border-red-900/40 rounded-md text-red-400/70 hover:text-red-400 hover:bg-red-900/20 bg-transparent cursor-pointer font-sans',
          })}>🗑️</button>
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
    const selectedTagIds = (tx.tags || []).map(tag => Number(tag.id));
    const creditOptions = this._transactionAccountOptions(tx.credit_account);
    const debitOptions = this._transactionAccountOptions(tx.debit_account);
    Modal.open(T.modalShell(`${t('form.edit_transaction')} #${tx.id}`, `
      <div class="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] gap-3 items-end bg-dark-700 rounded-xl p-3 mb-5">
        <div>
          ${T.label(t('form.transaction.source'))}
          ${T.select('f-credit', creditOptions)}
        </div>
        <div class="flex items-center justify-center text-2xl text-gasto pb-2">→</div>
        <div>
          ${T.label(t('form.transaction.destination'))}
          ${T.select('f-debit', debitOptions)}
        </div>
      </div>
      ${T.group(t('form.label.amount'), this._transactionAmountField({
        value: tx.original_amount ?? tx.amount,
        currency: selectedCurrency,
        rate: tx.fx_rate,
      }))}
      ${this._transactionFxEditor({ currency: selectedCurrency, rate: tx.fx_rate })}
      ${T.group(t('form.label.description'), T.input('f-desc', { val: tx.description || '' }))}
      ${this._tagSelectionField(selectedTagIds)}
      ${T.group(t('form.label.date'), T.input('f-date', { type: 'datetime-local', val: dtLocal }))}
    `, T.btnGhost(t('btn.cancel'), { 'data-modal-close': true })
      + T.btnGhost(t('btn.make_recurring'), this._makeRecurringButtonAttrs({
        mode: 'edit',
        txId: tx.id,
      }))
      + T.btnPrimary(t('btn.save'), { 'data-form-action': 'update-transaction', 'data-tx-id': tx.id })));

    setTimeout(() => {
      this._bindEditTransactionFxInputs();
      this._focusTransactionAmount({ preserveRate: true });
      void this._syncRecurringButtonState();
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
    this._renderAccountPropertiesFields(tid);
  },

  async _saveAccount() {
    const name    = document.getElementById('f-name')?.value.trim();
    const typeId  = parseInt(document.getElementById('f-type')?.value);
    const subId   = document.getElementById('f-subtype')?.value;
    const initialState = parseMoneyInput(document.getElementById('f-initial')?.value);
    const initial = initialState.isEmpty ? 0 : this._roundMoney(initialState.value);
    const desc    = document.getElementById('f-desc')?.value || '';
    const properties = this._readAccountProperties(typeId);
    if (!name || !typeId) return Toast.show(t('msg.name_type_required'), 'err');
    if (!initialState.isEmpty && !initialState.isValid) return Toast.show(t('msg.invalid_money_input'), 'err');
    try {
      await API.post('/accounts', { name, type_id: typeId,
        subtype_id: subId ? parseInt(subId) : null, initial_balance: initial, description: desc, properties });
      this._resetAccountEditorState();
      Modal.close(); Toast.show(t('msg.account_created', {name})); await View.refresh();
    } catch (e) { Toast.show(e.message, 'err'); }
  },

  async _updateAccount(accId) {
    const acc = State.accounts.find(item => item.id === accId);
    const name  = document.getElementById('f-name')?.value.trim();
    const subId = document.getElementById('f-subtype')?.value;
    const desc  = document.getElementById('f-desc')?.value || '';
    const properties = this._readAccountProperties(acc?.type_id);
    try {
      await API.put(`/accounts/${accId}`, { name, subtype_id: subId ? parseInt(subId) : null, description: desc, properties });
      this._resetAccountEditorState();
      Modal.close(); Toast.show(t('msg.account_updated')); await View.refresh();
    } catch (e) { Toast.show(e.message, 'err'); }
  },

  async _saveInitialBalance(accId) {
    const initialState = parseMoneyInput(document.getElementById('f-initial')?.value);
    if (!initialState.isEmpty && !initialState.isValid) return Toast.show(t('msg.invalid_money_input'), 'err');
    const initial = initialState.isEmpty ? 0 : this._roundMoney(initialState.value);
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
    const tagIds = this._selectedTagIds();

    const entryAmount = await this._resolveTransactionEntryAmount(rawAmount, { creditId, debitId });
    if (entryAmount == null) return;

    const txPayload = await this._buildTransactionPayload(entryAmount);
    if (!txPayload) return;

    try {
      const created = await API.post('/transactions', {
        debit_account: debitId,
        credit_account: creditId,
        tag_ids: tagIds,
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
    const tagIds   = this._selectedTagIds();
    if (creditId === debitId)    return Toast.show(t('msg.same_account'), 'err');

    const entryAmount = await this._resolveTransactionEntryAmount(rawAmount, { creditId, debitId });
    if (entryAmount == null) return;

    const txPayload = await this._buildTransactionPayload(entryAmount);
    if (!txPayload) return;

    try {
      const created = await API.post('/transactions', {
        debit_account: debitId,
        credit_account: creditId,
        tag_ids: tagIds,
        description: desc,
        date,
        ...txPayload,
      });
      State.recordUsage(creditId); State.recordUsage(debitId);
      Modal.close(); Toast.show(t('msg.tx_registered', { amount: fmt(created.amount) })); await View.refresh();
    } catch (e) { Toast.show(e.message, 'err'); }
  },

  async _updateTransaction(txId) {
    const amountState = this._transactionAmountState();
    const rawAmount = amountState.value;
    const creditId = Number.parseInt(document.getElementById('f-credit')?.value || '', 10);
    const debitId = Number.parseInt(document.getElementById('f-debit')?.value || '', 10);
    const desc   = document.getElementById('f-desc')?.value;
    const date   = document.getElementById('f-date')?.value?.replace('T', ' ');
    const tagIds = this._selectedTagIds();
    if (!Number.isInteger(creditId) || !Number.isInteger(debitId)) return Toast.show(t('msg.invalid_value'), 'err');
    if (creditId === debitId) return Toast.show(t('msg.same_account'), 'err');
    if (!amountState.isValid || rawAmount <= 0) return Toast.show(t('msg.invalid_amount'), 'err');

    const txPayload = await this._buildTransactionPayload(rawAmount);
    if (!txPayload) return;

    try {
      await API.put(`/transactions/${txId}`, {
        debit_account: debitId,
        credit_account: creditId,
        description: desc,
        date,
        tag_ids: tagIds,
        ...txPayload,
      });
      State.recordUsage(creditId);
      State.recordUsage(debitId);
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

window.Forms = Forms;

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
    case 'clear-account-image':
      Forms._clearAccountImage();
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
    case 'make-recurring-transaction':
      Forms._makeRecurringFromTransactionForm();
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
    case 'open-tags-modal':
      Forms.tagModal();
      break;
    case 'show-add-tag':
      Forms._tagEditor();
      break;
    case 'back-to-tags':
      Forms.tagModal();
      break;
    case 'create-tag':
      Forms._createTag();
      break;
    case 'edit-tag': {
      const tag = State.tags.find(item => Number(item.id) === Number(action.dataset.tagId));
      if (tag) Forms._tagEditor(tag);
      break;
    }
    case 'update-tag':
      Forms._updateTag(Number(action.dataset.tagId));
      break;
    case 'delete-tag':
      Forms._deleteTag(Number(action.dataset.tagId));
      break;
    case 'update-transaction':
      Forms._updateTransaction(Number(action.dataset.txId));
      break;
    default:
      break;
  }

  void Forms._syncRecurringButtonState();
});

document.addEventListener('change', async event => {
  const target = event.target.closest('[data-form-change]');
  if (!target) return;

  const modalContent = document.getElementById('modal-content');
  if (modalContent && !modalContent.contains(target)) return;

  switch (target.dataset.formChange) {
    case 'load-subtypes':
      Forms._loadSubtypes(target.value);
      break;
    case 'account-image-file':
      await Forms._handleAccountImageSelection(target.files?.[0] || null);
      break;
    case 'toggle-force-balance':
      Forms._syncForceBalanceMode(target.dataset.target);
      Forms._refreshForceBalanceNotes();
      break;
    case 'refresh-force-balance':
      Forms._refreshForceBalanceNotes();
      break;
    default:
      break;
  }

  void Forms._syncRecurringButtonState();
});

document.addEventListener('input', event => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;

  const modalContent = document.getElementById('modal-content');
  if (modalContent && !modalContent.contains(target)) return;

  if (target.id === 'f-amount' || target.id === 'f-fx-rate') {
    if (target.id === 'f-fx-rate') {
      Forms._primeAmountCurrencyHelp();
    }
    Forms._refreshTransactionEffectiveAmountNote();
  }

  void Forms._syncRecurringButtonState();
});
