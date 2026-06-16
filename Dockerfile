FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["sh", "-c", "python scripts/migrate.py && uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
