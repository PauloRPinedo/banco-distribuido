# O node compila, o nginx serve. A imagem final não leva node nenhum.
FROM node:20-slim AS construcao
WORKDIR /app

# O lock entra antes do resto e usa-se `npm ci`, não `npm install`: é o que
# faz a construção dar o mesmo resultado em dois portáteis diferentes, pela
# mesma razão que o compose.yaml fixa `postgres:16`.
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=construcao /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
