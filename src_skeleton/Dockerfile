FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends fonts-noto-cjk && \
    rm -rf /var/lib/apt/lists/*

COPY src_skeleton/requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

COPY src_skeleton/app ./app
COPY alchemy_creative_agent_3_0/__init__.py ./alchemy_creative_agent_3_0/__init__.py
COPY alchemy_creative_agent_3_0/app ./alchemy_creative_agent_3_0/app

EXPOSE 8017

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8017"]
