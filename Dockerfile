# Neighbor Partner - Flask application image (Req 7.1)
# Base image small enough to run on a Raspberry Pi with 4 GB of memory
FROM python:3.12-slim

# Keep Python output unbuffered and skip .pyc files for cleaner container logs
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first to leverage Docker layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source
COPY . .

# Flask app served by gunicorn listens on 5000
EXPOSE 5000

# Serve the WSGI app (app:app) with gunicorn on port 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
