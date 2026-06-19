import os
import re
import requests
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
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

# --- ENDPOINT 1: ENVÍOS MASIVOS ---
@app.post("/procesar")
async def procesar_envios(
    file: UploadFile = File(...),
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
        
        WATI_API_URL = "https://live-mt-server.wati.io/api/ext/v3/messageTemplates/send"
        WATI_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmlxdWVfbmFtZSI6InNpY2hpdHVyQGdtYWlsLmNvbSIsIm5hbWVpZCI6InNpY2hpdHVyQGdtYWlsLmNvbSIsImVtYWlsIjoic2ljaGl0dXJAZ21haWwuY29tIiwiYXV0aF90aW1lIjoiMDYvMTgvMjAyNiAyMTozMjozNCIsInRlbmFudF9pZCI6IjEwMTU3NzA5IiwiZGJfbmFtZSI6Im10LXByb2QtVGVuYW50cyIsImh0dHA6Ly9zY2hlbWFzLm1pY3Jvc29mdC5jb20vd3MvMjAwOC8wNi9pZGVudGl0eS9jbGFpbXMvcm9sZSI6IkFETUlOSVNUUkFUT1IiLCJleHAiOjI1MzQwMjMwMDgwMCwiaXNzIjoiQ2xhcmVfQUkiLCJhdWQiOiJDbGFyZV9BSSJ9.Yc38bchQyP3kuFCmW2cBIDdTrxvRPw3at1XuLyAzbuI"
        
        headers = {
            "accept": "application/json",
            "content-type": "application/json-patch+json",
            "Authorization": f"Bearer {WATI_TOKEN.strip()}"
        }
        
        reporte_envios = []

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
                
            municipio_limpio = localizacion.strip().strip('/')
            hotel_limpio = hotel.strip()
            
            liga_dinamica_param = f"{municipio_limpio}/?hotel={hotel_limpio}"
            broadcast_limpio = f"Encuesta_{municipio_limpio}".replace(" ", "_")
            
            payload = {
                "template_name": "encuestapv",
                "broadcast_name": broadcast_limpio,
                "recipients": [
                    {
                        "phone_number": telefono_limpio,
                        "local_message_id": f"local-{index}-{telefono_limpio}", 
                        "custom_params": [
                            {
                                "name": "1",
                                "value": str(localizacion).strip()
                            },
                            {
                                "name": "2",
                                "value": f"/{liga_dinamica_param}" 
                            }
                        ]
                    }
                ]
            }
            
            try:
                response = requests.post(WATI_API_URL, json=payload, headers=headers, timeout=10)
                
                if response.status_code in [200, 201]:
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

        return {
            "success": True,
            "tipo_dato": "telefono",
            "extracted_data": reporte_envios
        }

    except Exception as e:
        return {"success": False, "message": f"Error crítico del sistema: {str(e)}"}

# --- ENDPOINT 2: ENVÍO INDIVIDUAL (CORREGIDO DE INDENTACIÓN) ---
@app.post("/procesar-individual")
async def procesar_envio_individual(
    telefono: str = Form(...),
    localizacion: str = Form(...),
    hotel: str = Form(...)
):
    try:
        telefono_limpio = limpiar_y_formatear_telefono(telefono)
        
        if not telefono_limpio:
            return {
                "success": True,
                "extracted_data": [{
                    "dato": telefono,
                    "procesado": "Inválido",
                    "estado": "fallido (Número vacío o inválido)"
                }]
            }
            
        WATI_API_URL = "https://live-mt-server.wati.io/api/ext/v3/messageTemplates/send"
        WATI_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmlxdWVfbmFtZSI6InNpY2hpdHVyQGdtYWlsLmNvbSIsIm5hbWVpZCI6InNpY2hpdHVyQGdtYWlsLmNvbSIsImVtYWlsIjoic2ljaGl0dXJAZ21haWwuY29tIiwiYXV0aF90aW1lIjoiMDYvMTgvMjAyNiAyMTozMjozNCIsInRlbmFudF9pZCI6IjEwMTU3NzA5IiwiZGJfbmFtZSI6Im10LXByb2QtVGVuYW50cyIsImh0dHA6Ly9zY2hlbWFzLm1pY3Jvc29mdC5jb20vd3MvMjAwOC8wNi9pZGVudGl0eS9jbGFpbXMvcm9sZSI6IkFETUlOSVNUUkFUT1IiLCJleHAiOjI1MzQwMjMwMDgwMCwiaXNzIjoiQ2xhcmVfQUkiLCJhdWQiOiJDbGFyZV9BSSJ9.Yc38bchQyP3kuFCmW2cBIDdTrxvRPw3at1XuLyAzbuI"
        
        headers = {
            "accept": "application/json",
            "content-type": "application/json-patch+json",
            "Authorization": f"Bearer {WATI_TOKEN.strip()}"
        }
        
        municipio_limpio = localizacion.strip().strip('/')
        hotel_limpio = hotel.strip()
        
        liga_dinamica_param = f"{municipio_limpio}/?hotel={hotel_limpio}"
        broadcast_limpio = f"Encuesta_Ind_{municipio_limpio}".replace(" ", "_")
        
        payload = {
            "template_name": "encuestapv",
            "broadcast_name": broadcast_limpio,
            "recipients": [
                {
                    "phone_number": telefono_limpio,
                    "local_message_id": f"local-ind-{telefono_limpio}", 
                    "custom_params": [
                        { "name": "1", "value": str(localizacion).strip() },
                        { "name": "2", "value": f"/{liga_dinamica_param}" }
                    ]
                }
            ]
        }
        
        try:
            response = requests.post(WATI_API_URL, json=payload, headers=headers, timeout=10)
            if response.status_code in [200, 201]:
                estado = "enviado"
            else:
                try:
                    error_detail = response.json().get('info', response.text)
                except:
                    error_detail = response.text
                estado = f"fallido (Wati Error {response.status_code}: {error_detail})"
        except Exception as err:
            estado = f"fallido (Error Conexión: {type(err).__name__})"

        return {
            "success": True,
            "tipo_dato": "telefono",
            "extracted_data": [{
                "dato": telefono,
                "procesado": telefono_limpio,
                "estado": estado
            }]
        }

    except Exception as e:
        return {"success": False, "message": f"Error crítico en envío individual: {str(e)}"}
        

# --- HEALTH CHECK ---
@app.get("/health")
def health_check():
    return {"status": "healthy"}
