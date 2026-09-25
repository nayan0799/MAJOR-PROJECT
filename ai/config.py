from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
DEFAULT_MODEL_PATH = MODELS_DIR / "yolo11n.pt"
CUSTOM_MODEL_PATH = MODELS_DIR / "custom" / "best.pt"
BACKEND_URL = os.getenv("SMARTBUS_BACKEND_URL", "http://127.0.0.1:8000")
GPS_MODE = os.getenv("SMARTBUS_GPS_MODE", "mock")
GPS_PORT = os.getenv("SMARTBUS_GPS_PORT", "COM3")
GPS_BAUD = int(os.getenv("SMARTBUS_GPS_BAUD", "9600"))
CONFIDENCE = float(os.getenv("SMARTBUS_CONFIDENCE", "0.50"))
EVENT_COOLDOWN_SECONDS = float(os.getenv("SMARTBUS_EVENT_COOLDOWN", "5"))
VEHICLE_CLASSES = {"car", "bus", "truck", "motorcycle", "bicycle"}
ROAD_HAZARD_CLASSES = {"pothole", "garbage", "road_damage", "waterlogging", "zebra_crossing", "traffic_sign"}
