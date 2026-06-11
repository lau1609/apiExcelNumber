FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
run pip install --no-cache-dir -r requirements.txt

# Copiar el código de la app
COPY main.py .

# Exponer el puerto de FastAPI
EXPOSE 8000

# Comando para arrancar la API mediante uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
