from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import sqlite3
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INICIALIZACIÓN DE LA BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect('trivia.db')
    cursor = conn.cursor()
    # Creamos la tabla con todos los campos que tu juego ya usa
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS preguntas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pregunta TEXT NOT NULL,
            opciones TEXT NOT NULL,
            correcta TEXT NOT NULL,
            categoria TEXT,
            dificultad TEXT,
            idioma TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- MODELOS PARA RECIBIR DATOS ---
class PreguntaSchema(BaseModel):
    question_text: str
    options: List[str]
    correct_answer: str
    category: str
    difficulty: str
    language_code: str

class PaqueteInyeccion(BaseModel):
    secret_key: str
    preguntas: List[PreguntaSchema]

# --- RUTAS ---

@app.get("/pregunta-random")
def obtener_pregunta(lang: str = "es"):
    conn = sqlite3.connect('trivia.db')
    cursor = conn.cursor()
    # Obtenemos todas las preguntas del idioma seleccionado
    cursor.execute("SELECT * FROM preguntas WHERE idioma = ?", (lang,))
    filas = cursor.fetchall()
    conn.close()

    if not filas:
        return {
            "pregunta": "No hay preguntas cargadas aún",
            "opciones": ["Inyecta datos", "desde Colab", "para jugar", "suerte"],
            "correcta": "suerte",
            "categoria": "SISTEMA",
            "dificultad": "EASY"
        }

    # Selección aleatoria pura
    p = random.choice(filas)
    return {
        "id": p[0],
        "pregunta": p[1],
        "opciones": p[2].split("|"), # Convertimos el texto de la DB a lista
        "correcta": p[3],
        "categoria": p[4],
        "dificultad": p[5]
    }

@app.post("/inyectar-preguntas")
async def inyectar(paquete: PaqueteInyeccion):
    if paquete.secret_key != "Qbit2026":
        raise HTTPException(status_code=403, detail="Llave incorrecta")
    
    conn = sqlite3.connect('trivia.db')
    cursor = conn.cursor()
    for p in paquete.preguntas:
        cursor.execute('''
            INSERT INTO preguntas (pregunta, opciones, correcta, categoria, dificultad, idioma)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (p.question_text, "|".join(p.options), p.correct_answer, p.category, p.difficulty, p.language_code))
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM preguntas")
    total = cursor.fetchone()[0]
    conn.close()
    return {"status": "success", "total_actual": total}

@app.get("/")
def estado():
    conn = sqlite3.connect('trivia.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM preguntas")
    total = cursor.fetchone()[0]
    conn.close()
    return {"status": "online", "total_preguntas": total}