-- Estado do banco num só nó (Protótipo 1).
--
-- Duas tabelas, e não mais: `conta` guarda o saldo de agora, `operacao` guarda
-- tudo o que já aconteceu. A auditoria (RF-14) compara as duas — somar duas
-- vezes a mesma estrutura não auditaria nada.
--
-- O log replicado, o epoch e o voto são das etapas seguintes e vivem em
-- `projeto-final/`. Aqui não há nenhum dos três.

CREATE TABLE conta (
    -- O mesmo formato que `validar_id` exige no domínio. Duplicar a regra na
    -- base é barato e é a última rede: o id aparece em caminhos de URL e na
    -- ordenação dos locks, e um id fora do formato dava dois locks diferentes
    -- para a mesma conta.
    id              VARCHAR(32) PRIMARY KEY CHECK (id ~ '^[a-z0-9_-]{1,32}$'),

    -- Dinheiro é inteiro de centavos, nunca vírgula flutuante (SPECS 3.1).
    -- O CHECK é a segunda linha de defesa de RF-06: mesmo que o domínio
    -- falhasse, a base recusa um saldo negativo.
    saldo_centavos  BIGINT NOT NULL CHECK (saldo_centavos >= 0),

    -- Instante Unix, não TIMESTAMP (SPECS 3.2 diz `criada_em: float`). Com
    -- TIMESTAMP sem fuso, dois laptops com fusos diferentes leem valores
    -- diferentes da mesma linha, e a conversão passaria a acontecer em dois
    -- sítios em vez de um.
    criada_em       DOUBLE PRECISION NOT NULL
);

CREATE TABLE operacao (
    -- Gerado pelo cliente (SPECS 3.3), é a chave de deduplicação: repetir a
    -- mesma escrita com o mesmo op_id move o dinheiro uma só vez. VARCHAR e
    -- não UUID porque SPECS 3.3 dá "3f1c8a2e" como exemplo, que não é um UUID;
    -- o formato é validado na fronteira, antes de chegar aqui.
    op_id             VARCHAR(64) PRIMARY KEY,

    -- Ordem total das operações, da sequência `operacao_numero`. É o `indice`
    -- de SPECS 3.3 e é o que ordena o extrato: ordenar por instante empataria
    -- entre duas operações no mesmo microssegundo.
    numero            BIGINT NOT NULL UNIQUE,

    -- Os mesmos nomes que `Operacao.tipo` usa no domínio. Escrevê-los à mão
    -- aqui seria um segundo vocabulário a divergir do primeiro.
    tipo              VARCHAR(20) NOT NULL
                      CHECK (tipo IN ('criar_conta', 'deposito', 'saque',
                                      'transferencia')),

    conta_origem_id   VARCHAR(32) REFERENCES conta(id),
    conta_destino_id  VARCHAR(32) REFERENCES conta(id),
    valor_centavos    BIGINT NOT NULL CHECK (valor_centavos >= 0),

    -- A resposta que o cliente recebeu, guardada tal e qual. Ao repetir o
    -- op_id devolve-se isto, verbatim. Recalcular a partir dos saldos de agora
    -- daria uma resposta diferente se entretanto houve outras operações, e
    -- SPECS 3.3 exige "o resultado guardado", não um resultado equivalente.
    resposta          JSONB NOT NULL,

    instante          DOUBLE PRECISION NOT NULL
);

-- Não há coluna `estado`. Sem commit em duas fases, a linha só existe se a
-- transação confirmou: um `estado` seria um segundo sítio a dizer o mesmo, e
-- dois sítios divergem.

CREATE SEQUENCE operacao_numero;

CREATE INDEX idx_operacao_origem  ON operacao (conta_origem_id, numero);
CREATE INDEX idx_operacao_destino ON operacao (conta_destino_id, numero);
