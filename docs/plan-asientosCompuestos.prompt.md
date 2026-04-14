# Plan: Asientos compuestos — Reestructuración cabecera + líneas

Actualmente cada transacción es una sola fila con **un débito, un crédito y un importe**. Para permitir asientos compuestos (N cuentas al debe / M cuentas al haber), hay que separar la tabla en **cabecera + líneas** y adaptar backend, frontend y tests.

## Steps

1. **Crear nuevas tablas `journal_entries` y `journal_lines`** en `database.py`: la cabecera guarda `id`, `description`, `date`, `created_at`; cada línea guarda `entry_id`, `account_id`, `debit_amount`, `credit_amount` y los campos FX (`original_amount`, `original_currency`, `fx_rate`, `fx_source`), con un `CHECK` que impida que una línea tenga importe en ambas columnas a la vez. La tabla `transaction_tags` apuntará a `journal_entries` en vez de `transactions`.

2. **Actualizar modelos Pydantic** en `models.py`: crear `JournalEntryIn` (con lista de `JournalLineIn`) y `JournalEntryOut` (con lista de `JournalLineOut`). Opcionalmente conservar `TransactionIn`/`TransactionOut` como atajos de conveniencia que internamente se traduzcan a un asiento de 2 líneas.

3. **Reescribir el servicio de transacciones** en `services/transactions_service.py`: el CRUD debe insertar/actualizar la cabecera y sus líneas en una sola transacción DB, validando que `SUM(debit_amount) == SUM(credit_amount)` antes del commit. La resolución FX (`_resolve_fx`) se aplicará por línea.

4. **Adaptar las consultas de balance y reportes** en `services/accounts_service.py`, `services/reports_service.py` y `services/helpers.py`: reemplazar las consultas que discriminan por `debit_account`/`credit_account` por consultas sobre `journal_lines` filtrando por `account_id` y sumando `debit_amount`/`credit_amount`. El campo `counterpart` en `MovementOut` pasará a ser `"Varios"` cuando el asiento tenga más de 2 líneas.

5. **Adaptar router y frontend**: en `routers/transactions.py` exponer un endpoint nuevo `POST /journal-entries` (y mantener `POST /transactions` como wrapper de conveniencia). En `static/js/forms.js` añadir un formulario de "asiento compuesto" con líneas dinámicas (agregar/quitar filas, cada una con cuenta + debe/haber + moneda), preservando el flujo drag-and-drop actual para asientos simples. Actualizar `static/js/board.js` (`CommonTx`, visualización de contrapartida) y `static/js/reports.js` (diario y mayor).

6. **Escribir script de migración** en `scripts/migrate_transactions_to_journal.py`: crear las nuevas tablas, trasladar cada fila de `transactions` a una cabecera + 2 líneas, reasignar `transaction_tags`, verificar `SUM(debit) == SUM(credit)` por asiento, y eliminar la tabla antigua solo tras validación. La migración es **sin pérdida**: el `id` original de la transacción se conserva como `entry_id`.

## Further Considerations

1. **FX por línea vs. por asiento**: ¿Cada línea puede tener una moneda/tipo de cambio distinto (mayor flexibilidad, más complejidad) o el FX sigue siendo único por asiento? Recomiendo **FX por línea** dado que ya hay soporte multi-moneda y un asiento compuesto podría mezclar cuentas en distintas divisas.
2. **Endpoint de conveniencia**: ¿Mantener `POST /transactions` como alias que crea un asiento simple de 2 líneas para no romper el flujo drag-and-drop? Recomiendo **sí**, para minimizar cambios en el frontend existente.
3. **Proyecciones y seed**: `services/projections_service.py` consume saldos agregados y no necesita cambios estructurales; `scripts/seed_demo.py` y los tests (`tests/test_services_unit.py`) sí deberán adaptarse al nuevo modelo — ¿priorizar la migración del seed y los tests junto con el paso 6?
