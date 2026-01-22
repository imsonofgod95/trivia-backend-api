from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import random
import pandas as pd
import os
import io

app = FastAPI()

# Configuración de CORS
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
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM preguntas")
    if cursor.fetchone()[0] == 0:
        if os.path.exists(CSV_FILE):
            print(f"📦 Cargando datos desde {CSV_FILE}...")
            df = pd.read_csv(CSV_FILE)
            for _, row in df.iterrows():
                conn.execute('''
                    INSERT INTO preguntas (pregunta, opciones, correcta, categoria, dificultad, idioma)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (row['question_text'], row['options'], row['correct_answer'], 
                      row['category'], row['difficulty'], row['language_code']))
            conn.commit()
            print(f"✅ ¡Éxito! {len(df)} preguntas listas.")
    conn.close()

init_db()

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

# --- RUTAS ---

@app.get("/")
def health_check():
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) FROM preguntas").fetchone()[0]
    conn.close()
    return {"status": "online", "total_preguntas": count}



@app.get("/pregunta-random")
def get_pregunta(lang: str = "es", difficulty: Optional[str] = Query(None)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Normalizamos el parámetro: Si llega "Easy" o "easy", SQL lo comparará correctamente
    # Usamos LIKE o COLLATE NOCASE para evitar errores de mayúsculas
    if difficulty and difficulty.lower() != "random":
        print(f"🔍 Buscando pregunta con dificultad: {difficulty}")
        cursor.execute(
            "SELECT * FROM preguntas WHERE idioma = ? AND dificultad = ? COLLATE NOCASE", 
            (lang, difficulty)
        )
    else:
        print("🎲 Buscando pregunta aleatoria (sin filtro)")
        cursor.execute("SELECT * FROM preguntas WHERE idioma = ?", (lang,))
        
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        # Si no hay preguntas de esa dificultad, lanzamos error informativo
        raise HTTPException(
            status_code=404, 
            detail=f"No se encontraron preguntas para: {lang} - {difficulty}"
        )

    p = random.choice(rows)
    return {
        "id": p["id"],
        "pregunta": p["pregunta"],
        "opciones": p["opciones"],
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
    conn.close()
    return {"status": "success"}

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
    conn.close()
    return {"status": "CSV cargado"}