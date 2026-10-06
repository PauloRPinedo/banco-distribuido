# Imagem do balanceador — serviço próprio, sem estado (ver GUIA-IMPLANTACAO.md).
FROM python:3.12-slim

WORKDIR /app

COPY requisitos.txt .
RUN pip install --no-cache-dir -r requisitos.txt

COPY balanceador/ ./balanceador/

# A lista de nós monta-se como volume (o mesmo cluster.json que os nós usam) —
# não vai dentro da imagem, para não a reconstruir sempre que mudam endereços.
ENV CLUSTER_CONFIG=/config/cluster.json

EXPOSE 8000

CMD ["uvicorn", "balanceador.main:app", "--host", "0.0.0.0", "--port", "8000"]
