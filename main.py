from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Any, Optional
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

inicializar_db()

class RespuestaUsuario(BaseModel):
    pregunta_id: int
    respuesta_elegida: str
    tiempo_ms: int

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row 
    return conn

@app.get("/")
def home():
    return {"mensaje": "Qbit API Online", "version": "7.5 (Full Timer Support)"}

@app.get("/pregunta-random")
def obtener_pregunta(idioma: str = "es", region: str = "MX"):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM questions WHERE language_code = ? AND region_target = ? ORDER BY RANDOM() LIMIT 1", (idioma, region))
        row = cursor.fetchone()
        if not row: raise HTTPException(status_code=404)
        return {"id": row["id"], "pregunta": row["question_text"], "opciones": json.loads(row["options"])}
    finally:
        conn.close()

@app.post("/validar-respuesta")
def validar(datos: RespuestaUsuario):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT correct_answer FROM questions WHERE id = ?", (datos.pregunta_id,))
        row = cursor.fetchone()
        if not row: raise HTTPException(status_code=404)
        
        correcta = row["correct_answer"]
        es_correcta = datos.respuesta_elegida == correcta
        
        puntos = 0
        if es_correcta:
            # Si contesta en menos de 15 segundos, gana entre 10 y 100 puntos
            segundos = datos.tiempo_ms / 1000
            puntos = max(10, int(100 - (segundos * 6)))

        return {
            "resultado": es_correcta,
            "puntos_obtenidos": puntos,
            "correcta_era": correcta if not es_correcta else None
        }
    finally:
        conn.close()