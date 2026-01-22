from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import json

app = FastAPI()

# --- CONFIGURACIÓN DE SEGURIDAD (CORS) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "trivia_game.db"

# Modelo para recibir la respuesta del usuario
class RespuestaUsuario(BaseModel):
    pregunta_id: int
    respuesta_elegida: str

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row 
    return conn

@app.get("/")
def home():
    return {"mensaje": "¡Servidor Multilenguaje Activo!", "status": "online"}

# --- ENDPOINT 1: OBTENER PREGUNTA CON FILTROS ---
# Ahora acepta ?idioma=es&region=MX en la URL
@app.get("/pregunta-random")
def obtener_pregunta(idioma: str = "es", region: str = "MX"):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Buscamos preguntas que coincidan con el idioma y región solicitados
        cursor.execute("""
            SELECT * FROM questions 
            WHERE language_code = ? AND region_target = ?
            ORDER BY RANDOM() LIMIT 1
        """, (idioma, region))
        
        row = cursor.fetchone()
        
        if not row:
            # Si no hay preguntas (ej. seleccionas Inglés y no has generado nada)
            raise HTTPException(status_code=404, detail=f"No hay preguntas disponibles para {idioma}-{region}")
            
        opciones = json.loads(row["options"])
        
        return {
            "id": row["id"],
            "pregunta": row["question_text"],
            "opciones": opciones,
            "categoria": row["category"],
            "dificultad": row["difficulty"]
            # 🔒 NO enviamos la respuesta correcta
        }
    finally:
        conn.close()

# --- ENDPOINT 2: VALIDAR RESPUESTA (JUEZ) ---
@app.post("/validar-respuesta")
def validar(datos: RespuestaUsuario):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT correct_answer FROM questions WHERE id = ?", (datos.pregunta_id,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Pregunta no encontrada")
            
        correcta_real = row["correct_answer"]
        es_correcta = (datos.respuesta_elegida == correcta_real)
        
        return {
            "resultado": es_correcta,
            "correcta_era": correcta_real if not es_correcta else None
        }
    finally:
        conn.close()