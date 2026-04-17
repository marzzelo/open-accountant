/* ── core/ui.js — Shared HTML templates for modal UIs ── */
'use strict';

const UiTemplates = {
  modalShell: (title, body, footer) => `
    <div class="flex items-center justify-between px-5 pt-5 pb-3 border-b border-dark-600">
      <span data-modal-title class="text-base font-bold text-dark-100">${title}</span>
      <button type="button" data-modal-close aria-label="${escapeHtml(t('dialog.close'))}" class="text-dark-400 hover:text-dark-300 text-xl cursor-pointer border-0 bg-transparent">X</button>
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
  group: (label, inner) => `<div class="mb-4">${UiTemplates.label(label)}${inner}</div>`,
  row2: (...cols) => `<div class="grid grid-cols-1 sm:grid-cols-${cols.length} gap-3 mb-4">
                         ${cols.map(col => `<div>${col}</div>`).join('')}
                       </div>`,

  btn: (label, cls, attrs = {}) =>
    `<button ${htmlAttrs({
      type: 'button',
      class: `px-5 py-2 rounded-lg text-sm font-medium font-sans cursor-pointer transition-all border ${cls}`,
      ...attrs,
    })}>${label}</button>`,
  btnGhost: (label, attrs) => UiTemplates.btn(label, 'border-dark-600 text-dark-400 hover:text-dark-300 hover:bg-dark-700 bg-transparent', attrs),
  btnPrimary: (label, attrs) => UiTemplates.btn(label, 'bg-blue-600 hover:bg-blue-500 text-white border-blue-600', attrs),
  btnSuccess: (label, attrs) => UiTemplates.btn(label, 'bg-emerald-700 hover:bg-emerald-600 text-white border-emerald-700', attrs),
  btnDanger: (label, attrs) => UiTemplates.btn(label, 'bg-red-900/30 hover:bg-red-900/50 text-pasivo border-pasivo/30', attrs),
};

window.UI = { T: UiTemplates };