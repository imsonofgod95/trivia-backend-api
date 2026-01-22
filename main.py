from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import sqlite3
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "trivia_game.db"

# --- MODELOS ---
class PreguntaIA(BaseModel):
    question_text: str
    options: List[str]
    correct_answer: str
    category: str
    difficulty: str
    language_code: str
    region_target: str

# Nuevo modelo que envuelve las preguntas y la llave
class LotePreguntas(BaseModel):
    secret_key: str
    preguntas: List[PreguntaIA]

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row 
    return conn

@app.get("/")
def home():
    return {"mensaje": "Qbit API Online", "version": "4.0 (Bypass Mode)"}

@app.post("/admin/inyectar-preguntas")
def inyectar_preguntas(lote: LotePreguntas):
    # Validamos la llave que viene DENTRO del JSON
    if lote.secret_key != "Qbit2026":
        raise HTTPException(status_code=403, detail="Llave incorrecta en JSON")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        count = 0
        for p in lote.preguntas:
            cursor.execute("""
                INSERT INTO questions (question_text, options, correct_answer, category, difficulty, language_code, region_target)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (p.question_text, json.dumps(p.options), p.correct_answer, p.category, p.difficulty, p.language_code, p.region_target))
            count += 1
        conn.commit()
        return {"status": "success", "agregadas": count}
    finally:
        conn.close()

# Las rutas de juego (obtener y validar) se quedan igual que en la v3.0
@app.get("/pregunta-random")
def obtener_pregunta(idioma: str = "es", region: str = "MX"):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM questions WHERE language_code = ? AND region_target = ? ORDER BY RANDOM() LIMIT 1", (idioma, region))
        row = cursor.fetchone()
        if not row: raise HTTPException(status_code=404)
        return {"id": row["id"], "pregunta": row["question_text"], "opciones": json.loads(row["options"]), "categoria": row["category"], "dificultad": row["difficulty"]}
    finally:
        conn.close()

@app.post("/validar-respuesta")
def validar(datos: dict):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT correct_answer FROM questions WHERE id = ?", (datos['pregunta_id'],))
        row = cursor.fetchone()
        correcta = row["correct_answer"]
        return {"resultado": datos['respuesta_elegida'] == correcta, "correcta_era": correcta if datos['respuesta_elegida'] != correcta else None}
    finally:
        conn.close()