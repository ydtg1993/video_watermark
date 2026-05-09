import json
import os
from pathlib import Path

HISTORY_FILE = Path("logs/history.json")

class HistoryManager:
    def __init__(self):
        os.makedirs(HISTORY_FILE.parent, exist_ok=True)

    def load_history(self):
        if not HISTORY_FILE.exists():
            return []
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save_history(self, data):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)