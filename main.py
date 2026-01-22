from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import json

app = FastAPI()

# Configuración de Seguridad para el Navegador
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "trivia_game.db"

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

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row 
    return conn

@app.get("/")
def home():
    return {"mensaje": "Qbit API Online", "version": "2.0"}

# --- RUTA PARA AUTOMATIZACIÓN (INYECCIÓN) ---
@app.post("/admin/inyectar-preguntas")
def inyectar_preguntas(preguntas: List[PreguntaIA], secret_key: Optional[str] = Header(None, alias="secret-key")):
    # La llave que configuramos para Colab
    LLAVE_MAESTRA = "Qbit2026"
    
    if secret_key != LLAVE_MAESTRA:
        raise HTTPException(status_code=403, detail=f"Acceso denegado: Llave incorrecta")
    
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
        return {"status": "success", "preguntas_agregadas": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- RUTAS DE JUEGO ---
@app.get("/pregunta-random")
def obtener_pregunta(idioma: str = "es", region: str = "MX"):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM questions 
            WHERE language_code = ? AND region_target = ? 
            ORDER BY RANDOM() LIMIT 1
        """, (idioma, region))
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
        if not row: raise HTTPException(status_code=404)
        correcta = row["correct_answer"]
        return {"resultado": datos.respuesta_elegida == correcta, "correcta_era": correcta if datos.respuesta_elegida != correcta else None}
    finally:
        conn.close()