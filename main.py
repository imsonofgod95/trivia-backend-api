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
import asyncio # Necesario para los contadores de las salas

# --- CONFIGURACIÓN DE SOCKET.IO ---
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")
app = FastAPI()
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

# --- LÓGICA DE SALAS MASIVAS Y DUELOS ---
waiting_pool = {} # Para 1vs1
active_rooms = {} # Almacena datos de todas las partidas (1vs1 y Masivas)
massive_lobbies = {} # Gestiona los grupos de 10, 25, 50

def get_synced_questions(difficulty):
    conn = get_db_connection()
    cursor = conn.cursor()
    if difficulty and difficulty.lower() != "random":
        cursor.execute("SELECT * FROM preguntas WHERE dificultad = ? COLLATE NOCASE ORDER BY RANDOM() LIMIT 10", (difficulty,))
    else:
        cursor.execute("SELECT * FROM preguntas ORDER BY RANDOM() LIMIT 10")
    rows = cursor.fetchall()
    conn.close()
    return [{"pregunta": r["pregunta"], "opciones": r["opciones"], "correcta": r["correcta"], "categoria": r["categoria"], "dificultad": r["dificultad"]} for r in rows]

@sio.event
async def connect(sid, environ):
    print(f"🔌 Jugador conectado: {sid}")

# --- EVENTO PARA SALAS MASIVAS ---
@sio.event
async def join_massive_lobby(sid, data):
    name = data.get("name", "Anónimo")
    size = data.get("size", "10") # "10", "25" o "50"
    room_id = f"massive_{size}_lobby"
    
    await sio.enter_room(sid, room_id)
    
    if room_id not in massive_lobbies:
        massive_lobbies[room_id] = {"players": {}, "started": False, "countdown": 30}
        # Iniciar tarea de cuenta regresiva en segundo plano
        asyncio.create_task(massive_room_countdown(room_id))
    
    massive_lobbies[room_id]["players"][sid] = {"name": name, "score": 0}
    
    print(f"🏢 {name} entró a sala masiva de {size}")
    
    # Notificar a la sala el conteo actual
    await sio.emit('lobby_update', {
        "count": len(massive_lobbies[room_id]["players"]),
        "size": size,
        "seconds": massive_lobbies[room_id]["countdown"]
    }, room=room_id)

async def massive_room_countdown(room_id):
    while massive_lobbies[room_id]["countdown"] > 0:
        await asyncio.sleep(1)
        massive_lobbies[room_id]["countdown"] -= 1
        await sio.emit('lobby_timer', {"seconds": massive_lobbies[room_id]["countdown"]}, room=room_id)
    
    # EMPEZAR PARTIDA MASIVA
    if room_id in massive_lobbies:
        questions = get_synced_questions("Random")
        active_rooms[room_id] = {"questions": questions, "players": massive_lobbies[room_id]["players"]}
        
        print(f"🚀 Partida MASIVA {room_id} iniciando con {len(active_rooms[room_id]['players'])} jugadores")
        
        await sio.emit('start_massive_game', {
            "room": room_id,
            "first_question": questions[0]
        }, room=room_id)
        
        # Limpiar lobby para el siguiente grupo
        del massive_lobbies[room_id]

# --- LÓGICA 1VS1 (MANTENIDA) ---
@sio.event
async def join_queue(sid, data):
    name = data.get("name", "Anónimo")
    rank = int(data.get("rank", 1000))
    diff = data.get("difficulty", "Random")
    waiting_pool[sid] = {"name": name, "rank": rank, "difficulty": diff}
    await try_match(sid, rank)

async def try_match(sid, rank):
    player = waiting_pool.get(sid)
    if not player: return
    for opponent_sid, info in waiting_pool.items():
        if opponent_sid != sid:
            if abs(info['rank'] - rank) <= 500:
                room_id = f"room_{sid}_{opponent_sid}"
                questions = get_synced_questions(player["difficulty"])
                active_rooms[room_id] = {"questions": questions}
                await sio.enter_room(sid, room_id)
                await sio.enter_room(opponent_sid, room_id)
                p1, p2 = waiting_pool.pop(sid), waiting_pool.pop(opponent_sid)
                await sio.emit('match_found', {'room': room_id, 'opponent': p2['name'], 'opp_rank': p2['rank'], 'first_question': questions[0]}, room=sid)
                await sio.emit('match_found', {'room': room_id, 'opponent': p1['name'], 'opp_rank': p1['rank'], 'first_question': questions[0]}, room=opponent_sid)
                return

@sio.event
async def next_question(sid, data):
    room_id = data.get("room")
    index = data.get("index")
    if room_id in active_rooms and index < 10:
        question = active_rooms[room_id]["questions"][index]
        await sio.emit('receive_question', question, room=sid)

@sio.event
async def score_update(sid, data):
    room = data.get("room")
    score = data.get("score")
    # Para salas masivas, enviamos el leaderboard a todos
    if room.startswith("massive"):
        active_rooms[room]["players"][sid]["score"] = score
        # Crear ranking ordenado
        leaderboard = sorted(active_rooms[room]["players"].values(), key=lambda x: x["score"], reverse=True)
        await sio.emit('leaderboard_update', leaderboard, room=room)
    else:
        # Para 1vs1 normal
        await sio.emit('update_opponent_score', {'score': score}, room=room, skip_sid=sid)

@sio.event
async def disconnect(sid):
    if sid in waiting_pool: del waiting_pool[sid]
    # Limpiar de lobbies masivos si se desconecta antes de empezar
    for lobby in massive_lobbies.values():
        if sid in lobby["players"]:
            del lobby["players"][sid]
    print(f"🚫 Conexión cerrada: {sid}")

# --- MODELOS Y RUTAS ADMINISTRATIVAS (MANTENIDAS) ---
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