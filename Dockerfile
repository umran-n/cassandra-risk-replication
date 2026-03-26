FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    HOST=0.0.0.0 \
    PORT=8080 \
    CASSANDRA_BOOTSTRAP_ON_START=1

WORKDIR /app

COPY . /app

EXPOSE 8080

CMD ["sh", "-c", "python api/app.py --host ${HOST:-0.0.0.0} --port ${PORT:-8080}"]
