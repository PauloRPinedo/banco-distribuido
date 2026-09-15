# Revisão do estado real do projeto e recomendações

Documento de feedback, não uma etapa entregue. Registra o que foi verificado no
código e nos documentos existentes, e o que precisa de uma decisão do grupo antes
de avançar para "frontend + backend + BD replicada". A decisão em si fica em
[`adr/ADR-0001-persistencia-replicacao-implantacao.md`](adr/ADR-0001-persistencia-replicacao-implantacao.md).

---

## 1. Protótipo 1 — verificado, cumpre o que o README promete

Corri `python -m unittest discover -s tests` dentro de `prototipo-1/`:
**102 de 103 testes passam.**

O único que falha é `teste_erro_tem_tres_linhas_e_a_ultima_diz_o_que_fazer`, e a
causa é a *codepage* do console do Windows (o caracter `→` não sobrevive fora de
UTF-8) — não é um erro de lógica do domínio, e RNF-09 só promete um comando em
**Linux e macOS**, não Windows. Em Linux/macOS o esperado é passar os 103.

Confirmado por leitura do código (`banco/dominio/`, `banco/persistencia/wal.py`,
`banco/cluster/concorrencia.py`): dinheiro sempre em centavos `int`, WAL com
`write`+`flush`+`fsync`, *locks* por conta em ordem total, deduplicação por
`op_id`. Bate com o que `SPECS.md` e o `RELATORIO.md` descrevem.

**Conclusão: Protótipo 1 cumpre F-01 a F-07, F-12, RF-01 a RF-08, RF-14, RF-17,
RNF-01 e RNF-09.**

## 2. Protótipo 2 — ainda não existe código

`prototipo-2/` contém só `README.md`. Não há pacote `banco/` nesta pasta, nem uma
linha das 10 subfases do `ROADMAP.md` (config de cluster, log de replicação,
quórum, heartbeat, eleição, reintegração). O README já diz "não iniciada" — é
honesto — mas vale deixar explícito para quem for avaliar: **nenhum dos
requisitos F-08, F-09, RF-09 a RF-13, RNF-01 a RNF-03 e RNF-06 tem implementação
ainda.** Tudo isso é o que resolve tolerância a falhas, que é o assunto central
da pergunta sobre replicação.

## 3. Os dois documentos novos (`modelamiento_datos.md`, `diagramas_plantuml.md`)

Três observações, nenhuma delas um erro grave, mas que valem registro:

1. **Idioma.** `CONVENCOES.md` §1 fixa português para toda a documentação, com
   exceção só das siglas técnicas (`epoch`, `WAL`, `quorum`...). Os dois
   documentos novos estão inteiramente em espanhol. Se ficam assim, é uma
   exceção à convenção que o grupo deveria decidir e registrar — não algo para
   "corrigir" sem conversar, porque pode ser proposital (ex.: para uso pessoal
   fora da entrega).
2. **Modelo diferente do que `SPECS.md` já especifica.** `SPECS.md` §3.3–4.1
   define o estado persistente como um WAL em JSONL por nó, sem SGBD. O modelo
   novo (`Usuario`, `Cuenta`, `Operación`, `Servidor`, `RegistroReplicación`)
   pressupõe um motor relacional. O próprio `modelamiento_datos.md` reconhece
   isso na seção 7 ("o código atual usa JSON... isto é o modelo lógico"), o que
   é correto — mas significa que esse modelo ainda **não tem decisão de
   arquitetura por trás**, só o desenho de tabelas. É exatamente a lacuna que a
   ADR cobre.
3. **Entidade `Usuario` é uma extensão, não parte do escopo aprovado.**
   `proposta.md` não tem essa entidade nem um RF-xx correspondente. Não invalida
   o design, mas se for adiante deveria entrar como extensão documentada (o
   próprio arquivo já diz isso na introdução), e idealmente ganhar um F-xx/RF-xx
   próprio se for para a defesa.

## 4. A tensão central da pergunta "frontend + backend + BD replicada"

`proposta.md`, seção **Restrições**, é explícita:

> O consenso e o protocolo de transações são implementados do zero, sem
> bibliotecas prontas para essas funções.

Isso é o que RF-09 a RF-13 avaliam no Protótipo 2: eleição por maioria, quórum,
`epoch`/*fencing*, replicação por log — feitos pelo grupo, não por um SGBD.

Migrar para "backend + BD replicada" onde a replicação é a de um Postgres
gerenciado (Supabase, RDS Multi-AZ, Cloud SQL HA) **entrega a um terceiro** a
parte que é avaliada. Duas consequências práticas:

- Se a BD gerenciada resolve replicação e falha, os RF-09 a RF-13 deste projeto
  deixam de ter onde acontecer — não é mais o mesmo trabalho, é outro projeto
  com a mesma casca.
- Especificamente sobre **dois projetos Supabase**: eles não se replicam entre
  si automaticamente. São dois Postgres independentes; sincronizá-los exigiria
  escrever a lógica de replicação na aplicação — ou seja, o mesmo trabalho que
  os nós Python com WAL já fazem, só que com um salto de rede a mais até um
  Postgres. Não poupa o trabalho do curso, acrescenta uma camada.
- E mesmo dentro de **um só** projeto Supabase: a camada gratuita é uma única
  instância Postgres com backups diários, sem *failover* automático. Não dá
  tolerância a falhas de graça — isso é recurso pago (`Point-in-time recovery` /
  réplicas de leitura ficam nos planos Pro/Team).

Isto não decide a pergunta por vocês — decide-se em grupo, e por isso vai para a
ADR como pergunta em aberto com uma recomendação.
