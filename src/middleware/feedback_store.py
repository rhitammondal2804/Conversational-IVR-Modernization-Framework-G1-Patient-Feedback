"""
Feedback Store & Middleware Integration Layer
=============================================
Bridges the IVR session data with persistent storage.
Acts as the integration middleware between Milestone 2 (API layer)
and Milestone 3 (Conversational AI Interface).

Supports:
  - In-memory store (default, for testing/simulator)
  - JSON file persistence (lightweight production option)
  - Patient lookup (simulates EHR/HIS integration)

Milestone 3 - Conversational AI Interface Development
Project: AI-Enabled Conversational Patient Feedback IVR (Web Simulator Approach)
"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Simulated patient database (replaces EHR API call in production)
MOCK_PATIENT_DB = {
    "P12345": {"name": "Arjun Sharma",   "dob": "1985-03-12", "last_visit": "2025-04-20"},
    "P67890": {"name": "Priya Verma",    "dob": "1992-07-08", "last_visit": "2025-04-22"},
    "P11111": {"name": "Ramesh Mondal",  "dob": "1970-11-01", "last_visit": "2025-04-18"},
    "P22222": {"name": "Sunita Das",     "dob": "1988-05-25", "last_visit": "2025-04-25"},
}


class FeedbackStore:
    """
    Persistent store for patient feedback sessions.
    Integrates with the Milestone 2 middleware API layer.
    """

    def __init__(self, storage_path: str = "data/feedback_records.json"):
        self._records: list[dict] = []
        self._storage_path = Path(storage_path)
        self._load_from_disk()

    # --- Patient Lookup (EHR Integration stub) ---

    def get_patient(self, patient_id: str) -> dict | None:
        """
        Look up patient by ID.
        In production, this calls the ACS/BAP EHR API endpoint.
        """
        patient = MOCK_PATIENT_DB.get(patient_id.upper())
        if not patient:
            logger.warning(f"Patient not found: {patient_id}")
        return patient

    # --- Feedback Persistence ---

    def save(self, session) -> bool:
        """
        Persist a completed IVR session's feedback data.

        Args:
            session: IVRSession object

        Returns:
            True if saved successfully
        """
        try:
            record = session.to_dict()
            record["submitted_at"] = datetime.utcnow().isoformat()
            self._records.append(record)
            self._save_to_disk()
            logger.info(f"Feedback saved for session {session.session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")
            return False

    def get_all(self) -> list[dict]:
        """Return all stored feedback records."""
        return self._records

    def get_by_patient(self, patient_id: str) -> list[dict]:
        """Return all feedback for a specific patient."""
        return [r for r in self._records if r.get("patient_id") == patient_id]

    def get_summary_stats(self) -> dict:
        """Compute aggregate statistics across all feedback."""
        if not self._records:
            return {"total_responses": 0}

        rating_fields = ["overall", "doctor", "nurse", "facility", "wait_time"]
        stats = {"total_responses": len(self._records)}

        for field in rating_fields:
            values = [
                r["ratings"][field]
                for r in self._records
                if r.get("ratings", {}).get(field) is not None
            ]
            if values:
                stats[f"avg_{field}_rating"] = round(sum(values) / len(values), 2)

        recommend_count = sum(
            1 for r in self._records if r.get("would_recommend") is True
        )
        stats["recommend_rate_pct"] = round(
            (recommend_count / len(self._records)) * 100, 1
        )
        return stats

    # --- Disk I/O ---

    def _save_to_disk(self):
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._storage_path, "w") as f:
                json.dump(self._records, f, indent=2)
        except Exception as e:
            logger.error(f"Disk write failed: {e}")

    def _load_from_disk(self):
        try:
            if self._storage_path.exists():
                with open(self._storage_path) as f:
                    self._records = json.load(f)
                logger.info(f"Loaded {len(self._records)} records from disk")
        except Exception as e:
            logger.warning(f"Could not load records from disk: {e}")
            self._records = []
