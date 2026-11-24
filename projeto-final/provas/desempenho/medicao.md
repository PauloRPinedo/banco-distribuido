# Medição de desempenho (RNF-04, RNF-05)

Gerado por `provas/scripts/medir_desempenho.py` em 2026-11-23 15:17, 10 s por nível.

Máquina: 11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz, 8 núcleos lógicos, Linux 6.12.117+deb13-amd64. Os três nós, as três bases, o balanceador e o cliente correm todos nela, no `docker compose`.

Metas: 500 transações por segundo (RNF-04) e p99 abaixo de 200 ms (RNF-05).

## Escritas, pelo balanceador

| Clientes | Pedidos | Erros | Por segundo | p50 | p95 | p99 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 299 | 0 | 30 | 32.6 ms | 40.6 ms | 50.1 ms |
| 2 | 430 | 0 | 43 | 45.4 ms | 57.6 ms | 68.5 ms |
| 4 | 594 | 0 | 59 | 64.7 ms | 90.0 ms | 109.1 ms |
| 8 | 734 | 0 | 73 | 105.0 ms | 149.7 ms | 176.7 ms |
| 16 | 840 | 0 | 83 | 183.6 ms | 271.7 ms | 322.2 ms |
| 32 | 886 | 0 | 87 | 354.1 ms | 520.0 ms | 611.6 ms |

## Leituras, pelo balanceador

| Clientes | Pedidos | Erros | Por segundo | p50 | p95 | p99 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 954 | 0 | 95 | 10.0 ms | 14.0 ms | 19.2 ms |
| 2 | 1531 | 0 | 153 | 12.8 ms | 17.8 ms | 23.4 ms |
| 4 | 1858 | 0 | 186 | 20.7 ms | 32.0 ms | 42.6 ms |
| 8 | 1919 | 0 | 191 | 39.0 ms | 67.7 ms | 87.0 ms |
| 16 | 2092 | 0 | 208 | 72.8 ms | 115.2 ms | 143.8 ms |
| 32 | 1803 | 0 | 177 | 166.2 ms | 285.8 ms | 373.2 ms |

## Escritas, ao primário (nó A, direto)

| Clientes | Pedidos | Erros | Por segundo | p50 | p95 | p99 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 334 | 0 | 33 | 28.7 ms | 38.0 ms | 52.9 ms |
| 2 | 439 | 0 | 44 | 44.7 ms | 56.7 ms | 64.5 ms |
| 4 | 657 | 0 | 65 | 59.3 ms | 76.4 ms | 91.8 ms |
| 8 | 818 | 0 | 81 | 95.3 ms | 130.0 ms | 151.9 ms |
| 16 | 999 | 0 | 99 | 156.2 ms | 200.2 ms | 282.6 ms |
| 32 | 1112 | 0 | 110 | 287.9 ms | 343.5 ms | 370.1 ms |

## Leituras, ao primário (nó A, direto)

| Clientes | Pedidos | Erros | Por segundo | p50 | p95 | p99 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1732 | 0 | 173 | 5.2 ms | 9.6 ms | 16.5 ms |
| 2 | 2721 | 0 | 272 | 7.1 ms | 10.3 ms | 12.5 ms |
| 4 | 2882 | 0 | 288 | 13.4 ms | 19.5 ms | 24.3 ms |
| 8 | 2900 | 0 | 289 | 26.4 ms | 39.4 ms | 50.2 ms |
| 16 | 3185 | 0 | 317 | 49.6 ms | 65.5 ms | 73.2 ms |
| 32 | 3167 | 0 | 314 | 99.8 ms | 132.7 ms | 174.0 ms |
