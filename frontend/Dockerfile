# зависимости – отдельным слоем: при правке кода npm ci не повторяется
FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# автотесты Vitest
FROM deps AS test
COPY . .
CMD ["npm", "test"]

# сборка: проверка типов (vue-tsc) и бандл Vite; адрес API и базовый путь (для GitHub Pages – /KinoCompass/);
# 404.html – копия index.html: GitHub Pages отдаёт её на любой путь, и vue-router открывает нужную страницу
FROM deps AS build
COPY . .
ARG VITE_API_BASE_URL=https://kinocompass-backend.onrender.com
ARG BASE=/
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build -- --base=$BASE && cp dist/index.html dist/404.html

# раздача собранной статики через nginx (локальная проверка сборки)
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
