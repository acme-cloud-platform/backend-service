FROM python:3.12-slim

WORKDIR /app

# Install deps first, separately from app code — better Docker layer caching:
# rebuilding after a code change won't reinstall dependencies every time.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Run as non-root — standard hardening practice, and required by some
# cluster admission policies in real production setups.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
