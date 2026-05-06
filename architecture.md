# Architecture Documentation
## AI-Enabled Conversational Patient Feedback IVR — Milestone 3

---

## 1. Overview

This document describes the technical architecture of the **Web Simulator–based
Conversational IVR** for patient feedback collection at City Hospital.

The system modernizes a legacy DTMF IVR by introducing:
- Natural language understanding (NLU) for free-form voice/text input
- A state-machine dialogue controller replacing VoiceXML scripts
- A browser-based simulator replacing physical telephony

---

## 2. Component Breakdown

### 2.1 IVR Flow Controller (`ivr_flow_controller.py`)

Implements the core dialogue as a finite state machine (FSM).

**States:** INIT → WELCOME → VERIFY_PATIENT → MENU_MAIN → [RATING STATES] →
OPEN_COMMENTS → CONFIRM_SUBMISSION → THANK_YOU → EXIT

**Responsibilities:**
- Maintain `IVRSession` state across turns
- Validate state transitions
- Generate contextual prompts
- Trigger feedback persistence on session completion
- Enforce retry limits (max 3 retries before forced exit)

### 2.2 AI Conversation Engine (`conversation_engine.py`)

The NLU layer processes raw patient text.

**Pipeline:**
```
Raw text → lowercase & strip → [Intent classifier] → [Rating extractor] → [ID extractor] → ParsedResult
```

**Intent classes:** affirm | deny | start | exit | skip | submit | review | rating

**Rating map:** digit strings + English number words + sentiment adjectives (excellent=5, poor=1)

**LLM fallback:** When rule-based classification fails and `use_llm=True`, the engine
calls an LLM API with a structured classification prompt.

### 2.3 Web Simulator (`simulator_app.py`)

Flask REST API + single-page browser UI.

**REST endpoints:**
| Endpoint | Purpose |
|----------|---------|
| `POST /api/session/start` | Create session, return welcome prompt |
| `POST /api/session/{id}/input` | Process user turn, return IVR response |
| `GET /api/session/{id}/summary` | Full session data |
| `GET /api/feedback/all` | All submitted feedback |

**UI features:**
- Chat-style conversation display
- State-aware quick-reply buttons (auto-update each turn)
- Terminal state detection (call end)
- Link to JSON summary after completion

### 2.4 Feedback Store (`feedback_store.py`)

Middleware integration layer connecting IVR sessions to persistence.

**In Milestone 2:** This module wraps the ACS/BAP REST API.
**In Milestone 3 (simulator):** Uses JSON file storage for zero-infrastructure testing.

**Methods:**
- `get_patient(id)` — Simulates EHR API call
- `save(session)` — Persists completed session
- `get_summary_stats()` — Aggregate reporting

---

## 3. Data Flow

```
Browser input
    │
    ▼
POST /api/session/{id}/input
    │
    ▼
simulator_app.py
    │  user_text
    ▼
AIConversationEngine.parse_input()
    │  {intent, rating, patient_id, raw_text}
    ▼
IVRFlowController.process_input()
    │  _handle_state() → next_state, response_text
    ▼
FeedbackStore.save()  ← (only on terminal states)
    │
    ▼
JSON response → Browser
```

---

## 4. Integration with Milestones 1 & 2

| Milestone | Integration Point |
|-----------|------------------|
| M1 — Legacy Analysis | State machine mirrors VXML dialogue flow structure |
| M2 — Integration Layer | `FeedbackStore.get_patient()` calls the ACS API stub; `save()` posts to BAP endpoint |
| M3 — This module | Conversational AI flows + web simulator |
| M4 — Deployment | Replace JSON store with production DB; connect real ASR/TTS |

---

## 5. Extension Points

### Enabling Real ASR/TTS
Replace the text input field in the simulator UI with:
- **Web Speech API** (`SpeechRecognition`) for ASR in the browser
- **SpeechSynthesis API** for TTS playback of IVR prompts

### Enabling LLM-backed NLU
```python
from anthropic import Anthropic
client = Anthropic()
engine = AIConversationEngine(use_llm=True, llm_client=client)
```

### Production Database
Replace `FeedbackStore` JSON backend with PostgreSQL or MongoDB.

---

## 6. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit — NLU | All intent classes, rating words, ID regex |
| Unit — Store | Patient lookup, save, stats |
| Integration — FSM | Each state transition |
| E2E — Happy path | Full 10-step dialogue simulation |
| E2E — Error path | Max retry → forced EXIT |
