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
    file: UploadFile = File(...),
    enlace: str = Form(...),
    localizacion: str = Form(...),
    hotel: str = Form(...)
):
    try:
        # 1. Leer el archivo Excel
        contents = await file.read()
        df = pd.read_excel(contents)
        
        # Detectar de forma inteligente la columna de teléfonos
        col_telefono = [c for c in df.columns if 'tel' in c.lower() or 'cel' in c.lower()]
        if not col_telefono:
            return {"success": False, "message": "No se encontró la columna de teléfonos en el Excel."}
        
        nombre_columna = col_telefono[0]
        
        # 2. Configuración de Credenciales de Wati
        WATI_API_ENDPOINT = "https://live-mt-server.wati.io/10157709"
        WATI_TOKEN = "TU_TOKEN_SUPER_LARGO_DE_WATI_AQUI"
        
        headers = {
            "Authorization": f"Bearer {WATI_TOKEN.strip()}",
            "Content-Type": "application/json"
        }
        
        reporte_envios = []

        # 3. Iterar cada registro del Excel
        for index, row in df.iterrows():
            telefono_crudo = str(row[nombre_columna]).strip()
            telefono_limpio = limpiar_y_formatear_telefono(telefono_crudo)
            
            if not telefono_limpio:
                reporte_envios.append({
                    "dato": telefono_crudo,
                    "procesado": "Inválido",
                    "estado": "fallido (Número vacío o inválido)"
                })
                continue
                
            # Endpoint correcto para Plantillas Oficiales de Meta/Wati
            url_wati = f"{WATI_API_ENDPOINT}/api/v1/sendTemplateMessage/{telefono_limpio}"
            
            # 4. Construcción del Payload con Variables Dinámicas
            # Nota: Meta exige que las variables se envíen en orden secuencial (body_variable_1, body_variable_2, etc.)
            # Si tu botón dinámico es el que usa la URL, Wati suele mapearlo como el último parámetro o en una sección de botones.
            # En una estructura estándar de Wati con texto y botón dinámico, se envían en los parámetros del body:
            payload = {
                "templateName": "sichitur_prueba_1", 
                "broadcastName": f"Masivo_{hotel.replace(' ', '_')}",
                "parameters": [
                    {"name": "body_variable_1", "value": hotel},         # Ejemplo: {{1}} en el texto
                    {"name": "body_variable_2", "value": localizacion},  # Ejemplo: {{2}} en el texto
                    {"name": "body_variable_3", "value": enlace}          # Ejemplo: {{3}} que alimenta la liga dinámica
                ]
            }
            
            try:
                response = requests.post(url_wati, json=payload, headers=headers, timeout=10)
                if response.status_code == 200:
                    estado = "enviado"
                else:
                    try:
                        error_detail = response.json().get('info', response.text)
                    except:
                        error_detail = response.text
                    estado = f"fallido (Wati Error {response.status_code}: {error_detail})"
            except Exception as err:
                estado = f"fallido (Error Conexión: {type(err).__name__})"

            reporte_envios.append({
                "dato": telefono_crudo,
                "procesado": telefono_limpio,
                "estado": estado
            })

        # 5. Respuesta JSON completa para que JavaScript la pinte sin romperse
        return {
            "success": True,
            "tipo_dato": "telefono",
            "extracted_data": reporte_envios
        }

    except Exception as e:
        return {"success": False, "message": f"Error crítico del sistema: {str(e)}"}
# Endpoint de Healthcheck para que Coolify no piense que la app está muerta
@app.get("/health")
def health_check():
    return {"status": "healthy"}
