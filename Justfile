set shell := ["zsh", "-cu"]

default:
  @just --list

setup:
  cp -n .env.example .env || true
  cd backend && python3.11 -m venv .venv
  cd backend && source .venv/bin/activate && pip install -e ".[dev]"
  cd frontend && npm ci

db:
  docker compose up -d postgres

migrate: db
  cd backend && source .venv/bin/activate && alembic upgrade head

backend: migrate
  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload

frontend:
  cd frontend && npm run dev

dev:
  #!/usr/bin/env zsh
  set -e

  docker compose up -d postgres
  cd backend
  source .venv/bin/activate
  alembic upgrade head
  cd ..

  trap 'kill $(jobs -p) 2>/dev/null || true' INT TERM EXIT

  (cd backend && source .venv/bin/activate && uvicorn app.main:app --reload) &
  (cd frontend && npm run dev) &

  wait

test:
  cd backend && source .venv/bin/activate && pytest tests -q

lint:
  cd backend && source .venv/bin/activate && ruff check . && mypy app
  cd frontend && npm run lint

build:
  cd frontend && npm run build

check: lint test build

db-shell:
  docker compose exec postgres psql -U tutor -d tutor

db-reset:
  docker compose down -v
  docker compose up -d postgres
