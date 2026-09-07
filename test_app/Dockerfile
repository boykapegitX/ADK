FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir google-adk

COPY . /app/test_app

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8080", "/app/test_app"]
