-- Igual en los 2-3 nodos — copiado de
-- docs/entregables/05-modelo-de-datos/modelo-fisico.md. Cada nodo corre su
-- propia instancia; no se comparte una base de datos entre nodos (ver
-- GUIA-REPLICA-POSTGRESQL.md).

CREATE TABLE usuario (
    id              UUID PRIMARY KEY,
    nombre          VARCHAR(120) NOT NULL,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    fecha_creacion  TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE cuenta (
    id                     VARCHAR(64) PRIMARY KEY,
    usuario_id             UUID NOT NULL REFERENCES usuario(id),
    moneda                 VARCHAR(3) NOT NULL CHECK (moneda IN ('BRL','USD','PEN')),
    saldo_centavos         BIGINT NOT NULL DEFAULT 0 CHECK (saldo_centavos >= 0),
    fecha_creacion         TIMESTAMP NOT NULL DEFAULT now(),
    estado                 VARCHAR(20) NOT NULL DEFAULT 'ACTIVA'
                           CHECK (estado IN ('ACTIVA','BLOQUEADA','CERRADA')),
    tipo_producto          VARCHAR(20) NOT NULL DEFAULT 'CORRIENTE'
                           CHECK (tipo_producto IN ('CORRIENTE','AHORRO','PLAZO_FIJO')),
    tasa_interes           NUMERIC(9,6) CHECK (tasa_interes IS NULL OR tasa_interes > 0),
    fecha_ultimo_interes   TIMESTAMP,
    fecha_vencimiento      TIMESTAMP,
    CONSTRAINT chk_producto_completo CHECK (
        (tipo_producto = 'CORRIENTE'
            AND tasa_interes IS NULL AND fecha_ultimo_interes IS NULL AND fecha_vencimiento IS NULL)
        OR (tipo_producto = 'AHORRO'
            AND tasa_interes IS NOT NULL AND fecha_ultimo_interes IS NOT NULL AND fecha_vencimiento IS NULL)
        OR (tipo_producto = 'PLAZO_FIJO'
            AND tasa_interes IS NOT NULL AND fecha_ultimo_interes IS NULL
            AND fecha_vencimiento IS NOT NULL AND fecha_vencimiento > fecha_creacion)
    )
);
CREATE INDEX idx_cuenta_usuario ON cuenta(usuario_id);

CREATE TABLE tasa_cambio (
    moneda_origen   VARCHAR(3) NOT NULL,
    moneda_destino  VARCHAR(3) NOT NULL,
    valor           NUMERIC(18,8) NOT NULL CHECK (valor > 0),
    vigente_desde   TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (moneda_origen, moneda_destino, vigente_desde),
    CHECK (moneda_origen <> moneda_destino)
);

CREATE TABLE sistema_externo (
    id      VARCHAR(32) PRIMARY KEY,
    nombre  VARCHAR(120) NOT NULL,
    codigo  VARCHAR(20) NOT NULL UNIQUE,
    activo  BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE operacion (
    id                      UUID PRIMARY KEY,
    tipo                    VARCHAR(25) NOT NULL
                            CHECK (tipo IN ('CREACION','DEPOSITO','RETIRO','TRANSFERENCIA','CAMBIO',
                                             'INTERES','TRANSFERENCIA_EXTERNA')),
    cuenta_origen_id        VARCHAR(64) REFERENCES cuenta(id),
    cuenta_destino_id       VARCHAR(64) REFERENCES cuenta(id),
    valor_centavos          BIGINT NOT NULL CHECK (valor_centavos >= 0),
    moneda_origen           VARCHAR(3),
    moneda_destino          VARCHAR(3),
    tasa_aplicada           NUMERIC(18,8),
    valor_destino_centavos  BIGINT,
    sistema_externo_id      VARCHAR(32) REFERENCES sistema_externo(id),
    referencia_externa      VARCHAR(64),
    fecha_hora              TIMESTAMP NOT NULL DEFAULT now(),
    estado                  VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE'
                            CHECK (estado IN ('PENDIENTE','CONFIRMADA','RECHAZADA','CANCELADA')),
    CONSTRAINT chk_cambio_completo CHECK (
        tipo <> 'CAMBIO'
        OR (moneda_origen IS NOT NULL AND moneda_destino IS NOT NULL
            AND tasa_aplicada IS NOT NULL AND valor_destino_centavos IS NOT NULL)
    ),
    CONSTRAINT chk_externa_completa CHECK (
        tipo <> 'TRANSFERENCIA_EXTERNA' OR sistema_externo_id IS NOT NULL
    )
);
CREATE INDEX idx_operacion_origen ON operacion(cuenta_origen_id, fecha_hora);
CREATE INDEX idx_operacion_destino ON operacion(cuenta_destino_id, fecha_hora);
