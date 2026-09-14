# Imagen del balanceador — servicio propio, sin estado (ver GUIA-DESPLIEGUE.md).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY balanceador/ ./balanceador/

# La lista de nodos se monta como volumen (mismo cluster.json que usan los
# nodos) — no se hornea dentro de la imagen, para no reconstruir la imagen
# cada vez que cambian direcciones.
ENV CLUSTER_CONFIG=/config/cluster.json

EXPOSE 8000

CMD ["uvicorn", "balanceador.main:app", "--host", "0.0.0.0", "--port", "8000"]
