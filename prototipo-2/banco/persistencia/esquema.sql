-- Esquema do armazém do log. Uma base de dados por nó.
--
-- Duas tabelas, e nenhuma delas guarda saldos: o Livro reconstrói-se sempre por
-- replay do log. Uma tabela de saldos seria uma segunda fonte de verdade para o
-- dinheiro, que é a classe de erro que este projeto existe para impedir.

CREATE TABLE IF NOT EXISTS registo_do_log (
    indice   BIGINT PRIMARY KEY,
    epoch    BIGINT NOT NULL,
    op_id    TEXT   NOT NULL,
    tipo     TEXT   NOT NULL,
    -- O dinheiro vive aqui dentro, como inteiro de centavos. Nunca numeric,
    -- nunca money, nunca double precision: nenhum deles representa centavos
    -- exatos sem margem para arredondamento.
    dados    JSONB  NOT NULL,
    instante DOUBLE PRECISION NOT NULL,
    CONSTRAINT indice_positivo CHECK (indice > 0),
    CONSTRAINT epoch_positivo  CHECK (epoch  > 0),
    CONSTRAINT tipo_conhecido  CHECK (tipo IN
        ('criar_conta', 'deposito', 'saque', 'transferencia', 'noop'))
);

-- A deduplicação por op_id passa a ser garantida pela base, e não só pela tabela
-- em memória: se o processo morrer entre o commit do INSERT e o aplicar, uma
-- repetição não consegue inserir a mesma operação uma segunda vez.
CREATE UNIQUE INDEX IF NOT EXISTS log_op_id_unico ON registo_do_log (op_id);

CREATE TABLE IF NOT EXISTS estado_do_no (
    -- Chave primária de propósito: impede dois nós apontados ao mesmo DSN de
    -- partilharem log em silêncio. Sem isto, a corrupção parece um erro de
    -- protocolo e procura-se durante horas no sítio errado.
    no_id         TEXT PRIMARY KEY,
    epoch         BIGINT NOT NULL DEFAULT 1,
    votou_em      TEXT,
    -- O commit é um prefixo, não um sinal por linha.
    indice_commit BIGINT NOT NULL DEFAULT 0,
    CONSTRAINT commit_nao_negativo CHECK (indice_commit >= 0)
);
