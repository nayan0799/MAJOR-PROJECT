# ============================================================
# AI SMART BUS
# FILTERED OBJECT DETECTION (60 SELECTED CLASSES + GARBAGE)
# GARBAGE INCIDENT UPLOAD ONLY
# ============================================================

import os

# Low latency FFMPEG
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "fflags;nobuffer|flags;low_delay"

import time
import threading
from datetime import datetime

import cv2
import requests
from ultralytics import YOLO

# ------------------------------------------------------------
# PATHS & SETTINGS
# ------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))

PHONE_IP = "100.79.251.184"          # <-- SET YOUR PHONE IP
PHONE_PORT = 8080        # <-p- SET YOUR PHONE PORT
CAMERA_URL = f"http://{PHONE_IP}:{PHONE_PORT}/video"

BACKEND_URL = "http://127.0.0.1:8000"
BUS_ID = "BUS-001"

# General COCO model
COCO_MODEL_PATH = os.path.join(ROOT, "yolov8n.pt")

# Custom garbage model
GARBAGE_MODEL_PATH = os.path.join(ROOT, "runs", "detect", "garbage50-2", "weights", "best.pt")

PHOTO_DIR = os.path.join(ROOT, "backend", "detections")
os.makedirs(PHOTO_DIR, exist_ok=True)

# Detection thresholds
CONFIDENCE_THRESHOLD = 0.15          # for display
SEND_CONFIDENCE_THRESHOLD = 0.15     # for sending garbage to dashboard
YOLO_SIZE = 640
YOLO_INTERVAL = 0.05
COOLDOWN_SECONDS = 10
GPS_UPDATE_SECONDS = 3
HEARTBEAT_SECONDS = 10
DISPLAY_FPS = 60

TARGET_CLASS = "garbage"

# ------------------------------------------------------------
# ALLOWED CLASSES (60 classes + garbage, no bags)
# ------------------------------------------------------------
ALLOWED_CLASSES = {
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
    "cow", "elephant", "bear", "zebra", "giraffe",
    "umbrella", "tie", "frisbee", "skis",
    "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "wine glass", "cup",
    "bowl", "sandwich", "orange", "broccoli", "carrot", "hot dog",
    "pizza", "donut", "cake", "chair", "couch", "potted plant", "bed",
    # "dining table",  <-- REMOVED
    "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "garbage"
}

# ------------------------------------------------------------
# SHARED DATA
# ------------------------------------------------------------
latest_frame = None
latest_frame_id = 0
latest_detections = []
latest_detection_frame_id = -1
current_lat = None
current_lon = None
last_report_time = 0

camera_lock = threading.Lock()
detection_lock = threading.Lock()
gps_lock = threading.Lock()
stop_event = threading.Event()
session = requests.Session()


# ------------------------------------------------------------
# LOAD MODELS
# ------------------------------------------------------------
def load_models():
    print("=" * 70)
    print("🔎 LOADING DETECTION MODELS")
    print("=" * 70)

    # General COCO model
    print(f"📦 COCO model: {COCO_MODEL_PATH}")
    if not os.path.exists(COCO_MODEL_PATH):
        print("⬇️  Downloading YOLOv8n (COCO)...")
        coco_model = YOLO("yolov8n.pt")
    else:
        coco_model = YOLO(COCO_MODEL_PATH)

    # Custom garbage model
    print(f"🗑️ Garbage model: {GARBAGE_MODEL_PATH}")
    if not os.path.exists(GARBAGE_MODEL_PATH):
        raise SystemExit("❌ Garbage model not found")
    garbage_model = YOLO(GARBAGE_MODEL_PATH)

    print("✅ Both models loaded")
    print(f"   Allowed classes: {len(ALLOWED_CLASSES)}")
    print("=" * 70)

    return coco_model, garbage_model


# ------------------------------------------------------------
# GPS functions (same as before)
# ------------------------------------------------------------
def get_gps():
    global current_lat, current_lon
    try:
        response = session.get(f"{BACKEND_URL}/api/buses", timeout=2)
        if not response.ok:
            return
        data = response.json()
        if isinstance(data, dict):
            data = data.get("buses", data.get("data", []))
        if not isinstance(data, list):
            return
        for bus in data:
            if str(bus.get("bus_id", "")) != BUS_ID:
                continue
            new_lat = bus.get("latitude")
            new_lon = bus.get("longitude")
            if new_lat is not None and new_lon is not None:
                with gps_lock:
                    current_lat = float(new_lat)
                    current_lon = float(new_lon)
                return
    except Exception:
        pass

def get_current_gps():
    with gps_lock:
        return current_lat, current_lon

def send_heartbeat():
    lat, lon = get_current_gps()
    try:
        payload = {"bus_id": BUS_ID, "latitude": lat, "longitude": lon}
        response = session.post(
            f"{BACKEND_URL}/api/buses/heartbeat",
            json=payload,
            timeout=3
        )
        if response.ok:
            print(f"💓 Heartbeat | {BUS_ID} | GPS={lat},{lon}")
    except Exception as e:
        print("⚠️ Heartbeat failed:", e)

def gps_worker():
    print("📍 GPS worker started")
    last_gps = 0
    last_heartbeat = 0
    while not stop_event.is_set():
        now = time.time()
        if now - last_gps >= GPS_UPDATE_SECONDS:
            get_gps()
            last_gps = now
        if now - last_heartbeat >= HEARTBEAT_SECONDS:
            send_heartbeat()
            last_heartbeat = now
        time.sleep(0.05)
    print("📍 GPS worker stopped")


# ------------------------------------------------------------
# CAMERA functions
# ------------------------------------------------------------
def connect_camera():
    print("\n📱 Connecting to mobile camera...")
    cap = cv2.VideoCapture(CAMERA_URL, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if cap.isOpened():
        print("✅ Mobile camera connected")
        return cap
    cap.release()
    return None

def camera_worker():
    global latest_frame, latest_frame_id
    cap = None
    print("🎥 Camera worker started")
    while not stop_event.is_set():
        if cap is None:
            cap = connect_camera()
            if cap is None:
                print("⚠️ Camera connection failed.")
                time.sleep(2)
                continue

        ok, frame = cap.read()
        if not ok:
            print("⚠️ Camera frame unavailable.")
            cap.release()
            cap = None
            time.sleep(0.5)
            continue

        with camera_lock:
            latest_frame = frame
            latest_frame_id += 1

    if cap is not None:
        cap.release()
    print("🎥 Camera worker stopped")

def get_latest_frame():
    with camera_lock:
        if latest_frame is None:
            return None, -1
        return latest_frame.copy(), latest_frame_id


# ------------------------------------------------------------
# INCIDENT functions
# ------------------------------------------------------------
def send_report(name, confidence, photo_path, gps_lat, gps_lon):
    try:
        with open(photo_path, "rb") as image_file:
            data = {
                "type": name,
                "lat": gps_lat,
                "lon": gps_lon,
                "time": datetime.now().astimezone().isoformat(),
                "confidence": confidence,
                "status": "Pending",
                "bus_id": BUS_ID
            }
            response = session.post(
                f"{BACKEND_URL}/incidents",
                data=data,
                files={"photo": (os.path.basename(photo_path), image_file, "image/jpeg")},
                timeout=10
            )

        if response.ok:
            print("\n" + "=" * 60)
            print("✅ INCIDENT SENT")
            print(f"🚌 Bus        : {BUS_ID}")
            print(f"🗑️ Detection  : {name}")
            print(f"🎯 Confidence : {confidence * 100:.2f}%")
            print(f"📍 GPS        : {gps_lat},{gps_lon}")
            print("=" * 60)
        else:
            print("❌ Backend error:", response.status_code)
            print(response.text)
    except Exception as e:
        print("❌ Incident upload failed:", e)

def create_incident(frame, name, confidence):
    global last_report_time
    now = time.time()

    if now - last_report_time < COOLDOWN_SECONDS:
        return
    if confidence < SEND_CONFIDENCE_THRESHOLD:
        return

    last_report_time = now
    gps_lat, gps_lon = get_current_gps()

    filename = "garbage_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".jpg"
    photo_path = os.path.join(PHOTO_DIR, filename)

    saved = cv2.imwrite(photo_path, frame)
    if not saved:
        print("❌ Failed to save evidence")
        return

    print(f"\n📸 Evidence saved: {filename}")
    send_report(name, confidence, photo_path, gps_lat, gps_lon)


# ------------------------------------------------------------
# YOLO WORKER (runs both models, filters allowed classes)
# ------------------------------------------------------------
def yolo_worker(coco_model, garbage_model):
    global latest_detections, latest_detection_frame_id

    print("\n🤖 YOLO worker started")
    print(f"🔍 Full-frame detection enabled")
    print(f"🎯 Allowed classes: {len(ALLOWED_CLASSES)}")
    print(f"🎯 Display confidence: {CONFIDENCE_THRESHOLD}")
    print(f"🚨 Send confidence (garbage only): {SEND_CONFIDENCE_THRESHOLD}")

    last_processed_frame = -1
    last_inference_time = 0

    while not stop_event.is_set():
        now = time.time()
        if now - last_inference_time < YOLO_INTERVAL:
            time.sleep(0.001)
            continue

        frame, frame_id = get_latest_frame()
        if frame is None:
            time.sleep(0.005)
            continue

        if frame_id == last_processed_frame:
            time.sleep(0.001)
            continue

        last_processed_frame = frame_id
        last_inference_time = now

        # ----------------------------------------------------
        # Run COCO model
        # ----------------------------------------------------
        try:
            coco_results = coco_model.predict(
                source=frame,
                conf=CONFIDENCE_THRESHOLD,
                imgsz=YOLO_SIZE,
                verbose=False,
                device="cpu"
            )
        except Exception as e:
            print("❌ COCO YOLO error:", e)
            time.sleep(0.1)
            continue

        # ----------------------------------------------------
        # Run Garbage model
        # ----------------------------------------------------
        try:
            garbage_results = garbage_model.predict(
                source=frame,
                conf=CONFIDENCE_THRESHOLD,
                imgsz=YOLO_SIZE,
                verbose=False,
                device="cpu"
            )
        except Exception as e:
            print("❌ Garbage YOLO error:", e)
            time.sleep(0.1)
            continue

        # ----------------------------------------------------
        # Collect detections from both models, filter by allowed classes
        # ----------------------------------------------------
        detections = []

        def add_detections(results, model):
            if results and results[0].boxes is not None:
                for box in results[0].boxes:
                    confidence = float(box.conf[0])
                    class_id = int(box.cls[0])
                    name = str(model.names[class_id]).lower()

                    # Only keep if class is in allowed set
                    if name not in ALLOWED_CLASSES:
                        continue
                    if confidence < CONFIDENCE_THRESHOLD:
                        continue

                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    detections.append({
                        "name": name,
                        "confidence": confidence,
                        "x1": x1, "y1": y1,
                        "x2": x2, "y2": y2
                    })

        add_detections(coco_results, coco_model)
        add_detections(garbage_results, garbage_model)

        # ----------------------------------------------------
        # Save detections for display
        # ----------------------------------------------------
        with detection_lock:
            latest_detections = detections
            latest_detection_frame_id = frame_id

        # ----------------------------------------------------
        # Incident sending (only garbage)
        # ----------------------------------------------------
        garbage_dets = [d for d in detections if d["name"] == TARGET_CLASS]
        if garbage_dets:
            best_garbage = max(garbage_dets, key=lambda x: x["confidence"])
            print(f"🗑️ GARBAGE DETECTED | {best_garbage['confidence']*100:.1f}%")
            if best_garbage["confidence"] >= SEND_CONFIDENCE_THRESHOLD:
                create_incident(frame, best_garbage["name"], best_garbage["confidence"])
            else:
                print(f"   (below send threshold {SEND_CONFIDENCE_THRESHOLD*100:.0f}% – not uploaded)")

    print("🤖 YOLO worker stopped")


# ------------------------------------------------------------
# DRAW functions
# ------------------------------------------------------------
def draw_detections(frame, detections):
    output = frame.copy()
    for detection in detections:
        x1, y1, x2, y2 = detection["x1"], detection["y1"], detection["x2"], detection["y2"]
        confidence = detection["confidence"]
        name = detection["name"]

        # Green box
        cv2.rectangle(output, (x1, y1), (x2, y2), (0, 255, 0), 3)

        # Label
        label = f"{name.upper()} {confidence*100:.1f}%"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.75
        thickness = 2

        text_size = cv2.getTextSize(label, font, font_scale, thickness)[0]
        text_width, text_height = text_size

        label_x = max(0, min(x1, output.shape[1] - text_width - 10))
        label_y = max(text_height + 12, y1)

        # Label background (green)
        cv2.rectangle(output, (label_x, label_y - text_height - 12),
                      (label_x + text_width + 10, label_y), (0, 255, 0), -1)

        # Text (black)
        cv2.putText(output, label, (label_x + 5, label_y - 5),
                    font, font_scale, (0, 0, 0), thickness, cv2.LINE_AA)

    return output

def draw_status(frame):
    output = frame.copy()
    gps_lat, gps_lon = get_current_gps()
    height, width = output.shape[:2]

    status = f"AI SMART BUS | {BUS_ID}"
    cv2.putText(output, status, (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

    if gps_lat is not None and gps_lon is not None:
        gps_text = f"GPS: {gps_lat:.6f},{gps_lon:.6f}"
    else:
        gps_text = "GPS: Waiting..."

    cv2.putText(output, gps_text, (15, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(output, "FILTERED DETECTION", (15, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(output, "Press Q to quit", (15, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

    return output


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main():
    print("\n" + "=" * 70)
    print("              🚍 AI SMART BUS")
    print("       🔍 FILTERED OBJECT DETECTION")
    print("       🗑️ GARBAGE INCIDENT UPLOAD ONLY")
    print("=" * 70)

    print(f"🚌 Bus ID       : {BUS_ID}")
    print(f"📱 Camera       : {CAMERA_URL}")
    print(f"🌐 Backend      : {BACKEND_URL}")
    print(f"🤖 COCO Model   : {COCO_MODEL_PATH}")
    print(f"🤖 Garbage Model: {GARBAGE_MODEL_PATH}")
    print(f"🎯 Allowed Classes: {len(ALLOWED_CLASSES)}")
    print(f"🎯 Display Conf : {CONFIDENCE_THRESHOLD * 100:.0f}%")
    print(f"🚨 Send Conf    : {SEND_CONFIDENCE_THRESHOLD * 100:.0f}%")
    print(f"📐 YOLO size    : {YOLO_SIZE}")
    print("🟩 Box          : GREEN")
    print("📊 Detection    : Only 60 selected classes + garbage")
    print("📱 Aspect       : 19.5:9 supported")
    print("📸 Evidence     : ORIGINAL FRAME (garbage only)")
    print("🚫 ROI          : NONE")
    print("=" * 70)

    # Load models
    coco_model, garbage_model = load_models()

    # Start threads
    camera_thread = threading.Thread(target=camera_worker, daemon=True)
    gps_thread = threading.Thread(target=gps_worker, daemon=True)
    yolo_thread = threading.Thread(target=yolo_worker, args=(coco_model, garbage_model), daemon=True)

    camera_thread.start()
    gps_thread.start()
    yolo_thread.start()

    print("\n🚀 AI SMART BUS STARTED")
    print("🎥 Camera: RUNNING")
    print("🤖 YOLO: RUNNING")
    print("📍 GPS: RUNNING")
    print("💓 Heartbeat: RUNNING")
    print("\n🟩 Only allowed classes shown with GREEN BOX + CONFIDENCE")
    print(f"🚨 Only garbage with confidence ≥ {SEND_CONFIDENCE_THRESHOLD*100:.0f}% will be sent to dashboard")
    print("⌨️ Press Q to quit")
    print("=" * 70)

    # Display loop
    display_delay = max(1, int(1000 / DISPLAY_FPS))
    display_count = 0
    display_fps = 0
    fps_timer = time.time()

    while not stop_event.is_set():
        frame, frame_id = get_latest_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        with detection_lock:
            detections = list(latest_detections)

        annotated = draw_detections(frame, detections)
        annotated = draw_status(annotated)

        # FPS
        display_count += 1
        current_time = time.time()
        if current_time - fps_timer >= 1.0:
            display_fps = display_count / (current_time - fps_timer)
            display_count = 0
            fps_timer = current_time

        fps_text = f"Display FPS: {display_fps:.1f}"
        cv2.putText(annotated, fps_text, (max(15, annotated.shape[1] - 220), 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

        count_text = f"Objects: {len(detections)}"
        cv2.putText(annotated, count_text, (max(15, annotated.shape[1] - 220), 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

        cv2.imshow("AI Smart Bus - Filtered Object Detection", annotated)

        key = cv2.waitKey(display_delay) & 0xFF
        if key == ord("q"):
            break

    print("\n🛑 Stopping AI Smart Bus...")
    stop_event.set()
    time.sleep(1)
    cv2.destroyAllWindows()
    print("\n" + "=" * 70)
    print("🚍 AI Smart Bus stopped.")
    print("=" * 70)


if __name__ == "__main__":
    main()