# Etapa 1: Compilación de la aplicación estática con Node.js
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Etapa 2: Servidor web ultraligero Nginx para servir los archivos estáticos
FROM nginx:alpine

# Configuración personalizada de Nginx (SPA + Proxy API a backend)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copiar bundle compilado
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
