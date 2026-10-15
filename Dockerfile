FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[openai,anthropic]"

COPY config ./config
COPY kb ./kb
COPY data ./data
COPY eval/tickets.jsonl ./eval/tickets.jsonl

# Run as a non-root user.
RUN useradd --create-home triage && chown -R triage /app
USER triage

# API keys are passed at run time, for example: docker run --env-file .env ...
ENTRYPOINT ["triage"]
CMD ["run", "--provider", "keyword", "--ticket", "T12"]
