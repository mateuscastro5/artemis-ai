.PHONY: up up-d down restart rebuild logs logs-s infra migrate ps

# Sobe tudo (build se necessário)
up:
	docker-compose up --build

# Sobe em background
up-d:
	docker-compose up --build -d

# Desce tudo
down:
	docker-compose down

# Reinicia um serviço: make restart s=artemis-api
restart:
	docker-compose restart $(s)

# Rebuild e reinicia um serviço: make rebuild s=artemis-ai
rebuild:
	docker-compose up --build -d $(s)

# Logs de todos os serviços
logs:
	docker-compose logs -f

# Logs de um serviço: make logs-s s=artemis-ai
logs-s:
	docker-compose logs -f $(s)

# Sobe só infra (Qdrant + AI) — útil para dev local de NestJS/React
infra:
	docker-compose up --build -d qdrant artemis-ai

# Roda as migrations do NestJS
migrate:
	docker-compose exec artemis-api npm run migration:run

# Status dos containers
ps:
	docker-compose ps
