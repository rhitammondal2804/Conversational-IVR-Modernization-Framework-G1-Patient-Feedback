"""
Test Suite - Patient Feedback IVR System
==========================================
Unit + integration tests for:
  - AI engine intent/rating extraction
  - IVR state machine transitions
  - Full end-to-end dialogue simulation

Milestone 3 - Conversational AI Interface Development
"""

import unittest
from src.ivr_engine.ivr_flow_controller import IVRFlowController, IVRSession, IVRState
from src.ai_engine.conversation_engine import AIConversationEngine
from src.middleware.feedback_store import FeedbackStore


class TestAIEngine(unittest.TestCase):
    """Tests for NLU / intent extraction."""

    def setUp(self):
        self.engine = AIConversationEngine(use_llm=False)

    def _parse(self, text, state=IVRState.MENU_MAIN):
        return self.engine.parse_input(text, state)

    # --- Intent tests ---
    def test_affirm_yes(self):
        self.assertEqual(self._parse("Yes")["intent"], "affirm")

    def test_affirm_yeah(self):
        self.assertEqual(self._parse("yeah that's right")["intent"], "affirm")

    def test_deny_no(self):
        self.assertEqual(self._parse("No")["intent"], "deny")

    def test_start_feedback(self):
        self.assertEqual(self._parse("Start Feedback")["intent"], "start")

    def test_exit(self):
        self.assertEqual(self._parse("exit")["intent"], "exit")

    def test_skip(self):
        self.assertEqual(self._parse("skip")["intent"], "skip")

    def test_submit(self):
        self.assertEqual(self._parse("Submit")["intent"], "submit")

    def test_review(self):
        self.assertEqual(self._parse("Go back")["intent"], "review")

    # --- Rating tests ---
    def test_rating_digit(self):
        self.assertEqual(self._parse("4")["rating"], 4)

    def test_rating_word(self):
        self.assertEqual(self._parse("five")["rating"], 5)

    def test_rating_adjective_excellent(self):
        self.assertEqual(self._parse("excellent")["rating"], 5)

    def test_rating_adjective_poor(self):
        self.assertEqual(self._parse("poor")["rating"], 1)

    def test_rating_out_of_range(self):
        # "6" is not in NUMBER_WORDS so should be None
        self.assertIsNone(self._parse("6")["rating"])

    # --- Patient ID extraction ---
    def test_patient_id_extraction(self):
        result = self._parse("My ID is P12345", IVRState.WELCOME)
        self.assertEqual(result["patient_id"], "P12345")

    def test_patient_id_numeric(self):
        result = self._parse("67890", IVRState.WELCOME)
        self.assertIsNotNone(result["patient_id"])

    # --- Empathetic response ---
    def test_empathetic_low_rating(self):
        resp = self.engine.generate_empathetic_response("Next question.", 1)
        self.assertIn("sorry", resp.lower())

    def test_empathetic_high_rating(self):
        resp = self.engine.generate_empathetic_response("Next question.", 5)
        self.assertIn("wonderful", resp.lower())


class TestFeedbackStore(unittest.TestCase):
    """Tests for patient lookup and feedback persistence."""

    def setUp(self):
        # Use a temp path to avoid polluting real data
        self.store = FeedbackStore(storage_path="/tmp/test_feedback.json")

    def test_get_known_patient(self):
        p = self.store.get_patient("P12345")
        self.assertIsNotNone(p)
        self.assertEqual(p["name"], "Arjun Sharma")

    def test_get_unknown_patient(self):
        p = self.store.get_patient("P99999")
        self.assertIsNone(p)

    def test_save_and_retrieve(self):
        session = IVRSession(session_id="TEST-001", patient_id="P12345")
        session.overall_rating = 4
        session.doctor_rating = 5
        session.would_recommend = True
        self.store.save(session)
        records = self.store.get_all()
        self.assertTrue(any(r["session_id"] == "TEST-001" for r in records))

    def test_summary_stats(self):
        session = IVRSession(session_id="TEST-002", patient_id="P12345")
        session.overall_rating = 4
        session.doctor_rating = 3
        session.would_recommend = True
        self.store.save(session)
        stats = self.store.get_summary_stats()
        self.assertIn("total_responses", stats)
        self.assertGreater(stats["total_responses"], 0)


class TestIVRFlowFull(unittest.TestCase):
    """End-to-end dialogue simulation tests."""

    def setUp(self):
        self.store = FeedbackStore(storage_path="/tmp/test_flow_feedback.json")
        self.ai = AIConversationEngine(use_llm=False)
        self.ctrl = IVRFlowController(ai_engine=self.ai, feedback_store=self.store)

    def _make_session(self):
        s = IVRSession(session_id="E2E-001", current_state=IVRState.WELCOME)
        s.patient_id = "P12345"
        s.patient_name = "Arjun Sharma"
        return s

    def test_welcome_to_verify(self):
        s = self._make_session()
        s.current_state = IVRState.WELCOME
        resp, state = self.ctrl.process_input(s, "P12345")
        self.assertEqual(state, IVRState.VERIFY_PATIENT)

    def test_verify_affirm(self):
        s = self._make_session()
        s.current_state = IVRState.VERIFY_PATIENT
        resp, state = self.ctrl.process_input(s, "Yes")
        self.assertEqual(state, IVRState.MENU_MAIN)

    def test_verify_deny(self):
        s = self._make_session()
        s.current_state = IVRState.VERIFY_PATIENT
        resp, state = self.ctrl.process_input(s, "No")
        self.assertEqual(state, IVRState.EXIT)

    def test_start_feedback(self):
        s = self._make_session()
        s.current_state = IVRState.MENU_MAIN
        resp, state = self.ctrl.process_input(s, "Start Feedback")
        self.assertEqual(state, IVRState.FEEDBACK_OVERALL)

    def test_rating_flow(self):
        s = self._make_session()
        s.current_state = IVRState.FEEDBACK_OVERALL
        resp, state = self.ctrl.process_input(s, "4")
        self.assertEqual(state, IVRState.FEEDBACK_DOCTOR)
        self.assertEqual(s.overall_rating, 4)

    def test_invalid_rating_goes_to_error(self):
        s = self._make_session()
        s.current_state = IVRState.FEEDBACK_OVERALL
        resp, state = self.ctrl.process_input(s, "banana")
        self.assertEqual(state, IVRState.ERROR)

    def test_recommend_yes(self):
        s = self._make_session()
        s.current_state = IVRState.FEEDBACK_RECOMMEND
        resp, state = self.ctrl.process_input(s, "Yes")
        self.assertTrue(s.would_recommend)
        self.assertEqual(state, IVRState.OPEN_COMMENTS)

    def test_open_comments_skip(self):
        s = self._make_session()
        s.current_state = IVRState.OPEN_COMMENTS
        resp, state = self.ctrl.process_input(s, "Skip")
        self.assertEqual(state, IVRState.CONFIRM_SUBMISSION)

    def test_submit_completes_session(self):
        s = self._make_session()
        s.current_state = IVRState.CONFIRM_SUBMISSION
        resp, state = self.ctrl.process_input(s, "Submit")
        self.assertEqual(state, IVRState.THANK_YOU)

    def test_full_happy_path(self):
        """Simulate a complete successful feedback call."""
        s = IVRSession(session_id="HAPPY-001", current_state=IVRState.WELCOME)

        steps = [
            ("P12345",         IVRState.VERIFY_PATIENT),
            ("Yes",            IVRState.MENU_MAIN),
            ("Start Feedback", IVRState.FEEDBACK_OVERALL),
            ("5",              IVRState.FEEDBACK_DOCTOR),
            ("4",              IVRState.FEEDBACK_NURSE),
            ("5",              IVRState.FEEDBACK_FACILITY),
            ("3",              IVRState.FEEDBACK_WAIT_TIME),
            ("4",              IVRState.FEEDBACK_RECOMMEND),     # wait_time rating
            ("Yes",            IVRState.OPEN_COMMENTS),          # would recommend
            ("The nurses were very caring", IVRState.CONFIRM_SUBMISSION),
            ("Submit",         IVRState.THANK_YOU),
        ]

        for user_input, expected_state in steps:
            _, actual_state = self.ctrl.process_input(s, user_input)
            self.assertEqual(actual_state, expected_state,
                             f"After '{user_input}': expected {expected_state.name}, got {actual_state.name}")

        self.assertEqual(s.overall_rating, 5)
        self.assertEqual(s.doctor_rating, 4)
        self.assertTrue(s.would_recommend)


if __name__ == "__main__":
    unittest.main(verbosity=2)
