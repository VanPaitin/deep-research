# Deep Research

Deep Research is a full-stack research assistant. Users sign in, submit a topic,
answer clarifying questions, and receive a streamed Markdown report backed by
web search.

The app uses a job-based workflow so long research runs are not tied to one
fragile HTTP request. Research progress and report chunks are persisted in
Postgres, and the frontend reconnects to the stream when needed.

## Live Demo

Try the deployed app at [https://deep-research.app](https://deep-research.app).

## Stack

- FastAPI backend
- Next.js frontend
- PostgreSQL with SQLAlchemy and Alembic
- Clerk authentication
- OpenAI Agents SDK
- Brave Search MCP server for web search
- `mcp-server-fetch` for page inspection when available
- SendGrid for emailing saved reports

## Project Structure

- `main.py`: backend entrypoint
- `deep_research/app.py`: FastAPI routes and job orchestration
- `deep_research/schemas.py`: API request and response models
- `deep_research/research_manager.py`: MCP search and report orchestration
- `deep_research/agents/`: clarifier, planner, searcher, writer, and email agents
- `deep_research/db/`: SQLAlchemy models, queries, persistence, and sessions
- `alembic/`: database migrations
- `frontend/`: Next.js application

## Environment

Create a backend `.env` from `.env.example`:

```bash
cp .env.example .env
```

Backend variables:

```env
OPENAI_API_KEY=
BRAVE_API_KEY=
DATABASE_URL=postgresql://postgres:password@localhost:5432/deep_research
CLERK_SECRET_KEY=
CLERK_JWKS_URL=
SENDGRID_API_KEY=
SENDGRID_FROM_EMAIL=
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Create a frontend env file in `frontend/.env.local`:

```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

For production, set `ALLOWED_ORIGINS` to your deployed frontend origin, for
example:

```env
ALLOWED_ORIGINS=https://your-frontend-domain.com,https://your-vercel-app.vercel.app
```

## Database

Create the database named in `DATABASE_URL`, then run migrations:

```bash
uv run alembic upgrade head
```

The research job workflow requires the `research_jobs` and `research_events`
tables, so run migrations before deploying the updated backend.

Check database connectivity:

```bash
curl http://127.0.0.1:8000/health/db
```

## Local Development

Install backend dependencies:

```bash
uv sync
```

Run the backend:

```bash
uv run python main.py
```

Run the frontend in another terminal:

```bash
nvm use
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

## How Research Jobs Work

1. The frontend creates a research job with `POST /api/research-jobs`.
2. The backend asks clarifying questions and stores job events in Postgres.
3. After the final answer, the backend starts the research in a background task.
4. The frontend streams events from `GET /api/research-jobs/{id}/stream?after=N`.
5. The stream sends heartbeats and a reconnect event before platform timeouts.
6. The frontend reconnects with the latest sequence number and continues.
7. Completed reports are saved and can be viewed from `/researches`.

This preserves a streaming user experience while avoiding App Runner's two-minute
request limit.

## Useful Commands

Run backend compile checks:

```bash
uv run python -m compileall deep_research main.py alembic
```

Build the frontend:

```bash
cd frontend
npm run build
```

Run migrations:

```bash
uv run alembic upgrade head
```

## Notes

- Push notifications are no longer part of the app.
- Email delivery is optional and only requires SendGrid variables if you want the
  "Email report" feature.
- `mcp-server-fetch` is optional; the app will use it if the binary is available.
