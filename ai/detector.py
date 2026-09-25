import os
import time
import cv2
import requests
from ultralytics import YOLO
from .config import *
from .gps import GPS

SOURCE = int(os.getenv("SMARTBUS_CAMERA", "0")) if os.getenv("SMARTBUS_CAMERA", "0").isdigit() else os.getenv("SMARTBUS_CAMERA", "0")

def send_event(e):
    try:
        requests.post(BACKEND_URL + "/api/events", json=e, timeout=2)
    except Exception as ex:
        print("Backend:", ex)

def load_models():
    models = [YOLO(str(DEFAULT_MODEL_PATH))]
    if CUSTOM_MODEL_PATH.exists():
        custom = YOLO(str(CUSTOM_MODEL_PATH))
        names = {str(v).lower() for v in custom.names.values()}
        if names & ROAD_HAZARD_CLASSES:
            models.append(custom)
            print("Custom road-hazard model loaded.")
        else:
            print("models/custom/best.pt is a baseline YOLO model, not a trained road-hazard model; using it only as fallback is disabled.")
    else:
        print("No custom road-hazard model. Vehicle detection still works.")
    return models

def main():
    models = load_models()
    gps = GPS(GPS_MODE, GPS_PORT, GPS_BAUD)
    cap = cv2.VideoCapture(SOURCE)
    if not cap.isOpened():
        raise RuntimeError(f"Camera could not be opened: {SOURCE}")
    last = {}
    counts = {x: 0 for x in VEHICLE_CLASSES}
    while True:
        ok, frame = cap.read()
        if not ok:
            print("Camera frame could not be read.")
            break
        loc = gps.read()
        for model in models:
            for result in model(frame, verbose=False):
                for box in result.boxes:
                    conf = float(box.conf[0])
                    if conf < CONFIDENCE:
                        continue
                    cid = int(box.cls[0])
                    name = str(model.names[cid]).lower()
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"{name} {conf:.0%}", (x1, max(25, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, .65, (0,255,0), 2)
                    if name in VEHICLE_CLASSES:
                        counts[name] += 1
                    event_kind = "vehicle" if name in VEHICLE_CLASSES else ("road_hazard" if name in ROAD_HAZARD_CLASSES else "object")
                    now = time.time()
                    key = f"{event_kind}:{name}"
                    if event_kind != "object" and now - last.get(key, 0) >= EVENT_COOLDOWN_SECONDS:
                        send_event({"event_type": event_kind, "label": name, "confidence": conf,
                                    "latitude": loc["latitude"], "longitude": loc["longitude"],
                                    "metadata": {"bbox": [x1,y1,x2,y2]}})
                        last[key] = now
        y = 30
        for n, c in counts.items():
            cv2.putText(frame, f"{n}: {c}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, .6, (255,255,255), 2)
            y += 25
        cv2.imshow("AI Smart Bus - Phase 1", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
