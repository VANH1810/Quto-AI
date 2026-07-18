# FastAPI backend (api service).
FROM python:3.11-slim

WORKDIR /srv/backend

COPY backend/requirements.txt /srv/backend/requirements.txt
# celery[redis]: gửi task cho agent worker (broker RabbitMQ) + đọc AsyncResult (Redis).
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "celery[redis]>=5.3"

COPY backend /srv/backend

ENV PYTHONPATH=/srv/backend
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
