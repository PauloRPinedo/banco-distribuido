# RF-19 a RF-25 no domínio

O que já está, e o que falta. Cada linha marcada tem testes unitários em
`tests/unitarios/teste_produtos.py` e de integração em
`tests/integracao/teste_produtos.py`.

- [x] **Moeda por conta** (RF-19): `Conta.moeda` (BRL, USD, PEN); uma
      `Transferencia` entre moedas é recusada com `moedas_diferentes` (409).
- [x] **Câmbio** (RF-20, RN-06): operação `Cambio` com a taxa dentro dela, em
      milionésimos inteiros; arredonda para baixo ao centavo, num só sítio
      (`dinheiro.converter`). Rota `/transferencias/conversao`.
- [x] **Autotransferência** (CU-06): rota `/transferencias/autotransferencia`,
      com dono nas duas pontas; escolhe `Transferencia` ou `Cambio` pela moeda.
- [x] **Poupança e prazo fixo** (RF-23/24, RN-12, RN-13): `produto`, taxa de
      juros e vencimento na conta; prazo fixo bloqueia saídas até vencer;
      operação `Juros` com o instante dentro dela, chamada por um *tick*
      explícito (`POST /admin/juros`).
- [x] **Transferência externa** (RF-25, RN-14): `TransferenciaExterna` debita e
      `DesfechoExterno` confirma ou devolve, cada uma com o seu op_id.
- [x] **Auditoria por moeda**: soma dos saldos e soma do log separadas por
      moeda; o câmbio sai numa e entra noutra.
- [x] As taxas de câmbio registadas com `POST /admin/taxas` são uma entrada do
      log (`registar_taxa`), aplicada igual nos três nós.

Por fazer:

- [ ] Uma transferência externa que caia entre o débito e o desfecho fica
      pendente até alguém repetir o pedido com o mesmo op_id. Falta uma rotina
      que procure débitos sem desfecho e os resolva.
- [ ] O `GatewayExternoSimulado` não deduplica por op_id como um banco real
      faria; o projeto protege-se gravando o desfecho, mas duas repetições
      simultâneas ainda podem perguntar duas vezes (só a primeira resposta
      conta).
- [ ] Não há papéis: qualquer utilizador com sessão pode registar taxas e
      correr o *tick* de juros.
