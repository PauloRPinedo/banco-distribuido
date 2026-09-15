# Casos de uso

Reemplaza el formato de historia de usuario del PDF original por casos de uso
formales — ver la discusión de por qué en `docs/revisao_e_recomendacoes.md`
(sección de metodología) y la nota de trazabilidad de cada CU. El diagrama de
casos de uso y la relación con cada actor están en
[`matriz-actor-caso-de-uso.md`](matriz-actor-caso-de-uso.md).

## Antes de los casos de uso

- [`actores.md`](actores.md) — quién interactúa con el sistema
- [`acciones-del-sistema.md`](acciones-del-sistema.md) — lista plana de todo lo que el sistema permite hacer
- [`matriz-actor-caso-de-uso.md`](matriz-actor-caso-de-uso.md) — diagrama de casos de uso + relación actor × CU
- [`matriz-caso-de-uso-vs-rf.md`](matriz-caso-de-uso-vs-rf.md) — trazabilidad CU × requisito funcional

## Casos de uso

| ID | Nombre | Actor | Pantalla |
|---|---|---|---|
| [CU-01](cu-01-crear-cuenta.md) | Crear cuenta | Cliente | [mockup](mockups/cu-01-crear-cuenta.html) |
| [CU-02](cu-02-consultar-saldo.md) | Consultar saldo | Cliente | [mockup](mockups/cu-02-consultar-saldo.html) |
| [CU-03](cu-03-depositar-y-retirar.md) | Depositar y retirar | Cliente | [mockup](mockups/cu-03-depositar-y-retirar.html) |
| [CU-04](cu-04-transferir-misma-moneda.md) | Transferir (misma moneda) | Cliente | [mockup](mockups/cu-04-transferir-misma-moneda.html) |
| [CU-05](cu-05-transferir-con-conversion.md) | Transferir con conversión de moneda | Cliente | [mockup](mockups/cu-05-transferir-con-conversion.html) |
| [CU-06](cu-06-autotransferencia.md) | Autotransferencia | Cliente | [mockup](mockups/cu-06-autotransferencia.html) |
| [CU-07](cu-07-consultar-extracto.md) | Consultar extracto | Cliente | [mockup](mockups/cu-07-consultar-extracto.html) |
| [CU-08](cu-08-auditar-total.md) | Auditar total en circulación | Administrador | [mockup](mockups/cu-08-auditar-total.html) |
| [CU-09](cu-09-continuar-con-primario-caido.md) | Continuar operando con el primario caído | Cliente / Nodo | No aplica (propiedad del sistema) |
| [CU-10](cu-10-recuperar-estado-al-reiniciar.md) | Recuperar estado al reiniciar | Administrador / Nodo | No aplica (automático) |
| [CU-11](cu-11-operaciones-concurrentes.md) | Operaciones concurrentes | Cliente / Nodo | No aplica (propiedad del sistema) |
| [CU-12](cu-12-provocar-falla-para-pruebas.md) | Provocar falla para pruebas | Ingeniero de pruebas | [mockup](mockups/cu-12-provocar-falla-para-pruebas.html) |
| [CU-13](cu-13-ver-estado-del-cluster.md) | Ver estado del clúster | Administrador | [mockup](mockups/cu-13-ver-estado-del-cluster.html) |
| [CU-14](cu-14-abrir-cuenta-ahorro.md) | Abrir cuenta de ahorro con interés periódico | Cliente | [mockup](mockups/cu-14-abrir-cuenta-ahorro.html) |
| [CU-15](cu-15-abrir-deposito-plazo-fijo.md) | Abrir depósito a plazo fijo | Cliente | [mockup](mockups/cu-15-abrir-deposito-plazo-fijo.html) |
| [CU-16](cu-16-transferir-sistema-externo.md) | Transferir a un sistema externo | Cliente / Sistema externo | [mockup](mockups/cu-16-transferir-sistema-externo.html) |
| [CU-17](cu-17-iniciar-sesion.md) | Iniciar sesión | Cliente | Pendiente de diseño |

Los mockups siguen la línea gráfica de
[`../../docs/adr/ADR-0003-linha-grafica.md`](../../docs/adr/ADR-0003-linha-grafica.md)
y comparten la hoja de estilos [`mockups/estilo.css`](mockups/estilo.css).
