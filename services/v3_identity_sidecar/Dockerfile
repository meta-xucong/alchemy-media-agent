FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY sidecar /app/sidecar
RUN pip install .

RUN useradd --create-home --uid 10001 sidecar
USER sidecar

EXPOSE 8098
CMD ["uvicorn", "sidecar.main:app", "--host", "0.0.0.0", "--port", "8098"]
