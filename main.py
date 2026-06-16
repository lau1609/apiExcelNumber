import os
import re
import requests
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

app = FastAPI()

# 1. Aseguramos CORS para evitar el error de "Error de comunicación o CORS"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # O pon la URL de tu frontend de sichitur.org si prefieres cerrarlo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def limpiar_y_formatear_telefono(telefono_crudo: str) -> str:
    if not telefono_crudo or str(telefono_crudo).lower() == 'nan':
        return ""
    t_clean = str(telefono_crudo).strip()
    if t_clean.endswith('.0'):
        t_clean = t_clean[:-2]
    numeros = re.sub(r'\D', '', t_clean)
    if not numeros:
        return ""
    if len(numeros) == 10:
        numeros = '521' + numeros  
    return numeros

@app.post("/procesar")
async def procesar_envios(
    enlace: str = Form(...),
    localizacion: str = Form(...),
    hotel: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        # Leer el archivo Excel de manera segura
        contents = await file.read()
        df = pd.read_excel(contents)
        
        # Supongamos que tu columna se llama 'telefono' o 'Celular' (ajusta según tu excel)
        # Buscamos una columna que se parezca a teléfono si no viene exacta
        col_telefono = [c for c in df.columns if 'tel' in c.lower() or 'cel' in c.lower()]
        if not col_telefono:
            return {"success": False, "message": "No se encontró la columna de teléfonos en el Excel."}
        
        nombre_columna = col_telefono[0]
        
        # Configuración de Wati (Cámbialo por tus credenciales reales o variables de entorno)
        WATI_API_ENDPOINT = "https://live-mt-server.wati.io/10157709" 
        WATI_TOKEN = "TU_BEARER_TOKEN_AQUI" 
        
        headers = {
            "Authorization": f"Bearer {WATI_TOKEN}",
            "Content-Type": "application/json"
        }
        
        exitosos = 0
        fallidos = 0

        for index, row in df.iterrows():
            telefono_crudo = str(row[nombre_columna])
            telefono_limpio = limpiar_y_formatear_telefono(telefono_crudo)
            
            if not telefono_limpio:
                fallidos += 1
                continue
                
            # --- AQUÍ ESTÁ EL CAMBIO CLAVE SEGÚN LA DOCUMENTACIÓN DE WATI ---
            # El número ({target}) va EN LA RUTA, NO como parámetro query ?whatsappNumber=
            url_wati = f"{WATI_API_ENDPOINT}/api/v1/sendSessionMessage/{telefono_limpio}"
            
            # El texto que vas a mandar (puedes personalizarlo con tu enlace, hotel, etc.)
            payload = {
                "messageText": f"Hola, te invitamos a responder nuestra encuesta del hotel {hotel} en {localizacion}: {enlace}"
            }
            
            try:
                response = requests.post(url_wati, json=payload, headers=headers, timeout=10)
                if response.status_code == 200:
                    exitosos += 1
                else:
                    fallidos += 1
            except Exception:
                fallidos += 1

        # Devolvemos exactamente la estructura con "success" que espera tu JavaScript
        return {
            "success": True, 
            "message": f"Proceso terminado. Envíos exitosos: {exitosos}, Fallidos: {fallidos}"
        }

    except Exception as e:
        # Si algo falla críticamente, devolvemos un JSON válido para que JS no tire "undefined"
        return {"success": False, "message": f"Error interno en el servidor Python: {str(e)}"}

# Endpoint de Healthcheck para que Coolify no piense que la app está muerta
@app.get("/health")
def health_check():
    return {"status": "healthy"}
