# Inventário das instâncias implantadas

Estado real do que está a correr na AWS — complementa (não repete) o
[`GUIA-IMPLANTACAO.md`](GUIA-IMPLANTACAO.md), que é o "como se faz" genérico
e reutilizável; este ficheiro é a "fotografia" do que existe hoje, e tem de
ser atualizado à mão sempre que algo mude (uma instância nova, uma
reiniciada, uma terminada).

> Estas instâncias são as de uma implantação anterior, com dois nós; o código
> atual do Protótipo 2 (três nós com replicação) ainda não foi implantado nelas.

**Região:** `us-east-2` (Ohio)

## Decisão atual: 2 nós, não 3 — pela quota de vCPU da conta

Enquanto se aprova o aumento de quota da AWS (`Running On-Demand Standard
... instances`, ver `GUIA-IMPLANTACAO.md`), trabalha-se com **2 nós** (A e B)
em vez dos 3 que o desenho pede. É uma decisão consciente e temporária, não
o objetivo final — significa que, por agora, o sistema **não tolera nenhuma
queda sem perder a disponibilidade de escrita** (com 2 nós a maioria é 2;
perder qualquer um deixa o outro sem maioria). O nó C entra assim que a AWS
aprovar a quota — ver o Passo 1 de `GUIA-IMPLANTACAO.md` para o relançar em
`us-east-2c`.

## Instâncias

| Name | ID da instância | Papel | Zona (AZ) | Tipo | IP pública | IP privada | Estado (ao anotar) |
|---|---|---|---|---|---|---|---|
| `postgres-a` | `i-0794aefb11a9a02cb` | Postgres do nó A | `us-east-2a` | `t3.micro` | `3.148.185.193` | `172.31.12.43` | Em execução |
| `backend-a` | `i-0e051a5823e5833e3` | Backend do nó A | `us-east-2a` | `t3.micro` | `3.129.73.132` | `172.31.12.211` | Em execução |
| `postgres-b` | `i-0845c11b376c3b824` | Postgres do nó B | `us-east-2b` | `t3.micro` | `3.16.21.151` | `172.31.28.108` | Em execução |
| `backend-b` | `i-0829dbdfa5e7fb697` | Backend do nó B | `us-east-2b` | `t3.micro` | `3.142.185.122` | `172.31.29.55` | A inicializar |

**Pendente:** `postgres-c` / `backend-c` em `us-east-2c`, quando se aprovar a
quota de vCPU.

## Segurança — o que NÃO vai neste ficheiro

De propósito, esta tabela não inclui senhas do Postgres, `SECRET_KEY`, nem
nenhum segredo — são dados que não devem ficar num ficheiro versionado no
git (`INVENTARIO-INSTANCIAS.md` sobe para o repositório, ao contrário de
`config/cluster.json`, que está no `.gitignore`). Guardam-se à parte (um
gestor de senhas, ou variáveis de ambiente locais), não aqui.

## Endereços para copiar para `config/cluster.json` / `CLUSTER_CONFIG_JSON`

```json
{
  "nos": [
    {"id": "A", "endereco": "172.31.12.211", "porta": 8001},
    {"id": "B", "endereco": "172.31.29.55", "porta": 8001}
  ]
}
```

(IP **privada** de cada `backend-X` — para o balanceador em Lambda, usar em
vez disso os IPs **públicos** da tabela acima, ver `GUIA-IMPLANTACAO.md`
Passo 4.5)

## Nota sobre os IPs públicos

Mudam sempre que se para e se volta a arrancar uma instância (a não ser que
se reserve um IP elástico, que, se não estiver associado a uma instância a
correr, é cobrado). Antes de cada sessão de testes, volta-se a esta tabela e
atualiza-se com `aws ec2 describe-instances` ou pela consola — se o
balanceador ou o `cluster.json` ficarem com um IP antigo, aparecem erros de
ligação que parecem do protocolo mas são só um IP desatualizado.
