Genera el procedimiento contable de compactación de saldos históricos de ejercicios anteriores mediante cierre y reapertura. Supón que ya existen las cuentas "Resultado del ejercicio" y "Resultados acumulados".

Debes:

1. Respaldar primero todos los registros actuales de la tabla de transacciones mediante una descarga o exportación completa en formato SQL, de modo que sea posible reconstruir íntegramente la base original en caso de error.

2. Trabajar sobre el ejercicio anterior completo, identificando todas las transacciones comprendidas en ese período contable.

3. Generar el asiento de cierre de ingresos, debitando todas las cuentas de ingresos contra "Resultado del ejercicio".

4. Generar el asiento de cierre de gastos, acreditando todas las cuentas de gastos contra "Resultado del ejercicio".

5. Calcular el saldo final de "Resultado del ejercicio".

6. Transferir ese saldo a "Resultados acumulados":
   - si hay ganancia: debitar "Resultado del ejercicio" y acreditar "Resultados acumulados"
   - si hay pérdida: debitar "Resultados acumulados" y acreditar "Resultado del ejercicio"

7. Determinar los saldos finales de todas las cuentas patrimoniales al cierre del ejercicio, incluyendo:
   - activos
   - pasivos
   - patrimonio neto

8. Generar los asientos de apertura del nuevo ejercicio incluyendo solo cuentas patrimoniales:
   - activos
   - pasivos
   - patrimonio neto

9. No incluir cuentas de ingresos ni gastos en la apertura.

10. Mantener una línea por cada cuenta patrimonial analítica en los asientos de apertura, es decir, usar la opción menos compacta dentro de las alternativas de compactación.

11. Verificar que cada asiento nuevo esté balanceado individualmente y que en todos los nuevos registros insertados se cumpla estrictamente la igualdad entre debe y haber.

12. Verificar además que la suma total de débitos y créditos de los asientos de apertura coincida exactamente con los saldos finales patrimoniales calculados a partir del ejercicio anterior.

13. Una vez validado el respaldo y verificada la consistencia contable de los nuevos asientos:
   - eliminar de la tabla de transacciones todas las transacciones correspondientes al ejercicio anterior,
   - conservar únicamente los registros de apertura necesarios para iniciar el nuevo ejercicio con los saldos correctos.

14. Confirmar que, después de la eliminación y reinserción, la tabla de transacciones conserve exclusivamente:
   - los asientos de apertura vigentes,
   - y cualquier transacción posterior al inicio del nuevo ejercicio que no deba compactarse.

15. Presentar la salida en forma de procedimiento ordenado, indicando:
   - respaldo previo,
   - cierre contable,
   - transferencia del resultado,
   - cálculo de saldos patrimoniales,
   - generación de asientos de apertura,
   - validaciones de integridad contable,
   - eliminación de transacciones históricas,
   - estado final esperado de la tabla.

16. Incluir advertencias explícitas:
   - no ejecutar eliminaciones sin respaldo SQL completo verificado,
   - no eliminar transacciones si existe cualquier diferencia entre debe y haber,
   - no conservar cuentas de resultado dentro de los asientos de apertura,
   - preservar la trazabilidad suficiente para futura auditoría o restauración desde el respaldo.

Usa nombres genéricos de tipos de cuentas, salvo "Resultado del ejercicio" y "Resultados acumulados". No uses nombres particulares de cuentas específicas. El procedimiento debe estar redactado de forma que pueda ser utilizado como guía para implementar el proceso en una base de datos contable.

17. Antes de eliminar los registros históricos, generar y mostrar una previsualización de los asientos de apertura resultantes y un resumen de control con:
   - total de activos,
   - total de pasivos,
   - total de patrimonio neto,
   - total debe,
   - total haber,
   - diferencia final esperada igual a cero.