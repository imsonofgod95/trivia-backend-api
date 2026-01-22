from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Any
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

# --- FUNCIÓN QUE CREA LA TABLA SI NO EXISTE ---
def inicializar_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT,
            options TEXT,
            correct_answer TEXT,
            category TEXT,
            difficulty TEXT,
            language_code TEXT,
            region_target TEXT
        )
    """)
    conn.commit()
    conn.close()

# Ejecutamos la creación al iniciar el servidor
inicializar_db()

class LotePreguntas(BaseModel):
    secret_key: str
    preguntas: List[Any]

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row 
    return conn

@app.get("/")
def home():
    return {"mensaje": "Qbit API Online", "version": "6.0 (Auto-Repair Mode)"}

@app.post("/admin/inyectar-preguntas")
def inyectar_preguntas(lote: LotePreguntas):
    if lote.secret_key != "Qbit2026":
        raise HTTPException(status_code=403, detail="Llave incorrecta")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        count = 0
        for p in lote.preguntas:
            q_text = p.get("question_text", "Untitled")
            opts = json.dumps(p.get("options", []))
            correct = p.get("correct_answer", "")
            cat = p.get("category", "General")
            diff = p.get("difficulty", "Medium")
            lang = p.get("language_code", "en")
            reg = p.get("region_target", "US")

            cursor.execute("""
                INSERT INTO questions (question_text, options, correct_answer, category, difficulty, language_code, region_target)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (q_text, opts, correct, cat, diff, lang, reg))
            count += 1
        conn.commit()
        return {"status": "success", "agregadas": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error DB: {str(e)}")
    finally:
        conn.close()

# --- RUTAS DE JUEGO ---
@app.get("/pregunta-random")
def obtener_pregunta(idioma: str = "es", region: str = "MX"):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM questions WHERE language_code = ? AND region_target = ? ORDER BY RANDOM() LIMIT 1", (idioma, region))
        row = cursor.fetchone()
        if not row: raise HTTPException(status_code=404)
        return {
            "id": row["id"],
            "pregunta": row["question_text"],
            "opciones": json.loads(row["options"]),
            "categoria": row["category"],
            "dificultad": row["difficulty"]
        }
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