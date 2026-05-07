"""
AI Conversation Engine
========================
Natural Language Understanding layer for the Patient Feedback IVR.
Extracts intents, ratings, and entities from free-form patient voice input.

Supports two modes:
  - Rule-based (default, no API needed) for unit tests and offline use
  - LLM-backed (via Claude/OpenAI) for richer natural language understanding

Milestone 3 - Conversational AI Interface Development
Project: AI-Enabled Conversational Patient Feedback IVR (Web Simulator Approach)
"""

import re
import logging
from typing import Optional
from src.ivr_engine.ivr_flow_controller import IVRState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intent keyword maps
# ---------------------------------------------------------------------------

AFFIRM_KEYWORDS = {"yes", "yeah", "yep", "correct", "right", "sure", "absolutely",
                   "definitely", "confirm", "true", "yup", "ok", "okay"}

DENY_KEYWORDS   = {"no", "nope", "nah", "negative", "incorrect", "wrong", "not", "false"}

START_KEYWORDS  = {"start", "begin", "feedback", "go", "proceed", "ready", "continue"}

EXIT_KEYWORDS   = {"exit", "quit", "bye", "goodbye", "end", "stop", "cancel", "hang up"}

SKIP_KEYWORDS   = {"skip", "none", "pass", "next"}
SKIP_PHRASES    = {"no comment", "no comments", "nothing", "skip"}

SUBMIT_KEYWORDS = {"submit", "save", "confirm", "send", "done", "finish", "complete"}

REVIEW_KEYWORDS = {"review", "go back", "change", "restart"}

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
    "poor": 1, "bad": 1, "okay": 3, "good": 4, "great": 5, "excellent": 5,
    "very poor": 1, "very good": 4, "very bad": 1,
}

PATIENT_ID_PATTERN = re.compile(r"\b(P\d{4,8}|\d{5,8})\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Core AI Engine
# ---------------------------------------------------------------------------

class AIConversationEngine:
    """
    NLU engine that parses patient speech/text input into structured intents.

    In the web simulator, text from the browser is treated as ASR output
    and processed here before being handed to the IVR flow controller.
    """

    def __init__(self, use_llm: bool = False, llm_client=None):
        """
        Args:
            use_llm:    If True, fall back to LLM for ambiguous inputs.
            llm_client: Optional LLM API client (OpenAI / Anthropic compatible).
        """
        self.use_llm = use_llm
        self.llm_client = llm_client

    def parse_input(self, raw_text: str, current_state: IVRState) -> dict:
        """
        Main entry point. Converts raw patient utterance into a structured dict.

        Returns dict with keys:
          - intent: str (affirm | deny | start | exit | skip | submit | review)
          - rating: Optional[int] (1–5)
          - patient_id: Optional[str]
          - raw_text: str
        """
        cleaned = raw_text.strip().lower()
        result = {
            "intent": None,
            "rating": None,
            "patient_id": None,
            "raw_text": raw_text,
        }

        # --- Extract patient ID (for WELCOME state) ---
        id_match = PATIENT_ID_PATTERN.search(raw_text)
        if id_match:
            result["patient_id"] = id_match.group(0).upper()

        # --- Extract numeric rating ---
        result["rating"] = self._extract_rating(cleaned)

        # --- Extract intent ---
        result["intent"] = self._extract_intent(cleaned, current_state)

        # --- LLM fallback for ambiguous cases ---
        if result["intent"] is None and self.use_llm and self.llm_client:
            result["intent"] = self._llm_extract_intent(raw_text, current_state)
            logger.info(f"LLM resolved intent: {result['intent']}")

        logger.debug(f"Parsed: {result}")
        return result

    def _extract_rating(self, text: str) -> Optional[int]:
        """Pull a 1–5 rating from text."""
        for phrase, val in sorted(NUMBER_WORDS.items(), key=lambda x: -len(x[0])):
            if phrase in text:
                return val
        return None

    def _extract_intent(self, text: str, state: IVRState) -> Optional[str]:
        """Rule-based intent classification."""
        words = set(text.split())

        # Phrase-level checks first (before any word-level matching)
        if "of course" in text:
            return "affirm"
        if any(phrase in text for phrase in SKIP_PHRASES):
            return "skip"

        # Submit / confirm
        if any(kw in words for kw in SUBMIT_KEYWORDS):
            return "submit"
        # Review / go back
        if "go back" in text or any(kw in words for kw in REVIEW_KEYWORDS):
            return "review"
        # Start feedback
        if any(kw in words for kw in START_KEYWORDS):
            return "start"
        # Exit / goodbye
        if any(kw in words for kw in EXIT_KEYWORDS):
            return "exit"
        # Skip (single-word)
        if any(kw in words for kw in SKIP_KEYWORDS):
            return "skip"
        # Affirm / deny — whole-word
        if any(kw in words for kw in AFFIRM_KEYWORDS):
            return "affirm"
        if any(kw in words for kw in DENY_KEYWORDS):
            return "deny"
        # For rating states, if we got a number that's valid intent
        if state in _RATING_STATES and self._extract_rating(text) is not None:
            return "rating"
        return None

    def _llm_extract_intent(self, text: str, state: IVRState) -> Optional[str]:
        """
        Calls LLM API to classify intent when rule-based approach fails.
        Only used when use_llm=True and llm_client is provided.
        """
        try:
            system_prompt = (
                "You are an IVR intent classifier for a hospital patient feedback system. "
                "Given a patient's spoken input and the current IVR state, "
                "classify the intent as ONE of: affirm, deny, start, exit, skip, submit, review, rating, unknown. "
                "Reply with ONLY the intent word, nothing else."
            )
            user_msg = f"State: {state.name}\nPatient said: \"{text}\"\nIntent:"
            response = self.llm_client.chat(system=system_prompt, user=user_msg)
            intent = response.strip().lower()
            valid = {"affirm", "deny", "start", "exit", "skip", "submit", "review", "rating"}
            return intent if intent in valid else None
        except Exception as e:
            logger.error(f"LLM intent extraction failed: {e}")
            return None

    def generate_empathetic_response(self, base_response: str, rating: Optional[int]) -> str:
        """
        Optionally wrap IVR responses with empathetic language based on rating.
        Used to make the conversational experience feel more natural.
        """
        if rating is None:
            return base_response
        if rating <= 2:
            prefix = "I'm sorry to hear that. "
        elif rating == 3:
            prefix = "Thank you for letting us know. "
        else:
            prefix = "That's wonderful to hear! "
        return prefix + base_response


_RATING_STATES = {
    IVRState.FEEDBACK_OVERALL,
    IVRState.FEEDBACK_DOCTOR,
    IVRState.FEEDBACK_NURSE,
    IVRState.FEEDBACK_FACILITY,
    IVRState.FEEDBACK_WAIT_TIME,
}
