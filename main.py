from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import random

app = FastAPI()

# --- CONFIGURACIÓN DE SEGURIDAD (CORS) ---
# Permite que tu juego en GitHub Pages o local se conecte sin bloqueos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS DE DATOS ---
class Pregunta(BaseModel):
    question_text: str
    options: List[str]
    correct_answer: str
    category: str
    difficulty: str
    language_code: str
    region_target: str

class PaqueteInyeccion(BaseModel):
    secret_key: str
    preguntas: List[Pregunta]

# --- BASE DE DATOS EN MEMORIA ---
# Iniciamos con la pregunta de Canadá por defecto
db_preguntas = [
    {
        "id": 1,
        "pregunta": "¿Cuál es la capital de Canadá?",
        "opciones": ["Toronto", "Vancouver", "Montreal", "Ottawa"],
        "correcta": "Ottawa",
        "idioma": "es",
        "region": "MX"
    }
]

# Historial para evitar repeticiones en la misma sesión
preguntas_vistas = []

# --- RUTAS ---

@app.get("/")
def home():
    return {"status": "online", "server_time": "2026-01-22", "total_questions": len(db_preguntas)}

@app.get("/pregunta-random")
def obtener_pregunta(lang: str = "es"):
    # Filtrar por idioma seleccionado en el juego
    opciones = [p for p in db_preguntas if p.get("idioma") == lang]
    
    if not opciones:
        opciones = db_preguntas # Si no hay del idioma, usar cualquiera

    # Buscar preguntas que el usuario aún no haya visto
    disponibles = [p for p in opciones if p.get("id") not in preguntas_vistas]
    
    # Si ya se mostraron todas, reiniciamos el historial
    if not disponibles:
        preguntas_vistas.clear()
        disponibles = opciones

    seleccionada = random.choice(disponibles)
    
    # Registrar que ya se vio esta pregunta
    if "id" in seleccionada:
        preguntas_vistas.append(seleccionada["id"])
        
    return seleccionada

@app.post("/inyectar-preguntas")
async def inyectar(paquete: PaqueteInyeccion):
    # Verificación de seguridad con tu llave
    if paquete.secret_key != "Qbit2026":
        raise HTTPException(status_code=403, detail="Llave secreta incorrecta")
    
    for p in paquete.preguntas:
        nueva = {
            "id": len(db_preguntas) + 1,
            "pregunta": p.question_text,
            "opciones": p.options,
            "correcta": p.correct_answer,
            "categoria": p.category,
            "idioma": p.language_code,
            "region": p.region_target
        }
        db_preguntas.append(nueva)
    
    return {"status": "success", "agregadas": len(paquete.preguntas), "total_actual": len(db_preguntas)}

@app.post("/validar-respuesta")
def validar(datos: dict):
    return {"status": "received"}
