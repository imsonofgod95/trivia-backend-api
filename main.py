from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import random

app = FastAPI()

# Configuración de CORS para que tu GitHub Pages pueda conectarse
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

# --- BASE DE DATOS TEMPORAL (EN MEMORIA) ---
# En un proyecto real usarías SQL, aquí usamos una lista de Python
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

# --- RUTAS ---

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Qbit Trivia API v8.7"}

@app.get("/pregunta-random")
def obtener_pregunta(idioma: str = "es", region: str = "MX"):
    filtro = [p for p in db_preguntas if p.get("idioma") == idioma]
    if not filtro:
        return db_preguntas[0] # Devolver una por defecto si no hay del idioma
    return random.choice(filtro)

@app.post("/validar-respuesta")
def validar(datos: dict):
    # Lógica simple de validación
    return {"resultado": True, "puntos_obtenidos": 10}

# --- LA RUTA QUE TE FALTABA ---
@app.post("/inyectar-preguntas")
async def inyectar(paquete: PaqueteInyeccion):
    if paquete.secret_key != "Qbit2026":
        raise HTTPException(status_code=403, detail="Llave secreta incorrecta")
    
    contador = 0
    for p in paquete.preguntas:
        nueva = {
            "id": len(db_preguntas) + 1,
            "pregunta": p.question_text,
            "opciones": p.options,
            "correcta": p.correct_answer,
            "idioma": p.language_code,
            "region": p.region_target
        }
        db_preguntas.append(nueva)
        contador += 1
    
    return {"status": "success", "agregadas": contador, "total_db": len(db_preguntas)}
