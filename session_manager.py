# backend/session_manager.py

import random
from datetime import datetime

sessions = {}

def create_session():
    session_id = f"SIM_{random.randint(100000,999999)}"
    sessions[session_id] = {
        "current_menu": "main",
        "history": [],
        "start_time": datetime.now()
    }
    return session_id

def get_session(session_id):
    return sessions.get(session_id)

def update_menu(session_id, menu):
    sessions[session_id]["current_menu"] = menu

def end_session(session_id):
    if session_id in sessions:
        del sessions[session_id]