FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY ui/requirements.txt /srv/ui/requirements.txt
RUN pip install -r /srv/ui/requirements.txt

COPY ui /srv/ui

EXPOSE 8501

CMD ["streamlit", "run", "/srv/ui/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
