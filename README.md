# Geopolitical & Security Threat Dashboard (Israel)

A resource-efficient, **start-and-stop** friendly dashboard that ingests signals
about threats to Israel — including **Judea & Samaria** and the **Golan Heights** —
and runs **multimodal AI analysis (text + images)** in the cloud via
**OpenRouter**, using the lightweight **`meta-llama/llama-3.2-11b-vision-instruct`**
vision model.

> Standard WSGI (no WebSockets/ASGI), Celery + Redis for async work, MySQL 8 for
> storage, and Angular with HTTP polling for a light live feed. No local GPU or
> heavy model weights required — inference is fully offloaded to OpenRouter.

---

## Architecture

| Service          | Tech                                   | Role |
|------------------|----------------------------------------|------|
| `db`             | MySQL 8                                | Relational store + `JSON` raw payload column |
| `redis`          | Redis 7                                | Celery broker/result backend |
| `web`            | Django + DRF + Gunicorn (WSGI)         | REST API + Django Admin |
| `celery_worker`  | Celery                                 | Polling, media download, **multimodal analysis**, startup catch-up |
| `celery_beat`    | Celery beat                            | Periodic source polling |
| `frontend`       | Angular (+ Tailwind) on nginx          | Live dashboard, polls every 20s |

AI inference runs on **OpenRouter** (`https://openrouter.ai/api/v1`) — there is
no local model service to run or maintain.

```
[Sources] -> Celery poll -> Alert (PENDING) -> [download image]
                                                       |
                                   text + base64 image (Vision API content array)
                                                       |
                                         OpenRouter  ──►  llama-3.2-11b-vision-instruct
                                                       |
                                  JSON verdict (is_threat, region,
                                  threat_severity, visual_summary)
                                                       |
                                  Angular polls /api/alerts every 20s
```

---

## Project structure

```
.
├── docker-compose.yml          # db, redis, web, celery_worker, celery_beat, frontend
├── .env.example                # copy to .env (holds OpenRouter credentials)
├── backend/
│   ├── config/                 # Django project (settings, celery, wsgi, urls)
│   ├── threats/
│   │   ├── models.py           # Source, Alert (with image fields + JSON), Metric
│   │   ├── admin.py            # manage sources + alerts (with image preview)
│   │   ├── serializers.py / views.py / urls.py   # DRF API
│   │   ├── tasks.py            # startup catch-up, polling, media download, analysis
│   │   ├── llama4_service.py   # OpenRouter Vision client + strict-JSON parsing
│   │   └── management/commands/seed_sources.py
│   ├── Dockerfile / entrypoint.sh / requirements.txt
└── frontend/                   # Angular workspace
    └── src/app/
        ├── services/polling.service.ts      # RxJS timer polling (20s)
        ├── components/dashboard-grid/        # KPI tiles
        └── components/threat-feed/           # multimodal cards (images)
```

---

## Cloud AI: OpenRouter

All analysis is performed by a hosted model on OpenRouter, called with the
standard `requests` library from `backend/threats/llama4_service.py`.

- **Endpoint:** `https://openrouter.ai/api/v1/chat/completions`
- **Model:** `meta-llama/llama-3.2-11b-vision-instruct` (configurable)
- **Required headers** (sent on every request):
  - `Authorization: Bearer <OPENROUTER_API_KEY>`
  - `Content-Type: application/json`
  - `HTTP-Referer: http://localhost:8000` — OpenRouter app ranking / attribution
  - `X-Title: Geopolitical Threat Dashboard` — usage tracking under this app name
- **Strict JSON:** the payload sets `response_format: {"type": "json_object"}`
  and the output is defensively parsed by `_extract_json`.

### Required `.env` keys

Get an API key from <https://openrouter.ai/keys> and fund your account with
credits, then set:

```bash
OPENROUTER_API_KEY=sk-or-v1-...                       # your real key
OPENROUTER_MODEL=meta-llama/llama-3.2-11b-vision-instruct
```

These are injected into the `web` and `celery_worker` containers via
`docker-compose.yml`. Swapping `OPENROUTER_MODEL` to any other OpenRouter model
slug is all that's needed to change models (use a vision-capable slug to keep
image analysis working).

---

## Quick start

1. **Copy the environment file** and add your OpenRouter key:

   ```bash
   cp .env.example .env
   # edit .env -> set OPENROUTER_API_KEY (and DJANGO_SECRET_KEY, DB passwords)
   ```

2. **Build and start** the stack:

   ```bash
   docker compose up --build
   ```

   The `web` container runs migrations, collects static files, and creates the
   admin superuser from the `.env` credentials. No model download step — the
   worker calls OpenRouter directly.

3. **Open the apps:**
   - Dashboard: <http://localhost:4200>
   - API root: <http://localhost:8000/api/>
   - Django Admin: <http://localhost:8000/admin/> (or <http://localhost:4200/admin/>)

4. **Add sources** in the admin, or seed examples:

   ```bash
   docker compose exec web python manage.py seed_sources
   ```

---

## Multimodal analysis pipeline

When a new `Alert` is ingested:

1. If it has an `image_url`, `download_media` fetches and stores it locally
   (`image_path`).
2. `analyze_alert` reads the image bytes and calls `llama4_service.analyze()`,
   which base64-encodes the image into a `data:` URL and sends **both the text
   and the image** to OpenRouter using the Vision API content structure:

   ```json
   {
     "role": "user",
     "content": [
       { "type": "text", "text": "Return the JSON verdict now." },
       { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,<...>" } }
     ]
   }
   ```

3. The model returns a strict JSON object:

   ```json
   {
     "is_threat": true,
     "region": "Judea & Samaria",
     "threat_severity": 7,
     "visual_summary": "Smoke rising near a checkpoint; armed individuals visible."
   }
   ```

4. The verdict is normalized (region aliases, severity clamped to 1–10) and saved
   to the `Alert`, then surfaced in the live feed. Text-only items (no image)
   send just the text part and still return the same JSON shape.

---

## Start-and-stop lifecycle (catch-up)

`docker compose stop` then `docker compose start` is fully supported:

- On worker boot, `threats.apps.ThreatsConfig.ready()` queues `startup_catchup`.
- It backfills each active source from the last `CATCHUP_WINDOW_HOURS` (default 24h)
  and **re-queues any alerts left mid-analysis** when the stack went down.
- Redis is configured with light persistence and a memory cap to stay lean.

---

## Adding real source connectors

`backend/threats/tasks.py` ships a working **RSS** connector and clearly marked
stubs for **Telegram**, **X**, and **Gov** sites. Each connector returns a list of
dicts and the orchestration (dedupe, media download, analysis) is handled for you:

```python
{
  "external_id": "<unique id for dedupe>",
  "title": "...",
  "content": "...",
  "url": "https://...",
  "image_url": "https://...",   # triggers media download + visual analysis
  "published_at": "<iso8601 or datetime>",
  "raw": { ... }                # stored in the Alert.raw_data JSON column
}
```

Wire Telethon/Bot API (Telegram) and the X API v2 client into `_fetch_telegram`
and `_fetch_x` using `source.identifier`, `source.last_external_id`, and `since`.

---

## Configuration reference

Key `.env` values (see `.env.example` for all):

| Variable | Default | Notes |
|----------|---------|-------|
| `OPENROUTER_API_KEY` | _(empty)_ | **Required.** Your OpenRouter API key |
| `OPENROUTER_MODEL` | `meta-llama/llama-3.2-11b-vision-instruct` | Any OpenRouter model slug (use a vision slug for image analysis) |
| `CATCHUP_WINDOW_HOURS` | `24` | Backfill window on startup |
| `SOURCE_POLL_INTERVAL` | `120` | Periodic poll cadence (seconds) |
| `CELERY_CONCURRENCY` | `2` | Worker concurrency (memory vs throughput) |

### Switching models

Set `OPENROUTER_MODEL` to any slug from <https://openrouter.ai/models>. To keep
the multimodal (image) pipeline functional, choose a **vision-capable** model.
Text-only models will still work for text but ignore the image part.

---

## Local development (without Docker)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export OPENROUTER_API_KEY=sk-or-v1-...               # Windows: setx OPENROUTER_API_KEY ...
python manage.py migrate
python manage.py runserver

# Frontend
cd frontend
npm install
npm start            # ng serve on http://localhost:4200 -> talks to :8000
```

You will still need Redis and MySQL reachable at the hosts configured in your
environment. AI inference needs only outbound HTTPS access to OpenRouter — no
local model server.

---

## Docker CLI (debugging)

```bash
# Lifecycle
docker compose up -d --build              # start stack (detached)
docker compose stop                       # pause containers (keep volumes)
docker compose start                      # resume after stop
docker compose down                       # remove containers (volumes kept)
docker compose down --rmi all             # remove containers + built images
docker compose down -v                    # ⚠ wipe db/redis/media volumes
docker compose ps                         # service status
docker compose build web celery_worker    # rebuild backend images only
docker compose restart web celery_worker  # reload after .env change

# Logs
docker compose logs -f web                # Django API
docker compose logs -f celery_worker      # polling + AI pipeline
docker compose logs -f celery_beat        # periodic source poll schedule
docker compose logs -f --tail=100         # all services (last 100 lines)

# Django shell inside web
docker compose exec web python manage.py check
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate
docker compose exec web python manage.py seed_admin
docker compose exec web python manage.py seed_sources
docker compose exec web python manage.py test_openrouter_pipeline --no-save
docker compose exec web python manage.py shell
docker compose exec web bash              # interactive container shell

# DB quick check (MySQL)
docker compose exec db mysql -u threats -pthreats_pass threats -e "SHOW TABLES;"

# Auth smoke test (JWT)
curl -s -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"nurADMIN","password":"<ADMIN_PASSWORD>"}'
```
