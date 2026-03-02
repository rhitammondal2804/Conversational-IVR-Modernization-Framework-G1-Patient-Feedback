# backend/menu_engine.py

from database import save_feedback
from session_manager import update_menu, end_session

MENUS = {
    "main": {
        "prompt": "Welcome to City Hospital. Press 1 for Doctor Consultation Feedback. Press 2 for Facilities Feedback.",
        "options": {
            "1": {"action": "goto", "target": "consultation"},
            "2": {"action": "goto", "target": "facilities"}
        }
    },
    "consultation": {
        "prompt": "Please rate your doctor from 1 to 5. Press 0 to go back.",
        "options": {
            "1": {"action": "save", "category": "Doctor", "rating": "1"},
            "2": {"action": "save", "category": "Doctor", "rating": "2"},
            "3": {"action": "save", "category": "Doctor", "rating": "3"},
            "4": {"action": "save", "category": "Doctor", "rating": "4"},
            "5": {"action": "save", "category": "Doctor", "rating": "5"},
            "0": {"action": "goto", "target": "main"}
        }
    },
    "facilities": {
        "prompt": "Please rate hospital facilities from 1 to 5. Press 0 to go back.",
        "options": {
            "1": {"action": "save", "category": "Facilities", "rating": "1"},
            "2": {"action": "save", "category": "Facilities", "rating": "2"},
            "3": {"action": "save", "category": "Facilities", "rating": "3"},
            "4": {"action": "save", "category": "Facilities", "rating": "4"},
            "5": {"action": "save", "category": "Facilities", "rating": "5"},
            "0": {"action": "goto", "target": "main"}
        }
    }
}

def process_input(session_id, digit, current_menu):

    menu = MENUS.get(current_menu)

    if digit not in menu["options"]:
        return {"status": "invalid", "prompt": menu["prompt"]}

    option = menu["options"][digit]

    if option["action"] == "goto":
        update_menu(session_id, option["target"])
        return {
            "status": "ok",
            "menu": option["target"],
            "prompt": MENUS[option["target"]]["prompt"]
        }

    elif option["action"] == "save":
        save_feedback(session_id, option["category"], option["rating"])
        end_session(session_id)
        return {
            "status": "hangup",
            "action": "hangup",
            "message": "Thank you. Your feedback has been recorded."
        }