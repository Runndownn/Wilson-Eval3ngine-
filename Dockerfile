FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE /app/
COPY src /app/src
RUN python -m pip install --no-cache-dir ".[postgres]"

COPY examples /app/examples
COPY contracts /app/contracts

RUN useradd --create-home --uid 10001 we3 && \
    mkdir -p /app/var /var/lib/we3/artifacts && \
    chown -R we3:we3 /app /var/lib/we3
USER 10001

EXPOSE 8000
CMD ["we3", "serve", "--host", "0.0.0.0", "--port", "8000"]
