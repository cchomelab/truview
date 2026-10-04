# truview — OpenShift learning project

FastAPI app for the `conklinc` OpenShift project, built up in stages.

## Run locally

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/uvicorn app.main:app --reload --port 8080
    curl localhost:8080/datetime      # API docs at http://localhost:8080/docs

## Endpoints

| Path        | Description                                        |
|-------------|----------------------------------------------------|
| `/`         | Retro LCD clock (polls `/datetime` every second)   |
| `/datetime` | Current date/time as JSON                          |
| `/history`  | Most recent logged `/datetime` calls (`?limit=1..1000`, default 50) |
| `/healthz`  | Health check for probes                            |
| `/docs`     | Interactive API docs                               |

## Request log (SQLite)

Calls to `/datetime` are written to a SQLite `requestlog` table. The landing page's
own polling is not logged: it sends an `X-Truview-Client: lcd` header and the server
skips those requests. The file location comes from `DB_PATH`:

- Local run: `./truview.db` (default)
- Container: `/data/truview.db` (set in the Containerfile)

Without a volume, the database is lost when the container is removed:

    podman run --rm -p 127.0.0.1:8080:8080 -v truview-data:/data truview   # keeps data in a named volume

Inspect it directly: `sqlite3 truview.db 'select * from requestlog order by id desc limit 10;'`

## Container image

    podman build -t truview -f Containerfile .
    podman run --rm -p 127.0.0.1:8080:8080 truview   # bind IPv4 only; IPv6 forwarding hangs on "localhost"

The image defaults to `TZ=America/New_York`; override with `-e TZ=UTC` (or any zone name).

The app listens on port 8080 and runs as a non-root user, so it works with
OpenShift's restricted security settings. Use `/healthz` for readiness and liveness probes.

## Roadmap

1. **Stateless pod** *(done)*: Deployment, Service, Route, probes.
2. **Configuration**: ConfigMap for settings (e.g. timezone), Secret for anything sensitive.
3. **SQLite (ephemeral)** *(done)*: SQLModel; log `/datetime` calls, add `GET /history`.
   Data is lost when the pod restarts. That's the point of the exercise.
4. **Persistent storage**: PersistentVolumeClaim mounted at `/data`, DB path from env var.
   Set `replicas: 1` and `strategy: Recreate` because SQLite + RWO volume = one writer.
5. **Next steps**: PostgreSQL (separate Deployment/StatefulSet) to scale replicas,
   Kustomize or Helm, CI with Tekton/GitHub Actions.
