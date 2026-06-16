from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import requests
import time
import io
import re

app = FastAPI(title="Wati Bulk Sender API")

# Permitir que tu frontend se conecte sin problemas de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WATI_URL = "https://live-mt-server.wati.io/10157709/api/v1/sendSessionMessage"
# ¡IMPORTANTE!: Quitamos la palabra "Bearer ". Deja solo tu clave pura.
WATTI_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmlxdWVfbmFtZSI6InNpY2hpdHVyQGdtYWlsLmNvbSIsIm5hbWVpZCI6InNpY2hpdHVyQGdtYWlsLmNvbSIsImVtYWlsIjoic2ljaGl0dXJAZ21haWwuY29tIiwiYXV0aF90aW1lIjoiMDYvMTYvMjAyNiAxNzo1NToyNCIsInRlbmFudF9pZCI6IjEwMTU3NzA5IiwiZGJfbmFtZSI6Im10LXByb2QtVGVuYW50cyIsImh0dHA6Ly9zY2hlbWFzLm1pY3Jvc29mdC5jb20vd3MvMjAwOC8wNi9pZGVudGl0eS9jbGFpbXMvcm9sZSI6IkFETUlOSVNUUkFUT1IiLCJleHAiOjI1MzQwMjMwMDgwMCwiaXNzIjoiQ2xhcmVfQUkiLCJhdWQiOiJDbGFyZV9BSSJ9.ValZyX1jO5C_2uO-TM6Dlpt5q9sQWgY-xCQZuUMNkY8..." 

def limpiar_y_formatear_telefono(telefono_crudo: str) -> str:
    """
    Limpia cualquier formato de teléfono y lo convierte al estándar internacional de Wati.
    Ejemplos para México:
    - '(614) 123-4567' -> '526141234567'
    - '6141234567' -> '526141234567'
    - '5216141234567' -> '526141234567' (Remueve el '1' intermedio de WhatsApp)
    """
    if not telefono_crudo or telefono_crudo == 'nan':
        return ""
        
    # 1. Si Pandas lo leyó como flotante (ej: 5216141234.0), le quitamos el decimal
    if telefono_crudo.endswith('.0'):
        telefono_crudo = telefono_crudo[:-2]
        
    # 2. Dejar única y estrictamente los números (borra paréntesis, espacios, guiones y signos +)
    numeros = re.sub(r'\D', '', telefono_crudo)
    
    if not numeros:
        return ""
        
    # 3. Formatear lógica específica para México / Internacional
    # Si tiene 13 dígitos y empieza con 521 (formato viejo de WhatsApp México con el '1' intermedio)
    if len(numeros) == 13 and numeros.startswith('521'):
        numeros = '52' + numeros[3:]  # Quitamos el '1' para dejarlo en 52 + 10 dígitos
        
    # Si el usuario solo metió los 10 dígitos locales (ej: 6141234567)
    elif len(numeros) == 10:
        numeros = '52' + numeros  # Le agregamos de forma automática el prefijo de México
        
    return numeros

@app.post("/procesar")
async def procesar_archivo(
    file: UploadFile = File(...),
    url: str = Form(None),
    loc: str = Form(None),
    hotel: str = Form(None)
):
    if not file.filename.endswith(('.xlsx', '.xls')):
        return {"success": False, "message": "El archivo debe ser un Excel válido (.xlsx o .xls)"}

    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        df.columns = df.columns.str.strip()

        if 'Telefono' not in df.columns:
            return {"success": False, "message": "El Excel debe contener una columna llamada 'Telefono'"}

        # Encabezados corregidos: Wati espera el token crudo en la propiedad Authorization
        headers = {
            "Authorization": WATTI_API_KEY,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        reporte_envios = []

        for index, fila in df.iterrows():
            str_telefono = str(fila['Telefono']).strip()
            
            # Pasamos el teléfono por nuestra función inteligente de limpieza
            telefono_limpio = limpiar_y_formatear_telefono(str_telefono)
            
            # Saltarse filas vacías o que no arrojaron un número válido
            if not telefono_limpio:
                continue

            mensaje = f"¡Hola! Te invitamos a contestar nuestra encuesta en el siguiente enlace: {url or 'sichtur.org'}"
            url_envio = f"{WATI_URL}?whatsappNumber={telefono_limpio}"
            payload = {"messageText": mensaje}

            try:
                response = requests.post(url_envio, json=payload, headers=headers, timeout=10)
                
                # Evaluamos si Wati aceptó el mensaje (Códigos 200 o 201)
                if response.status_code in [200, 201]:
                    estado = "enviado"
                else:
                    estado = f"fallido (API Error {response.status_code})"
            except Exception as err:
                estado = f"fallido ({type(err).__name__})"

            # Guardamos en el reporte el teléfono ya formateado para que el usuario vea cómo se mandó
            reporte_envios.append({
                "dato": telefono_limpio,
                "estado": estado
            })

            # ⏳ Pausa de 1.5 segundos regulada
            time.sleep(1.5)

        return {
            "success": True,
            "tipo_dato": "telefono",
            "extracted_data": reporte_envios
        }

    except Exception as e:
        return {"success": False, "message": f"Error al procesar el Excel: {str(e)}"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
