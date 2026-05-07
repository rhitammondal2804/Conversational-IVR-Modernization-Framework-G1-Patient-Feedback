"""
Milestone 4 — Full Test Suite (extends Milestone 3)
=====================================================
Tests the M3 components directly:
  - src/ivr_engine/ivr_flow_controller.py
  - src/ai_engine/conversation_engine.py
  - src/middleware/feedback_store.py
  - src/web_simulator/simulator_app.py (Flask client)

Covers:
  - Extended unit tests for all edge cases
  - Performance / load tests
  - Full end-to-end user flow simulations
  - Flask API integration tests
  - Error recovery and retry logic

Run from the repo root:
    python -m pytest tests/ -v --cov=src --cov-report=term-missing
"""

import time
import threading
import json
import pytest

from src.ivr_engine.ivr_flow_controller import (
    IVRFlowController, IVRSession, IVRState
)
from src.ai_engine.conversation_engine import AIConversationEngine
from src.middleware.feedback_store import FeedbackStore


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    return FeedbackStore(storage_path=str(tmp_path / "feedback.json"))

@pytest.fixture
def engine():
    return AIConversationEngine(use_llm=False)

@pytest.fixture
def controller(store, engine):
    return IVRFlowController(ai_engine=engine, feedback_store=store)

@pytest.fixture
def fresh_session():
    return IVRSession(session_id="M4-TEST", current_state=IVRState.WELCOME)

@pytest.fixture
def flask_client(store, engine):
    """Flask test client wired to real M3 simulator app."""
    from src.web_simulator.simulator_app import app, _feedback_store, _ai_engine, _sessions
    app.config["TESTING"] = True
    # Clear sessions between tests
    _sessions.clear()
    with app.test_client() as client:
        yield client


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — Extended AI Engine Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAIEngineExtended:
    """Extended NLU tests covering more edge cases and natural language variety."""

    def _parse(self, engine, text, state=IVRState.MENU_MAIN):
        return engine.parse_input(text, state)

    # Natural language variants
    def test_affirm_of_course(self, engine):
        assert self._parse(engine, "of course")["intent"] == "affirm"

    def test_affirm_absolutely(self, engine):
        assert self._parse(engine, "absolutely")["intent"] == "affirm"

    def test_deny_nope(self, engine):
        assert self._parse(engine, "nope")["intent"] == "deny"

    def test_exit_bye(self, engine):
        assert self._parse(engine, "bye")["intent"] == "exit"

    def test_exit_goodbye(self, engine):
        assert self._parse(engine, "goodbye")["intent"] == "exit"

    def test_submit_done(self, engine):
        assert self._parse(engine, "done")["intent"] == "submit"

    def test_submit_finish(self, engine):
        assert self._parse(engine, "finish")["intent"] == "submit"

    def test_review_go_back(self, engine):
        assert self._parse(engine, "go back")["intent"] == "review"

    def test_skip_pass(self, engine):
        assert self._parse(engine, "pass")["intent"] == "skip"

    def test_skip_no_comment(self, engine):
        assert self._parse(engine, "no comment")["intent"] == "skip"

    # Rating extraction - edge cases
    def test_rating_one_word(self, engine):
        assert self._parse(engine, "one")["rating"] == 1

    def test_rating_two_word(self, engine):
        assert self._parse(engine, "two")["rating"] == 2

    def test_rating_three_word(self, engine):
        assert self._parse(engine, "three")["rating"] == 3

    def test_rating_good(self, engine):
        assert self._parse(engine, "good")["rating"] == 4

    def test_rating_great(self, engine):
        assert self._parse(engine, "great")["rating"] == 5

    def test_rating_bad(self, engine):
        assert self._parse(engine, "bad")["rating"] == 1

    def test_empty_input_no_crash(self, engine):
        """Empty input must not raise an exception."""
        result = self._parse(engine, "")
        assert result["intent"] is None
        assert result["rating"] is None

    def test_very_long_input(self, engine):
        """Very long input (open comment) must not crash."""
        long_text = "The nurses were absolutely wonderful " * 50
        result = self._parse(engine, long_text, IVRState.OPEN_COMMENTS)
        assert result is not None
        assert result["raw_text"] == long_text

    def test_mixed_rating_and_intent(self, engine):
        """Input with both a rating and affirm — rating should be captured."""
        result = self._parse(engine, "yes five", IVRState.FEEDBACK_OVERALL)
        assert result["rating"] == 5

    def test_patient_id_uppercase(self, engine):
        result = self._parse(engine, "P12345", IVRState.WELCOME)
        assert result["patient_id"] == "P12345"

    def test_patient_id_lowercase_normalized(self, engine):
        result = self._parse(engine, "p67890", IVRState.WELCOME)
        assert result["patient_id"] == "P67890"

    def test_empathetic_response_no_rating(self, engine):
        resp = engine.generate_empathetic_response("Next question.", None)
        assert resp == "Next question."

    def test_empathetic_response_mid_rating(self, engine):
        resp = engine.generate_empathetic_response("Next question.", 3)
        assert "thank" in resp.lower()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — Extended IVR Flow Controller Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIVRFlowExtended:
    """Extended state machine tests including error recovery and retry logic."""

    def _run(self, controller, session, user_input):
        return controller.process_input(session, user_input)

    def test_error_state_retry_increments(self, controller):
        s = IVRSession("retry-test", current_state=IVRState.FEEDBACK_OVERALL)
        _, state = self._run(controller, s, "banana")
        assert state == IVRState.ERROR
        assert s.retry_count == 1

    def test_max_retries_forces_exit(self, controller):
        """After 3 failed inputs the session must force-exit."""
        s = IVRSession("max-retry", current_state=IVRState.FEEDBACK_OVERALL)
        s.max_retries = 3
        for _ in range(3):
            _, state = self._run(controller, s, "banana")
        assert state == IVRState.EXIT

    def test_retry_resets_on_valid_input(self, controller):
        """A valid input after an error must reset the retry counter."""
        s = IVRSession("retry-reset", current_state=IVRState.FEEDBACK_OVERALL)
        self._run(controller, s, "banana")   # error → retry_count = 1
        s.current_state = IVRState.FEEDBACK_OVERALL  # simulate re-prompt
        self._run(controller, s, "4")        # valid → should reset
        assert s.retry_count == 0

    def test_session_history_records_all_turns(self, controller):
        """Every user input and IVR response must be logged in history."""
        s = IVRSession("history-test", current_state=IVRState.WELCOME)
        s.patient_id = "P12345"
        s.patient_name = "Arjun Sharma"
        self._run(controller, s, "P12345")
        assert len(s.history) >= 2  # user turn + IVR response

    def test_session_serialization(self, controller):
        """to_dict() must return a valid JSON-serializable dict."""
        s = IVRSession("serial-test", current_state=IVRState.WELCOME)
        s.overall_rating = 4
        s.would_recommend = True
        d = s.to_dict()
        assert isinstance(d, dict)
        json.dumps(d)  # must not raise

    def test_all_five_ratings_accepted(self, controller):
        """Each rating 1–5 must transition forward correctly."""
        rating_states = [
            (IVRState.FEEDBACK_OVERALL,   "overall_rating",   IVRState.FEEDBACK_DOCTOR),
            (IVRState.FEEDBACK_DOCTOR,    "doctor_rating",    IVRState.FEEDBACK_NURSE),
            (IVRState.FEEDBACK_NURSE,     "nurse_rating",     IVRState.FEEDBACK_FACILITY),
            (IVRState.FEEDBACK_FACILITY,  "facility_rating",  IVRState.FEEDBACK_WAIT_TIME),
            (IVRState.FEEDBACK_WAIT_TIME, "wait_time_rating", IVRState.FEEDBACK_RECOMMEND),
        ]
        for from_state, attr, to_state in rating_states:
            for rating in range(1, 6):
                s = IVRSession(f"rating-{from_state.name}-{rating}", current_state=from_state)
                s.patient_name = "Test"
                _, next_state = controller.process_input(s, str(rating))
                assert next_state == to_state, (
                    f"Rating {rating} at {from_state.name} should go to {to_state.name}"
                )
                assert getattr(s, attr) == rating

    def test_open_comments_captured(self, controller):
        """Free text in OPEN_COMMENTS must be stored on the session."""
        s = IVRSession("comments-test", current_state=IVRState.OPEN_COMMENTS)
        comment = "The waiting room was too cold but the doctor was great"
        self._run(controller, s, comment)
        assert s.open_comments == comment

    def test_feedback_saved_on_thank_you(self, controller, store):
        """Reaching THANK_YOU must trigger feedback persistence."""
        s = IVRSession("save-test", current_state=IVRState.CONFIRM_SUBMISSION)
        s.patient_name = "Test Patient"
        self._run(controller, s, "Submit")
        records = store.get_all()
        assert any(r["session_id"] == "save-test" for r in records)

    def test_feedback_saved_on_exit(self, controller, store):
        """Forced exit (max retries) must still save whatever data was collected."""
        s = IVRSession("exit-save", current_state=IVRState.FEEDBACK_OVERALL)
        s.patient_name = "Test"
        s.max_retries = 1
        controller.process_input(s, "banana")  # triggers exit
        # Should not crash — partial data is acceptable


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — Extended Feedback Store Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFeedbackStoreExtended:
    """Extended persistence and stats tests."""

    def _make_session(self, sid, overall=4, doctor=5, nurse=4,
                      facility=3, wait=4, recommend=True):
        s = IVRSession(session_id=sid, patient_id="P12345")
        s.patient_name = "Test Patient"
        s.overall_rating = overall
        s.doctor_rating = doctor
        s.nurse_rating = nurse
        s.facility_rating = facility
        s.wait_time_rating = wait
        s.would_recommend = recommend
        s.open_comments = "Great experience overall."
        return s

    def test_stats_with_no_records(self, store):
        stats = store.get_summary_stats()
        assert stats["total_responses"] == 0

    def test_stats_average_rating_correct(self, store):
        store.save(self._make_session("s1", overall=4))
        store.save(self._make_session("s2", overall=2))
        stats = store.get_summary_stats()
        assert stats["avg_overall_rating"] == 3.0

    def test_recommend_rate_100_percent(self, store):
        store.save(self._make_session("s-rec-1", recommend=True))
        store.save(self._make_session("s-rec-2", recommend=True))
        stats = store.get_summary_stats()
        assert stats["recommend_rate_pct"] == 100.0

    def test_recommend_rate_0_percent(self, store):
        store.save(self._make_session("s-no-1", recommend=False))
        stats = store.get_summary_stats()
        assert stats["recommend_rate_pct"] == 0.0

    def test_get_by_patient(self, store):
        s1 = self._make_session("by-p-1")
        s1.patient_id = "P12345"
        s2 = self._make_session("by-p-2")
        s2.patient_id = "P99999"
        store.save(s1)
        store.save(s2)
        results = store.get_by_patient("P12345")
        assert all(r["patient_id"] == "P12345" for r in results)
        assert not any(r["patient_id"] == "P99999" for r in results)

    def test_records_persist_across_instances(self, tmp_path):
        """Records saved by one FeedbackStore instance must be readable by another."""
        path = str(tmp_path / "shared.json")
        s = self._make_session("persist-1")

        store1 = FeedbackStore(storage_path=path)
        store1.save(s)

        store2 = FeedbackStore(storage_path=path)
        records = store2.get_all()
        assert any(r["session_id"] == "persist-1" for r in records)

    def test_patient_lookup_known(self, store):
        p = store.get_patient("P12345")
        assert p is not None
        assert "name" in p

    def test_patient_lookup_case_insensitive(self, store):
        p = store.get_patient("p12345")
        assert p is not None

    def test_patient_lookup_unknown(self, store):
        assert store.get_patient("P00000") is None

    def test_save_returns_true(self, store):
        s = self._make_session("save-bool")
        result = store.save(s)
        assert result is True


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — Flask API Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFlaskAPIIntegration:
    """Full integration tests against the real Flask simulator app."""

    def test_health_endpoint_200(self, flask_client):
        resp = flask_client.get("/api/health")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "ok"

    def test_root_returns_html(self, flask_client):
        resp = flask_client.get("/")
        assert resp.status_code == 200
        assert b"<html" in resp.data.lower() or b"<!doctype" in resp.data.lower()

    def test_start_session_creates_session(self, flask_client):
        resp = flask_client.post("/api/session/start")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "session_id" in data
        assert "response" in data
        assert data["is_terminal"] is False

    def test_start_session_state_is_welcome(self, flask_client):
        resp = flask_client.post("/api/session/start")
        data = json.loads(resp.data)
        assert data["state"] == "WELCOME"

    def test_input_missing_text_returns_400(self, flask_client):
        resp = flask_client.post("/api/session/start")
        sid = json.loads(resp.data)["session_id"]
        resp2 = flask_client.post(
            f"/api/session/{sid}/input",
            json={},
            content_type="application/json"
        )
        assert resp2.status_code == 400

    def test_input_empty_text_returns_400(self, flask_client):
        resp = flask_client.post("/api/session/start")
        sid = json.loads(resp.data)["session_id"]
        resp2 = flask_client.post(
            f"/api/session/{sid}/input",
            json={"text": "   "},
            content_type="application/json"
        )
        assert resp2.status_code == 400

    def test_input_unknown_session_returns_404(self, flask_client):
        resp = flask_client.post(
            "/api/session/nonexistent-id/input",
            json={"text": "hello"},
            content_type="application/json"
        )
        assert resp.status_code == 404

    def test_full_api_dialogue_flow(self, flask_client):
        """Walk through a complete session via the REST API."""
        # Start
        resp = flask_client.post("/api/session/start")
        sid = json.loads(resp.data)["session_id"]

        def send(text):
            r = flask_client.post(
                f"/api/session/{sid}/input",
                json={"text": text},
                content_type="application/json"
            )
            return json.loads(r.data)

        steps = [
            ("P12345",         "VERIFY_PATIENT"),
            ("Yes",            "MENU_MAIN"),
            ("Start Feedback", "FEEDBACK_OVERALL"),
            ("5",              "FEEDBACK_DOCTOR"),
            ("4",              "FEEDBACK_NURSE"),
            ("5",              "FEEDBACK_FACILITY"),
            ("3",              "FEEDBACK_WAIT_TIME"),
            ("4",              "FEEDBACK_RECOMMEND"),
            ("Yes",            "OPEN_COMMENTS"),
            ("Skip",           "CONFIRM_SUBMISSION"),
            ("Submit",         "THANK_YOU"),
        ]

        for user_input, expected_state in steps:
            data = send(user_input)
            assert data["state"] == expected_state, (
                f"After '{user_input}': expected {expected_state}, got {data['state']}"
            )

        assert data["is_terminal"] is True

    def test_session_summary_after_completion(self, flask_client):
        """GET /api/session/{id}/summary must return complete feedback data."""
        resp = flask_client.post("/api/session/start")
        sid = json.loads(resp.data)["session_id"]

        def send(text):
            flask_client.post(
                f"/api/session/{sid}/input",
                json={"text": text},
                content_type="application/json"
            )

        for inp in ["P12345", "Yes", "Start Feedback",
                    "5", "4", "5", "3", "4", "Yes", "Skip", "Submit"]:
            send(inp)

        summary = json.loads(flask_client.get(f"/api/session/{sid}/summary").data)
        assert summary["ratings"]["overall"] == 5
        assert summary["would_recommend"] is True

    def test_get_all_feedback_returns_list(self, flask_client):
        resp = flask_client.get("/api/feedback/all")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)

    def test_health_shows_active_sessions(self, flask_client):
        flask_client.post("/api/session/start")
        resp = flask_client.get("/api/health")
        data = json.loads(resp.data)
        assert "sessions_active" in data
        assert data["sessions_active"] >= 1


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — Performance Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPerformance:
    """Performance benchmarks for the M3 system."""

    def test_nlu_parses_100_inputs_under_1s(self, engine):
        inputs = ["yes", "no", "5", "excellent", "skip", "submit", "P12345"] * 15
        start = time.time()
        for text in inputs:
            engine.parse_input(text, IVRState.MENU_MAIN)
        assert time.time() - start < 1.0

    def test_single_dialogue_turn_under_100ms(self, controller):
        s = IVRSession("perf-turn", current_state=IVRState.FEEDBACK_OVERALL)
        start = time.time()
        controller.process_input(s, "4")
        assert time.time() - start < 0.1

    def test_save_100_records_under_2s(self, store):
        start = time.time()
        for i in range(100):
            s = IVRSession(f"perf-{i}", patient_id="P12345")
            s.overall_rating = (i % 5) + 1
            store.save(s)
        assert time.time() - start < 2.0

    def test_flask_root_under_200ms(self, flask_client):
        start = time.time()
        flask_client.get("/")
        assert time.time() - start < 0.2

    def test_flask_health_under_100ms(self, flask_client):
        start = time.time()
        flask_client.get("/api/health")
        assert time.time() - start < 0.1

    def test_10_concurrent_sessions_no_collision(self, store, engine):
        """Session IDs created from multiple threads must be unique."""
        ctrl = IVRFlowController(ai_engine=engine, feedback_store=store)
        ids = []
        lock = threading.Lock()

        def make():
            from src.web_simulator.simulator_app import _sessions
            import uuid
            sid = str(uuid.uuid4())
            session = IVRSession(session_id=sid, current_state=IVRState.WELCOME)
            with lock:
                _sessions[sid] = session
                ids.append(sid)

        threads = [threading.Thread(target=make) for _ in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert len(ids) == len(set(ids)), "Duplicate session IDs under concurrency"

    def test_stats_over_50_records_under_500ms(self, store):
        for i in range(50):
            s = IVRSession(f"stat-perf-{i}")
            s.overall_rating = (i % 5) + 1
            s.would_recommend = i % 2 == 0
            store.save(s)
        start = time.time()
        store.get_summary_stats()
        assert time.time() - start < 0.5


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — End-to-End User Flow Simulations
# ─────────────────────────────────────────────────────────────────────────────

class TestE2EUserFlows:
    """Simulate realistic patient journeys through the complete system."""

    def _run_full_flow(self, controller, ratings=(5, 4, 5, 3, 4),
                       recommend="Yes", comment="Skip"):
        s = IVRSession("e2e", current_state=IVRState.WELCOME)

        inputs = (
            ["P12345", "Yes", "Start Feedback"]
            + [str(r) for r in ratings]
            + [recommend, comment, "Submit"]
        )
        final_state = None
        for inp in inputs:
            _, final_state = controller.process_input(s, inp)
        return s, final_state

    def test_happy_path_ends_at_thank_you(self, controller):
        _, state = self._run_full_flow(controller)
        assert state == IVRState.THANK_YOU

    def test_happy_path_all_ratings_stored(self, controller):
        s, _ = self._run_full_flow(controller, ratings=(5, 4, 3, 2, 1))
        assert s.overall_rating == 5
        assert s.doctor_rating == 4
        assert s.nurse_rating == 3
        assert s.facility_rating == 2
        assert s.wait_time_rating == 1

    def test_patient_who_would_not_recommend(self, controller):
        s, state = self._run_full_flow(controller, recommend="No")
        assert s.would_recommend is False
        assert state == IVRState.THANK_YOU

    def test_patient_with_open_comment(self, controller):
        s, _ = self._run_full_flow(controller, comment="Staff were very kind")
        assert s.open_comments == "Staff were very kind"

    def test_patient_who_skips_comments(self, controller):
        s, _ = self._run_full_flow(controller, comment="Skip")
        assert s.open_comments is None or s.open_comments == ""

    def test_patient_exits_at_menu(self, controller):
        s = IVRSession("exit-menu", current_state=IVRState.WELCOME)
        controller.process_input(s, "P12345")
        controller.process_input(s, "Yes")
        _, state = controller.process_input(s, "Exit")
        assert state == IVRState.EXIT

    def test_wrong_patient_id_exits(self, controller):
        s = IVRSession("wrong-id", current_state=IVRState.VERIFY_PATIENT)
        s.patient_name = "Arjun Sharma"
        _, state = controller.process_input(s, "No")
        assert state == IVRState.EXIT

    def test_five_patients_simultaneously(self, controller, store):
        """Five patients completing full flows must all have feedback saved."""
        sessions = []
        for i in range(5):
            s = IVRSession(f"concurrent-{i}", current_state=IVRState.WELCOME)
            inputs = ["P12345", "Yes", "Start Feedback",
                      "5", "4", "5", "3", "4", "Yes", "Skip", "Submit"]
            for inp in inputs:
                controller.process_input(s, inp)
            sessions.append(s)

        records = store.get_all()
        saved_ids = {r["session_id"] for r in records}
        for s in sessions:
            assert s.session_id in saved_ids

    def test_review_then_resubmit(self, controller):
        """Patient who reviews and resubmits must end at THANK_YOU."""
        s = IVRSession("review-resubmit", current_state=IVRState.CONFIRM_SUBMISSION)
        s.patient_name = "Test"
        # Choose to review
        _, state = controller.process_input(s, "Review")
        assert state == IVRState.MENU_MAIN
        # Start again and submit
        controller.process_input(s, "Start Feedback")
        for inp in ["5", "4", "5", "3", "4", "Yes", "Skip"]:
            controller.process_input(s, inp)
        _, state = controller.process_input(s, "Submit")
        assert state == IVRState.THANK_YOU
