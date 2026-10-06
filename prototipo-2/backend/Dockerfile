# Imagem de um nó — a mesma para A, B e C; só muda o ambiente com que arranca
# (NO_ID, PGHOST). Ver docs/GUIA-IMPLANTACAO.md.
FROM python:3.12-slim

WORKDIR /app

COPY requisitos.txt .
RUN pip install --no-cache-dir -r requisitos.txt

COPY banco/ ./banco/

ENV NO_ID=A
ENV PORTA=8001

EXPOSE 8001

CMD ["python", "-m", "banco.servidor"]
