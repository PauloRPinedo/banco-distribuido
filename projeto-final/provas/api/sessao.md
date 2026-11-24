# Sessão de operações de teste — projeto final

Executada a 2026-11-23 15:18:04, sufixo `db2349`, contra `http://localhost:8080/api` (painel → balanceador → nó).

**65 passos certos, 0 falhados, 0 lacunas confirmadas**, de 65.


## 1. O cluster está de pé

**Balanceador responde** — ✅

```http
GET /saude
→ 200 (esperado 200)
{"balanceador": "ativo"}
```

**Nó A responde** — ✅

```http
GET http://localhost:8001/interno/estado
→ 200 (esperado 200)
{"no": "A", "papel": "primário", "epoch": 2, "lider": "A", "ultimo_indice": 1, "indice_commit": 1, "ultimo_aplicado": 1, "pronto": true, "falhas": {"atraso_ms": 0, "isolado_de": []}}
```

**Nó B responde** — ✅

```http
GET http://localhost:8002/interno/estado
→ 200 (esperado 200)
{"no": "B", "papel": "réplica", "epoch": 2, "lider": "A", "ultimo_indice": 1, "indice_commit": 1, "ultimo_aplicado": 1, "pronto": true, "falhas": {"atraso_ms": 0, "isolado_de": []}}
```

**Nó C responde** — ✅

```http
GET http://localhost:8003/interno/estado
→ 200 (esperado 200)
{"no": "C", "papel": "réplica", "epoch": 2, "lider": "A", "ultimo_indice": 1, "indice_commit": 1, "ultimo_aplicado": 1, "pronto": true, "falhas": {"atraso_ms": 0, "isolado_de": []}}
```

**Há exatamente um primário, e as réplicas sabem quem é** — ✅

```http
GET /interno/cluster
→ 200 (esperado 200)
{"eu": "A", "maioria": 2, "nos": [{"no": "A", "papel": "primário", "epoch": 2, "lider": "A", "ultimo_indice": 1, "indice_commit": 1, "ultimo_aplicado": 1, "pronto": true, "falhas": {"atraso_ms": 0, "isolado_de": []}, "vivo": true, "endereco": "no-a:8001"}, {"no": "B", "papel": "réplica", "epoch": 2, "lider": "A", "ultimo_indice": 1, "indice_commit": 1, "ultimo_aplicado": 1, "pronto": true, "falhas": {"atraso_ms": 0, "isolado_de": []}, "endereco": "no-b:8001", "vivo": true}, {"no": "C", "papel": "réplica", "epoch": 2, "lider": "A", "ultimo_indice": 1, "indice_commit": 1, "ultimo_aplicado": 1, " …
```


## 2. Registo e sessão

**Registar a Ana** — ✅

```http
POST /auth/registo
{"nome": "Ana", "email": "ana-db2349@teste.pt", "senha": "segredo-ana"}
→ 200 (esperado 200)
{"id": "33965af1-1de2-4a70-a093-04b36ec87bac", "email": "ana-db2349@teste.pt"}
```

**Registar o Rui** — ✅

```http
POST /auth/registo
{"nome": "Rui", "email": "rui-db2349@teste.pt", "senha": "segredo-rui"}
→ 200 (esperado 200)
{"id": "497547fc-a541-49cc-95aa-211fc6303dbc", "email": "rui-db2349@teste.pt"}
```

**Email repetido é recusado** — ✅

```http
POST /auth/registo
{"nome": "Outra", "email": "ana-db2349@teste.pt", "senha": "outra-senha"}
→ 409 (esperado 409)
{"erro": "email_duplicado", "mensagem": "o email 'ana-db2349@teste.pt' já está registado"}
```

**Senha errada é recusada** — ✅

```http
POST /auth/login
{"email": "ana-db2349@teste.pt", "senha": "errada"}
→ 401 (esperado 401)
{"erro": "credenciais_invalidas", "mensagem": "email ou senha incorretos"}
```

**Login da Ana** — ✅

```http
POST /auth/login
{"email": "ana-db2349@teste.pt", "senha": "segredo-ana"}
→ 200 (esperado 200)
{"token": "eyJ1c3Vhcmlv…"}
```

**Login do Rui** — ✅

```http
POST /auth/login
{"email": "rui-db2349@teste.pt", "senha": "segredo-rui"}
→ 200 (esperado 200)
{"token": "eyJ1c3Vhcmlv…"}
```

**Abrir conta sem sessão é recusado** — ✅

```http
POST /contas
{"conta": "x-db2349", "op_id": "op-13af739ec7864356bbe9"}
→ 401 (esperado 401)
{"erro": "sem_sessao", "mensagem": "falta o cabeçalho Authorization: Bearer <token>"}
```


## 3. Abrir contas: moedas e produtos

**Conta corrente em reais** — ✅

```http
POST /contas
{"conta": "ana-corrente-db2349", "saldo_inicial": "100.00", "op_id": "op-af98c1bd69994734a3f8"}
→ 200 (esperado 200)
{"conta": "ana-corrente-db2349", "saldo_centavos": 10000, "moeda": "BRL", "agencia": "0001", "numero": "27136116-6", "saldo": "R$ 100,00"}
```

**Conta em dólares** — ✅

```http
POST /contas
{"conta": "ana-dolares-db2349", "saldo_inicial": "50.00", "moeda": "USD", "op_id": "op-e1d241f88b194cc2ab72"}
→ 200 (esperado 200)
{"conta": "ana-dolares-db2349", "saldo_centavos": 5000, "moeda": "USD", "agencia": "0001", "numero": "91370217-0", "saldo": "US$ 50,00"}
```

**Poupança a 10 % ao ano** — ✅

```http
POST /contas
{"conta": "ana-poupanca-db2349", "saldo_inicial": "1000.00", "produto": "poupanca", "taxa_juros": "0.10", "op_id": "op-528681fddea441b183cf"}
→ 200 (esperado 200)
{"conta": "ana-poupanca-db2349", "saldo_centavos": 100000, "moeda": "BRL", "agencia": "0001", "numero": "21581418-5", "saldo": "R$ 1.000,00"}
```

**Prazo fixo a 12 %, 30 dias** — ✅

```http
POST /contas
{"conta": "ana-prazo-db2349", "saldo_inicial": "500.00", "produto": "prazo_fixo", "taxa_juros": "0.12", "prazo_dias": 30, "op_id": "op-0f9864ea534e4ae7addd"}
→ 200 (esperado 200)
{"conta": "ana-prazo-db2349", "saldo_centavos": 50000, "moeda": "BRL", "agencia": "0001", "numero": "93601727-9", "saldo": "R$ 500,00"}
```

**Conta do Rui** — ✅

```http
POST /contas
{"conta": "rui-db2349", "saldo_inicial": "0", "op_id": "op-3076c7ed628d4e759a98"}
→ 200 (esperado 200)
{"conta": "rui-db2349", "saldo_centavos": 0, "moeda": "BRL", "agencia": "0001", "numero": "91730236-2", "saldo": "R$ 0,00"}
```

**A Ana vê só as suas quatro contas** — ✅

```http
GET /contas
→ 200 (esperado 200)
{"contas": [{"conta": "ana-corrente-db2349", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 10000, "saldo": "R$ 100,00", "taxa_juros": null, "vence_em": null, "criada_em": 1795457885.9763088, "agencia": "0001", "numero": "27136116-6"}, {"conta": "ana-dolares-db2349", "moeda": "USD", "produto": "corrente", "saldo_centavos": 5000, "saldo": "US$ 50,00", "taxa_juros": null, "vence_em": null, "criada_em": 1795457886.0272233, "agencia": "0001", "numero": "91370217-0"}, {"conta": "ana-poupanca-db2349", "moeda": "BRL", "produto": "poupanca", "saldo_centavos": 100000, "saldo": "R$ 1.000,00",  …
```


## 4. Pedidos mal formados

**Dinheiro como número JSON** — ✅

```http
POST /contas/ana-corrente-db2349/deposito
{"valor": 25.0, "op_id": "op-6f8ebfc6aeb241bf8f3f"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "o valor tem de vir como texto, não float: 25.0"}
```

**Três casas decimais** — ✅

```http
POST /contas/ana-corrente-db2349/deposito
{"valor": "1.005", "op_id": "op-04b037caa7ab46249cf7"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "valor mal formado: '1.005'"}
```

**Id de conta com espaços** — ✅

```http
POST /contas
{"conta": "Ana Silva", "op_id": "op-87430d2741d44607a4bf"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "id de conta inválido: 'Ana Silva' (1 a 32 caracteres de a-z, 0-9, _ ou -)"}
```

**Conta repetida** — ✅

```http
POST /contas
{"conta": "ana-corrente-db2349", "saldo_inicial": "1.00", "op_id": "op-65353fc8aa6642c18b1e"}
→ 409 (esperado 409)
{"erro": "conta_duplicada", "mensagem": "a conta 'ana-corrente-db2349' já existe"}
```

**Moeda desconhecida** — ✅

```http
POST /contas
{"conta": "euros-db2349", "moeda": "EUR", "op_id": "op-31a22b78c6db46b0a704"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "moeda desconhecida: 'EUR' (BRL, USD, PEN)"}
```

**Conta corrente com taxa de juros** — ✅

```http
POST /contas
{"conta": "estranha-db2349", "taxa_juros": "0.10", "op_id": "op-e7cfd24fa50b4d97aa03"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "a conta corrente não tem taxa de juros nem prazo"}
```

**op_id curto demais** — ✅

```http
POST /contas/ana-corrente-db2349/deposito
{"valor": "1.00", "op_id": "curto"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "op_id inválido: 'curto' (8 a 64 caracteres de A-Z, a-z, 0-9, _ ou -)"}
```


## 5. Depósitos, saques e transferências

**O Rui deposita na conta da Ana (depositar é aberto)** — ✅

```http
POST /contas/ana-corrente-db2349/deposito
{"valor": "5.00", "op_id": "op-f0ed2966e1284e1e9fe9"}
→ 200 (esperado 200)
{"conta": "ana-corrente-db2349", "moeda": "BRL"}
```

**Saque de 10,00** — ✅

```http
POST /contas/ana-corrente-db2349/saque
{"valor": "10.00", "op_id": "op-b9724fc3ba3749a0a182"}
→ 200 (esperado 200)
{"conta": "ana-corrente-db2349", "saldo_centavos": 9500, "moeda": "BRL", "saldo": "R$ 95,00"}
```

**Saque maior que o saldo** — ✅

```http
POST /contas/ana-corrente-db2349/saque
{"valor": "9999.00", "op_id": "op-ef00f543b9f74ef58dd9"}
→ 422 (esperado 422)
{"erro": "saldo_insuficiente", "mensagem": "ana-corrente-db2349 tem R$ 95,00 e a operação pede R$ 9.999,00"}
```

**Saque de prazo fixo antes de vencer** — ✅

```http
POST /contas/ana-prazo-db2349/saque
{"valor": "1.00", "op_id": "op-e1cc898cca5b4746bfc7"}
→ 409 (esperado 409)
{"erro": "conta_bloqueada", "mensagem": "ana-prazo-db2349 é um prazo fixo e só vence a 2026-12-23"}
```

**Transferência de 25,00 para o Rui** — ✅

```http
POST /transferencias
{"de": "ana-corrente-db2349", "para": "rui-db2349", "valor": "25.00", "op_id": "op-8f2ebcd68d154c069ee5"}
→ 200 (esperado 200)
{"de": "ana-corrente-db2349", "para": "rui-db2349", "moeda": "BRL", "saldos_centavos": {"ana-corrente-db2349": 7000}, "saldos": {"ana-corrente-db2349": "R$ 70,00"}}
```

**A mesma transferência repetida devolve o mesmo corpo** — ✅

```http
POST /transferencias
{"de": "ana-corrente-db2349", "para": "rui-db2349", "valor": "25.00", "op_id": "op-8f2ebcd68d154c069ee5"}
→ 200 (esperado 200)
{"de": "ana-corrente-db2349", "para": "rui-db2349", "moeda": "BRL", "saldos_centavos": {"ana-corrente-db2349": 7000}, "saldos": {"ana-corrente-db2349": "R$ 70,00"}}
```

**O mesmo op_id com outro valor devolve o guardado** — ✅

```http
POST /transferencias
{"de": "ana-corrente-db2349", "para": "rui-db2349", "valor": "70.00", "op_id": "op-8f2ebcd68d154c069ee5"}
→ 200 (esperado 200)
{"de": "ana-corrente-db2349", "para": "rui-db2349", "moeda": "BRL", "saldos_centavos": {"ana-corrente-db2349": 7000}, "saldos": {"ana-corrente-db2349": "R$ 70,00"}}
```

**O Rui só recebeu uma vez** — ✅

```http
GET /contas/rui-db2349
→ 200 (esperado 200)
{"conta": "rui-db2349", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 2500, "saldo": "R$ 25,00", "taxa_juros": null, "vence_em": null, "criada_em": 1795457886.127164, "agencia": "0001", "numero": "91730236-2"}
```


## 6. Dono da conta

**O Rui não consulta a conta da Ana** — ✅

```http
GET /contas/ana-corrente-db2349
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'ana-corrente-db2349' não te pertence"}
```

**O Rui não vê o extrato da Ana** — ✅

```http
GET /contas/ana-corrente-db2349/extrato
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'ana-corrente-db2349' não te pertence"}
```

**O Rui não saca da conta da Ana** — ✅

```http
POST /contas/ana-corrente-db2349/saque
{"valor": "1.00", "op_id": "op-11a607d34ced488da891"}
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'ana-corrente-db2349' não te pertence"}
```

**O Rui não transfere a partir da conta da Ana** — ✅

```http
POST /transferencias
{"de": "ana-corrente-db2349", "para": "rui-db2349", "valor": "1.00", "op_id": "op-a50b1c55bc7f4e6b8c9b"}
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'ana-corrente-db2349' não te pertence"}
```

**O Rui não repete um op_id da Ana para ler a resposta dela** — ✅

```http
POST /transferencias
{"de": "ana-corrente-db2349", "para": "rui-db2349", "valor": "25.00", "op_id": "op-8f2ebcd68d154c069ee5"}
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'ana-corrente-db2349' não te pertence"}
```


## 7. Moedas e câmbio

**Transferência simples entre moedas é recusada** — ✅

```http
POST /transferencias
{"de": "ana-dolares-db2349", "para": "ana-corrente-db2349", "valor": "1.00", "op_id": "op-fa9eadcc5dc644db8b9f"}
→ 409 (esperado 409)
{"erro": "moedas_diferentes", "mensagem": "ana-dolares-db2349 está em USD e ana-corrente-db2349 em BRL; entre moedas é um câmbio (/transferencias/conversao)"}
```

**Taxa USD→BRL em vigor** — ✅

```http
GET /taxas/USD/BRL
→ 200 (esperado 200)
{"moeda_origem": "USD", "moeda_destino": "BRL", "taxa_milionesimos": 5430000, "taxa": "5.430000"}
```

**Câmbio de 10,00 USD** — ✅

```http
POST /transferencias/conversao
{"de": "ana-dolares-db2349", "para": "ana-corrente-db2349", "valor": "10.00", "op_id": "op-d88ef7ca9c3e45968021"}
→ 200 (esperado 200)
{"de": "ana-dolares-db2349", "para": "ana-corrente-db2349", "valor_centavos": 1000, "valor_destino_centavos": 5430, "taxa_milionesimos": 5430000, "moedas": {"ana-dolares-db2349": "USD", "ana-corrente-db2349": "BRL"}, "saldos_centavos": {"ana-dolares-db2349": 4000, "ana-corrente-db2349": 12430}, "saldos": {"ana-dolares-db2349": "US$ 40,00", "ana-corrente-db2349": "R$ 124,30"}, "taxa": "5.430000", "valor": "US$ 10,00", "valor_destino": "R$ 54,30"}
```

**Registar uma taxa nova, 6,00** — ✅

```http
POST /admin/taxas
{"moeda_origem": "USD", "moeda_destino": "BRL", "taxa": "6.00"}
→ 200 (esperado 200)
{"moeda_origem": "USD", "moeda_destino": "BRL", "taxa_milionesimos": 6000000, "vigente_desde": 1795457886.5969737, "taxa": "6.000000"}
```

**O câmbio repetido mantém a taxa de então** — ✅

```http
POST /transferencias/conversao
{"de": "ana-dolares-db2349", "para": "ana-corrente-db2349", "valor": "10.00", "op_id": "op-d88ef7ca9c3e45968021"}
→ 200 (esperado 200)
{"de": "ana-dolares-db2349", "para": "ana-corrente-db2349", "moedas": {"ana-dolares-db2349": "USD", "ana-corrente-db2349": "BRL"}, "valor_centavos": 1000, "saldos_centavos": {"ana-dolares-db2349": 4000, "ana-corrente-db2349": 12430}, "taxa_milionesimos": 5430000, "valor_destino_centavos": 5430, "saldos": {"ana-dolares-db2349": "US$ 40,00", "ana-corrente-db2349": "R$ 124,30"}, "taxa": "5.430000", "valor": "US$ 10,00", "valor_destino": "R$ 54,30"}
```

**Um câmbio novo usa a taxa nova** — ✅

```http
POST /transferencias/conversao
{"de": "ana-dolares-db2349", "para": "ana-corrente-db2349", "valor": "10.00", "op_id": "op-655ef317a50f45d0aa53"}
→ 200 (esperado 200)
{"de": "ana-dolares-db2349", "para": "ana-corrente-db2349", "valor_centavos": 1000, "valor_destino_centavos": 6000, "taxa_milionesimos": 6000000, "moedas": {"ana-dolares-db2349": "USD", "ana-corrente-db2349": "BRL"}, "saldos_centavos": {"ana-dolares-db2349": 3000, "ana-corrente-db2349": 18430}, "saldos": {"ana-dolares-db2349": "US$ 30,00", "ana-corrente-db2349": "R$ 184,30"}, "taxa": "6.000000", "valor": "US$ 10,00", "valor_destino": "R$ 60,00"}
```

**Autotransferência entre moedas** — ✅

```http
POST /transferencias/autotransferencia
{"de": "ana-dolares-db2349", "para": "ana-corrente-db2349", "valor": "1.00", "op_id": "op-29c7f0087d8e4ec8b41e"}
→ 200 (esperado 200)
{"de": "ana-dolares-db2349", "para": "ana-corrente-db2349", "valor_centavos": 100, "valor_destino_centavos": 600, "taxa_milionesimos": 6000000, "moedas": {"ana-dolares-db2349": "USD", "ana-corrente-db2349": "BRL"}, "saldos_centavos": {"ana-dolares-db2349": 2900, "ana-corrente-db2349": 19030}, "saldos": {"ana-dolares-db2349": "US$ 29,00", "ana-corrente-db2349": "R$ 190,30"}, "taxa": "6.000000", "valor": "US$ 1,00", "valor_destino": "R$ 6,00"}
```

**Autotransferência para conta alheia é recusada** — ✅

```http
POST /transferencias/autotransferencia
{"de": "ana-corrente-db2349", "para": "rui-db2349", "valor": "1.00", "op_id": "op-ed0f6caaee654353ac8f"}
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'rui-db2349' não te pertence"}
```


## 8. Transferência para outro banco

O compose usa o `GatewayExternoSimulado`: confirma cerca de 85 % das vezes, ao acaso. Envia-se até aparecer uma confirmação e uma rejeição.

**Bancos disponíveis** — ✅

```http
GET /sistemas-externos
→ 200 (esperado 200)
{"sistemas": [{"id": "banco-externo", "nome": "Banco externo simulado", "codigo": "EXT001"}]}
```

**Envio 1: confirmada (repetido para registo)** — ✅

```http
POST /transferencias/externa
{"de": "ana-corrente-db2349", "sistema_externo_id": "banco-externo", "valor": "1.00", "op_id": "op-401e7ab922954b38aa91"}
→ 200 (esperado 200)
{"conta": "ana-corrente-db2349", "moeda": "BRL", "estado": "confirmada", "op_original": "op-401e7ab922954b38aa91", "saldo_centavos": 18930, "valor_centavos": 100, "referencia_externa": "be30388d-d815-57f9-babb-98051f5b8305", "saldo": "R$ 189,30"}
```

**Envio 7: rejeitada (repetido para registo)** — ✅

```http
POST /transferencias/externa
{"de": "ana-corrente-db2349", "sistema_externo_id": "banco-externo", "valor": "1.00", "op_id": "op-8085b32471974f0ea4a3"}
→ 200 (esperado 200)
{"conta": "ana-corrente-db2349", "moeda": "BRL", "estado": "rejeitada", "op_original": "op-8085b32471974f0ea4a3", "saldo_centavos": 18430, "valor_centavos": 100, "referencia_externa": null, "saldo": "R$ 184,30"}
```

Foram precisos 7 envios para ver os dois desfechos. A repetição de cada um devolveu o desfecho gravado, sem voltar a perguntar ao outro banco.

**Banco desconhecido** — ✅

```http
POST /transferencias/externa
{"de": "ana-corrente-db2349", "sistema_externo_id": "nao-existe", "valor": "1.00", "op_id": "op-4ede6e611f05488fa99c"}
→ 404 (esperado 404)
{"erro": "sistema_externo_inexistente", "mensagem": "sistema externo desconhecido: 'nao-existe'"}
```

**Sem saldo, nem chega ao outro banco** — ✅

```http
POST /transferencias/externa
{"de": "ana-corrente-db2349", "sistema_externo_id": "banco-externo", "valor": "99999.00", "op_id": "op-0c5cd4f940224454aca2"}
→ 422 (esperado 422)
{"erro": "saldo_insuficiente", "mensagem": "ana-corrente-db2349 tem R$ 184,30 e a operação pede R$ 99.999,00"}
```


## 9. Juros

**Tick de juros** — ✅

```http
POST /admin/juros
→ 200 (esperado 200)
{"ate": 1795457891.3163524, "creditadas": []}
```

A poupança abriu há segundos: os juros devidos ainda não chegam a um centavo, por isso a lista sai vazia. O cálculo ao longo de um ano e o prazo fixo vencido estão provados em `tests/unitarios/teste_produtos.py`, onde o instante é um argumento e não é preciso esperar.


## 10. Concorrência

**20 depósitos de 1,00 ao mesmo tempo (20 aceites): nenhum se perde** — ✅

```http
GET /contas/rui-db2349
→ 200 (esperado 200)
{"conta": "rui-db2349", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 4500, "saldo": "R$ 45,00", "taxa_juros": null, "vence_em": null, "criada_em": 1795457886.127164, "agencia": "0001", "numero": "91730236-2"}
```

**20 saques de 1,00 sobre 10,00 ao mesmo tempo: 10 aceites, 10 recusados** — ✅

```http
GET /contas/rui-pequena-db2349
→ 200 (esperado 200)
{"conta": "rui-pequena-db2349", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 0, "saldo": "R$ 0,00", "taxa_juros": null, "vence_em": null, "criada_em": 1795457892.128914, "agencia": "0001", "numero": "27938422-0"}
```


## 11. Extrato e auditoria

**Extrato da conta corrente da Ana** — ✅

```http
GET /contas/ana-corrente-db2349/extrato
→ 200 (esperado 200)
{"conta": "ana-corrente-db2349", "moeda": "BRL", "movimentos": [{"indice": 4, "tipo": "criar_conta", "valor_centavos": 10000, "valor": "R$ 100,00", "contraparte": null, "saldo_depois_centavos": 10000, "saldo_depois": "R$ 100,00", "instante": 1795457885.9763088}, {"indice": 9, "tipo": "deposito", "valor_centavos": 500, "valor": "R$ 5,00", "contraparte": null, "saldo_depois_centavos": 10500, "saldo_depois": "R$ 105,00", "instante": 1795457886.265155}, {"indice": 10, "tipo": "saque", "valor_centavos": -1000, "valor": "-R$ 10,00", "contraparte": null, "saldo_depois_centavos": 9500, "saldo_depois": …
```

**Auditoria: cada moeda bate** — ✅

```http
GET /auditoria
→ 200 (esperado 200)
{"divergente": false, "moedas": [{"moeda": "BRL", "total_centavos": 172930, "total": "R$ 1.729,30", "total_esperado_centavos": 172930, "total_esperado": "R$ 1.729,30", "divergencia_centavos": 0, "divergencia": "R$ 0,00"}, {"moeda": "USD", "total_centavos": 2900, "total": "US$ 29,00", "total_esperado_centavos": 2900, "total_esperado": "US$ 29,00", "divergencia_centavos": 0, "divergencia": "US$ 0,00"}]}
```


## 12. Replicação e queda do primário a meio de transferências

Antes da queda, as três bases têm de ser iguais — cada escrita acima foi confirmada pela maioria e aplicada nos três nós:

| Nó | Base de dados do nó |
|---|---|
| A | 2 utilizadores · 6 contas · 56 operações · log até 60 · md5 11af5df2245a |
| B | 2 utilizadores · 6 contas · 56 operações · log até 60 · md5 11af5df2245a |
| C | 2 utilizadores · 6 contas · 56 operações · log até 60 · md5 11af5df2245a |

`docker compose kill no-a` — o primário (nó A, epoch 2) morre a meio de transferências concorrentes, sem fechar nada.

O nó **C** passou a primário **1.30 s** depois do `kill`. Durante a transição, 18 tentativas receberam um erro (`[503]`) e foram repetidas com o mesmo op_id; 102 transferências foram confirmadas no total.

**Outro nó é primário, com epoch maior** — ✅

```http
GET /interno/estado
→ 200 (esperado 200)
{"no": "C", "papel": "primário", "epoch": 3, "lider": "C", "ultimo_indice": 163, "indice_commit": 163, "ultimo_aplicado": 163, "pronto": true, "falhas": {"atraso_ms": 0, "isolado_de": []}}
```

**Eleito em menos de 2 s (RNF-03)** — ✅

```http
GET /saude
→ 200 (esperado 200)
{"balanceador": "ativo"}
```

**A sessão da Ana continua válida no novo primário** — ✅

```http
GET /contas
→ 200 (esperado 200)
{"contas": [{"conta": "ana-corrente-db2349", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 18328, "saldo": "R$ 183,28", "taxa_juros": null, "vence_em": null, "criada_em": 1795457885.9763088, "agencia": "0001", "numero": "27136116-6"}, {"conta": "ana-dolares-db2349", "moeda": "USD", "produto": "corrente", "saldo_centavos": 2900, "saldo": "US$ 29,00", "taxa_juros": null, "vence_em": null, "criada_em": 1795457886.0272233, "agencia": "0001", "numero": "91370217-0"}, {"conta": "ana-poupanca-db2349", "moeda": "BRL", "produto": "poupanca", "saldo_centavos": 100000, "saldo": "R$ 1.000,00",  …
```

**Cada transferência confirmada ao cliente está lá** — ✅

```http
GET /contas/rui-db2349
→ 200 (esperado 200)
{"conta": "rui-db2349", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 4602, "saldo": "R$ 46,02", "taxa_juros": null, "vence_em": null, "criada_em": 1795457886.127164, "agencia": "0001", "numero": "91730236-2"}
```

**A transferência do início, repetida, devolve o mesmo corpo** — ✅

```http
POST /transferencias
{"de": "ana-corrente-db2349", "para": "rui-db2349", "valor": "25.00", "op_id": "op-8f2ebcd68d154c069ee5"}
→ 200 (esperado 200)
{"de": "ana-corrente-db2349", "para": "rui-db2349", "moeda": "BRL", "saldos_centavos": {"ana-corrente-db2349": 7000}, "saldos": {"ana-corrente-db2349": "R$ 70,00"}}
```

**O novo primário aceita escritas** — ✅

```http
POST /contas/ana-corrente-db2349/deposito
{"valor": "1.00", "op_id": "op-8a1390fb2b0749229aae"}
→ 200 (esperado 200)
{"conta": "ana-corrente-db2349", "moeda": "BRL"}
```

**O dinheiro total não mudou com a queda** — ✅

```http
GET /auditoria
→ 200 (esperado 200)
{"divergente": false, "moedas": [{"moeda": "BRL", "total_centavos": 173030, "total": "R$ 1.730,30", "total_esperado_centavos": 173030, "total_esperado": "R$ 1.730,30", "divergencia_centavos": 0, "divergencia": "R$ 0,00"}, {"moeda": "USD", "total_centavos": 2900, "total": "US$ 29,00", "total_esperado_centavos": 2900, "total_esperado": "US$ 29,00", "divergencia_centavos": 0, "divergencia": "US$ 0,00"}]}
```

`docker compose start no-a` — o nó morto volta.

**O nó A voltou como réplica e pôs-se em dia** — ✅

```http
GET http://localhost:8001/interno/estado
→ 200 (esperado 200)
{"no": "A", "papel": "réplica", "epoch": 3, "lider": "C", "ultimo_indice": 164, "indice_commit": 164, "ultimo_aplicado": 164, "pronto": true, "falhas": {"atraso_ms": 0, "isolado_de": []}}
```

E as três bases voltam a ser iguais — incluindo o que aconteceu enquanto o nó A estava morto:

| Nó | Base de dados do nó |
|---|---|
| A | 2 utilizadores · 6 contas · 159 operações · log até 164 · md5 812d01b0a84d |
| B | 2 utilizadores · 6 contas · 159 operações · log até 164 · md5 812d01b0a84d |
| C | 2 utilizadores · 6 contas · 159 operações · log até 164 · md5 812d01b0a84d |

**Impressão digital igual nas três bases** — ✅

```http
GET /saude
→ 200 (esperado 200)
{"balanceador": "ativo"}
```
