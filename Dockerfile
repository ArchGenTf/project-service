FROM python:3.11-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
RUN groupadd -r appgroup && useradd -m -r -g appgroup appuser
COPY --chown=appuser:appgroup --from=builder /root/.local /home/appuser/.local
# Fix CVE-2026-23949 (jaraco.context<6.1.0) and CVE-2026-24049 (wheel<0.46.2):
# Upgrade at system level, then explicitly purge stale old-version dist-info from user-local
# that pip cannot automatically remove (it only tracks what it installed itself)
RUN pip install --no-cache-dir --upgrade pip "wheel>=0.46.2" "jaraco.context>=6.1.0" \
    && find /home/appuser/.local -type d -name "wheel-0.4[0-5]*.dist-info" -exec rm -rf {} + 2>/dev/null; \
       find /home/appuser/.local -type d \( -name "jaraco.context-5*.dist-info" -o -name "jaraco_context-5*.dist-info" \) -exec rm -rf {} + 2>/dev/null; \
       true
COPY . .
RUN chown -R appuser:appgroup /app
USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
