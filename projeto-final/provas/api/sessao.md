# Sessão de operações de teste — projeto final

Executada a 2026-11-23 14:04:39, sufixo `7b7291`, contra `http://localhost:8080/api` (painel → balanceador → nó).

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
{"no": "A", "papel": "réplica", "epoch": 30, "lider": "B", "ultimo_indice": 1734, "indice_commit": 1734, "ultimo_aplicado": 1734, "pronto": true, "falhas": {"atraso_ms": 0, "isolado_de": []}}
```

**Nó B responde** — ✅

```http
GET http://localhost:8002/interno/estado
→ 200 (esperado 200)
{"no": "B", "papel": "primário", "epoch": 30, "lider": "B", "ultimo_indice": 1734, "indice_commit": 1734, "ultimo_aplicado": 1734, "pronto": true, "falhas": {"atraso_ms": 0, "isolado_de": []}}
```

**Nó C responde** — ✅

```http
GET http://localhost:8003/interno/estado
→ 200 (esperado 200)
{"no": "C", "papel": "réplica", "epoch": 30, "lider": "B", "ultimo_indice": 1734, "indice_commit": 1734, "ultimo_aplicado": 1734, "pronto": true, "falhas": {"atraso_ms": 0, "isolado_de": []}}
```

**Há exatamente um primário, e as réplicas sabem quem é** — ✅

```http
GET /interno/cluster
→ 200 (esperado 200)
{"eu": "B", "maioria": 2, "nos": [{"no": "A", "papel": "réplica", "epoch": 30, "lider": "B", "ultimo_indice": 1734, "indice_commit": 1734, "ultimo_aplicado": 1734, "pronto": true, "falhas": {"atraso_ms": 0, "isolado_de": []}, "endereco": "no-a:8001", "vivo": true}, {"no": "B", "papel": "primário", "epoch": 30, "lider": "B", "ultimo_indice": 1734, "indice_commit": 1734, "ultimo_aplicado": 1734, "pronto": true, "falhas": {"atraso_ms": 0, "isolado_de": []}, "vivo": true, "endereco": "no-b:8001"}, {"no": "C", "papel": "réplica", "epoch": 30, "lider": "B", "ultimo_indice": 1734, "indice_commit": 17 …
```


## 2. Registo e sessão

**Registar a Ana** — ✅

```http
POST /auth/registo
{"nome": "Ana", "email": "ana-7b7291@teste.pt", "senha": "segredo-ana"}
→ 200 (esperado 200)
{"id": "8c241db0-61e8-46c5-8334-23313d4f60a3", "email": "ana-7b7291@teste.pt"}
```

**Registar o Rui** — ✅

```http
POST /auth/registo
{"nome": "Rui", "email": "rui-7b7291@teste.pt", "senha": "segredo-rui"}
→ 200 (esperado 200)
{"id": "78222262-e596-4d22-9735-d91a2d29bcdd", "email": "rui-7b7291@teste.pt"}
```

**Email repetido é recusado** — ✅

```http
POST /auth/registo
{"nome": "Outra", "email": "ana-7b7291@teste.pt", "senha": "outra-senha"}
→ 409 (esperado 409)
{"erro": "email_duplicado", "mensagem": "o email 'ana-7b7291@teste.pt' já está registado"}
```

**Senha errada é recusada** — ✅

```http
POST /auth/login
{"email": "ana-7b7291@teste.pt", "senha": "errada"}
→ 401 (esperado 401)
{"erro": "credenciais_invalidas", "mensagem": "email ou senha incorretos"}
```

**Login da Ana** — ✅

```http
POST /auth/login
{"email": "ana-7b7291@teste.pt", "senha": "segredo-ana"}
→ 200 (esperado 200)
{"token": "eyJ1c3Vhcmlv…"}
```

**Login do Rui** — ✅

```http
POST /auth/login
{"email": "rui-7b7291@teste.pt", "senha": "segredo-rui"}
→ 200 (esperado 200)
{"token": "eyJ1c3Vhcmlv…"}
```

**Abrir conta sem sessão é recusado** — ✅

```http
POST /contas
{"conta": "x-7b7291", "op_id": "op-3c7f5e9632354206bbbb"}
→ 401 (esperado 401)
{"erro": "sem_sessao", "mensagem": "falta o cabeçalho Authorization: Bearer <token>"}
```


## 3. Abrir contas: moedas e produtos

**Conta corrente em reais** — ✅

```http
POST /contas
{"conta": "ana-corrente-7b7291", "saldo_inicial": "100.00", "op_id": "op-8f8179aec4654bcd81da"}
→ 200 (esperado 200)
{"conta": "ana-corrente-7b7291", "saldo_centavos": 10000, "moeda": "BRL", "agencia": "0001", "numero": "04338636-9", "saldo": "R$ 100,00"}
```

**Conta em dólares** — ✅

```http
POST /contas
{"conta": "ana-dolares-7b7291", "saldo_inicial": "50.00", "moeda": "USD", "op_id": "op-8f0321a6ad414193af23"}
→ 200 (esperado 200)
{"conta": "ana-dolares-7b7291", "saldo_centavos": 5000, "moeda": "USD", "agencia": "0001", "numero": "36027003-4", "saldo": "US$ 50,00"}
```

**Poupança a 10 % ao ano** — ✅

```http
POST /contas
{"conta": "ana-poupanca-7b7291", "saldo_inicial": "1000.00", "produto": "poupanca", "taxa_juros": "0.10", "op_id": "op-041c8fee2fcb466fbf19"}
→ 200 (esperado 200)
{"conta": "ana-poupanca-7b7291", "saldo_centavos": 100000, "moeda": "BRL", "agencia": "0001", "numero": "31450777-9", "saldo": "R$ 1.000,00"}
```

**Prazo fixo a 12 %, 30 dias** — ✅

```http
POST /contas
{"conta": "ana-prazo-7b7291", "saldo_inicial": "500.00", "produto": "prazo_fixo", "taxa_juros": "0.12", "prazo_dias": 30, "op_id": "op-0c7fe878598e4dc8a715"}
→ 200 (esperado 200)
{"conta": "ana-prazo-7b7291", "saldo_centavos": 50000, "moeda": "BRL", "agencia": "0001", "numero": "06002888-2", "saldo": "R$ 500,00"}
```

**Conta do Rui** — ✅

```http
POST /contas
{"conta": "rui-7b7291", "saldo_inicial": "0", "op_id": "op-9c8bcd611e244bf2977e"}
→ 200 (esperado 200)
{"conta": "rui-7b7291", "saldo_centavos": 0, "moeda": "BRL", "agencia": "0001", "numero": "52035745-0", "saldo": "R$ 0,00"}
```

**A Ana vê só as suas quatro contas** — ✅

```http
GET /contas
→ 200 (esperado 200)
{"contas": [{"conta": "ana-corrente-7b7291", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 10000, "saldo": "R$ 100,00", "taxa_juros": null, "vence_em": null, "criada_em": 1795453480.9831502, "agencia": "0001", "numero": "04338636-9"}, {"conta": "ana-dolares-7b7291", "moeda": "USD", "produto": "corrente", "saldo_centavos": 5000, "saldo": "US$ 50,00", "taxa_juros": null, "vence_em": null, "criada_em": 1795453481.1510506, "agencia": "0001", "numero": "36027003-4"}, {"conta": "ana-poupanca-7b7291", "moeda": "BRL", "produto": "poupanca", "saldo_centavos": 100000, "saldo": "R$ 1.000,00",  …
```


## 4. Pedidos mal formados

**Dinheiro como número JSON** — ✅

```http
POST /contas/ana-corrente-7b7291/deposito
{"valor": 25.0, "op_id": "op-4c5ec64fb81349f490b9"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "o valor tem de vir como texto, não float: 25.0"}
```

**Três casas decimais** — ✅

```http
POST /contas/ana-corrente-7b7291/deposito
{"valor": "1.005", "op_id": "op-acc8032b37c2481b9437"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "valor mal formado: '1.005'"}
```

**Id de conta com espaços** — ✅

```http
POST /contas
{"conta": "Ana Silva", "op_id": "op-a7021e4d6f0e47c0b759"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "id de conta inválido: 'Ana Silva' (1 a 32 caracteres de a-z, 0-9, _ ou -)"}
```

**Conta repetida** — ✅

```http
POST /contas
{"conta": "ana-corrente-7b7291", "saldo_inicial": "1.00", "op_id": "op-e61122b398034a68a54e"}
→ 409 (esperado 409)
{"erro": "conta_duplicada", "mensagem": "a conta 'ana-corrente-7b7291' já existe"}
```

**Moeda desconhecida** — ✅

```http
POST /contas
{"conta": "euros-7b7291", "moeda": "EUR", "op_id": "op-ebeb3c70b1244c348e25"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "moeda desconhecida: 'EUR' (BRL, USD, PEN)"}
```

**Conta corrente com taxa de juros** — ✅

```http
POST /contas
{"conta": "estranha-7b7291", "taxa_juros": "0.10", "op_id": "op-d972deab2aa54a94a266"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "a conta corrente não tem taxa de juros nem prazo"}
```

**op_id curto demais** — ✅

```http
POST /contas/ana-corrente-7b7291/deposito
{"valor": "1.00", "op_id": "curto"}
→ 400 (esperado 400)
{"erro": "valor_invalido", "mensagem": "op_id inválido: 'curto' (8 a 64 caracteres de A-Z, a-z, 0-9, _ ou -)"}
```


## 5. Depósitos, saques e transferências

**O Rui deposita na conta da Ana (depositar é aberto)** — ✅

```http
POST /contas/ana-corrente-7b7291/deposito
{"valor": "5.00", "op_id": "op-880e42adb3524869ae65"}
→ 200 (esperado 200)
{"conta": "ana-corrente-7b7291", "moeda": "BRL"}
```

**Saque de 10,00** — ✅

```http
POST /contas/ana-corrente-7b7291/saque
{"valor": "10.00", "op_id": "op-74bc94d2da2b4a47b772"}
→ 200 (esperado 200)
{"conta": "ana-corrente-7b7291", "saldo_centavos": 9500, "moeda": "BRL", "saldo": "R$ 95,00"}
```

**Saque maior que o saldo** — ✅

```http
POST /contas/ana-corrente-7b7291/saque
{"valor": "9999.00", "op_id": "op-0a074336a1ff47dda562"}
→ 422 (esperado 422)
{"erro": "saldo_insuficiente", "mensagem": "ana-corrente-7b7291 tem R$ 95,00 e a operação pede R$ 9.999,00"}
```

**Saque de prazo fixo antes de vencer** — ✅

```http
POST /contas/ana-prazo-7b7291/saque
{"valor": "1.00", "op_id": "op-7de869e9b7b5405d9956"}
→ 409 (esperado 409)
{"erro": "conta_bloqueada", "mensagem": "ana-prazo-7b7291 é um prazo fixo e só vence a 2026-12-23"}
```

**Transferência de 25,00 para o Rui** — ✅

```http
POST /transferencias
{"de": "ana-corrente-7b7291", "para": "rui-7b7291", "valor": "25.00", "op_id": "op-6690b55ad76549ceba8d"}
→ 200 (esperado 200)
{"de": "ana-corrente-7b7291", "para": "rui-7b7291", "moeda": "BRL", "saldos_centavos": {"ana-corrente-7b7291": 7000}, "saldos": {"ana-corrente-7b7291": "R$ 70,00"}}
```

**A mesma transferência repetida devolve o mesmo corpo** — ✅

```http
POST /transferencias
{"de": "ana-corrente-7b7291", "para": "rui-7b7291", "valor": "25.00", "op_id": "op-6690b55ad76549ceba8d"}
→ 200 (esperado 200)
{"de": "ana-corrente-7b7291", "para": "rui-7b7291", "moeda": "BRL", "saldos_centavos": {"ana-corrente-7b7291": 7000}, "saldos": {"ana-corrente-7b7291": "R$ 70,00"}}
```

**O mesmo op_id com outro valor devolve o guardado** — ✅

```http
POST /transferencias
{"de": "ana-corrente-7b7291", "para": "rui-7b7291", "valor": "70.00", "op_id": "op-6690b55ad76549ceba8d"}
→ 200 (esperado 200)
{"de": "ana-corrente-7b7291", "para": "rui-7b7291", "moeda": "BRL", "saldos_centavos": {"ana-corrente-7b7291": 7000}, "saldos": {"ana-corrente-7b7291": "R$ 70,00"}}
```

**O Rui só recebeu uma vez** — ✅

```http
GET /contas/rui-7b7291
→ 200 (esperado 200)
{"conta": "rui-7b7291", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 2500, "saldo": "R$ 25,00", "taxa_juros": null, "vence_em": null, "criada_em": 1795453481.61818, "agencia": "0001", "numero": "52035745-0"}
```


## 6. Dono da conta

**O Rui não consulta a conta da Ana** — ✅

```http
GET /contas/ana-corrente-7b7291
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'ana-corrente-7b7291' não te pertence"}
```

**O Rui não vê o extrato da Ana** — ✅

```http
GET /contas/ana-corrente-7b7291/extrato
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'ana-corrente-7b7291' não te pertence"}
```

**O Rui não saca da conta da Ana** — ✅

```http
POST /contas/ana-corrente-7b7291/saque
{"valor": "1.00", "op_id": "op-a89cc88d61fc4c59a94a"}
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'ana-corrente-7b7291' não te pertence"}
```

**O Rui não transfere a partir da conta da Ana** — ✅

```http
POST /transferencias
{"de": "ana-corrente-7b7291", "para": "rui-7b7291", "valor": "1.00", "op_id": "op-b5338a1d68a1453f84bd"}
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'ana-corrente-7b7291' não te pertence"}
```

**O Rui não repete um op_id da Ana para ler a resposta dela** — ✅

```http
POST /transferencias
{"de": "ana-corrente-7b7291", "para": "rui-7b7291", "valor": "25.00", "op_id": "op-6690b55ad76549ceba8d"}
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'ana-corrente-7b7291' não te pertence"}
```


## 7. Moedas e câmbio

**Transferência simples entre moedas é recusada** — ✅

```http
POST /transferencias
{"de": "ana-dolares-7b7291", "para": "ana-corrente-7b7291", "valor": "1.00", "op_id": "op-4e73930712a54e499389"}
→ 409 (esperado 409)
{"erro": "moedas_diferentes", "mensagem": "ana-dolares-7b7291 está em USD e ana-corrente-7b7291 em BRL; entre moedas é um câmbio (/transferencias/conversao)"}
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
{"de": "ana-dolares-7b7291", "para": "ana-corrente-7b7291", "valor": "10.00", "op_id": "op-915b27387f0e4d0fbe28"}
→ 200 (esperado 200)
{"de": "ana-dolares-7b7291", "para": "ana-corrente-7b7291", "valor_centavos": 1000, "valor_destino_centavos": 5430, "taxa_milionesimos": 5430000, "moedas": {"ana-dolares-7b7291": "USD", "ana-corrente-7b7291": "BRL"}, "saldos_centavos": {"ana-dolares-7b7291": 4000, "ana-corrente-7b7291": 12430}, "saldos": {"ana-dolares-7b7291": "US$ 40,00", "ana-corrente-7b7291": "R$ 124,30"}, "taxa": "5.430000", "valor": "US$ 10,00", "valor_destino": "R$ 54,30"}
```

**Registar uma taxa nova, 6,00** — ✅

```http
POST /admin/taxas
{"moeda_origem": "USD", "moeda_destino": "BRL", "taxa": "6.00"}
→ 200 (esperado 200)
{"moeda_origem": "USD", "moeda_destino": "BRL", "taxa_milionesimos": 6000000, "vigente_desde": 1795453484.3597624, "taxa": "6.000000"}
```

**O câmbio repetido mantém a taxa de então** — ✅

```http
POST /transferencias/conversao
{"de": "ana-dolares-7b7291", "para": "ana-corrente-7b7291", "valor": "10.00", "op_id": "op-915b27387f0e4d0fbe28"}
→ 200 (esperado 200)
{"de": "ana-dolares-7b7291", "para": "ana-corrente-7b7291", "moedas": {"ana-dolares-7b7291": "USD", "ana-corrente-7b7291": "BRL"}, "valor_centavos": 1000, "saldos_centavos": {"ana-dolares-7b7291": 4000, "ana-corrente-7b7291": 12430}, "taxa_milionesimos": 5430000, "valor_destino_centavos": 5430, "saldos": {"ana-dolares-7b7291": "US$ 40,00", "ana-corrente-7b7291": "R$ 124,30"}, "taxa": "5.430000", "valor": "US$ 10,00", "valor_destino": "R$ 54,30"}
```

**Um câmbio novo usa a taxa nova** — ✅

```http
POST /transferencias/conversao
{"de": "ana-dolares-7b7291", "para": "ana-corrente-7b7291", "valor": "10.00", "op_id": "op-bcf6e037d748432db733"}
→ 200 (esperado 200)
{"de": "ana-dolares-7b7291", "para": "ana-corrente-7b7291", "valor_centavos": 1000, "valor_destino_centavos": 6000, "taxa_milionesimos": 6000000, "moedas": {"ana-dolares-7b7291": "USD", "ana-corrente-7b7291": "BRL"}, "saldos_centavos": {"ana-dolares-7b7291": 3000, "ana-corrente-7b7291": 18430}, "saldos": {"ana-dolares-7b7291": "US$ 30,00", "ana-corrente-7b7291": "R$ 184,30"}, "taxa": "6.000000", "valor": "US$ 10,00", "valor_destino": "R$ 60,00"}
```

**Autotransferência entre moedas** — ✅

```http
POST /transferencias/autotransferencia
{"de": "ana-dolares-7b7291", "para": "ana-corrente-7b7291", "valor": "1.00", "op_id": "op-7b0128845947406bb013"}
→ 200 (esperado 200)
{"de": "ana-dolares-7b7291", "para": "ana-corrente-7b7291", "valor_centavos": 100, "valor_destino_centavos": 600, "taxa_milionesimos": 6000000, "moedas": {"ana-dolares-7b7291": "USD", "ana-corrente-7b7291": "BRL"}, "saldos_centavos": {"ana-dolares-7b7291": 2900, "ana-corrente-7b7291": 19030}, "saldos": {"ana-dolares-7b7291": "US$ 29,00", "ana-corrente-7b7291": "R$ 190,30"}, "taxa": "6.000000", "valor": "US$ 1,00", "valor_destino": "R$ 6,00"}
```

**Autotransferência para conta alheia é recusada** — ✅

```http
POST /transferencias/autotransferencia
{"de": "ana-corrente-7b7291", "para": "rui-7b7291", "valor": "1.00", "op_id": "op-768b160725704f97bd82"}
→ 403 (esperado 403)
{"erro": "proibido", "mensagem": "a conta 'rui-7b7291' não te pertence"}
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
{"de": "ana-corrente-7b7291", "sistema_externo_id": "banco-externo", "valor": "1.00", "op_id": "op-19a7f3e5134a4c269c7b"}
→ 200 (esperado 200)
{"conta": "ana-corrente-7b7291", "moeda": "BRL", "estado": "confirmada", "op_original": "op-19a7f3e5134a4c269c7b", "saldo_centavos": 18930, "valor_centavos": 100, "referencia_externa": "ed7f2f16-a3d9-5143-86b7-2c0976f7a3ce", "saldo": "R$ 189,30"}
```

**Envio 5: rejeitada (repetido para registo)** — ✅

```http
POST /transferencias/externa
{"de": "ana-corrente-7b7291", "sistema_externo_id": "banco-externo", "valor": "1.00", "op_id": "op-a3f5000f974f4eccb9d6"}
→ 200 (esperado 200)
{"conta": "ana-corrente-7b7291", "moeda": "BRL", "estado": "rejeitada", "op_original": "op-a3f5000f974f4eccb9d6", "saldo_centavos": 18630, "valor_centavos": 100, "referencia_externa": null, "saldo": "R$ 186,30"}
```

Foram precisos 5 envios para ver os dois desfechos. A repetição de cada um devolveu o desfecho gravado, sem voltar a perguntar ao outro banco.

**Banco desconhecido** — ✅

```http
POST /transferencias/externa
{"de": "ana-corrente-7b7291", "sistema_externo_id": "nao-existe", "valor": "1.00", "op_id": "op-0c99dfc638c54f558a6d"}
→ 404 (esperado 404)
{"erro": "sistema_externo_inexistente", "mensagem": "sistema externo desconhecido: 'nao-existe'"}
```

**Sem saldo, nem chega ao outro banco** — ✅

```http
POST /transferencias/externa
{"de": "ana-corrente-7b7291", "sistema_externo_id": "banco-externo", "valor": "99999.00", "op_id": "op-13735ca93ea8449fab34"}
→ 422 (esperado 422)
{"erro": "saldo_insuficiente", "mensagem": "ana-corrente-7b7291 tem R$ 186,30 e a operação pede R$ 99.999,00"}
```


## 9. Juros

**Tick de juros** — ✅

```http
POST /admin/juros
→ 200 (esperado 200)
{"ate": 1795453489.4304793, "creditadas": []}
```

A poupança abriu há segundos: os juros devidos ainda não chegam a um centavo, por isso a lista sai vazia. O cálculo ao longo de um ano e o prazo fixo vencido estão provados em `tests/unitarios/teste_produtos.py`, onde o instante é um argumento e não é preciso esperar.


## 10. Concorrência

**20 depósitos de 1,00 ao mesmo tempo (20 aceites): nenhum se perde** — ✅

```http
GET /contas/rui-7b7291
→ 200 (esperado 200)
{"conta": "rui-7b7291", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 4500, "saldo": "R$ 45,00", "taxa_juros": null, "vence_em": null, "criada_em": 1795453481.61818, "agencia": "0001", "numero": "52035745-0"}
```

**20 saques de 1,00 sobre 10,00 ao mesmo tempo: 10 aceites, 10 recusados** — ✅

```http
GET /contas/rui-pequena-7b7291
→ 200 (esperado 200)
{"conta": "rui-pequena-7b7291", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 0, "saldo": "R$ 0,00", "taxa_juros": null, "vence_em": null, "criada_em": 1795453492.0683796, "agencia": "0001", "numero": "31821881-0"}
```


## 11. Extrato e auditoria

**Extrato da conta corrente da Ana** — ✅

```http
GET /contas/ana-corrente-7b7291/extrato
→ 200 (esperado 200)
{"conta": "ana-corrente-7b7291", "moeda": "BRL", "movimentos": [{"indice": 1737, "tipo": "criar_conta", "valor_centavos": 10000, "valor": "R$ 100,00", "contraparte": null, "saldo_depois_centavos": 10000, "saldo_depois": "R$ 100,00", "instante": 1795453480.9831502}, {"indice": 1742, "tipo": "deposito", "valor_centavos": 500, "valor": "R$ 5,00", "contraparte": null, "saldo_depois_centavos": 10500, "saldo_depois": "R$ 105,00", "instante": 1795453482.6114244}, {"indice": 1743, "tipo": "saque", "valor_centavos": -1000, "valor": "-R$ 10,00", "contraparte": null, "saldo_depois_centavos": 9500, "saldo …
```

**Auditoria: cada moeda bate** — ✅

```http
GET /auditoria
→ 200 (esperado 200)
{"divergente": false, "moedas": [{"moeda": "BRL", "total_centavos": 1849363, "total": "R$ 18.493,63", "total_esperado_centavos": 1849363, "total_esperado": "R$ 18.493,63", "divergencia_centavos": 0, "divergencia": "R$ 0,00"}, {"moeda": "USD", "total_centavos": 2900, "total": "US$ 29,00", "total_esperado_centavos": 2900, "total_esperado": "US$ 29,00", "divergencia_centavos": 0, "divergencia": "US$ 0,00"}]}
```


## 12. Replicação e queda do primário a meio de transferências

Antes da queda, as três bases têm de ser iguais — cada escrita acima foi confirmada pela maioria e aplicada nos três nós:

| Nó | Base de dados do nó |
|---|---|
| A | 24 utilizadores · 104 contas · 1752 operações · log até 1789 · md5 6feb59d20740 |
| B | 24 utilizadores · 104 contas · 1752 operações · log até 1789 · md5 6feb59d20740 |
| C | 24 utilizadores · 104 contas · 1752 operações · log até 1789 · md5 6feb59d20740 |

`docker compose kill no-b` — o primário (nó B, epoch 30) morre a meio de transferências concorrentes, sem fechar nada.

O nó **C** passou a primário **1.23 s** depois do `kill`. Durante a transição, 16 tentativas receberam um erro (`[503]`) e foram repetidas com o mesmo op_id; 21 transferências foram confirmadas no total.

**Outro nó é primário, com epoch maior** — ✅

```http
GET /interno/estado
→ 200 (esperado 200)
{"no": "C", "papel": "primário", "epoch": 31, "lider": "C", "ultimo_indice": 1811, "indice_commit": 1811, "ultimo_aplicado": 1811, "pronto": true, "falhas": {"atraso_ms": 0, "isolado_de": []}}
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
{"contas": [{"conta": "ana-corrente-7b7291", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 18609, "saldo": "R$ 186,09", "taxa_juros": null, "vence_em": null, "criada_em": 1795453480.9831502, "agencia": "0001", "numero": "04338636-9"}, {"conta": "ana-dolares-7b7291", "moeda": "USD", "produto": "corrente", "saldo_centavos": 2900, "saldo": "US$ 29,00", "taxa_juros": null, "vence_em": null, "criada_em": 1795453481.1510506, "agencia": "0001", "numero": "36027003-4"}, {"conta": "ana-poupanca-7b7291", "moeda": "BRL", "produto": "poupanca", "saldo_centavos": 100000, "saldo": "R$ 1.000,00",  …
```

**Cada transferência confirmada ao cliente está lá** — ✅

```http
GET /contas/rui-7b7291
→ 200 (esperado 200)
{"conta": "rui-7b7291", "moeda": "BRL", "produto": "corrente", "saldo_centavos": 4521, "saldo": "R$ 45,21", "taxa_juros": null, "vence_em": null, "criada_em": 1795453481.61818, "agencia": "0001", "numero": "52035745-0"}
```

**A transferência do início, repetida, devolve o mesmo corpo** — ✅

```http
POST /transferencias
{"de": "ana-corrente-7b7291", "para": "rui-7b7291", "valor": "25.00", "op_id": "op-6690b55ad76549ceba8d"}
→ 200 (esperado 200)
{"de": "ana-corrente-7b7291", "para": "rui-7b7291", "moeda": "BRL", "saldos_centavos": {"ana-corrente-7b7291": 7000}, "saldos": {"ana-corrente-7b7291": "R$ 70,00"}}
```

**O novo primário aceita escritas** — ✅

```http
POST /contas/ana-corrente-7b7291/deposito
{"valor": "1.00", "op_id": "op-837ce5dc80e34f559a89"}
→ 200 (esperado 200)
{"conta": "ana-corrente-7b7291", "moeda": "BRL"}
```

**O dinheiro total não mudou com a queda** — ✅

```http
GET /auditoria
→ 200 (esperado 200)
{"divergente": false, "moedas": [{"moeda": "BRL", "total_centavos": 1849463, "total": "R$ 18.494,63", "total_esperado_centavos": 1849463, "total_esperado": "R$ 18.494,63", "divergencia_centavos": 0, "divergencia": "R$ 0,00"}, {"moeda": "USD", "total_centavos": 2900, "total": "US$ 29,00", "total_esperado_centavos": 2900, "total_esperado": "US$ 29,00", "divergencia_centavos": 0, "divergencia": "US$ 0,00"}]}
```

`docker compose start no-b` — o nó morto volta.

**O nó B voltou como réplica e pôs-se em dia** — ✅

```http
GET http://localhost:8002/interno/estado
→ 200 (esperado 200)
{"no": "B", "papel": "réplica", "epoch": 31, "lider": "C", "ultimo_indice": 1812, "indice_commit": 1812, "ultimo_aplicado": 1812, "pronto": true, "falhas": {"atraso_ms": 0, "isolado_de": []}}
```

E as três bases voltam a ser iguais — incluindo o que aconteceu enquanto o nó B estava morto:

| Nó | Base de dados do nó |
|---|---|
| A | 24 utilizadores · 104 contas · 1774 operações · log até 1812 · md5 f213b0d6eb10 |
| B | 24 utilizadores · 104 contas · 1774 operações · log até 1812 · md5 f213b0d6eb10 |
| C | 24 utilizadores · 104 contas · 1774 operações · log até 1812 · md5 f213b0d6eb10 |

**Impressão digital igual nas três bases** — ✅

```http
GET /saude
→ 200 (esperado 200)
{"balanceador": "ativo"}
```
