from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import random

app = FastAPI()

# --- MODELO DE DATOS ---
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

# Tu base de datos (lista) actual
db_preguntas = [] 

# --- LA RUTA QUE DEBE EXISTIR ---
@app.post("/inyectar-preguntas")
async def inyectar(paquete: PaqueteInyeccion):
    # Verificación de seguridad
    if paquete.secret_key != "Qbit2026":
        raise HTTPException(status_code=403, detail="Llave incorrecta")
    
    for p in paquete.preguntas:
        nueva_pregunta = {
            "id": len(db_preguntas) + 1,
            "pregunta": p.question_text,
            "opciones": p.options,
            "correcta": p.correct_answer,
            "categoria": p.category,
            "idioma": p.language_code,
            "region": p.region_target
        }
        db_preguntas.append(nueva_pregunta)
    
    return {"status": "success", "agregadas": len(paquete.preguntas), "total": len(db_preguntas)}

# No olvides tus otras rutas (GET /pregunta-random, etc.)
