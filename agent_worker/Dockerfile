# AI Agent worker (Celery) — TỰ CHỨA. Build context = thư mục agent_worker/.
#   docker build -t quto-agent -f Dockerfile .        (chạy TRONG agent_worker/)
#   hoặc qua agent_worker/docker-compose.yml (context: .)
FROM python:3.11-slim

# PYTHONPATH=/srv để 'import agent_worker' (package ở /srv/agent_worker).
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/srv

WORKDIR /srv

# 1) Deps trước (tận dụng layer cache).
COPY requirements.txt /srv/requirements.txt
RUN pip install -r /srv/requirements.txt

# 2) Source agent_worker (context = agent_worker/ → copy vào /srv/agent_worker).
COPY . /srv/agent_worker

# 3) Chạy non-root.
RUN useradd -m -u 10001 worker
USER worker

# Mặc định: worker queue 'agent'. dispatch worker override command trong compose.
CMD ["celery", "-A", "agent_worker.celery_app", "worker", "-Q", "agent", "--loglevel=info"]
