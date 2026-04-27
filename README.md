---
title: Deep_Research_with_MCP
app_file: main.py
---
# Deep Research with MCP

This app recreates the deep-research workflow from `2_openai/community_contributions/mayowa`, but rewires the implementation around MCP servers.

## What changed

- Web research uses the Brave Search MCP server instead of `googleserper`.
- Page inspection can use `mcp-server-fetch` when search snippets are not enough.
- Completion alerts are sent through a local `deep_research/services/push_server.py` MCP server.
- Email delivery has been removed.
- The frontend is a Next.js app that talks to a FastAPI backend.

## Environment

Set these variables before running:

- `OPENAI_API_KEY`
- `BRAVE_API_KEY`
- `PUSHOVER_USER` and `PUSHOVER_TOKEN` if you want real push notifications
- `DATABASE_URL`, for example `postgresql://postgres:password@localhost:5432/deep_research`
- `CLERK_SECRET_KEY`
- `CLERK_JWKS_URL`, for example `https://your-app.clerk.accounts.dev/.well-known/jwks.json`

The frontend also needs `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`. Put it in `frontend/.env.local`.

## Database

The backend uses SQLAlchemy with async Postgres access through `asyncpg`.

Create your local database, set `DATABASE_URL`, then run migrations:

```bash
uv run alembic upgrade head
```

To check the app can reach Postgres:

```bash
curl http://127.0.0.1:8000/health/db
```

## Run

```bash
uv sync
uv run python main.py
```

In another terminal:

```bash
nvm use
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The Next.js app calls the backend at `http://127.0.0.1:8000` by default. To use a different backend URL, set `NEXT_PUBLIC_API_URL`.

## Files

- `main.py`: root entrypoint for the app
- `deep_research/app.py`: FastAPI backend and clarification flow
- `frontend/`: Next.js frontend
- `deep_research/agents/clarifier.py`: clarification agent plus input guardrail
- `deep_research/agents/planner.py`: search-plan generation
- `deep_research/agents/searcher.py`: web research agent
- `deep_research/agents/writer.py`: report writer agent
- `deep_research/research_manager.py`: MCP orchestration and report streaming
- `deep_research/services/notification.py`: push-notification agent wrapper
- `deep_research/services/push_server.py`: local MCP push notification server
