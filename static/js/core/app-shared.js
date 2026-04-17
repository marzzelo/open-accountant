const API_BASE = `${window.location.origin}/api`;
const BOARD_VIEW_MODES = new Set(['cards', 'compact']);

export const BOARD_VIEW_MODE_DEFAULT = 'cards';
export const BOARD_IMAGE_DEFAULT_URL = '/images/account-tile-default.svg';
export const BOARD_IMAGE_MIME_TYPES = ['image/png', 'image/webp'];
export const BOARD_IMAGE_NORMALIZED_SIZE = 200;

export function buildApiUrl(path = '') {
  const normalizedPath = String(path || '').replace(/^\/+/, '');
  return new URL(normalizedPath, `${API_BASE}/`).toString();
}

export function localNow() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

export function fmt(value) {
  if (value == null) return '$ 0.00';
  const amount = Number(value) || 0;
  const formatted = Math.abs(amount).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${amount < 0 ? '-$' : '$'} ${formatted}`;
}

export function fmtSigned(value) {
  if (value == null) return '$ 0.00';
  return `${(Number(value) || 0) < 0 ? '-' : '+'}$ ${Math.abs(Number(value) || 0).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function invalidParsedMoney(reason = 'invalid') {
  return {
    isEmpty: false,
    isValid: false,
    value: Number.NaN,
    normalized: '',
    reason,
  };
}

function countChar(value, char) {
  return (String(value || '').match(new RegExp(`\\${char}`, 'g')) || []).length;
}

function isValidThousandsInteger(value, separator) {
  if (!/^\d+(?:[.,]\d+)*$/.test(value)) return false;
  if (!value.includes(separator)) return /^\d+$/.test(value);

  const groups = value.split(separator);
  if (!/^\d{1,3}$/.test(groups[0])) return false;
  return groups.slice(1).every(group => /^\d{3}$/.test(group));
}

function parseMoneyLiteral(rawValue, { maxFractionDigits = 2 } = {}) {
  const trimmedValue = String(rawValue ?? '').trim();
  if (!trimmedValue) {
    return {
      isEmpty: true,
      isValid: false,
      value: Number.NaN,
      normalized: '',
      reason: 'empty',
    };
  }

  const compactValue = trimmedValue.replace(/\s+/g, '');
  if (!/^[+-]?\d[\d.,]*$/.test(compactValue)) return invalidParsedMoney('invalid_chars');

  const sign = /^[+-]/.test(compactValue) ? compactValue[0] : '';
  const unsignedValue = sign ? compactValue.slice(1) : compactValue;
  const commaCount = countChar(unsignedValue, ',');
  const dotCount = countChar(unsignedValue, '.');

  if (!commaCount && !dotCount) {
    return {
      isEmpty: false,
      isValid: true,
      value: Number(sign + unsignedValue),
      normalized: sign + unsignedValue,
      reason: null,
    };
  }

  if (commaCount && dotCount) {
    const decimalSeparator = unsignedValue.lastIndexOf(',') > unsignedValue.lastIndexOf('.') ? ',' : '.';
    const groupSeparator = decimalSeparator === ',' ? '.' : ',';
    const decimalIndex = unsignedValue.lastIndexOf(decimalSeparator);
    const integerPart = unsignedValue.slice(0, decimalIndex);
    const decimalPart = unsignedValue.slice(decimalIndex + 1);

    if (!integerPart || integerPart.includes(decimalSeparator)) return invalidParsedMoney('ambiguous');
    if (!new RegExp(`^\\d{1,${maxFractionDigits}}$`).test(decimalPart)) return invalidParsedMoney('ambiguous');
    if (!isValidThousandsInteger(integerPart, groupSeparator)) return invalidParsedMoney('ambiguous');

    const normalized = `${sign}${integerPart.split(groupSeparator).join('')}.${decimalPart}`;
    return {
      isEmpty: false,
      isValid: true,
      value: Number(normalized),
      normalized,
      reason: null,
    };
  }

  const separator = commaCount ? ',' : '.';
  const separatorCount = commaCount || dotCount;

  if (separatorCount === 1) {
    const [integerPart, decimalPart] = unsignedValue.split(separator);
    if (!integerPart || !decimalPart || !/^\d+$/.test(integerPart) || !/^\d+$/.test(decimalPart)) {
      return invalidParsedMoney('invalid');
    }
    if (decimalPart.length >= 1 && decimalPart.length <= maxFractionDigits) {
      const normalized = `${sign}${integerPart}.${decimalPart}`;
      return {
        isEmpty: false,
        isValid: true,
        value: Number(normalized),
        normalized,
        reason: null,
      };
    }
    return invalidParsedMoney(decimalPart.length === 3 && maxFractionDigits < 3 ? 'ambiguous' : 'invalid');
  }

  if (!isValidThousandsInteger(unsignedValue, separator)) return invalidParsedMoney('ambiguous');

  const normalized = sign + unsignedValue.split(separator).join('');
  return {
    isEmpty: false,
    isValid: true,
    value: Number(normalized),
    normalized,
    reason: null,
  };
}

function normalizeMoneyExpression(rawValue, { maxFractionDigits = 2 } = {}) {
  const expression = String(rawValue ?? '');
  if (!/^[\d\s.,+\-*/%()]+$/.test(expression)) return invalidParsedMoney('invalid_expression');

  const tokenPattern = /(?<![\d.,])[-+]?(?:\d[\d.,\s]*\d|\d)(?![\d.,])/g;
  let sawToken = false;
  let invalidReason = '';

  const normalized = expression.replace(tokenPattern, token => {
    sawToken = true;
    const parsed = parseMoneyLiteral(token, { maxFractionDigits });
    if (!parsed.isValid) {
      invalidReason = parsed.reason || 'invalid_expression';
      return '__INVALID_MONEY_TOKEN__';
    }
    return parsed.normalized;
  });

  if (!sawToken || invalidReason || normalized.includes('__INVALID_MONEY_TOKEN__')) {
    return invalidParsedMoney(invalidReason || 'invalid_expression');
  }
  if (!/^[\d\s.+\-*/%()]+$/.test(normalized)) return invalidParsedMoney('invalid_expression');

  return {
    isEmpty: false,
    isValid: true,
    value: Number.NaN,
    normalized,
    reason: null,
  };
}

export function parseMoneyInput(rawValue, { allowExpression = false, maxFractionDigits = 2 } = {}) {
  const parsedLiteral = parseMoneyLiteral(rawValue, { maxFractionDigits });
  if (parsedLiteral.isEmpty || parsedLiteral.isValid || !allowExpression) return parsedLiteral;

  const normalizedExpression = normalizeMoneyExpression(rawValue, { maxFractionDigits });
  if (!normalizedExpression.isValid) return normalizedExpression;

  try {
    const evaluated = Function(`"use strict"; return (${normalizedExpression.normalized});`)();
    if (!Number.isFinite(evaluated)) return invalidParsedMoney('invalid_expression');
    return {
      isEmpty: false,
      isValid: true,
      value: evaluated,
      normalized: normalizedExpression.normalized,
      reason: null,
    };
  } catch (_) {
    return invalidParsedMoney('invalid_expression');
  }
}

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[char]));
}

export function htmlAttrs(attrs = {}) {
  return Object.entries(attrs)
    .filter(([, value]) => value !== false && value != null)
    .map(([key, value]) => value === true ? key : `${key}="${escapeHtml(value)}"`)
    .join(' ');
}

export function normalizeBoardViewMode(mode) {
  return BOARD_VIEW_MODES.has(mode) ? mode : BOARD_VIEW_MODE_DEFAULT;
}

export function accountBoardImageUrl(source) {
  const properties = source?.properties && typeof source.properties === 'object'
    ? source.properties
    : source && typeof source === 'object'
      ? source
      : {};
  const candidate = typeof properties.board_image_url === 'string'
    ? properties.board_image_url.trim()
    : '';
  return candidate || BOARD_IMAGE_DEFAULT_URL;
}

export function hasCustomBoardImageUrl(source) {
  return accountBoardImageUrl(source).startsWith('data:image/');
}

export function formatApiError(payload, fallback = 'Unknown error') {
  if (payload == null) return fallback;
  if (typeof payload === 'string') return payload;

  if (Array.isArray(payload)) {
    const parts = payload
      .map(item => formatApiError(item, ''))
      .filter(Boolean);
    return parts.join(' | ') || fallback;
  }

  if (typeof payload === 'object') {
    if (typeof payload.detail === 'string') return payload.detail;
    if (payload.detail != null) return formatApiError(payload.detail, fallback);
    if (typeof payload.message === 'string') return payload.message;

    if (typeof payload.msg === 'string') {
      const location = Array.isArray(payload.loc) ? payload.loc.join('.') : '';
      return location ? `${location}: ${payload.msg}` : payload.msg;
    }

    const values = Object.values(payload)
      .map(value => formatApiError(value, ''))
      .filter(Boolean);
    return values.join(' | ') || fallback;
  }

  return String(payload);
}

export function normalizeTagColor(color) {
  return /^#[0-9a-f]{6}$/i.test(String(color || '')) ? String(color) : '#3B82F6';
}

export function renderTagBadge(tag, extraClass = '') {
  const color = normalizeTagColor(tag?.color);
  return `
    <span class="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${extraClass}" style="border-color:${color}55;background:${color}1A;color:${color}">
      <span class="h-1.5 w-1.5 rounded-full" style="background:${color}"></span>
      <span>${escapeHtml(tag?.name || '')}</span>
    </span>`;
}