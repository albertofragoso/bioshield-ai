.PHONY: up down logs status seed tunnel help

COMPOSE = docker compose -f docker-compose.prod.yml --env-file .env.prod

help:
	@echo "BioShield AI — Production Commands"
	@echo ""
	@echo "  make up      Build and start all services (detached)"
	@echo "  make down    Stop all services (preserves volumes)"
	@echo "  make logs    Stream logs from all services (last 200 lines)"
	@echo "  make status  Show service status, disk, and RAM usage"
	@echo "  make seed    Populate ChromaDB + create demo user (run once after first up)"
	@echo "  make tunnel  Show the Cloudflare Tunnel public URL"

up:
	@test -f .env.prod || (echo "ERROR: .env.prod not found. Copy .env.prod.example and fill in values." && exit 1)
	@stat -c "%a" .env.prod 2>/dev/null | grep -qE "^[46]00$$" || stat -f "%A" .env.prod 2>/dev/null | grep -qE "^[46]00$$" || (echo "ERROR: .env.prod permissions must be 600. Run: chmod 600 .env.prod" && exit 1)
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200

status:
	$(COMPOSE) ps
	@echo ""
	@echo "=== Disk ==="
	@df -h . 2>/dev/null || df -h /
	@echo ""
	@echo "=== RAM ==="
	@free -m

seed:
	$(COMPOSE) exec backend python /app/scripts/seed_chromadb.py
	$(COMPOSE) exec backend python /app/scripts/create_demo_user.py

tunnel:
	@cat .tunnel_url 2>/dev/null || echo "No tunnel URL found — complete Slice 2 of docs/deployment.md first"
