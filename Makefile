.PHONY: dev stop migrate logs

dev:
	docker compose -f docker-compose.dev.yml up --build

stop:
	docker compose -f docker-compose.dev.yml down

migrate:
	docker compose -f docker-compose.dev.yml exec api alembic upgrade head

new-migration:
	docker compose -f docker-compose.dev.yml exec api alembic revision --autogenerate -m "$(MSG)"

logs:
	docker compose -f docker-compose.dev.yml logs -f

logs-api:
	docker compose -f docker-compose.dev.yml logs -f api

db-shell:
	docker compose -f docker-compose.dev.yml exec db psql -U postgres agent_console
