"""
Entry Point
============
Run the Patient Feedback IVR Web Simulator.

Usage:
    python app.py

Then open http://localhost:5000 in your browser.
"""

import logging
from src.web_simulator.simulator_app import app

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    app.run(debug=True, host="0.0.0.0", port=5000)
