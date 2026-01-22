from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import sqlite3
import random
import pandas as pd
import os
import io

app = FastAPI()

# Configuración de CORS para que tu juego (frontend) pueda comunicarse con este servidor
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = 'qbit_trivia.db'
CSV_FILE = 'preguntas_master_1k.csv'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Crear la tabla con la estructura que definimos en Data Science
    conn.execute('''
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
    
    # CARGA AUTOMÁTICA: Si la base está vacía, lee el CSV que subiste
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM preguntas")
    if cursor.fetchone()[0] == 0:
        if os.path.exists(CSV_FILE):
            print(f"📦 Detectado {CSV_FILE}. Cargando preguntas iniciales...")
            df = pd.read_csv(CSV_FILE)
            for _, row in df.iterrows():
                conn.execute('''
                    INSERT INTO preguntas (pregunta, opciones, correcta, categoria, dificultad, idioma)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (row['question_text'], row['options'], row['correct_answer'], 
                      row['category'], row['difficulty'], row['language_code']))
            conn.commit()
            print(f"✅ ¡Éxito! Se cargaron {len(df)} preguntas automáticamente.")
        else:
            print("⚠️ No se encontró el CSV. La base de datos iniciará vacía.")
    
    conn.close()

# Ejecutar la inicialización al arrancar
init_db()

# --- MODELOS DE DATOS ---
class Pregunta(BaseModel):
    question_text: str
    options: List[str]
    correct_answer: str
    category: str
    difficulty: str
    language_code: str

class Paquete(BaseModel):
    secret_key: str
    preguntas: List[Pregunta]

# --- RUTAS DEL SERVIDOR ---

@app.get("/")
def health_check():
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) FROM preguntas").fetchone()[0]
    conn.close()
    return {
        "status": "online",
        "total_preguntas_en_db": count,
        "mensaje": "Servidor de Trivia Qbit activo"
    }

@app.get("/pregunta-random")
def get_pregunta(lang: str = "es"):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM preguntas WHERE idioma = ?", (lang,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No hay preguntas en este idioma.")

    p = random.choice(rows)
    return {
        "id": p["id"],
        "pregunta": p["pregunta"],
        "opciones": p["opciones"].split("|"),
        "correcta": p["correcta"],
        "categoria": p["categoria"],
        "dificultad": p["dificultad"]
    }

@app.post("/inyectar-preguntas")
def inyectar_manual(paquete: Paquete):
    if paquete.secret_key != "Qbit2026":
        raise HTTPException(status_code=403, detail="Llave secreta inválida")
    
    conn = get_db_connection()
    for p in paquete.preguntas:
        conn.execute('''
            INSERT INTO preguntas (pregunta, opciones, correcta, categoria, dificultad, idioma)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (p.question_text, "|".join(p.options), p.correct_answer, p.category, p.difficulty, p.language_code))
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM preguntas").fetchone()[0]
    conn.close()
    return {"status": "success", "total_actual": total}

@app.post("/cargar-csv-emergencia")
async def cargar_csv(secret_key: str, file: UploadFile = File(...)):
    if secret_key != "Qbit2026":
        raise HTTPException(status_code=403)
    
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))
    
    conn = get_db_connection()
    for _, row in df.iterrows():
        conn.execute('''
            INSERT INTO preguntas (pregunta, opciones, correcta, categoria, dificultad, idioma)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (row['question_text'], row['options'], row['correct_answer'], 
              row['category'], row['difficulty'], row['language_code']))
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM preguntas").fetchone()[0]
    conn.close()
    return {"status": "CSV cargado manualmente", "total_actual": total}