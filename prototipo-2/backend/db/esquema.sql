-- Estado de um nó do banco (Protótipo 2). Igual nos três nós: cada um corre a
-- sua própria base, e nenhuma fala com as outras (ver docs/GUIA-REPLICA-POSTGRESQL.md).
--
-- `conta` guarda o saldo de agora, `operacao` guarda tudo o que já aconteceu.
-- A auditoria (RF-14) compara as duas — somar duas vezes a mesma estrutura não
-- auditaria nada.
--
-- Moedas, produtos (poupança, prazo fixo), câmbio e transferência externa
-- cobrem RF-19 a RF-25. Taxas — de juros e de câmbio — guardam-se em
-- milionésimos inteiros (5,4321 é 5432100), pela mesma razão que o dinheiro é
-- inteiro de centavos: nada de vírgula flutuante entre três nós.

CREATE TABLE usuario (
    id           UUID PRIMARY KEY,
    nome         VARCHAR(120) NOT NULL,
    -- Guardado em minúsculas pelo serviço. O UNIQUE é a garantia contra dois
    -- registos simultâneos; o serviço só traduz a recusa num 409 limpo.
    email        VARCHAR(255) NOT NULL UNIQUE,
    -- PBKDF2 com sal, no formato algoritmo$iteracoes$sal$derivado.
    hash_senha   VARCHAR(255) NOT NULL,
    criado_em    DOUBLE PRECISION NOT NULL
);

CREATE TABLE conta (
    -- O mesmo formato que `validar_id` exige no domínio. Duplicar a regra na
    -- base é barato e é a última rede: o id aparece em caminhos de URL e na
    -- ordenação dos locks.
    id                 VARCHAR(32) PRIMARY KEY CHECK (id ~ '^[a-z0-9_-]{1,32}$'),

    usuario_id         UUID NOT NULL REFERENCES usuario(id),

    -- Dinheiro é inteiro de centavos, nunca vírgula flutuante. O CHECK é a
    -- segunda linha de defesa de RF-06.
    saldo_centavos     BIGINT NOT NULL CHECK (saldo_centavos >= 0),

    -- Instante Unix, não TIMESTAMP: com TIMESTAMP sem fuso, duas máquinas com
    -- fusos diferentes leem valores diferentes da mesma linha.
    criada_em          DOUBLE PRECISION NOT NULL,

    moeda              VARCHAR(3) NOT NULL DEFAULT 'BRL'
                       CHECK (moeda IN ('BRL', 'USD', 'PEN')),

    produto            VARCHAR(20) NOT NULL DEFAULT 'corrente'
                       CHECK (produto IN ('corrente', 'poupanca', 'prazo_fixo')),
    -- Ao ano, em milionésimos: 100000 é 10 % ao ano.
    taxa_juros_milionesimos  INTEGER CHECK (taxa_juros_milionesimos > 0),
    -- Poupança: até quando já se pagaram juros. Prazo fixo: o vencimento,
    -- depois de pagos; NULL enquanto não vence.
    ultimo_juros_em    DOUBLE PRECISION,
    vence_em           DOUBLE PRECISION,

    -- A mesma coerência que `CriarConta.validar` exige, repetida como última rede.
    CONSTRAINT produto_coerente CHECK (
        (produto = 'corrente'
            AND taxa_juros_milionesimos IS NULL AND ultimo_juros_em IS NULL
            AND vence_em IS NULL)
        OR (produto = 'poupanca'
            AND taxa_juros_milionesimos IS NOT NULL AND ultimo_juros_em IS NOT NULL
            AND vence_em IS NULL)
        OR (produto = 'prazo_fixo'
            AND taxa_juros_milionesimos IS NOT NULL
            AND vence_em IS NOT NULL AND vence_em > criada_em)
    )
);

CREATE INDEX idx_conta_usuario ON conta (usuario_id);

CREATE TABLE taxa_cambio (
    moeda_origem    VARCHAR(3) NOT NULL,
    moeda_destino   VARCHAR(3) NOT NULL,
    -- Quantas unidades da moeda de destino vale uma da de origem, em milionésimos.
    taxa_milionesimos  BIGINT NOT NULL CHECK (taxa_milionesimos > 0),
    vigente_desde   DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (moeda_origem, moeda_destino, vigente_desde),
    CHECK (moeda_origem <> moeda_destino)
);

CREATE TABLE sistema_externo (
    id      VARCHAR(32) PRIMARY KEY,
    nome    VARCHAR(120) NOT NULL,
    codigo  VARCHAR(20) NOT NULL UNIQUE,
    ativo   BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE operacao (
    -- Gerado pelo cliente, é a chave de deduplicação: repetir a mesma escrita
    -- com o mesmo op_id move o dinheiro uma só vez. VARCHAR e não UUID porque
    -- um op_id como "3f1c8a2e" é válido e não é um UUID. O cliente manda até
    -- 64 caracteres; os 80 dão lugar ao sufixo "-desfecho" do segundo passo
    -- de uma transferência externa.
    op_id             VARCHAR(80) PRIMARY KEY,

    -- O índice da entrada no log replicado: a ordem total, igual nos três nós.
    -- É o que ordena o extrato.
    numero            BIGINT NOT NULL UNIQUE,

    -- Os mesmos nomes que `Operacao.tipo` usa no domínio.
    tipo              VARCHAR(25) NOT NULL
                      CHECK (tipo IN ('criar_conta', 'deposito', 'saque',
                                      'transferencia', 'cambio', 'juros',
                                      'transferencia_externa',
                                      'desfecho_externo')),

    conta_origem_id   VARCHAR(32) REFERENCES conta(id),
    conta_destino_id  VARCHAR(32) REFERENCES conta(id),
    valor_centavos    BIGINT NOT NULL CHECK (valor_centavos >= 0),

    -- Só para câmbio: a taxa fica gravada na operação, para que repetir o
    -- op_id ou reaplicar o log use a mesma taxa e não a de agora.
    moeda_origem            VARCHAR(3),
    moeda_destino           VARCHAR(3),
    taxa_milionesimos       BIGINT,
    valor_destino_centavos  BIGINT,

    -- Só para a transferência externa.
    sistema_externo_id  VARCHAR(32) REFERENCES sistema_externo(id),
    referencia_externa  VARCHAR(64),

    -- A resposta que o cliente recebeu, guardada tal e qual. Ao repetir o
    -- op_id devolve-se isto, verbatim.
    resposta          JSONB NOT NULL,

    instante          DOUBLE PRECISION NOT NULL,

    CONSTRAINT cambio_completo CHECK (
        tipo <> 'cambio'
        OR (moeda_origem IS NOT NULL AND moeda_destino IS NOT NULL
            AND taxa_milionesimos IS NOT NULL AND valor_destino_centavos IS NOT NULL)
    ),
    CONSTRAINT externa_completa CHECK (
        tipo <> 'transferencia_externa' OR sistema_externo_id IS NOT NULL
    )
);

-- Não há coluna `estado`. A transferência externa pendente é a que tem
-- operação `transferencia_externa` sem o `desfecho_externo` correspondente
-- (op_id + "-desfecho"): um `estado` seria um segundo sítio a dizer o mesmo.

CREATE INDEX idx_operacao_origem  ON operacao (conta_origem_id, numero);
CREATE INDEX idx_operacao_destino ON operacao (conta_destino_id, numero);

-- Dados de partida para a demonstração. As taxas valem desde o instante 0, e
-- novas taxas registam-se com POST /admin/taxas.
INSERT INTO taxa_cambio (moeda_origem, moeda_destino, taxa_milionesimos, vigente_desde) VALUES
    ('USD', 'BRL', 5430000, 0), ('BRL', 'USD', 184162, 0),
    ('PEN', 'BRL', 1450000, 0), ('BRL', 'PEN',  689655, 0),
    ('USD', 'PEN', 3745000, 0), ('PEN', 'USD', 267022, 0);

INSERT INTO sistema_externo (id, nome, codigo) VALUES
    ('banco-externo', 'Banco externo simulado', 'EXT001');

-- ------------------------------------------------------------ replicação --

-- O log replicado. É a fonte da verdade: as tabelas acima são o resultado de
-- aplicar, por ordem de índice, as entradas confirmadas — e é por isso que três
-- nós com o mesmo log confirmado têm as mesmas tabelas.
CREATE TABLE log_replicado (
    indice    BIGINT PRIMARY KEY CHECK (indice > 0),
    epoch     BIGINT NOT NULL CHECK (epoch > 0),
    -- Único: uma repetição com o mesmo op_id não entra duas vezes no log.
    op_id     VARCHAR(80) NOT NULL UNIQUE,
    tipo      VARCHAR(25) NOT NULL,
    -- Os argumentos da operação, com tudo o que não é determinista já decidido
    -- pelo primário (instante, ids, hash da senha). O dinheiro vai aqui dentro
    -- como inteiro de centavos.
    dados     JSONB NOT NULL,
    instante  DOUBLE PRECISION NOT NULL
);

-- O que um nó tem de se lembrar sobre si próprio ao arrancar.
CREATE TABLE estado_do_no (
    -- Chave primária de propósito: impede dois nós apontados à mesma base de
    -- partilharem log em silêncio.
    no_id            VARCHAR(16) PRIMARY KEY,
    epoch            BIGINT NOT NULL DEFAULT 1,
    -- O voto é durável: um nó que vota, cai e esquece votaria outra vez.
    votou_em         VARCHAR(16),
    -- O commit é um prefixo do log, não um sinal por linha.
    indice_commit    BIGINT NOT NULL DEFAULT 0 CHECK (indice_commit >= 0),
    -- Até onde as tabelas já refletem o log. Avança na mesma transação que
    -- aplica a entrada: nunca há uma entrada meio aplicada.
    ultimo_aplicado  BIGINT NOT NULL DEFAULT 0 CHECK (ultimo_aplicado >= 0)
);
