"""
Web Simulator
==============
Flask-based browser IVR simulator for the Patient Feedback system.
Replaces physical IVR hardware with a web interface for development/testing.

Architecture:
  Browser (HTML/JS) <-> Flask REST API <-> IVR Flow Controller <-> AI Engine

Milestone 3 - Conversational AI Interface Development
Project: AI-Enabled Conversational Patient Feedback IVR (Web Simulator Approach)
"""

import uuid
import logging
from flask import Flask, request, jsonify, render_template_string
from src.ivr_engine.ivr_flow_controller import IVRFlowController, IVRSession, IVRState
from src.ai_engine.conversation_engine import AIConversationEngine
from src.middleware.feedback_store import FeedbackStore

logger = logging.getLogger(__name__)

app = Flask(__name__)

# In-memory session store (replace with Redis for production)
_sessions: dict[str, IVRSession] = {}

# Shared singletons
_feedback_store = FeedbackStore()
_ai_engine = AIConversationEngine(use_llm=False)
_controller = IVRFlowController(ai_engine=_ai_engine, feedback_store=_feedback_store)


# ---------------------------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/session/start", methods=["POST"])
def start_session():
    """
    POST /api/session/start
    Creates a new IVR session and returns the welcome prompt.
    """
    session_id = str(uuid.uuid4())
    session = IVRSession(session_id=session_id, current_state=IVRState.WELCOME)
    _sessions[session_id] = session

    welcome_text = _controller.get_prompt_for_state(IVRState.WELCOME)
    session.log_turn("IVR", welcome_text)

    logger.info(f"Session started: {session_id}")
    return jsonify({
        "session_id": session_id,
        "state": session.current_state.name,
        "response": welcome_text,
        "is_terminal": False,
    })


@app.route("/api/session/<session_id>/input", methods=["POST"])
def process_input(session_id: str):
    """
    POST /api/session/<session_id>/input
    Body: { "text": "user's spoken/typed input" }
    Returns the IVR response and next state.
    """
    session = _sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "Missing 'text' field in request body"}), 400

    user_text = data["text"].strip()
    if not user_text:
        return jsonify({"error": "Input text cannot be empty"}), 400

    response_text, next_state = _controller.process_input(session, user_text)
    is_terminal = next_state in (IVRState.EXIT, IVRState.THANK_YOU)

    return jsonify({
        "session_id": session_id,
        "state": next_state.name,
        "response": response_text,
        "is_terminal": is_terminal,
    })


@app.route("/api/session/<session_id>/summary", methods=["GET"])
def get_session_summary(session_id: str):
    """
    GET /api/session/<session_id>/summary
    Returns full session data including all collected feedback.
    """
    session = _sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(session.to_dict())


@app.route("/api/feedback/all", methods=["GET"])
def get_all_feedback():
    """GET /api/feedback/all — Returns all stored feedback records."""
    return jsonify(_feedback_store.get_all())


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "sessions_active": len(_sessions)})


# ---------------------------------------------------------------------------
# Web Simulator UI (single-page HTML)
# ---------------------------------------------------------------------------

SIMULATOR_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Patient Feedback IVR Simulator</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', sans-serif;
      background: #f0f4f8;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
    }
    .simulator {
      background: white;
      border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.12);
      width: 420px;
      overflow: hidden;
    }
    .header {
      background: linear-gradient(135deg, #1a5276, #2e86c1);
      color: white;
      padding: 20px 24px;
      text-align: center;
    }
    .header h1 { font-size: 18px; font-weight: 600; }
    .header p  { font-size: 12px; opacity: 0.8; margin-top: 4px; }
    .status-bar {
      background: #eaf4fb;
      padding: 8px 20px;
      font-size: 12px;
      color: #1a5276;
      border-bottom: 1px solid #d6eaf8;
    }
    .chat-window {
      height: 380px;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .bubble {
      max-width: 80%;
      padding: 10px 14px;
      border-radius: 12px;
      font-size: 14px;
      line-height: 1.5;
    }
    .ivr  { background:#eaf4fb; color:#1a5276; align-self:flex-start; border-bottom-left-radius:4px; }
    .user { background:#2e86c1; color:white; align-self:flex-end; border-bottom-right-radius:4px; }
    .controls {
      padding: 16px;
      border-top: 1px solid #eee;
    }
    .input-row {
      display: flex;
      gap: 8px;
    }
    input[type=text] {
      flex: 1;
      padding: 10px 14px;
      border: 1.5px solid #d0d7de;
      border-radius: 8px;
      font-size: 14px;
      outline: none;
      transition: border 0.2s;
    }
    input[type=text]:focus { border-color: #2e86c1; }
    button {
      padding: 10px 18px;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 600;
      transition: background 0.2s;
    }
    .btn-send  { background: #2e86c1; color: white; }
    .btn-send:hover { background: #1a5276; }
    .btn-send:disabled { background: #aaa; cursor: default; }
    .btn-start { width:100%; background:#27ae60; color:white; margin-bottom:10px; padding:12px; border-radius:8px; }
    .btn-start:hover { background:#1e8449; }
    .quick-btns { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
    .qbtn {
      padding: 6px 12px;
      border-radius: 16px;
      border: 1.5px solid #2e86c1;
      background: white;
      color: #2e86c1;
      font-size: 12px;
      cursor: pointer;
    }
    .qbtn:hover { background: #eaf4fb; }
    .terminal-msg { text-align:center; color:#888; font-size:13px; padding:8px; }
  </style>
</head>
<body>
<div class="simulator">
  <div class="header">
    <h1>🏥 City Hospital IVR Simulator</h1>
    <p>AI-Enabled Patient Feedback System · Web Simulator Mode</p>
  </div>
  <div class="status-bar" id="statusBar">State: Ready to start</div>
  <div class="chat-window" id="chatWindow">
    <div class="bubble ivr">Welcome! Click "Start Call" to begin the patient feedback session.</div>
  </div>
  <div class="controls">
    <button class="btn-start" id="startBtn" onclick="startCall()">📞 Start Call</button>
    <div class="input-row">
      <input type="text" id="userInput" placeholder="Type your response..." disabled onkeydown="if(event.key==='Enter') sendInput()"/>
      <button class="btn-send" id="sendBtn" onclick="sendInput()" disabled>Send</button>
    </div>
    <div class="quick-btns" id="quickBtns"></div>
  </div>
</div>

<script>
  let sessionId = null;
  let isTerminal = false;

  const QUICK_REPLIES = {
    WELCOME:           ["P12345", "P67890"],
    VERIFY_PATIENT:    ["Yes", "No"],
    MENU_MAIN:         ["Start Feedback", "Exit"],
    FEEDBACK_OVERALL:  ["1","2","3","4","5"],
    FEEDBACK_DOCTOR:   ["1","2","3","4","5"],
    FEEDBACK_NURSE:    ["1","2","3","4","5"],
    FEEDBACK_FACILITY: ["1","2","3","4","5"],
    FEEDBACK_WAIT_TIME:["1","2","3","4","5"],
    FEEDBACK_RECOMMEND:["Yes","No"],
    OPEN_COMMENTS:     ["Skip","The staff were very kind"],
    CONFIRM_SUBMISSION:["Submit","Review"],
  };

  async function startCall() {
    document.getElementById("startBtn").disabled = true;
    const res = await fetch("/api/session/start", { method:"POST" });
    const data = await res.json();
    sessionId = data.session_id;
    addBubble("ivr", data.response);
    updateState(data.state);
    setInputEnabled(true);
  }

  async function sendInput() {
    const input = document.getElementById("userInput");
    const text = input.value.trim();
    if (!text || isTerminal) return;
    input.value = "";
    addBubble("user", text);

    const res = await fetch(`/api/session/${sessionId}/input`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    addBubble("ivr", data.response);
    updateState(data.state);

    if (data.is_terminal) {
      isTerminal = true;
      setInputEnabled(false);
      document.getElementById("chatWindow").innerHTML +=
        `<div class="terminal-msg">✅ Session complete. <a href="/api/session/${sessionId}/summary" target="_blank">View full summary</a></div>`;
    }
  }

  function addBubble(role, text) {
    const div = document.createElement("div");
    div.className = `bubble ${role}`;
    div.textContent = text;
    const win = document.getElementById("chatWindow");
    win.appendChild(div);
    win.scrollTop = win.scrollHeight;
  }

  function updateState(state) {
    document.getElementById("statusBar").textContent = `State: ${state.replace(/_/g," ")}`;
    const qb = document.getElementById("quickBtns");
    qb.innerHTML = "";
    const replies = QUICK_REPLIES[state] || [];
    replies.forEach(r => {
      const btn = document.createElement("button");
      btn.className = "qbtn";
      btn.textContent = r;
      btn.onclick = () => {
        document.getElementById("userInput").value = r;
        sendInput();
      };
      qb.appendChild(btn);
    });
  }

  function setInputEnabled(enabled) {
    document.getElementById("userInput").disabled = !enabled;
    document.getElementById("sendBtn").disabled = !enabled;
  }
</script>
</body>
</html>
"""


@app.route("/")
def simulator_ui():
    """Serve the web simulator single-page interface."""
    return render_template_string(SIMULATOR_HTML)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True, port=5000)
