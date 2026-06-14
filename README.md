# AI 学习导师

Agentic personal learning tutor MVP: upload course materials, ground answers in those materials, generate quiz items, schedule reviews, and later plug in DKT mastery prediction.

## Local Development

```bash
cp .env.example .env
docker compose up -d postgres
```

Backend:

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. The frontend proxies `/api/*` to `http://localhost:8000` locally. In Docker Compose it uses `http://backend:8000`.

## Database Troubleshooting

If `alembic upgrade head` or `/health` fails with:

```text
FATAL: role "tutor" does not exist
```

you are connecting to a Postgres instance that was not initialized by this project's `docker-compose.yml`. The usual causes are an old Docker volume or another local Postgres already using port `5432`.

Check which container is running:

```bash
docker compose ps
```

If you do not need the current local project database, reset the Compose database volume:

```bash
docker compose down -v
docker compose up -d postgres
```

Then rerun:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

If you have another important Postgres on port `5432`, change the Postgres port mapping in `docker-compose.yml` and the local `DATABASE_URL` in `.env` to the same new port.

## Checks

```bash
cd backend
ruff check .
mypy app
pytest tests -q
```

```bash
cd frontend
npm run lint
npm run build
```
