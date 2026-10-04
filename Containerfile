# UBI Python image runs as a non-root user and tolerates OpenShift's random UIDs
FROM registry.access.redhat.com/ubi9/python-312

WORKDIR /opt/app-root/src
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# SQLite lives in /data (mount a PVC here later). OpenShift runs as a random
# UID in group 0, so the directory must be group-writable.
USER 0
RUN mkdir -p /data && chown 1001:0 /data && chmod 2775 /data
USER 1001
ENV DB_PATH=/data/truview.db

# Default timezone; override with -e TZ=... or a Deployment env var
ENV TZ=America/New_York

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
