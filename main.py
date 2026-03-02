# backend/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from session_manager import create_session, get_session
from menu_engine import process_input, MENUS

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class StartCallRequest(BaseModel):
    caller_number: str = "WebSimulator"

class InputRequest(BaseModel):
    session_id: str
    digit: str
    current_menu: str

@app.post("/ivr/start")
def start_call(request: StartCallRequest):
    session_id = create_session()
    return {
        "session_id": session_id,
        "menu": "main",
        "prompt": MENUS["main"]["prompt"]
    }

@app.post("/ivr/input")
def handle_input(request: InputRequest):
    session = get_session(request.session_id)

    if not session:
        return {"error": "Session expired"}

    return process_input(
        request.session_id,
        request.digit,
        request.current_menu
    )

@app.get("/")
def health():
    return {"status": "IVR Running"}