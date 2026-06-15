# Etapa 1: Builder
FROM python:3.13 AS builder
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /install

COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt gunicorn python-dotenv

# Etapa 2: Producción
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV FLASK_APP=main.py

RUN groupadd -r rentagroup && useradd -r -g rentagroup -m -d /app rentapp
WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=rentapp:rentagroup src/ ./src/
COPY --chown=rentapp:rentagroup main.py ./
COPY --chown=rentapp:rentagroup requirements.txt ./

RUN mkdir -p /app/uploads /app/data && \
    chown -R rentapp:rentagroup /app/uploads /app/data && \
    chmod 755 /app/uploads /app/data

USER rentapp
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "2", "--timeout", "120", "main:app"]
