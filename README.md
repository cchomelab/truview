# truview — project

FastAPI app built up in stages.

## Run locally

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/uvicorn app.main:app --reload --port 8080
    curl localhost:8080/datetime      # API docs at http://localhost:8080/docs

## Endpoints

| Path        | Description                                        |
|-------------|----------------------------------------------------|
| `/`         | Retro LCD clock (polls `/datetime` every second)   |
| `/datetime` | Current date/time as JSON                          |
| `/stats`    | Total logged calls, first call time, database path |
| `/history`  | Most recent logged `/datetime` calls (`?limit=1..1000`, default 50) |
| `/healthz`  | Health check for probes                            |
| `/docs`     | Interactive API docs                               |

## Request log (SQLite)

Calls to `/datetime` are written to a SQLite `requestlog` table. The landing page's
own polling is not logged: it sends an `X-Truview-Client: lcd` header and the server
skips those requests. The file location comes from `DB_PATH`:

- Local run: `./truview.db` (default)
- Container: `/data/truview.db` (set in the Containerfile)

Inspect it directly: `sqlite3 truview.db 'select * from requestlog order by id desc limit 10;'`

## Persistent storage

The database lives in `/data`. Without a volume it disappears with the container.
Mount a volume at `/data` to keep it. The landing page shows `TOTAL n SINCE ...` from
`/stats`, which makes it easy to see whether data survived a restart.

If `/data` isn't writable, the app refuses to start and logs the directory, uid and gid.

### Locally with podman

    podman volume create truview-data
    podman run --rm -p 127.0.0.1:8080:8080 -v truview-data:/data truview

Stop and re-run the container; the total keeps counting up. Remove the data with
`podman volume rm truview-data`.

### On OpenShift

Create a PVC and mount it at `/data`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: truview-data
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 1Gi
```

In the Deployment:

```yaml
spec:
  replicas: 1                 # SQLite allows a single writer
  strategy:
    type: Recreate            # stop the old pod before the new one mounts the RWO volume
  template:
    spec:
      containers:
        - name: truview
          volumeMounts:
            - name: data
              mountPath: /data
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: truview-data
```

Notes:

- **Recreate, not RollingUpdate**: with a ReadWriteOnce volume, a rolling update can hang
  (new pod can't attach the volume) or briefly run two writers against one SQLite file.
- **Permissions**: OpenShift's restricted SCC sets an `fsGroup` on the pod so the random
  UID can write to the volume. If the pod crash-loops with "not writable", check
  `oc rsh <pod> ls -ln /data` and the pod's `securityContext`.
- **Storage class**: use block storage (the default class is usually fine). Avoid NFS-backed
  volumes for SQLite; file locking over NFS is unreliable.
- **Verify**: `curl https://<route>/datetime`, then `oc delete pod -l app=truview`.
  After the new pod starts, `/stats` should still show the earlier total.

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
4. **Persistent storage** *(app ready; see above)*: PersistentVolumeClaim mounted at `/data`, DB path from env var.
   Set `replicas: 1` and `strategy: Recreate` because SQLite + RWO volume = one writer.
5. **Next steps**: PostgreSQL (separate Deployment/StatefulSet) to scale replicas,
   Kustomize or Helm, CI with Tekton/GitHub Actions.
