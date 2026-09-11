FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir google-adk

COPY . /app/agent1

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8080", "/app/agent1"]
