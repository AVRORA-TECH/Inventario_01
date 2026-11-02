"""Configuration module for Refribreak Inventory Core (RIC).
Reads settings securely and sets up project constants.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("REFRIBREAK_DB_PATH", str(BASE_DIR / "refribreak.db"))
APP_HOST = os.environ.get("APP_HOST", "127.0.0.1")
APP_PORT = int(os.environ.get("APP_PORT", "8000"))
EXPIRATION_ALERT_DAYS = int(os.environ.get("EXPIRATION_ALERT_DAYS", "7"))
WASTE_APPROVAL_THRESHOLD_COP = float(os.environ.get("WASTE_APPROVAL_THRESHOLD_COP", "200000.0"))
