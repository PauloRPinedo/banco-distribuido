Ver inspect

docker inspect backend-a --format '{{range .Config.Env}}{{println .}}{{end}}'


Aqui el comando para copiar

cat > schema.sql <<'EOF'
(todo el contenido schema.sql)
EOF

Levantar postgre-b, luego de copiar el archivo schema.sql

docker run -d --name postgres-b -p 5432:5432 \
  --restart unless-stopped --memory=512m \
  -e POSTGRES_DB=banco -e POSTGRES_USER=banco -e POSTGRES_PASSWORD='TU_PGPASSWORD' \
  -v ~/schema.sql:/docker-entrypoint-initdb.d/schema.sql:ro \
  postgres:16-alpine

Lo mismo para postgre-c
docker run -d --name postgres-c -p 5432:5432 \
  --restart unless-stopped --memory=512m \
  -e POSTGRES_DB=banco -e POSTGRES_USER=banco -e POSTGRES_PASSWORD='TU_PGPASSWORD' \
  -v ~/schema.sql:/docker-entrypoint-initdb.d/schema.sql:ro \
  postgres:16-alpine

Comprobar B

docker ps
docker exec postgres-b psql -U banco -d banco -c '\dt'

Comprobar C

docker ps
docker exec postgres-c psql -U banco -d banco -c '\dt'


Vamos arrancar backend-a 
docker rm -f backend-a
docker run -d --name backend-a -p 8001:8001 --restart unless-stopped \
  -e NODO_ID=A -e ROL=primario -e PUERTO=8001 \
  -e URL_PROPIA=http://172.31.12.211:8001 \
  -e PARES=http://10.1.0.27:8001,http://10.1.31.94:8001 \
  -e PGHOST=172.31.12.43 -e PGPORT=5432 -e PGDATABASE=banco -e PGUSER=banco \
  -e PGPASSWORD='TU_PGPASSWORD' -e SECRET_KEY='TU_SECRET_KEY' \
  backend

Backend-b

docker run -d --name backend-b -p 8001:8001 --restart unless-stopped \
  -e NODO_ID=B -e ROL=replica -e PUERTO=8001 \
  -e URL_PROPIA=http://10.1.0.27:8001 \
  -e PARES=http://172.31.12.211:8001,http://10.1.31.94:8001 \
  -e PGHOST=10.1.5.208 -e PGPORT=5432 -e PGDATABASE=banco -e PGUSER=banco \
  -e PGPASSWORD='TU_PGPASSWORD' -e SECRET_KEY='TU_SECRET_KEY' \
  backend

Backend-c
docker run -d --name backend-c -p 8001:8001 --restart unless-stopped \
  -e NODO_ID=C -e ROL=replica -e PUERTO=8001 \
  -e URL_PROPIA=http://10.1.31.94:8001 \
  -e PARES=http://172.31.12.211:8001,http://10.1.0.27:8001 \
  -e PGHOST=10.1.26.86 -e PGPORT=5432 -e PGDATABASE=banco -e PGUSER=banco \
  -e PGPASSWORD='TU_PGPASSWORD' -e SECRET_KEY='TU_SECRET_KEY' \
  backend

Comprobaciones
curl -sS -m 3 http://127.0.0.1:8001/interno/estado
curl -sS -m 3 http://172.31.12.211:8001/interno/estado
curl -sS -m 3 http://10.1.31.94:8001/interno/estado



COMPROBACIONES

Backend-c
curl -sS http://127.0.0.1:8001/interno/estado

curl -sS http://172.31.12.211:8001/interno/estado
curl -sS http://10.1.0.27:8001/interno/estado


Datos en la BD-c
docker exec postgres-c psql -U banco -d banco -c "SELECT email FROM usuario;" -c "SELECT indice, tipo FROM log_replicacion;"

