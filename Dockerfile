# Use Python 3.11 slim image for a lightweight and secure build
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Set working directory inside the container
WORKDIR /app

# Install system dependencies if needed (e.g. git, build-essential)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first to leverage Docker build cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files into the container
COPY . .

# Expose port 8080 (Cloud Run will route traffic to this port)
EXPOSE 8080

# Start FastAPI server using uvicorn, dynamically binding to the PORT env variable
CMD ["sh", "-c", "uvicorn web.web_app:app --host 0.0.0.0 --port ${PORT:-8080}"]
