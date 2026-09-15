# A imagem do nó. Ver compose.yaml para como se levanta tudo de uma vez.
FROM python:3.12-slim

WORKDIR /app

COPY requisitos.txt .
RUN pip install --no-cache-dir -r requisitos.txt

COPY banco/ ./banco/

# `--id` e `--porta` chegam por variável de ambiente para a mesma imagem servir
# qualquer nó na etapa 2, sem ter de ser reconstruída.
ENV NO_ID=A
ENV PORTA=8001

EXPOSE 8001

CMD ["python", "-m", "banco.servidor"]
