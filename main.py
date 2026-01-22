# main.py actualizado para AUTOMATIZACIÓN
from fastapi import FastAPI, HTTPException, Header
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

# --- MODELOS DE DATOS ---
class PreguntaIA(BaseModel):
    question_text: str
    options: List[str]
    correct_answer: str
    category: str
    difficulty: str
    language_code: str
    region_target: str

class RespuestaUsuario(BaseModel):
    pregunta_id: int
    respuesta_elegida: str

DB_NAME = "trivia_game.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row 
    return conn

# --- RUTA SECRETA PARA AUTOMATIZAR (INYECCIÓN DE DATOS) ---
@app.post("/admin/inyectar-preguntas")
def inyectar_preguntas(preguntas: List[PreguntaIA], secret_key: str = Header(None)):
    # Ciberseguridad básica: Solo tú puedes usar esta ruta
    # Cambia 'Qbit2026' por la contraseña que quieras
    if secret_key != "Qbit2026":
        raise HTTPException(status_code=403, detail="No autorizado")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        count = 0
        for p in preguntas:
            cursor.execute("""
                INSERT INTO questions (question_text, options, correct_answer, category, difficulty, language_code, region_target)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (p.question_text, json.dumps(p.options), p.correct_answer, p.category, p.difficulty, p.language_code, p.region_target))
            count += 1
        conn.commit()
        return {"mensaje": f"Se inyectaron {count} preguntas exitosamente"}
    finally:
        conn.close()

# --- RUTAS DE JUEGO (IGUAL QUE ANTES) ---
@app.get("/pregunta-random")
def obtener_pregunta(idioma: str = "es", region: str = "MX"):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM questions WHERE language_code = ? AND region_target = ? ORDER BY RANDOM() LIMIT 1", (idioma, region))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No hay preguntas")
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
def validar(datos: RespuestaUsuario):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT correct_answer FROM questions WHERE id = ?", (datos.pregunta_id,))
        row = cursor.fetchone()
        correcta_real = row["correct_answer"]
        return {"resultado": datos.respuesta_elegida == correcta_real, "correcta_era": correcta_real if datos.respuesta_elegida != correcta_real else None}
    finally:
        conn.close()