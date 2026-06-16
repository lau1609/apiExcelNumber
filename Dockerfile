FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
run pip install --no-cache-dir -r requirements.txt

# Copiar el código de la app
COPY main.py .

# FastAPI
EXPOSE 8080

# uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
