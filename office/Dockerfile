FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/srv

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-jpn \
    tesseract-ocr-jpn-vert \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY office/requirements.txt /srv/office/requirements.txt
RUN pip install -r /srv/office/requirements.txt

COPY office /srv/office

EXPOSE 8501

CMD ["streamlit", "run", "/srv/office/streamlit_app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
