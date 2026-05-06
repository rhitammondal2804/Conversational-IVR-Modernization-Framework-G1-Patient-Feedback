"""
IVR Flow Controller
====================
Manages the state machine for the Patient Feedback IVR system.
Handles VXML-style dialogue flow transitions mapped to conversational AI states.

Milestone 3 - Conversational AI Interface Development
Project: AI-Enabled Conversational Patient Feedback IVR (Web Simulator Approach)
Infosys Virtual Internship - AI Domain
"""

import logging
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class IVRState(Enum):
    """All possible states in the Patient Feedback IVR dialogue flow."""
    INIT = auto()
    WELCOME = auto()
    VERIFY_PATIENT = auto()
    MENU_MAIN = auto()
    FEEDBACK_OVERALL = auto()
    FEEDBACK_DOCTOR = auto()
    FEEDBACK_NURSE = auto()
    FEEDBACK_FACILITY = auto()
    FEEDBACK_WAIT_TIME = auto()
    FEEDBACK_RECOMMEND = auto()
    OPEN_COMMENTS = auto()
    CONFIRM_SUBMISSION = auto()
    THANK_YOU = auto()
    ERROR = auto()
    EXIT = auto()


@dataclass
class IVRSession:
    """Represents a single patient IVR session with all collected data."""
    session_id: str
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    current_state: IVRState = IVRState.INIT
    previous_state: Optional[IVRState] = None
    retry_count: int = 0
    max_retries: int = 3

    # Feedback collected
    overall_rating: Optional[int] = None           # 1–5
    doctor_rating: Optional[int] = None            # 1–5
    nurse_rating: Optional[int] = None             # 1–5
    facility_rating: Optional[int] = None          # 1–5
    wait_time_rating: Optional[int] = None         # 1–5
    would_recommend: Optional[bool] = None         # Yes/No
    open_comments: Optional[str] = None

    history: list = field(default_factory=list)    # transcript of turns

    def log_turn(self, speaker: str, text: str):
        """Append a dialogue turn to session history."""
        self.history.append({"speaker": speaker, "text": text})

    def to_dict(self) -> dict:
        """Serialize session data for storage/API response."""
        return {
            "session_id": self.session_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "ratings": {
                "overall": self.overall_rating,
                "doctor": self.doctor_rating,
                "nurse": self.nurse_rating,
                "facility": self.facility_rating,
                "wait_time": self.wait_time_rating,
            },
            "would_recommend": self.would_recommend,
            "open_comments": self.open_comments,
            "history": self.history,
        }


class IVRFlowController:
    """
    Core state machine controller for the Patient Feedback IVR.

    Mirrors legacy VXML dialogue transitions while enabling
    natural language input via the AI engine layer.
    """

    # Maps each state to its handler method name
    STATE_HANDLERS: dict = {}

    def __init__(self, ai_engine, feedback_store):
        """
        Args:
            ai_engine: NLU/LLM engine for intent extraction (AIConversationEngine)
            feedback_store: Storage backend for persisting feedback (FeedbackStore)
        """
        self.ai_engine = ai_engine
        self.feedback_store = feedback_store
        self._build_transition_map()

    def _build_transition_map(self):
        """Define valid state transitions."""
        self.transitions = {
            IVRState.INIT:              [IVRState.WELCOME],
            IVRState.WELCOME:           [IVRState.VERIFY_PATIENT, IVRState.EXIT, IVRState.ERROR],
            IVRState.VERIFY_PATIENT:    [IVRState.MENU_MAIN, IVRState.EXIT, IVRState.ERROR],
            IVRState.MENU_MAIN:         [IVRState.FEEDBACK_OVERALL, IVRState.EXIT, IVRState.ERROR],
            IVRState.FEEDBACK_OVERALL:  [IVRState.FEEDBACK_DOCTOR, IVRState.ERROR],
            IVRState.FEEDBACK_DOCTOR:   [IVRState.FEEDBACK_NURSE, IVRState.ERROR],
            IVRState.FEEDBACK_NURSE:    [IVRState.FEEDBACK_FACILITY, IVRState.ERROR],
            IVRState.FEEDBACK_FACILITY: [IVRState.FEEDBACK_WAIT_TIME, IVRState.ERROR],
            IVRState.FEEDBACK_WAIT_TIME:[IVRState.FEEDBACK_RECOMMEND, IVRState.ERROR],
            IVRState.FEEDBACK_RECOMMEND:[IVRState.OPEN_COMMENTS, IVRState.ERROR],
            IVRState.OPEN_COMMENTS:     [IVRState.CONFIRM_SUBMISSION],
            IVRState.CONFIRM_SUBMISSION:[IVRState.THANK_YOU, IVRState.MENU_MAIN],
            IVRState.THANK_YOU:         [IVRState.EXIT],
            IVRState.ERROR:             [IVRState.MENU_MAIN, IVRState.EXIT],
        }

    def get_prompt_for_state(self, state: IVRState) -> str:
        """Return the IVR prompt text for a given state."""
        prompts = {
            IVRState.WELCOME: (
                "Welcome to the City Hospital Patient Feedback System. "
                "Your feedback helps us improve care for everyone. "
                "Please say your Patient ID or press the star key to continue."
            ),
            IVRState.VERIFY_PATIENT: (
                "Thank you. Please confirm: are you {patient_name}? Say Yes or No."
            ),
            IVRState.MENU_MAIN: (
                "Hello {patient_name}, we'd love to hear about your recent visit. "
                "Say 'Start Feedback' to begin, or 'Exit' to end the call."
            ),
            IVRState.FEEDBACK_OVERALL: (
                "On a scale of 1 to 5, how would you rate your overall experience? "
                "1 is Very Poor and 5 is Excellent."
            ),
            IVRState.FEEDBACK_DOCTOR: (
                "How would you rate the care provided by your doctor? "
                "Please say a number from 1 to 5."
            ),
            IVRState.FEEDBACK_NURSE: (
                "How would you rate the nursing staff? "
                "Say a number from 1 to 5."
            ),
            IVRState.FEEDBACK_FACILITY: (
                "How would you rate the cleanliness and comfort of our facilities? "
                "Say 1 for Very Poor up to 5 for Excellent."
            ),
            IVRState.FEEDBACK_WAIT_TIME: (
                "How satisfied were you with the wait times during your visit? "
                "Rate from 1 to 5."
            ),
            IVRState.FEEDBACK_RECOMMEND: (
                "Would you recommend City Hospital to friends or family? "
                "Say Yes or No."
            ),
            IVRState.OPEN_COMMENTS: (
                "Do you have any additional comments about your visit? "
                "You may speak freely now, or say 'Skip' to continue."
            ),
            IVRState.CONFIRM_SUBMISSION: (
                "Thank you for your responses. "
                "Say 'Submit' to save your feedback, or 'Review' to go back."
            ),
            IVRState.THANK_YOU: (
                "Your feedback has been recorded. Thank you for helping us improve. "
                "We look forward to serving you again. Goodbye!"
            ),
            IVRState.ERROR: (
                "I'm sorry, I didn't catch that. Let's try again."
            ),
            IVRState.EXIT: (
                "Thank you for calling City Hospital. Goodbye!"
            ),
        }
        return prompts.get(state, "I'm sorry, an error occurred. Goodbye.")

    def process_input(self, session: IVRSession, user_input: str) -> tuple[str, IVRState]:
        """
        Process user input for the current state.

        Args:
            session: Active IVR session object
            user_input: Raw text from simulator or ASR

        Returns:
            (response_text, next_state)
        """
        current = session.current_state
        session.log_turn("USER", user_input)

        # Use AI engine to extract intent / rating from user input
        parsed = self.ai_engine.parse_input(user_input, current)

        next_state, response = self._handle_state(session, current, parsed)

        # Validate transition
        if next_state not in self.transitions.get(current, []):
            logger.warning(f"Invalid transition {current} -> {next_state}, defaulting to ERROR")
            next_state = IVRState.ERROR

        session.previous_state = session.current_state
        session.current_state = next_state
        session.retry_count = 0 if next_state != IVRState.ERROR else session.retry_count + 1

        # Force exit after too many retries
        if session.retry_count >= session.max_retries:
            next_state = IVRState.EXIT
            response = "We're having trouble understanding. Thank you for calling. Goodbye."
            session.current_state = IVRState.EXIT

        session.log_turn("IVR", response)

        # Persist when complete
        if next_state in (IVRState.THANK_YOU, IVRState.EXIT):
            self.feedback_store.save(session)

        return response, next_state

    def _handle_state(self, session: IVRSession, state: IVRState, parsed: dict) -> tuple:
        """Route to the correct state handler."""
        handlers = {
            IVRState.WELCOME:           self._handle_welcome,
            IVRState.VERIFY_PATIENT:    self._handle_verify_patient,
            IVRState.MENU_MAIN:         self._handle_menu_main,
            IVRState.FEEDBACK_OVERALL:  self._handle_rating("overall_rating", IVRState.FEEDBACK_DOCTOR),
            IVRState.FEEDBACK_DOCTOR:   self._handle_rating("doctor_rating",  IVRState.FEEDBACK_NURSE),
            IVRState.FEEDBACK_NURSE:    self._handle_rating("nurse_rating",   IVRState.FEEDBACK_FACILITY),
            IVRState.FEEDBACK_FACILITY: self._handle_rating("facility_rating",IVRState.FEEDBACK_WAIT_TIME),
            IVRState.FEEDBACK_WAIT_TIME:self._handle_rating("wait_time_rating",IVRState.FEEDBACK_RECOMMEND),
            IVRState.FEEDBACK_RECOMMEND:self._handle_recommend,
            IVRState.OPEN_COMMENTS:     self._handle_open_comments,
            IVRState.CONFIRM_SUBMISSION:self._handle_confirm,
        }
        handler = handlers.get(state)
        if handler:
            return handler(session, parsed)
        return IVRState.ERROR, self.get_prompt_for_state(IVRState.ERROR)

    # --- Individual state handlers ---

    def _handle_welcome(self, session: IVRSession, parsed: dict):
        pid = parsed.get("patient_id")
        if pid:
            # Lookup patient in store
            patient = self.feedback_store.get_patient(pid)
            if patient:
                session.patient_id = pid
                session.patient_name = patient.get("name", "Patient")
                prompt = self.get_prompt_for_state(IVRState.VERIFY_PATIENT).format(
                    patient_name=session.patient_name
                )
                return IVRState.VERIFY_PATIENT, prompt
        return IVRState.ERROR, "I could not find that patient ID. Please try again."

    def _handle_verify_patient(self, session: IVRSession, parsed: dict):
        if parsed.get("intent") == "affirm":
            prompt = self.get_prompt_for_state(IVRState.MENU_MAIN).format(
                patient_name=session.patient_name
            )
            return IVRState.MENU_MAIN, prompt
        elif parsed.get("intent") == "deny":
            return IVRState.EXIT, "We're sorry for the confusion. Please call back with your correct ID. Goodbye."
        return IVRState.ERROR, self.get_prompt_for_state(IVRState.ERROR)

    def _handle_menu_main(self, session: IVRSession, parsed: dict):
        intent = parsed.get("intent")
        if intent == "start":
            return IVRState.FEEDBACK_OVERALL, self.get_prompt_for_state(IVRState.FEEDBACK_OVERALL)
        elif intent == "exit":
            return IVRState.EXIT, self.get_prompt_for_state(IVRState.EXIT)
        return IVRState.ERROR, self.get_prompt_for_state(IVRState.ERROR)

    def _handle_rating(self, field_name: str, next_state: IVRState) -> Callable:
        """Factory: returns a handler that stores a 1-5 rating."""
        def handler(session: IVRSession, parsed: dict):
            rating = parsed.get("rating")
            if rating and 1 <= rating <= 5:
                setattr(session, field_name, rating)
                return next_state, self.get_prompt_for_state(next_state)
            return IVRState.ERROR, f"Please say a number between 1 and 5. {self.get_prompt_for_state(session.current_state)}"
        return handler

    def _handle_recommend(self, session: IVRSession, parsed: dict):
        intent = parsed.get("intent")
        if intent == "affirm":
            session.would_recommend = True
        elif intent == "deny":
            session.would_recommend = False
        else:
            return IVRState.ERROR, "Please say Yes or No. " + self.get_prompt_for_state(IVRState.FEEDBACK_RECOMMEND)
        return IVRState.OPEN_COMMENTS, self.get_prompt_for_state(IVRState.OPEN_COMMENTS)

    def _handle_open_comments(self, session: IVRSession, parsed: dict):
        if parsed.get("intent") != "skip":
            session.open_comments = parsed.get("raw_text", "")
        return IVRState.CONFIRM_SUBMISSION, self.get_prompt_for_state(IVRState.CONFIRM_SUBMISSION)

    def _handle_confirm(self, session: IVRSession, parsed: dict):
        intent = parsed.get("intent")
        if intent == "submit":
            return IVRState.THANK_YOU, self.get_prompt_for_state(IVRState.THANK_YOU)
        elif intent == "review":
            return IVRState.MENU_MAIN, self.get_prompt_for_state(IVRState.MENU_MAIN).format(
                patient_name=session.patient_name or "Patient"
            )
        return IVRState.ERROR, self.get_prompt_for_state(IVRState.ERROR)
