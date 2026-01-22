from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import random

app = FastAPI()

# --- CONFIGURACIÓN DE SEGURIDAD (CORS) ---
# Esto evita el error "Error de conexión con la base de datos"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite conexiones desde cualquier origen (Local o GitHub Pages)
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
# Aquí se guardan las preguntas que inyectas desde Colab
db_preguntas = [
    {
        "pregunta": "¿Cuál es la capital de Canadá?",
        "opciones": ["Toronto", "Vancouver", "Montreal", "Ottawa"],
        "correcta": "Ottawa",
        "idioma": "es",
        "region": "MX"
    }
]

# --- RUTAS ---

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Qbit Trivia API v8.7"}

@app.get("/pregunta-random")
def obtener_pregunta():
    if not db_preguntas:
        raise HTTPException(status_code=404, detail="No hay preguntas en la base de datos")
    return random.choice(db_preguntas)

@app.post("/inyectar-preguntas")
async def inyectar(paquete: PaqueteInyeccion):
    if paquete.secret_key != "Qbit2026":
        raise HTTPException(status_code=403, detail="Llave secreta incorrecta")
    
    for p in paquete.preguntas:
        nueva = {
            "pregunta": p.question_text,
            "opciones": p.options,
            "correcta": p.correct_answer,
            "categoria": p.category,
            "idioma": p.language_code,
            "region": p.region_target
        }
        db_preguntas.append(nueva)
    
    return {"status": "success", "total_db": len(db_preguntas)}

@app.post("/validar-respuesta")
def validar(datos: dict):
    # Lógica simple de validación para el frontend
    return {"resultado": True}
