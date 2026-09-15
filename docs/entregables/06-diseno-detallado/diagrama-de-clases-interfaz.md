# Diagrama de clases — interfaz (frontera)

Capa *boundary*: lo que recibe las peticiones (HTTP desde el frontend/CLI, o
internas de otros nodos) y las traduce a llamadas de la capa de servicio. No
contiene reglas de negocio — solo valida la **forma** de la petición.

```mermaid
classDiagram
    class CuentaController {
        +POST /cuentas crearCuenta(req)
        +POST /cuentas/ahorro abrirCuentaAhorro(req)
        +POST /cuentas/plazo-fijo abrirPlazoFijo(req)
        +GET /cuentas/{id} consultarSaldo(id)
        +POST /cuentas/{id}/deposito depositar(id, req)
        +POST /cuentas/{id}/retiro retirar(id, req)
        +GET /cuentas/{id}/extracto consultarExtracto(id)
    }

    class TransferenciaController {
        +POST /transferencias transferir(req)
        +POST /transferencias/autotransferencia autotransferir(req)
        +POST /transferencias/externa transferirExterna(req)
    }

    class AuditoriaController {
        +GET /auditoria auditar()
    }

    class AuthController {
        +POST /auth/login iniciarSesion(req)
    }

    class ClusterInternoController {
        +POST /interno/replicar replicar(req)
        +POST /interno/votar votar(req)
        +GET /interno/log consultarLogDesde(indice)
        +GET /interno/estado estadoDelNodo()
    }

    class AdminController {
        +GET /admin/metricas metricas()
        +POST /admin/falla inyectarFalla(req)
    }

    class ManejadorDeErrores {
        +traducir(ErrorDeDominio) RespuestaHttp
    }

    CuentaController ..> ManejadorDeErrores
    TransferenciaController ..> ManejadorDeErrores
    AuditoriaController ..> ManejadorDeErrores
    AuthController ..> ManejadorDeErrores
    ClusterInternoController ..> ManejadorDeErrores
    AdminController ..> ManejadorDeErrores
```

## Regla de esta capa

`ManejadorDeErrores` centraliza la traducción de un error de dominio a un
código HTTP y un cuerpo JSON — el mismo principio que ya tenía
`servidor_http.py` en Prototipo 1 (`_responder_erro`, "en un sitio solo"). No
se repite ese `try/except` en cada controlador.

## Por qué no hay un endpoint para la respuesta del sistema externo

`POST /transferencias/externa` solo **inicia** la `TRANSFERENCIA_EXTERNA`
(RF-25). No existe un endpoint de entrada para que el sistema externo
confirme, porque en esta etapa es un *stub* simulado dentro del mismo
proceso (ver
[`../03-arquitectura/diagrama-de-componentes.md`](../03-arquitectura/diagrama-de-componentes.md)):
`GatewayExterno` simula la latencia y llama directamente a
`ServicioTransferenciasExternas.manejarRespuestaExterna(...)` en memoria. Si
más adelante se integra un sistema externo real, ahí sí haría falta un
controlador de *callback* — hoy agregarlo sería documentar un endpoint que
nada externo llamaría.
