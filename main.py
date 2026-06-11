from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONEncoder
import pandas as pd
import requests
import time
import io

app = FastAPI(title="Wati Bulk Sender API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WATI_URL = "https://live-mt-server.wati.io/10157709/api/v1/sendSessionMessage"
WATTI_API_KEY = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6..." # Reemplaza con tu Token completo

@app.post("/procesar")
async def procesar_archivo(
    file: UploadFile = File(...),
    url: str = Form(None),
    loc: str = Form(None),
    hotel: str = Form(None)
):
    # 1. Validar extensión del archivo
    if not file.filename.endswith(('.xlsx', '.xls')):
        return {"success": False, "message": "El archivo debe ser un Excel válido (.xlsx o .xls)"}

    try:
        # 2. Leer el Excel directamente desde la memoria
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        # Limpiar nombres de columnas (quitar espacios en blanco)
        df.columns = df.columns.str.strip()

        # Verificar si existe la columna requerida
        if 'Telefono' not in df.columns:
            return {"success": False, "message": "El Excel debe contener una columna llamada 'Telefono'"}

        headers = {
            "Authorization": WATTI_API_KEY,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        reporte_envios = []

        # 3. Iterar y enviar mensajes vía Wati
        for index, fila in df.iterrows():
            telefono_crudo = str(fila['Telefono']).strip()
            
            # Limpieza básica del número de teléfono procesado por Pandas (ej: 521614.0 -> 521614)
            if telefono_crudo.endswith('.0'):
                telefono_crudo = telefono_crudo[:-2]
            
            # Saltarse filas vacías
            if not telefono_crudo or telefono_crudo == 'nan':
                continue

            mensaje = f"¡Hola! Te invitamos a contestar nuestra encuesta en el siguiente enlace: {url or 'sichtur.org'}"
            url_envio = f"{WATI_URL}?whatsappNumber={telefono_crudo}"
            payload = {"messageText": mensaje}

            try:
                # Petición a la API de Wati
                response = requests.post(url_envio, json=payload, headers=headers, timeout=10)
                
                # Evaluamos si Wati aceptó el mensaje (Código 200)
                if response.status_code == 200:
                    estado = "enviado"
                else:
                    estado = "fallido"
            except Exception:
                estado = "fallido"

            reporte_envios.append({
                "dato": telefono_crudo,
                "estado": estado
            })

            # ⏳ Pausa de 1.5 segundos para no saturar tu línea ni la API de Wati
            time.sleep(1.5)

        # 4. Responder con la misma estructura exacta que tu JS espera
        return {
            "success": True,
            "tipo_dato": "telefono",
            "extracted_data": reporte_envios
        }

    except Exception as e:
        return {"success": False, "message": f"Error al procesar el Excel: {str(e)}"}

# Para que Coolify pueda validar el estado del contenedor
@app.get("/health")
def health_check():
    return {"status": "healthy"}
