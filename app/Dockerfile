FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY app/requirements.txt /srv/app/requirements.txt
RUN pip install -r /srv/app/requirements.txt

COPY app /srv/app
COPY ingest /srv/ingest
COPY preprocess /srv/preprocess

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
