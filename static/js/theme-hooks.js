/* ══════════════════════════════════════════════════════════════════════
   theme-hooks.js — Puramente visual.
   Observa cambios en el DOM ya generado por la app y marca <body> con
   data-ledger-type según la cuenta activa en el Libro Mayor, para que
   el tema pueda tintar el título por tipo (ACTIVO / PASIVO / …).

   NO modifica lógica de negocio, endpoints, eventos ni estado global.
   ══════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var body = document.body;

  function updateLedgerType() {
    try {
      var sel = document.querySelector('select[data-report-change="ledger-account"]');
      if (!sel) {
        // Si el select ya no está en el DOM, limpiamos para no mantener tinte viejo.
        body.removeAttribute('data-ledger-type');
        return;
      }
      var accId = parseInt(sel.value, 10);
      if (!Number.isFinite(accId)) {
        body.removeAttribute('data-ledger-type');
        return;
      }
      // window.State.accounts existe en app.js; lo usamos en modo lectura.
      var State = window.State;
      var acc = (State && Array.isArray(State.accounts))
        ? State.accounts.find(function (a) { return a.id === accId; })
        : null;
      if (acc && (acc.type_id != null)) {
        body.setAttribute('data-ledger-type', String(acc.type_id));
      } else {
        body.removeAttribute('data-ledger-type');
      }
    } catch (_err) {
      body.removeAttribute('data-ledger-type');
    }
  }

  // Observa cualquier cambio en #main (donde la app renderiza vistas)
  // y reacciona a cambios del <select> del Mayor.
  var main = document.getElementById('main');
  if (main && 'MutationObserver' in window) {
    var obs = new MutationObserver(function () {
      updateLedgerType();
    });
    obs.observe(main, { childList: true, subtree: true });
  }

  // Cuando el usuario cambia la cuenta en el selector del Mayor.
  document.addEventListener('change', function (ev) {
    var t = ev.target;
    if (t && t.matches && t.matches('select[data-report-change="ledger-account"]')) {
      // Dejamos que el handler de la app actualice el DOM, y luego re-leemos.
      setTimeout(updateLedgerType, 0);
    }
  }, true);

  // Primera ejecución al cargar.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', updateLedgerType);
  } else {
    updateLedgerType();
  }
})();
