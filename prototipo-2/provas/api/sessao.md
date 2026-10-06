# Sessão de operações de teste — Protótipo 2

Executada a 2026-10-05 13:27:09, sufixo `654c59`, contra `http://localhost:8080/api` (painel → balanceador → nó).

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
{"no": "A", "papel": "réplica", "epoch": 3, "lider": "B", "ultimo_indice": 15, "indice_commit": 15, "ultimo_aplicado": 15, "falhas": {"atraso_ms": 0, "isolado_de": []}}
```

**Nó B responde** — ✅

```http
GET http://localhost:8002/interno/estado
→ 200 (esperado 200)
{"no": "B", "papel": "primário", "epoch": 3, "lider": "B", "ultimo_indice": 15, "indice_commit": 15, "ultimo_aplicado": 15, "falhas": {"atraso_ms": 0, "isolado_de": []}}
```

**Nó C responde** — ✅

```http
GET http://localhost:8003/interno/estado
→ 200 (esperado 200)
{"no": "C", "papel": "réplica", "epoch": 3, "lider": "B", "ultimo_indice": 15, "indice_commit": 15, "ultimo_aplicado": 15, "falhas": {"atraso_ms": 0, "isolado_de": []}}
```

**Há exatamente um primário, e as réplicas sabem quem é** — ✅

```http
GET /interno/cluster
→ 200 (esperado 200)
{"eu": "B", "maioria": 2, "nos": [{"no": "A", "papel": "réplica", "epoch": 3, "lider": "B", "ultimo_indice": 15, "indice_commit": 15, "ultimo_aplicado": 15, "falhas": {"atraso_ms": 0, "isolado_de": []}, "endereco": "no-a:8001", "vivo": true}, {"no": "B", "papel": "primário", "epoch": 3, "lider": "B", "ultimo_indice": 15, "indice_commit": 15, "ultimo_aplicado": 15, "falhas": {"atraso_ms": 0, "isolado_de": []}, "vivo": true, "endereco": "no-b:8001"}, {"no": "C", "papel": "réplica", "epoch": 3, "lider": "B", "ultimo_indice": 15, "indice_commit": 15, "ultimo_aplicado": 15, "falhas": {"atraso_ms":  …
```


## 2. Registo e sessão

**Registar a Ana** — ✅

```http
POST /auth/registo
{"nome": "Ana", "email": "ana-654c59@teste.pt", "senha": "segredo-ana"}
→ 200 (esperado 200)
{"id": "bf2baa45-f6c0-48d2-8987-c2b8473be644", "email": "ana-654c59@teste.pt"}
```

**Registar o Rui** — ✅

```http
POST /auth/registo
{"nome": "Rui", "email": "rui-654c59@teste.pt", "senha": "segredo-rui"}
→ 200 (esperado 200)
{"id": "832bb412-5535-411f-89d5-ba0b1d97b2ab", "email": "rui-654c59@teste.pt"}
```

**Email repetido é recusado** — ✅

```http
POST /auth/registo
{"nome": "Outra", "email": "ana-654c59@teste.pt", "senha": "outra-senha"}
→ 409 (esperado 409)
{"erro": "email_duplicado", "mensagem": "o email 'ana-654c59@teste.pt' já está registado"}
```

**Senha errada é recusada** — ✅

```http
POST /auth/login
{"email": "ana-654c59@teste.pt", "senha": "errada"}
→ 401 (esperado 401)
{"erro": "credenciais_invalidas", "mensagem": "email ou senha incorretos"}
```

**Login da Ana** — ✅

```http
POST /auth/login
{"email": "ana-654c59@teste.pt", "senha": "segredo-ana"}
→ 200 (esperado 200)
{"token": "eyJ1c3Vhcmlv…"}
```

**Login do Rui** — ✅

```http
POST /auth/login
{"email": "rui-654c59@teste.pt", "senha": "segredo-rui"}
→ 200 (esperado 200)
{"token": "eyJ1c3Vhcmlv…"}
```

**Abrir conta sem sessão é recusado** — ✅

```http
POST /contas
{"conta": "x-654c59", "op_id": "op-3b179d03a3264dec9df8"}
→ 401 (esperado 401)
{"erro": "sem_sessao", "mensagem": "falta o cabeçalho Authorization: Bearer <token>"}
```


## 3. Abrir contas: moedas e produtos

**Conta corrente em reais** — ✅

```http
POST /contas
{"conta": "ana-corrente-654c59", "saldo_inicial": "100.00", "op_id": "op-a65e81a5fa554a5688b3"}
→ 200 (esperado 200)
{"conta": "ana-corrente-654c59", "saldo_centavos": 10000, "moeda": "BRL", "saldo": "R$ 100,00"}
```

**Conta em dólares** — ✅

```http
POST /contas
{"conta": "ana-dolares-654c59", "saldo_inicial": "50.00", "moeda": "USD", "op_id": "op-1c98f27ea26e4637a542"}
→ 200 (esperado 200)
{"conta": "ana-dolares-654c59", "saldo_centavos": 5000, "moeda": "USD", "saldo": "US$ 50,00"}
```

**Poupança a 10 % ao ano** — ✅

```http
POST /contas
{"conta": "ana-poupanca-654c59", "saldo_inicial": "1000.00", "produto": "poupanca", "taxa_juros": "0.10", "op_id": "op-93fef5c1efd44735ab0d"}
→ 200 (esperado 200)
{"conta": "ana-poupanca-654c59", "saldo_centavos": 100000, "moeda": "BRL", "saldo": "R$ 1.000,00"}
```

**Prazo fixo a 12 %, 30 dias** — ✅

```http
POST /contas
{"conta": "ana-prazo-654c59", "saldo_inicial": "500.00", "produto": "prazo_fixo", "taxa_juros": "0.12", "prazo_dias": 30, "op_id": "op-8210de67675e4f3ab8c1"}
→ 200 (esperado 200)
{"conta": "ana-prazo-654c59", "saldo_centavos": 50000, "moeda": "BRL", "saldo": "R$ 500,00"}
```

**Conta do Rui** — ✅

```http
POST /contas
{"conta": "rui-654c59", "saldo_inicial": "0", "op_id": "op-6eb73d8e91294ad8be94"}
→ 200 (esperado 200)
{"conta": "rui-654c59", "saldo_centavos": 0, "moeda": "BRL", "saldo": "R$ 0,00"}
```

**A Ana vê só as suas quatro contas** — ✅

```http
GET /contas
→ 200 (esperado 200)
{"contas": [{"conta": "ana-corrente-654c59", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 10000, "saldo": "R$ 100,00", "taxa_juros": null, "vence_em": null, "criada_em": 1791217630.9835272}, {"conta": "ana-dolares-654c59", "moeda": "USD", "produto": "corrente", "saldo_centavos": 5000, "saldo": "US$ 50,00", "taxa_juros": null, "vence_em": null, "criada_em": 1791217631.0996165}, {"conta": "ana-poupanca-654c59", "moeda": "BRL", "produto": "poupanca", "saldo_centavos": 100000, "saldo": "R$ 1.000,00", "taxa_juros": "0.100000", "vence_em": null, "criada_em": 1791217631.2403646}, {"conta" …
```


## 4. Pedidos mal formados

**Dinheiro como número JSON** — ✅

```http
POST /contas/ana-corrente-654c59/deposito
{"valor": 25.0, "op_id": "op-c3b18a6122c94c22aac4"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "o valor tem de vir como texto, não float: 25.0"}
```

**Três casas decimais** — ✅

```http
POST /contas/ana-corrente-654c59/deposito
{"valor": "1.005", "op_id": "op-4ca16eb549fd46e08672"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "valor mal formado: '1.005'"}
```

**Id de conta com espaços** — ✅

```http
POST /contas
{"conta": "Ana Silva", "op_id": "op-50a2c89a48f4433c9590"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "id de conta inválido: 'Ana Silva' (1 a 32 caracteres de a-z, 0-9, _ ou -)"}
```

**Conta repetida** — ✅

```http
POST /contas
{"conta": "ana-corrente-654c59", "saldo_inicial": "1.00", "op_id": "op-7e37d1268e40428ea08b"}
→ 409 (esperado 409)
{"erro": "conta_duplicada", "mensagem": "a conta 'ana-corrente-654c59' já existe"}
```

**Moeda desconhecida** — ✅

```http
POST /contas
{"conta": "euros-654c59", "moeda": "EUR", "op_id": "op-d92dbe3408e143a7a04f"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "moeda desconhecida: 'EUR' (BRL, USD, PEN)"}
```

**Conta corrente com taxa de juros** — ✅

```http
POST /contas
{"conta": "estranha-654c59", "taxa_juros": "0.10", "op_id": "op-7ca7021c80324f32aab0"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "a conta corrente não tem taxa de juros nem prazo"}
```

**op_id curto demais** — ✅

```http
POST /contas/ana-corrente-654c59/deposito
{"valor": "1.00", "op_id": "curto"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "op_id inválido: 'curto' (8 a 64 caracteres de A-Z, a-z, 0-9, _ ou -)"}
```


## 5. Depósitos, saques e transferências

**O Rui deposita na conta da Ana (depositar é aberto)** — ✅

```http
POST /contas/ana-corrente-654c59/deposito
{"valor": "5.00", "op_id": "op-d9f7a7c5fdbd4b1289af"}
→ 200 (esperado 200)
{"conta": "ana-corrente-654c59", "saldo_centavos": 10500, "moeda": "BRL", "saldo": "R$ 105,00"}
```

**Saque de 10,00** — ✅

```http
POST /contas/ana-corrente-654c59/saque
{"valor": "10.00", "op_id": "op-6beea74b696c49a7802f"}
→ 200 (esperado 200)
{"conta": "ana-corrente-654c59", "saldo_centavos": 9500, "moeda": "BRL", "saldo": "R$ 95,00"}
```

**Saque maior que o saldo** — ✅

```http
POST /contas/ana-corrente-654c59/saque
{"valor": "9999.00", "op_id": "op-5249e336200c47b4a5f1"}
→ 422 (esperado 422)
{"erro": "saldo_insuficiente", "mensagem": "ana-corrente-654c59 tem R$ 95,00 e a operação pede R$ 9.999,00"}
```

**Saque de prazo fixo antes de vencer** — ✅

```http
POST /contas/ana-prazo-654c59/saque
{"valor": "1.00", "op_id": "op-b372343f968d474c8fad"}
→ 409 (esperado 409)
{"erro": "conta_bloqueada", "mensagem": "ana-prazo-654c59 é um prazo fixo e só vence a 2026-11-04"}
```

**Transferência de 25,00 para o Rui** — ✅

```http
POST /transferencias
{"de": "ana-corrente-654c59", "para": "rui-654c59", "valor": "25.00", "op_id": "op-3db8da0ed5d14aaabf0f"}
→ 200 (esperado 200)
{"de": "ana-corrente-654c59", "para": "rui-654c59", "moeda": "BRL", "saldos_centavos": {"ana-corrente-654c59": 7000, "rui-654c59": 2500}, "saldos": {"ana-corrente-654c59": "R$ 70,00", "rui-654c59": "R$ 25,00"}}
```

**A mesma transferência repetida devolve o mesmo corpo** — ✅

```http
POST /transferencias
{"de": "ana-corrente-654c59", "para": "rui-654c59", "valor": "25.00", "op_id": "op-3db8da0ed5d14aaabf0f"}
→ 200 (esperado 200)
{"de": "ana-corrente-654c59", "para": "rui-654c59", "moeda": "BRL", "saldos_centavos": {"rui-654c59": 2500, "ana-corrente-654c59": 7000}, "saldos": {"rui-654c59": "R$ 25,00", "ana-corrente-654c59": "R$ 70,00"}}
```

**O mesmo op_id com outro valor devolve o guardado** — ✅

```http
POST /transferencias
{"de": "ana-corrente-654c59", "para": "rui-654c59", "valor": "70.00", "op_id": "op-3db8da0ed5d14aaabf0f"}
→ 200 (esperado 200)
{"de": "ana-corrente-654c59", "para": "rui-654c59", "moeda": "BRL", "saldos_centavos": {"rui-654c59": 2500, "ana-corrente-654c59": 7000}, "saldos": {"rui-654c59": "R$ 25,00", "ana-corrente-654c59": "R$ 70,00"}}
```

**O Rui só recebeu uma vez** — ✅

```http
GET /contas/rui-654c59
→ 200 (esperado 200)
{"conta": "rui-654c59", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 2500, "saldo": "R$ 25,00", "taxa_juros": null, "vence_em": null, "criada_em": 1791217631.5024378}
```


## 6. Dono da conta

**O Rui não consulta a conta da Ana** — ✅

```http
GET /contas/ana-corrente-654c59
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'ana-corrente-654c59' não te pertence"}
```

**O Rui não vê o extrato da Ana** — ✅

```http
GET /contas/ana-corrente-654c59/extrato
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'ana-corrente-654c59' não te pertence"}
```

**O Rui não saca da conta da Ana** — ✅

```http
POST /contas/ana-corrente-654c59/saque
{"valor": "1.00", "op_id": "op-fee37524ee1048e0b0b7"}
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'ana-corrente-654c59' não te pertence"}
```

**O Rui não transfere a partir da conta da Ana** — ✅

```http
POST /transferencias
{"de": "ana-corrente-654c59", "para": "rui-654c59", "valor": "1.00", "op_id": "op-e71a823a6143472786db"}
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'ana-corrente-654c59' não te pertence"}
```

**O Rui não repete um op_id da Ana para ler a resposta dela** — ✅

```http
POST /transferencias
{"de": "ana-corrente-654c59", "para": "rui-654c59", "valor": "25.00", "op_id": "op-3db8da0ed5d14aaabf0f"}
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'ana-corrente-654c59' não te pertence"}
```


## 7. Moedas e câmbio

**Transferência simples entre moedas é recusada** — ✅

```http
POST /transferencias
{"de": "ana-dolares-654c59", "para": "ana-corrente-654c59", "valor": "1.00", "op_id": "op-c8d44b8f53c44e96a4bc"}
→ 409 (esperado 409)
{"erro": "moedas_diferentes", "mensagem": "ana-dolares-654c59 está em USD e ana-corrente-654c59 em BRL; entre moedas é um câmbio (/transferencias/conversao)"}
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
{"de": "ana-dolares-654c59", "para": "ana-corrente-654c59", "valor": "10.00", "op_id": "op-0ebc3187e5434b229cba"}
→ 200 (esperado 200)
{"de": "ana-dolares-654c59", "para": "ana-corrente-654c59", "valor_centavos": 1000, "valor_destino_centavos": 5430, "taxa_milionesimos": 5430000, "moedas": {"ana-dolares-654c59": "USD", "ana-corrente-654c59": "BRL"}, "saldos_centavos": {"ana-dolares-654c59": 4000, "ana-corrente-654c59": 12430}, "saldos": {"ana-dolares-654c59": "US$ 40,00", "ana-corrente-654c59": "R$ 124,30"}, "taxa": "5.430000", "valor": "US$ 10,00", "valor_destino": "R$ 54,30"}
```

**Registar uma taxa nova, 6,00** — ✅

```http
POST /admin/taxas
{"moeda_origem": "USD", "moeda_destino": "BRL", "taxa": "6.00"}
→ 200 (esperado 200)
{"moeda_origem": "USD", "moeda_destino": "BRL", "taxa_milionesimos": 6000000, "vigente_desde": 1791217633.6424904, "taxa": "6.000000"}
```

**O câmbio repetido mantém a taxa de então** — ✅

```http
POST /transferencias/conversao
{"de": "ana-dolares-654c59", "para": "ana-corrente-654c59", "valor": "10.00", "op_id": "op-0ebc3187e5434b229cba"}
→ 200 (esperado 200)
{"de": "ana-dolares-654c59", "para": "ana-corrente-654c59", "moedas": {"ana-dolares-654c59": "USD", "ana-corrente-654c59": "BRL"}, "valor_centavos": 1000, "saldos_centavos": {"ana-dolares-654c59": 4000, "ana-corrente-654c59": 12430}, "taxa_milionesimos": 5430000, "valor_destino_centavos": 5430, "saldos": {"ana-dolares-654c59": "US$ 40,00", "ana-corrente-654c59": "R$ 124,30"}, "taxa": "5.430000", "valor": "US$ 10,00", "valor_destino": "R$ 54,30"}
```

**Um câmbio novo usa a taxa nova** — ✅

```http
POST /transferencias/conversao
{"de": "ana-dolares-654c59", "para": "ana-corrente-654c59", "valor": "10.00", "op_id": "op-982d6d963d02498593f8"}
→ 200 (esperado 200)
{"de": "ana-dolares-654c59", "para": "ana-corrente-654c59", "valor_centavos": 1000, "valor_destino_centavos": 6000, "taxa_milionesimos": 6000000, "moedas": {"ana-dolares-654c59": "USD", "ana-corrente-654c59": "BRL"}, "saldos_centavos": {"ana-dolares-654c59": 3000, "ana-corrente-654c59": 18430}, "saldos": {"ana-dolares-654c59": "US$ 30,00", "ana-corrente-654c59": "R$ 184,30"}, "taxa": "6.000000", "valor": "US$ 10,00", "valor_destino": "R$ 60,00"}
```

**Autotransferência entre moedas** — ✅

```http
POST /transferencias/autotransferencia
{"de": "ana-dolares-654c59", "para": "ana-corrente-654c59", "valor": "1.00", "op_id": "op-4418f4e920fc46b89e14"}
→ 200 (esperado 200)
{"de": "ana-dolares-654c59", "para": "ana-corrente-654c59", "valor_centavos": 100, "valor_destino_centavos": 600, "taxa_milionesimos": 6000000, "moedas": {"ana-dolares-654c59": "USD", "ana-corrente-654c59": "BRL"}, "saldos_centavos": {"ana-dolares-654c59": 2900, "ana-corrente-654c59": 19030}, "saldos": {"ana-dolares-654c59": "US$ 29,00", "ana-corrente-654c59": "R$ 190,30"}, "taxa": "6.000000", "valor": "US$ 1,00", "valor_destino": "R$ 6,00"}
```

**Autotransferência para conta alheia é recusada** — ✅

```http
POST /transferencias/autotransferencia
{"de": "ana-corrente-654c59", "para": "rui-654c59", "valor": "1.00", "op_id": "op-db25a7f911bd4a979ffb"}
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'rui-654c59' não te pertence"}
```


## 8. Transferência para outro banco

O compose usa o `GatewayExternoSimulado`: confirma cerca de 85 % das vezes, ao acaso. Envia-se até aparecer uma confirmação e uma rejeição.

**Bancos disponíveis** — ✅

```http
GET /sistemas-externos
→ 200 (esperado 200)
{"sistemas": [{"id": "banco-externo", "nome": "Banco externo simulado", "codigo": "EXT001"}]}
```

**Envio 1: rejeitada (repetido para registo)** — ✅

```http
POST /transferencias/externa
{"de": "ana-corrente-654c59", "sistema_externo_id": "banco-externo", "valor": "1.00", "op_id": "op-201ae9a4b9e3470a9a19"}
→ 200 (esperado 200)
{"conta": "ana-corrente-654c59", "moeda": "BRL", "estado": "rejeitada", "op_original": "op-201ae9a4b9e3470a9a19", "saldo_centavos": 19030, "valor_centavos": 100, "referencia_externa": null, "saldo": "R$ 190,30"}
```

**Envio 2: confirmada (repetido para registo)** — ✅

```http
POST /transferencias/externa
{"de": "ana-corrente-654c59", "sistema_externo_id": "banco-externo", "valor": "1.00", "op_id": "op-19e6aab979014bbc9379"}
→ 200 (esperado 200)
{"conta": "ana-corrente-654c59", "moeda": "BRL", "estado": "confirmada", "op_original": "op-19e6aab979014bbc9379", "saldo_centavos": 18930, "valor_centavos": 100, "referencia_externa": "831c07c0-cc4c-4751-88eb-308e5fff826b", "saldo": "R$ 189,30"}
```

Foram precisos 2 envios para ver os dois desfechos. A repetição de cada um devolveu o desfecho gravado, sem voltar a perguntar ao outro banco.

**Banco desconhecido** — ✅

```http
POST /transferencias/externa
{"de": "ana-corrente-654c59", "sistema_externo_id": "nao-existe", "valor": "1.00", "op_id": "op-9302a07789664afc9a3b"}
→ 404 (esperado 404)
{"erro": "sistema_externo_inexistente", "mensagem": "sistema externo desconhecido: 'nao-existe'"}
```

**Sem saldo, nem chega ao outro banco** — ✅

```http
POST /transferencias/externa
{"de": "ana-corrente-654c59", "sistema_externo_id": "banco-externo", "valor": "99999.00", "op_id": "op-f022f38ee02d43849f54"}
→ 422 (esperado 422)
{"erro": "saldo_insuficiente", "mensagem": "ana-corrente-654c59 tem R$ 189,30 e a operação pede R$ 99.999,00"}
```


## 9. Juros

**Tick de juros** — ✅

```http
POST /admin/juros
→ 200 (esperado 200)
{"ate": 1791217635.9340773, "creditadas": []}
```

A poupança abriu há segundos: os juros devidos ainda não chegam a um centavo, por isso a lista sai vazia. O cálculo ao longo de um ano e o prazo fixo vencido estão provados em `tests/unitarios/teste_produtos.py`, onde o instante é um argumento e não é preciso esperar.


## 10. Concorrência

**20 depósitos de 1,00 ao mesmo tempo (20 aceites): nenhum se perde** — ✅

```http
GET /contas/rui-654c59
→ 200 (esperado 200)
{"conta": "rui-654c59", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 4500, "saldo": "R$ 45,00", "taxa_juros": null, "vence_em": null, "criada_em": 1791217631.5024378}
```

**20 saques de 1,00 sobre 10,00 ao mesmo tempo: 10 aceites, 10 recusados** — ✅

```http
GET /contas/rui-pequena-654c59
→ 200 (esperado 200)
{"conta": "rui-pequena-654c59", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 0, "saldo": "R$ 0,00", "taxa_juros": null, "vence_em": null, "criada_em": 1791217638.2589986}
```


## 11. Extrato e auditoria

**Extrato da conta corrente da Ana** — ✅

```http
GET /contas/ana-corrente-654c59/extrato
→ 200 (esperado 200)
{"conta": "ana-corrente-654c59", "moeda": "BRL", "movimentos": [{"indice": 18, "tipo": "criar_conta", "valor_centavos": 10000, "valor": "R$ 100,00", "contraparte": null, "saldo_depois_centavos": 10000, "saldo_depois": "R$ 100,00", "instante": 1791217630.9835272}, {"indice": 23, "tipo": "deposito", "valor_centavos": 500, "valor": "R$ 5,00", "contraparte": null, "saldo_depois_centavos": 10500, "saldo_depois": "R$ 105,00", "instante": 1791217632.1108825}, {"indice": 24, "tipo": "saque", "valor_centavos": -1000, "valor": "-R$ 10,00", "contraparte": null, "saldo_depois_centavos": 9500, "saldo_depoi …
```

**Auditoria: cada moeda bate** — ✅

```http
GET /auditoria
→ 200 (esperado 200)
{"divergente": false, "moedas": [{"moeda": "BRL", "total_centavos": 340010, "total": "R$ 3.400,10", "total_esperado_centavos": 340010, "total_esperado": "R$ 3.400,10", "divergencia_centavos": 0, "divergencia": "R$ 0,00"}, {"moeda": "USD", "total_centavos": 6900, "total": "US$ 69,00", "total_esperado_centavos": 6900, "total_esperado": "US$ 69,00", "divergencia_centavos": 0, "divergencia": "US$ 0,00"}]}
```


## 12. Replicação e queda do primário a meio de transferências

Antes da queda, as três bases têm de ser iguais — cada escrita acima foi confirmada pela maioria e aplicada nos três nós:

| Nó | Base de dados do nó |
|---|---|
| A | 3 utilizadores · 11 contas · 58 operações · log até 64 · md5 2e3b5f39ccf4 |
| B | 3 utilizadores · 11 contas · 58 operações · log até 64 · md5 2e3b5f39ccf4 |
| C | 3 utilizadores · 11 contas · 58 operações · log até 64 · md5 2e3b5f39ccf4 |

`docker compose kill no-b` — o primário (nó B, epoch 3) morre a meio de transferências concorrentes, sem fechar nada.

O nó **C** passou a primário **1.23 s** depois do `kill`. Durante a transição, 15 tentativas receberam um erro (`[503]`) e foram repetidas com o mesmo op_id; 27 transferências foram confirmadas no total.

**Outro nó é primário, com epoch maior** — ✅

```http
GET /interno/estado
→ 200 (esperado 200)
{"no": "C", "papel": "primário", "epoch": 4, "lider": "C", "ultimo_indice": 92, "indice_commit": 92, "ultimo_aplicado": 92, "falhas": {"atraso_ms": 0, "isolado_de": []}}
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
{"contas": [{"conta": "ana-corrente-654c59", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 18903, "saldo": "R$ 189,03", "taxa_juros": null, "vence_em": null, "criada_em": 1791217630.9835272}, {"conta": "ana-dolares-654c59", "moeda": "USD", "produto": "corrente", "saldo_centavos": 2900, "saldo": "US$ 29,00", "taxa_juros": null, "vence_em": null, "criada_em": 1791217631.0996165}, {"conta": "ana-poupanca-654c59", "moeda": "BRL", "produto": "poupanca", "saldo_centavos": 100000, "saldo": "R$ 1.000,00", "taxa_juros": "0.100000", "vence_em": null, "criada_em": 1791217631.2403646}, {"conta" …
```

**Cada transferência confirmada ao cliente está lá** — ✅

```http
GET /contas/rui-654c59
→ 200 (esperado 200)
{"conta": "rui-654c59", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 4527, "saldo": "R$ 45,27", "taxa_juros": null, "vence_em": null, "criada_em": 1791217631.5024378}
```

**A transferência do início, repetida, devolve o mesmo corpo** — ✅

```http
POST /transferencias
{"de": "ana-corrente-654c59", "para": "rui-654c59", "valor": "25.00", "op_id": "op-3db8da0ed5d14aaabf0f"}
→ 200 (esperado 200)
{"de": "ana-corrente-654c59", "para": "rui-654c59", "moeda": "BRL", "saldos_centavos": {"rui-654c59": 2500, "ana-corrente-654c59": 7000}, "saldos": {"rui-654c59": "R$ 25,00", "ana-corrente-654c59": "R$ 70,00"}}
```

**O novo primário aceita escritas** — ✅

```http
POST /contas/ana-corrente-654c59/deposito
{"valor": "1.00", "op_id": "op-8e15eef80da9419b953e"}
→ 200 (esperado 200)
{"conta": "ana-corrente-654c59", "saldo_centavos": 19003, "moeda": "BRL", "saldo": "R$ 190,03"}
```

**O dinheiro total não mudou com a queda** — ✅

```http
GET /auditoria
→ 200 (esperado 200)
{"divergente": false, "moedas": [{"moeda": "BRL", "total_centavos": 340110, "total": "R$ 3.401,10", "total_esperado_centavos": 340110, "total_esperado": "R$ 3.401,10", "divergencia_centavos": 0, "divergencia": "R$ 0,00"}, {"moeda": "USD", "total_centavos": 6900, "total": "US$ 69,00", "total_esperado_centavos": 6900, "total_esperado": "US$ 69,00", "divergencia_centavos": 0, "divergencia": "US$ 0,00"}]}
```

`docker compose start no-b` — o nó morto volta.

**O nó B voltou como réplica e pôs-se em dia** — ✅

```http
GET http://localhost:8002/interno/estado
→ 200 (esperado 200)
{"no": "B", "papel": "réplica", "epoch": 4, "lider": "C", "ultimo_indice": 93, "indice_commit": 93, "ultimo_aplicado": 93, "falhas": {"atraso_ms": 0, "isolado_de": []}}
```

E as três bases voltam a ser iguais — incluindo o que aconteceu enquanto o nó B estava morto:

| Nó | Base de dados do nó |
|---|---|
| A | 3 utilizadores · 11 contas · 86 operações · log até 93 · md5 59dd4ef431cd |
| B | 3 utilizadores · 11 contas · 86 operações · log até 93 · md5 59dd4ef431cd |
| C | 3 utilizadores · 11 contas · 86 operações · log até 93 · md5 59dd4ef431cd |

**Impressão digital igual nas três bases** — ✅

```http
GET /saude
→ 200 (esperado 200)
{"balanceador": "ativo"}
```
