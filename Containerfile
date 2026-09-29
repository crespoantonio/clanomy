# Use a slim Python image for a smaller footprint
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Set working directory
WORKDIR /app

# Install system dependencies needed for some libraries (like faster-whisper or cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create non-root system user and adjust permissions
RUN groupadd -r clanomy && useradd -r -g clanomy -d /app -s /sbin/nologin clanomy \
    && chown -R clanomy:clanomy /app

# Switch to non-root user
USER clanomy

# Expose the port the app runs on
EXPOSE 8000

# Healthcheck to verify the FastAPI service and DB connectivity are healthy
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -sf http://localhost:8000/health || exit 1

# Command to run the application (production default without --reload)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

