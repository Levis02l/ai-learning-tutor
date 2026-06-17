# AI 学习导师

Agentic personal learning tutor MVP: upload course materials, ground answers in those materials, generate quiz items, schedule reviews, and later plug in DKT mastery prediction.

## Local Development

Recommended command runner:

```bash
brew install just
just setup
just dev
```

Then open:

```text
http://localhost:5173
http://localhost:8000/docs
```

Useful commands:

```bash
just db          # start Postgres only
just backend     # run DB migration and start FastAPI
just frontend    # start Vite
just check       # backend lint/type/test + frontend lint/build
just db-shell    # open psql inside the Postgres container
```

Manual startup:

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

FastAPI docs:

```text
http://localhost:8000/docs
```

Documents API:

- `POST /documents` uploads `.pdf`, `.pptx`, `.docx`, `.txt`, or `.md`, parses text, chunks it, embeds chunks with OpenAI `text-embedding-3-small`, and stores the result in Postgres/pgvector.
- `GET /documents` lists uploaded documents for `demo-user` by default.

Set `OPENAI_API_KEY` in `.env` before using `POST /documents`.

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

This project maps Postgres to local port `5433` by default to avoid conflicts with a local Postgres on `5432`.

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
