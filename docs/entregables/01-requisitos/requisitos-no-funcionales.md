# Requisitos no funcionales (RNF)

Fuente original: `docs/proposta_banco_distribuido_simples.pdf`, sección 9. Se
agrega la columna **Métrica objetivo**, separada del criterio de aceptación,
porque un criterio ("el total nunca cambia") no siempre dice *cuánto* se mide
ni *cómo*. El **Estado** de cada uno se sigue en
[`../08-pruebas-y-despliegue/matriz-trazabilidad-completa.md`](../08-pruebas-y-despliegue/matriz-trazabilidad-completa.md).

| ID | Requisito | Métrica objetivo | Criterio de aceptación |
|---|---|---|---|
| RNF-01 | Corretude bajo fallas | 0 discrepancias en la suma de saldos, tras miles de operaciones sorteadas | El total de dinero nunca cambia, en ningún test |
| RNF-02 | Durabilidad | 100% de las operaciones confirmadas sobreviven a un `SIGKILL` del primario | Operación confirmada sobrevive a la caída del primario |
| RNF-03 | Disponibilidad (failover) | Tiempo de failover medido < 2 s | Nuevo primario asume en pocos segundos tras la falla |
| RNF-04 | Desempeño | ≥ 500 transacciones por segundo en ambiente local (meta de medición, no bloqueante — ver `docs/SPECS.md` §11.3) | Se reporta el número real medido, cumpla o no la meta |
| RNF-05 | Latencia | p99 < 200 ms | Transferencia con p99 bajo 200 ms sin fallas activas — no aplica a `TRANSFERENCIA_EXTERNA` (RF-25), cuya duración depende del sistema externo simulado, no del clúster |
| RNF-06 | Pruebas reproducibles | Misma semilla ⇒ mismo resultado en el 100% de las ejecuciones | Semilla de ejecución fija produce el mismo resultado |
| RNF-07 | Observabilidad | 100% de los eventos clave (voto, elección, réplica, falla) en log estructurado | Log estructurado en todos los servidores |
| RNF-08 | Modularidad | 100% de los módulos con código, prueba y documentación propios | Cada componente documentado según `CODESTYLE.md` |
| RNF-09 | Portabilidad | Arranque con un solo comando, 0 pasos manuales adicionales | Ejecución en Linux y macOS con un único comando — **en revisión**: con PostgreSQL como motor (ADR-0002), esto ahora incluye tener el servidor de base de datos accesible, ya no es "sin dependencias" puro |
| RNF-10 | Documentación | 100% de los componentes con sus modos de falla documentados | Cada componente documenta su funcionamiento y sus fallas |
| RNF-11 | Disponibilidad (mínima) | El sistema responde mientras ≥ 1 de 2-3 nodos esté activo | Sigue respondiendo con al menos un servidor activo |
