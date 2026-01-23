from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import random
import pandas as pd
import os
import io
import socketio

# --- CONFIGURACIÓN DE SOCKET.IO (TIEMPO REAL) ---
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")
app = FastAPI()
# Combinamos FastAPI con Socket.io en una sola aplicación
socket_app = socketio.ASGIApp(sio, app)

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

# --- LÓGICA DE MATCHMAKING (SALAS) ---
# Almacén temporal de jugadores buscando partida
# Estructura: { sid: {"name": str, "rank": int} }
waiting_pool = {}

@sio.event
async def connect(sid, environ):
    print(f"🔌 Jugador conectado: {sid}")

@sio.event
async def join_queue(sid, data):
    """
    Un jugador entra a la cola de espera.
    data: {"name": "apodo", "rank": 1200}
    """
    name = data.get("name", "Anónimo")
    rank = int(data.get("rank", 0))
    
    waiting_pool[sid] = {"name": name, "rank": rank}
    print(f"⏳ {name} (Rank: {rank}) buscando oponente...")
    
    # Intentar emparejar inmediatamente
    await try_match(sid, rank)

async def try_match(sid, rank):
    # Buscamos oponente con diferencia de rank <= 300
    for opponent_sid, info in waiting_pool.items():
        if opponent_sid != sid:
            diff = abs(info['rank'] - rank)
            if diff <= 300:
                # ¡PARTIDA ENCONTRADA!
                room_id = f"room_{sid}_{opponent_sid}"
                
                # Unir a ambos a la sala de combate
                await sio.enter_room(sid, room_id)
                await sio.enter_room(opponent_sid, room_id)
                
                # Obtener info y quitarlos de la cola
                p1 = waiting_pool.pop(sid)
                p2 = waiting_pool.pop(opponent_sid)
                
                print(f"🎮 Duelo creado: {p1['name']} vs {p2['name']}")
                
                # Notificar a ambos jugadores
                await sio.emit('match_found', {
                    'room': room_id,
                    'opponent': p2['name'],
                    'opp_rank': p2['rank']
                }, room=sid)
                
                await sio.emit('match_found', {
                    'room': room_id,
                    'opponent': p1['name'],
                    'opp_rank': p1['rank']
                }, room=opponent_sid)
                return

@sio.event
async def disconnect(sid):
    if sid in waiting_pool:
        del waiting_pool[sid]
    print(f"🚫 Conexión cerrada: {sid}")

# --- MODELOS DE DATOS Y RUTAS HTTP EXISTENTES ---
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

@app.get("/")
def health_check():
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) FROM preguntas").fetchone()[0]
    conn.close()
    return {"status": "online", "total_preguntas": count, "en_cola": len(waiting_pool)}

@app.get("/pregunta-random")
def get_pregunta(lang: str = "es", difficulty: Optional[str] = Query(None)):
    conn = get_db_connection()
    cursor = conn.cursor()
    if difficulty and difficulty.lower() != "random":
        cursor.execute("SELECT * FROM preguntas WHERE idioma = ? AND dificultad = ? COLLATE NOCASE", (lang, difficulty))
    else:
        cursor.execute("SELECT * FROM preguntas WHERE idioma = ?", (lang,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail="No hay preguntas.")
    p = random.choice(rows)
    return {
        "id": p["id"], "pregunta": p["pregunta"], "opciones": p["opciones"],
        "correcta": p["correcta"], "categoria": p["categoria"], "dificultad": p["dificultad"]
    }

@app.post("/inyectar-preguntas")
def inyectar_manual(paquete: Paquete):
    if paquete.secret_key != "Qbit2026": raise HTTPException(status_code=403)
    conn = get_db_connection()
    for p in paquete.preguntas:
        conn.execute('INSERT INTO preguntas (pregunta, opciones, correcta, categoria, dificultad, idioma) VALUES (?, ?, ?, ?, ?, ?)', 
        (p.question_text, "|".join(p.options), p.correct_answer, p.category, p.difficulty, p.language_code))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/cargar-csv-emergencia")
async def cargar_csv(secret_key: str, file: UploadFile = File(...)):
    if secret_key != "Qbit2026": raise HTTPException(status_code=403)
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))
    conn = get_db_connection()
    for _, row in df.iterrows():
        conn.execute('INSERT INTO preguntas (pregunta, opciones, correcta, categoria, dificultad, idioma) VALUES (?, ?, ?, ?, ?, ?)', 
        (row['question_text'], row['options'], row['correct_answer'], row['category'], row['difficulty'], row['language_code']))
    conn.commit()
    conn.close()
    return {"status": "CSV cargado"}