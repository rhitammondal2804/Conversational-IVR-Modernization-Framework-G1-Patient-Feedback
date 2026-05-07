# 🏥 AI-Enabled Conversational Patient Feedback IVR
### Web Simulator Approach — Milestone 3

> **Infosys Virtual Internship | AI Domain**
> **Project:** Conversational IVR Modernization Framework — G1
> **Topic:** AI-Enabled Conversational Patient Feedback IVR using Web Simulator Approach

---

## 📋 Project Overview

This repository implements **Milestone 3** of the Conversational IVR Modernization Framework:
building and integrating **AI-powered conversational dialogue flows** that replace traditional
DTMF-based IVR menus with natural language voice interaction for hospital patient feedback.

The **Web Simulator** replaces physical telephony hardware, allowing the full IVR dialogue
to be tested and demonstrated entirely in a browser — making development, testing, and
evaluation accessible without any telephony infrastructure.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Web Browser (Simulator UI)                      │
│              Patient types/speaks → Text input panel                │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP REST
┌────────────────────────────▼────────────────────────────────────────┐
│                    Flask REST API (simulator_app.py)                │
│   POST /api/session/start   |   POST /api/session/{id}/input        │
└────────────────────────────┬────────────────────────────────────────┘
                             │
          ┌──────────────────▼──────────────────┐
          │        IVR Flow Controller           │
          │   (State Machine — ivr_flow.py)      │
          │  INIT → WELCOME → VERIFY → MENU →    │
          │  RATINGS → COMMENTS → SUBMIT → EXIT  │
          └──────────┬──────────────┬────────────┘
                     │              │
          ┌──────────▼──┐    ┌──────▼────────────┐
          │  AI Engine  │    │  Feedback Store   │
          │  (NLU +     │    │  (Middleware /    │
          │   Intent)   │    │   Persistence)    │
          └─────────────┘    └───────────────────┘
```

### Milestone Mapping

| Milestone | Scope | Status |
|-----------|-------|--------|
| M1 | Legacy System Analysis & Requirements | ✅ Complete |
| M2 | Integration Layer (VXML ↔ ACS/BAP middleware) | ✅ Complete |
| **M3** | **Conversational AI Interface + Web Simulator** | 🔄 **This repo** |
| M4 | Testing & Deployment | ⏳ Upcoming |

---

## 📁 Project Structure

```
patient-feedback-ivr/
│
├── app.py                          # Entry point — run the simulator
├── requirements.txt
│
├── src/
│   ├── ivr_engine/
│   │   └── ivr_flow_controller.py  # State machine + dialogue prompts
│   │
│   ├── ai_engine/
│   │   └── conversation_engine.py  # NLU: intent & rating extraction
│   │
│   ├── web_simulator/
│   │   └── simulator_app.py        # Flask app + browser UI
│   │
│   └── middleware/
│       └── feedback_store.py       # Patient DB + feedback persistence
│
├── tests/
│   └── test_ivr_system.py          # Full unit + integration test suite
│
├── data/
│   └── feedback_records.json       # Auto-generated feedback storage
│
├── docs/
│   └── architecture.md             # System design documentation
│
└── configs/
    └── config.yaml                 # Configuration parameters
```

---

## 🚀 Setup & Running

### 1. Clone the repository

```bash
git clone https://github.com/rhitammondal2804/Conversational-IVR-Modernization-Framework-G1-Patient-Feedback.git
cd Conversational-IVR-Modernization-Framework-G1-Patient-Feedback
```

### 2. Create virtual environment & install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run the Web Simulator

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

---

## 🖥️ Using the Web Simulator

1. Click **"📞 Start Call"** to begin a session
2. The IVR will greet you and ask for your Patient ID
3. Use **quick-reply buttons** or type freely in the text box
4. Progress through the feedback flow:
   - Patient verification
   - Overall, Doctor, Nurse, Facility, Wait-time ratings (1–5)
   - Recommendation (Yes/No)
   - Open comments
   - Submit

**Demo Patient IDs:** `P12345` (Arjun Sharma), `P67890` (Priya Verma)

---

## 🔌 REST API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/session/start` | Start new IVR session |
| `POST` | `/api/session/{id}/input` | Submit user input |
| `GET`  | `/api/session/{id}/summary` | Get full session data |
| `GET`  | `/api/feedback/all` | View all feedback records |
| `GET`  | `/api/health` | Health check |

### Example: Start a session

```bash
curl -X POST http://localhost:5000/api/session/start
```

```json
{
  "session_id": "abc123",
  "state": "WELCOME",
  "response": "Welcome to City Hospital Patient Feedback...",
  "is_terminal": false
}
```

### Example: Submit input

```bash
curl -X POST http://localhost:5000/api/session/abc123/input \
     -H "Content-Type: application/json" \
     -d '{"text": "P12345"}'
```

---

## 🧪 Running Tests

```bash
python -m pytest tests/ -v
```

The test suite covers:
- Intent classification (affirm, deny, start, exit, skip, submit, review)
- Rating extraction from digits and words ("five", "excellent", "poor")
- Patient ID extraction
- State machine transitions
- Full end-to-end happy-path dialogue simulation

---

## 🤖 AI Engine — How NLU Works

The `AIConversationEngine` uses a **rule-based NLU pipeline** (no external API required):

1. **Intent classification** — keyword matching against curated intent sets
2. **Rating extraction** — maps number words and adjectives to 1–5 ratings
3. **Patient ID detection** — regex extraction of `P12345`-style IDs
4. **Empathetic response wrapping** — prefixes responses based on rating sentiment

An optional **LLM fallback** (via OpenAI/Anthropic compatible client) is available for
ambiguous utterances when `use_llm=True` is passed to `AIConversationEngine`.

---

## 🔄 IVR State Flow

```
INIT → WELCOME → VERIFY_PATIENT → MENU_MAIN
                                      │
                              FEEDBACK_OVERALL
                              FEEDBACK_DOCTOR
                              FEEDBACK_NURSE
                              FEEDBACK_FACILITY
                              FEEDBACK_WAIT_TIME
                              FEEDBACK_RECOMMEND
                              OPEN_COMMENTS
                              CONFIRM_SUBMISSION
                                      │
                               THANK_YOU → EXIT
```

Each state has:
- A defined **prompt** (IVR announcement)
- Valid **transitions** to next states
- A **handler** that processes user input
- **Error recovery** with up to 3 retries

---

## 👤 Author

**Rhitam Mondal**
B.Tech — Computer Science & Business Systems
Meghnad Saha Institute of Technology

Infosys Virtual Internship — AI Domain
Conversational IVR Modernization Framework — Group 1

---

## 📄 License

This project is developed as part of the Infosys Springboard Virtual Internship Program.
