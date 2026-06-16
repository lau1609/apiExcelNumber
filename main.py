from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import requests
import time
import io
import re

app = FastAPI(title="Wati Bulk Sender API")

# Configuración de CORS habilitada para tu frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# URL Base según tu documentación oficial (¡Ya no incluye la ruta del endpoint al final!)
WATI_URL = "https://live-mt-server.wati.io/10157709"

# Tu clave JWT pura
WATTI_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmlxdWVfbmFtZSI6InNpY2hpdHVyQGdtYWlsLmNvbSIsEwMTU3NzA5IiwiZGJfbmFtZSI6Im10LXByb2QtVGVuYW50cyIsImh0dHA6Ly9zY2hlbWFzLm1pY3Jvc29mdC5jb20vd3MvMjAwOC8wNi9pZGVudGl0eS9jbGFpbXMvcm9sZSI6IkFETUlOSVNUUkFUT1IiLCJleHAiOjI1MzQwMjMwMDgwMCwiaXNzIjoiQ2xhcmVfQUkiLCJhdWQiOiJDbGFyZV9BSSJ9.ValZyX1jO5C_2uO-TM6Dlpt5q9sQWgY-xCQZuUMNkY8..." 

def limpiar_y_formatear_telefono(telefono_crudo: str) -> str:
    """
    Limpia cualquier formato extraño del número y asegura el formato internacional 
    adecuado para México (52 + 10 dígitos), removiendo el '1' si viene integrado
    ya que las versiones actuales de WhatsApp API no lo requieren.
    """
    if not telefono_crudo or telefono_crudo == 'nan':
        return ""
        
    # 1. Forzar limpieza si Pandas guardó residuos de tipo flotante (.0)
    t_clean = telefono_crudo.strip()
    if t_clean.endswith('.0'):
        t_clean = t_clean[:-2]
        
    # 2. Dejar única y estrictamente los caracteres numéricos
    numeros = re.sub(r'\D', '', t_clean)
    
    if not numeros:
        return ""
        
    # 3. Normalización de lada internacional para México (52)
    # Si viene a 10 dígitos locales (ej: 6142843215), le ponemos el prefijo 52
    if len(numeros) == 10:
        numeros = '52' + numeros  
        
    # Si viene con 13 dígitos (ej: 5216142843215), le removemos el '1' sobrante
    if len(numeros) == 13 and numeros.startswith('521'):
        numeros = '52' + numeros[3:]
        
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

        # Mantenemos los encabezados limpios. Si Wati te rechaza el token por el "Bearer ", 
        # puedes cambiarlo a: "Authorization": WATTI_API_KEY
        headers = {
            "Authorization": f"Bearer {WATTI_API_KEY}",
            "Accept": "application/json"
        }

        reporte_envios = []

        for index, fila in df.iterrows():
            # Convertimos el contenido de la celda a string antes de limpiar
            str_telefono = str(fila['Telefono']).strip()
            telefono_limpio = limpiar_y_formatear_telefono(str_telefono)
            
            if not telefono_limpio:
                continue

            mensaje = f"¡Hola! Te invitamos a contestar nuestra encuesta en el siguiente enlace: {url or 'sichtur.org'}"
            
            # CORRECCIÓN 1: El teléfono ({target}) ahora va incrustado directamente en la ruta (Path Parameter)
            url_envio = f"{WATI_URL}/api/v1/sendSessionMessage/{telefono_limpio}"
            
            # CORRECCIÓN 2: El mensaje viaja como Query Parameter en la URL, no en el cuerpo JSON
            query_params = {
                "messageText": mensaje
            }

            try:
                # Enviamos la petición usando 'params' para inyectar las variables en la URL
                response = requests.post(url_envio, params=query_params, headers=headers, timeout=10)
                
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
                "dato": str_telefono,             # Entrada original del Excel
                "procesado": telefono_limpio,     # Teléfono procesado final
                "estado": estado
            })

            # Control de flujo de envío respetando los límites de Wati
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
