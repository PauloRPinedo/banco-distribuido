# Medição de desempenho (RNF-04, RNF-05)

Gerado por `provas/scripts/medir_desempenho.py` em 2026-11-23 14:00, 10 s por nível.

Máquina: 11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz, 8 núcleos lógicos, Linux 6.12.117+deb13-amd64. Os três nós, as três bases, o balanceador e o cliente correm todos nela, no `docker compose`.

Metas: 500 transações por segundo (RNF-04) e p99 abaixo de 200 ms (RNF-05).

## Escritas, pelo balanceador

| Clientes | Pedidos | Erros | Por segundo | p50 | p95 | p99 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 55 | 0 | 5 | 179.0 ms | 223.9 ms | 259.6 ms |
| 2 | 94 | 0 | 9 | 212.8 ms | 253.1 ms | 303.3 ms |
| 4 | 96 | 0 | 9 | 427.8 ms | 481.7 ms | 507.4 ms |
| 8 | 101 | 0 | 9 | 833.7 ms | 900.0 ms | 912.8 ms |
| 16 | 104 | 0 | 9 | 1727.7 ms | 1899.0 ms | 1934.1 ms |
| 32 | 29 | 66 | 2 | 2012.3 ms | 3687.9 ms | 3697.9 ms |

## Leituras, pelo balanceador

| Clientes | Pedidos | Erros | Por segundo | p50 | p95 | p99 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 143 | 0 | 14 | 64.1 ms | 94.3 ms | 108.8 ms |
| 2 | 251 | 0 | 25 | 77.1 ms | 104.2 ms | 119.0 ms |
| 4 | 376 | 0 | 37 | 103.9 ms | 138.3 ms | 235.5 ms |
| 8 | 444 | 0 | 44 | 175.1 ms | 237.8 ms | 258.5 ms |
| 16 | 440 | 0 | 43 | 366.3 ms | 516.9 ms | 594.8 ms |
| 32 | 484 | 0 | 47 | 680.7 ms | 897.8 ms | 1022.5 ms |

## Escritas, ao primário (nó B, direto)

| Clientes | Pedidos | Erros | Por segundo | p50 | p95 | p99 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 79 | 0 | 8 | 130.6 ms | 152.9 ms | 160.6 ms |
| 2 | 98 | 0 | 10 | 203.5 ms | 257.1 ms | 319.4 ms |
| 4 | 101 | 0 | 10 | 399.3 ms | 449.6 ms | 460.0 ms |
| 8 | 105 | 0 | 10 | 802.2 ms | 874.3 ms | 895.4 ms |
| 16 | 108 | 0 | 9 | 1642.8 ms | 1879.7 ms | 1974.6 ms |
| 32 | 127 | 0 | 10 | 3292.1 ms | 3365.1 ms | 3379.7 ms |

## Leituras, ao primário (nó B, direto)

| Clientes | Pedidos | Erros | Por segundo | p50 | p95 | p99 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 414 | 0 | 41 | 23.4 ms | 29.2 ms | 33.7 ms |
| 2 | 733 | 0 | 73 | 26.2 ms | 36.9 ms | 45.5 ms |
| 4 | 1150 | 0 | 115 | 33.2 ms | 48.9 ms | 62.8 ms |
| 8 | 1261 | 0 | 126 | 58.7 ms | 96.3 ms | 145.8 ms |
| 16 | 1341 | 0 | 133 | 114.5 ms | 176.2 ms | 209.1 ms |
| 32 | 1428 | 0 | 140 | 220.4 ms | 303.9 ms | 355.5 ms |
