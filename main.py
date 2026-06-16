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
        contents = await file.read()
        df = pd.read_excel(contents)
        
        col_telefono = [c for c in df.columns if 'tel' in c.lower() or 'cel' in c.lower()]
        if not col_telefono:
            return {"success": False, "message": "No se encontró la columna de teléfonos en el Excel."}
        
        nombre_columna = col_telefono[0]
        
        WATI_API_ENDPOINT = "https://live-mt-server.wati.io/10157709"
        WATI_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmlxdWVfbmFtZSI6InNpY2hpdHVyQGdtYWlsLmNvbSIsIm5hbWVpZCI6InNpY2hpdHVyQGdtYWlsLmNvbSIsImVtYWlsIjoic2ljaGl0dXJAZ21haWwuY29tIiwiYXV0aF90aW1lIjoiMDYvMTYvMjAyNiAyMDoyNTo1OCIsInRlbmFudF9pZCI6IjEwMTU3NzA5IiwiZGJfbmFtZSI6Im10LXByb2QtVGVuYW50cyIsImh0dHA6Ly9zY2hlbWFzLm1pY3Jvc29mdC5jb20vd3MvMjAwOC8wNi9pZGVudGl0eS9jbGFpbXMvcm9sZSI6IkFETUlOSVNUUkFUT1IiLCJleHAiOjI1MzQwMjMwMDgwMCwiaXNzIjoiQ2xhcmVfQUkiLCJhdWQiOiJDbGFyZV9BSSJ9.i4VDAn20RPQ3wEe2HizMNBaRJ4Jj7EM0kk18YxSEMdc"
        
        headers = {
            "Authorization": f"Bearer {WATI_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # --- AQUÍ VOLVEMOS A DECLARAR EL REPORTE DETALLADO ---
        reporte_envios = []

        for index, row in df.iterrows():
            telefono_crudo = str(row[nombre_columna]).strip()
            telefono_limpio = limpiar_y_formatear_telefono(telefono_crudo)
            
            if not telefono_limpio:
                reporte_envios.append({
                    "dato": telefono_crudo,
                    "procesado": "Inválido",
                    "estado": "fallido (Número vacío o mal estructurado)"
                })
                continue
                
            url_wati = f"{WATI_API_ENDPOINT}/api/v1/sendSessionMessage/{telefono_limpio}"
            payload = {
                "templateName": "sichitur_prueba_1",
                "broadcastName": "Encuesta_Masiva",
                "parameters": [
                    {"name": "body_variable_1", "value": hotel},         # Si tu plantilla usa {{1}}
                    {"name": "body_variable_2", "value": localizacion},   # Si usa {{2}}
                    {"name": "body_variable_3", "value": enlace}          # Si usa {{3}}
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

            # Guardamos el resultado de esta fila
            reporte_envios.append({
                "dato": telefono_crudo,
                "procesado": telefono_limpio,
                "estado": estado
            })

        # --- RETORNAMOS LA ESTRUCTURA COMPLETA QUE BUSCA EL FOREACH ---
        return {
            "success": True,
            "tipo_dato": "telefono",
            "extracted_data": reporte_envios
        }

    except Exception as e:
        return {"success": False, "message": f"Error al procesar el archivo: {str(e)}"}

# Endpoint de Healthcheck para que Coolify no piense que la app está muerta
@app.get("/health")
def health_check():
    return {"status": "healthy"}
