.PHONY: test build run dev lock stop

IMAGE := kinocompass-frontend
CONTAINER := kinocompass-frontend

# Git Bash на Windows иначе превращает пути контейнера в пути Windows
export MSYS_NO_PATHCONV=1

# автотесты Vitest в контейнере (локально node_modules не нужен)
test:
	docker build --target test -t $(IMAGE)-test .
	docker run --rm $(IMAGE)-test

# собрать образ: проверка типов, сборка Vite, nginx; API=<адрес> – другой API вместо Render
# (например, make run API=http://localhost:8000 вместе с make -C backend run)
build:
	docker build $(if $(API),--build-arg VITE_API_BASE_URL=$(API)) -t $(IMAGE) .

# собранный сайт на http://localhost:8080 (данные – API на Render)
run: build
	docker run --rm -d -p 8080:80 --name $(CONTAINER) $(IMAGE)

# dev-сервер Vite с горячей перезагрузкой на http://localhost:5173; node_modules живёт в томе контейнера
dev:
	docker run --rm -it -p 5173:5173 -e VITE_USE_POLLING=1 -v "$(CURDIR):/app" -v /app/node_modules -w /app \
		node:24-alpine sh -c "npm ci --no-audit --no-fund && npm run dev"

# обновить package-lock.json после правки package.json (без node_modules на диске)
lock:
	docker run --rm -v "$(CURDIR):/app" -w /app node:24-alpine npm install --package-lock-only --no-audit --no-fund

stop:
	docker stop $(CONTAINER)
