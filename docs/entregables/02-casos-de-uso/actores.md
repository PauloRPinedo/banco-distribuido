# Actores del sistema

| Actor | Descripción | Casos de uso principales |
|---|---|---|
| **Cliente** | Dueño de una o más cuentas. Opera desde el frontend web (o el CLI heredado de Prototipo 1) | CU-01 a CU-07, CU-09, CU-11 |
| **Administrador** | Monitorea la salud del clúster y el total de dinero en circulación. No opera cuentas de clientes | CU-08, CU-10, CU-13 |
| **Ingeniero de pruebas** | Provoca fallas controladas para validar que la tolerancia a fallas funciona (rol tomado del PDF de la propuesta, historia 10) | CU-12 |
| **Nodo (actor secundario/sistema)** | No es una persona: representa a los otros servidores del clúster cuando participan en un caso de uso (replicar, votar, confirmar) | Aparece como actor secundario en CU-04, CU-05, CU-09, CU-10, CU-11, CU-16 |
| **Sistema externo (actor secundario/sistema)** | No es una persona ni un nodo del clúster: representa la contraparte fuera del banco que confirma o rechaza una transferencia interoperable. En esta etapa es un *stub* simulado (latencia y fallas aleatorias), no una integración real | Aparece como actor secundario en CU-16 |

## Notas

- Un mismo usuario real puede ser Cliente y, en el contexto de una demo o
  ensayo, también Administrador o Ingeniero de pruebas — son roles
  funcionales, no personas necesariamente distintas.
- "Nodo" se documenta como actor porque en varios casos de uso (fallas,
  replicación) el sistema interactúa consigo mismo entre servidores, y eso es
  parte de lo que hay que representar en el diagrama de casos de uso.

Ver la relación completa actor × caso de uso en
[`matriz-actor-caso-de-uso.md`](matriz-actor-caso-de-uso.md).
