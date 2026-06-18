# Geopolitical & Security Threat Dashboard (Israel)

A resource-efficient, **start-and-stop** friendly dashboard that ingests signals
about threats to Israel — including **Judea & Samaria** and the **Golan Heights** —
and runs **multimodal AI analysis (text + images)** using **Llama 4 Scout** locally
via Ollama.

> Standard WSGI (no WebSockets/ASGI), Celery + Redis for async work, MySQL 8 for
> storage, and Angular with HTTP polling for a light live feed.

---

## Architecture

| Service          | Tech                                   | Role |
|------------------|----------------------------------------|------|
| `db`             | MySQL 8                                | Relational store + `JSON` raw payload column |
| `redis`          | Redis 7                                | Celery broker/result backend |
| `web`            | Django + DRF + Gunicorn (WSGI)         | REST API + Django Admin |
| `celery_worker`  | Celery                                 | Polling, media download, **multimodal analysis**, startup catch-up |
| `celery_beat`    | Celery beat                            | Periodic source polling |
| `ollama`         | Ollama + `llama4:scout`                | Local multimodal LLM inference |
| `frontend`       | Angular (+ Tailwind) on nginx          | Live dashboard, polls every 20s |

```
[Sources] -> Celery poll -> Alert (PENDING) -> [download image] -> Llama 4 Scout
                                                       |                |
                                                  base64 image     text prompt
                                                       \               /
                                                  JSON verdict (is_threat, region,
                                                  threat_severity, visual_summary)
                                                       |
                                          Angular polls /api/alerts every 20s
```

---

## Project structure

```
.
├── docker-compose.yml          # all services wired
├── .env.example                # copy to .env
├── backend/
│   ├── config/                 # Django project (settings, celery, wsgi, urls)
│   ├── threats/
│   │   ├── models.py           # Source, Alert (with image fields + JSON), Metric
│   │   ├── admin.py            # manage sources + alerts (with image preview)
│   │   ├── serializers.py / views.py / urls.py   # DRF API
│   │   ├── tasks.py            # startup catch-up, polling, media download, analysis
│   │   ├── llama4_service.py   # multimodal Ollama client + strict-JSON parsing
│   │   └── management/commands/seed_sources.py
│   ├── Dockerfile / entrypoint.sh / requirements.txt
├── frontend/                   # Angular workspace
│   └── src/app/
│       ├── services/polling.service.ts      # RxJS timer polling (20s)
│       ├── components/dashboard-grid/        # KPI tiles
│       └── components/threat-feed/           # multimodal cards (images)
└── ollama/
    ├── entrypoint.sh           # boots server + pulls llama4:scout
    └── Modelfile               # optional custom FP8 build
```

---

## Quick start

1. **Copy the environment file** and adjust secrets:

   ```bash
   cp .env.example .env
   ```

2. **Build and start** the stack:

   ```bash
   docker compose up --build
   ```

   On first boot, the `ollama` container pulls `llama4:scout` (large download).
   The `web` container runs migrations, collects static files, and creates the
   admin superuser from the `.env` credentials.

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
2. `analyze_alert` reads the image bytes, base64-encodes them, and sends **both
   the text and the image** to Llama 4 Scout via the `ollama` Python client.
3. The model is constrained (`format="json"`) to return:

   ```json
   {
     "is_threat": true,
     "region": "Judea & Samaria",
     "threat_severity": 7,
     "visual_summary": "Smoke rising near a checkpoint; armed individuals visible."
   }
   ```

4. The verdict is normalized (region aliases, severity clamped to 1–10) and saved
   to the `Alert`, then surfaced in the live feed.

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
| `OLLAMA_MODEL` | `llama4:scout` | Model tag pulled/built by the ollama service |
| `OLLAMA_TIMEOUT` | `300` | Seconds for inference requests |
| `CATCHUP_WINDOW_HOURS` | `24` | Backfill window on startup |
| `SOURCE_POLL_INTERVAL` | `120` | Periodic poll cadence (seconds) |
| `CELERY_CONCURRENCY` | `2` | Worker concurrency (memory vs throughput) |

### FP8 / custom model

To run a specific FP8 quantization, edit `ollama/Modelfile` to add a `FROM`
directive (a tag or local GGUF path), then rebuild:

```bash
docker compose up -d --build ollama
```

The ollama entrypoint detects a real `FROM` line and runs `ollama create`
instead of a plain pull.

### GPU

The `ollama` service has a commented-out NVIDIA `deploy.resources` block in
`docker-compose.yml`. Uncomment it (with the NVIDIA Container Toolkit installed)
for GPU acceleration. Llama 4 Scout is large — GPU or ample RAM is recommended.

---

## Local development (without Docker)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Frontend
cd frontend
npm install
npm start            # ng serve on http://localhost:4200 -> talks to :8000
```

You will still need Redis, MySQL, and Ollama reachable at the hosts configured in
your environment.
