# Imagen del backend de un nodo — ver GUIA-DESPLIEGUE.md.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY banco/ ./banco/

# --id y --puerto se pasan por variables de entorno (NODO_ID, PUERTO), para
# que la misma imagen sirva a cualquiera de los 2-3 nodos — solo cambia la
# configuración con la que se levanta el contenedor.
ENV NODO_ID=A
ENV PUERTO=8001

EXPOSE 8001

CMD ["python", "-m", "banco.servidor"]
