FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/srv

# Tesseract is kept as a fallback engine. poppler-utils is needed by pdf2image.
# libgl1 / libglib2.0-0 are runtime libs used by opencv (pulled in by NDLOCR-Lite).
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    tesseract-ocr \
    tesseract-ocr-jpn \
    tesseract-ocr-jpn-vert \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# --- Install NDLOCR-Lite (CC BY 4.0, 国立国会図書館) -------------------------
# https://github.com/ndl-lab/ndlocr-lite
ARG NDL_OCR_REF=master
RUN git clone --depth 1 --branch ${NDL_OCR_REF} \
      https://github.com/ndl-lab/ndlocr-lite.git /opt/ndlocr-lite \
 && pip install -r /opt/ndlocr-lite/requirements.txt

ENV NDL_OCR_SRC=/opt/ndlocr-lite/src

# --- App deps ---------------------------------------------------------------
WORKDIR /srv

COPY office/requirements.txt /srv/office/requirements.txt
RUN pip install -r /srv/office/requirements.txt

COPY office /srv/office

EXPOSE 8501

CMD ["streamlit", "run", "/srv/office/streamlit_app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
