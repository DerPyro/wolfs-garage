FROM python:3.12-slim@sha256:6b25cbe6577518889d553cdd5a5da97d259348d8f6e45b527dd731caaba27a07
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 GARAGE_FRONTEND=/app/frontend
WORKDIR /app
COPY frontend /app/frontend
COPY garage_gateway/server.py /app/garage_gateway/server.py
COPY garage_gateway/status_store.py /app/garage_gateway/status_store.py
COPY garage_gateway/backup_status.py /app/garage_gateway/backup_status.py
COPY garage_gateway/seed_status.py /app/garage_gateway/seed_status.py
RUN chmod -R a+rX /app && mkdir -p /var/lib/wolfs-garage && chown 65532:65532 /var/lib/wolfs-garage
USER 65532:65532
EXPOSE 8000
CMD ["python3", "/app/garage_gateway/server.py"]
