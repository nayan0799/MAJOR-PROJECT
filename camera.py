# ============================================================
# AI SMART BUS
# FULL-FRAME OBJECT DETECTION (ALL CLASSES)
# GARBAGE INCIDENT UPLOAD ONLY
#
# Features:
# - Detect all objects in the camera frame
# - Green bounding box with class name + confidence
# - Only garbage detections (≥30% confidence) are sent to dashboard
# - Background YOLO inference
# - Background GPS
# - Background heartbeat
# - Background incident upload
# - Original evidence image
# - 19.5:9 phone camera supported
# ============================================================

import os

# ============================================================
# LOW LATENCY FFMPEG
# ============================================================

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "fflags;nobuffer|flags;low_delay"
)

import time
import threading
from datetime import datetime

import cv2
import requests
from ultralytics import YOLO


# ============================================================
# PATH
# ============================================================

ROOT = os.path.dirname(
    os.path.abspath(__file__)
)


# ============================================================
# PHONE CAMERA
# ============================================================

PHONE_IP ="100.79.251.184"
PHONE_PORT =8080

CAMERA_URL = (
    f"http://{PHONE_IP}:{PHONE_PORT}/video"
)

# ============================================================
# FASTAPI BACKEND
# ============================================================

BACKEND_URL = "http://127.0.0.1:8000"


# ============================================================
# BUS
# ============================================================

BUS_ID = "BUS-001"


# ============================================================
# MODEL
# ============================================================

MODEL_PATH = os.path.join(
    ROOT,
    "runs",
    "detect",
    "garbage50-2",
    "weights",
    "best.pt"
)


# ============================================================
# EVIDENCE DIRECTORY
# ============================================================

PHOTO_DIR = os.path.join(
    ROOT,
    "backend",
    "detections"
)

os.makedirs(
    PHOTO_DIR,
    exist_ok=True
)


# ============================================================
# DETECTION SETTINGS
# ============================================================

# Class we want to send as incident
TARGET_CLASS = "garbage"

# Display confidence threshold (all objects above this are shown)
CONFIDENCE_THRESHOLD = 0.15

# Minimum confidence for sending garbage incident to dashboard
SEND_CONFIDENCE_THRESHOLD = 0.15

# YOLO image size.
#
# 640 = better detection
# 320 = faster but weaker
#
YOLO_SIZE = 640

# Detect approximately every 50 ms.
# Actual speed depends on CPU/model.
YOLO_INTERVAL = 0.05

# Prevent duplicate incidents.
COOLDOWN_SECONDS = 10

# GPS update.
GPS_UPDATE_SECONDS = 3

# Heartbeat.
HEARTBEAT_SECONDS = 10

# Display target.
DISPLAY_FPS = 60


# ============================================================
# SHARED DATA
# ============================================================

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


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()


# ============================================================
# LOAD MODEL
# ============================================================

def load_model():

    print()
    print("=" * 70)
    print("🔎 LOADING OBJECT DETECTION MODEL")
    print("=" * 70)

    print(
        "Model:",
        MODEL_PATH
    )

    if not os.path.exists(MODEL_PATH):

        raise SystemExit(
            "\n❌ MODEL NOT FOUND\n\n"
            + MODEL_PATH
        )

    model = YOLO(
        MODEL_PATH
    )

    print()
    print("✅ MODEL LOADED")

    print(
        "Classes:",
        model.names
    )

    print(
        "🎯 Incident target:",
        TARGET_CLASS
    )

    print(
        "📐 YOLO image size:",
        YOLO_SIZE
    )

    print(
        "🎯 Display confidence:",
        CONFIDENCE_THRESHOLD
    )

    print(
        "🚨 Send confidence (dashboard):",
        SEND_CONFIDENCE_THRESHOLD
    )

    print("=" * 70)

    return model


# ============================================================
# GET CURRENT GPS
# ============================================================

def get_gps():

    global current_lat
    global current_lon

    try:

        response = session.get(
            f"{BACKEND_URL}/api/buses",
            timeout=2
        )

        if not response.ok:

            return

        data = response.json()

        if isinstance(data, dict):

            data = data.get(
                "buses",
                data.get(
                    "data",
                    []
                )
            )

        if not isinstance(data, list):

            return

        for bus in data:

            if str(
                bus.get(
                    "bus_id",
                    ""
                )
            ) != BUS_ID:

                continue

            new_lat = bus.get(
                "latitude"
            )

            new_lon = bus.get(
                "longitude"
            )

            if (
                new_lat is not None
                and
                new_lon is not None
            ):

                with gps_lock:

                    current_lat = float(
                        new_lat
                    )

                    current_lon = float(
                        new_lon
                    )

                return

    except Exception:

        pass


# ============================================================
# GET GPS COPY
# ============================================================

def get_current_gps():

    with gps_lock:

        return (
            current_lat,
            current_lon
        )


# ============================================================
# HEARTBEAT
# ============================================================

def send_heartbeat():

    lat, lon = get_current_gps()

    try:

        payload = {
            "bus_id": BUS_ID,
            "latitude": lat,
            "longitude": lon
        }

        response = session.post(

            f"{BACKEND_URL}/api/buses/heartbeat",

            json=payload,

            timeout=3
        )

        if response.ok:

            print(
                f"💓 Heartbeat | "
                f"{BUS_ID} | "
                f"GPS={lat},{lon}"
            )

    except Exception as e:

        print(
            "⚠️ Heartbeat failed:",
            e
        )


# ============================================================
# GPS THREAD
# ============================================================

def gps_worker():

    print(
        "📍 GPS worker started"
    )

    last_gps = 0
    last_heartbeat = 0

    while not stop_event.is_set():

        now = time.time()

        # ----------------------------------------------------
        # GPS
        # ----------------------------------------------------

        if (
            now - last_gps
            >= GPS_UPDATE_SECONDS
        ):

            get_gps()

            last_gps = now

        # ----------------------------------------------------
        # HEARTBEAT
        # ----------------------------------------------------

        if (
            now - last_heartbeat
            >= HEARTBEAT_SECONDS
        ):

            send_heartbeat()

            last_heartbeat = now

        time.sleep(0.05)

    print(
        "📍 GPS worker stopped"
    )


# ============================================================
# CAMERA CONNECT
# ============================================================

def connect_camera():

    print()
    print(
        "📱 Connecting to mobile camera..."
    )

    cap = cv2.VideoCapture(
        CAMERA_URL,
        cv2.CAP_FFMPEG
    )

    cap.set(
        cv2.CAP_PROP_BUFFERSIZE,
        1
    )

    if cap.isOpened():

        print(
            "✅ Mobile camera connected"
        )

        return cap

    cap.release()

    return None


# ============================================================
# CAMERA THREAD
# ============================================================

def camera_worker():

    global latest_frame
    global latest_frame_id

    cap = None

    print(
        "🎥 Camera worker started"
    )

    while not stop_event.is_set():

        # ----------------------------------------------------
        # CONNECT
        # ----------------------------------------------------

        if cap is None:

            cap = connect_camera()

            if cap is None:

                print(
                    "⚠️ Camera connection failed."
                )

                time.sleep(2)

                continue

        # ----------------------------------------------------
        # READ
        # ----------------------------------------------------

        ok, frame = cap.read()

        if not ok:

            print(
                "⚠️ Camera frame unavailable."
            )

            cap.release()

            cap = None

            time.sleep(0.5)

            continue

        # ----------------------------------------------------
        # SAVE LATEST FRAME
        # ----------------------------------------------------

        with camera_lock:

            latest_frame = frame

            latest_frame_id += 1

        # No sleep here.
        #
        # Camera thread continuously reads
        # the newest available frame.

    if cap is not None:

        cap.release()

    print(
        "🎥 Camera worker stopped"
    )


# ============================================================
# GET LATEST FRAME
# ============================================================

def get_latest_frame():

    with camera_lock:

        if latest_frame is None:

            return None, -1

        return (
            latest_frame.copy(),
            latest_frame_id
        )


# ============================================================
# SEND INCIDENT
# ============================================================

def send_report(
    name,
    confidence,
    photo_path,
    gps_lat,
    gps_lon
):

    try:

        with open(
            photo_path,
            "rb"
        ) as image_file:

            data = {

                "type": name,

                "lat": gps_lat,

                "lon": gps_lon,

                "time":
                    datetime.now()
                    .astimezone()
                    .isoformat(),

                "confidence":
                    confidence,

                "status":
                    "Pending",

                "bus_id":
                    BUS_ID
            }

            response = session.post(

                f"{BACKEND_URL}/incidents",

                data=data,

                files={
                    "photo": (
                        os.path.basename(
                            photo_path
                        ),
                        image_file,
                        "image/jpeg"
                    )
                },

                timeout=10
            )

        if response.ok:

            print()
            print("=" * 60)
            print(
                "✅ INCIDENT SENT"
            )
            print(
                f"🚌 Bus        : {BUS_ID}"
            )
            print(
                f"🗑️ Detection  : {name}"
            )
            print(
                f"🎯 Confidence : "
                f"{confidence * 100:.2f}%"
            )
            print(
                f"📍 GPS        : "
                f"{gps_lat},{gps_lon}"
            )
            print("=" * 60)

        else:

            print(
                "❌ Backend error:",
                response.status_code
            )

            print(
                response.text
            )

    except Exception as e:

        print(
            "❌ Incident upload failed:",
            e
        )


# ============================================================
# SAVE + SEND INCIDENT
# ============================================================

def create_incident(
    frame,
    name,
    confidence
):

    global last_report_time

    now = time.time()

    # --------------------------------------------------------
    # COOLDOWN
    # --------------------------------------------------------

    if (
        now - last_report_time
        < COOLDOWN_SECONDS
    ):

        return

    # --------------------------------------------------------
    # CHECK SEND CONFIDENCE (safety)
    # --------------------------------------------------------
    if confidence < SEND_CONFIDENCE_THRESHOLD:
        return

    last_report_time = now

    # --------------------------------------------------------
    # GPS COPY
    # --------------------------------------------------------

    gps_lat, gps_lon = get_current_gps()

    # --------------------------------------------------------
    # FILE NAME
    # --------------------------------------------------------

    filename = (

        "garbage_"

        + datetime.now()
        .strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        + ".jpg"
    )

    photo_path = os.path.join(
        PHOTO_DIR,
        filename
    )

    # --------------------------------------------------------
    # SAVE ORIGINAL FRAME
    # --------------------------------------------------------

    saved = cv2.imwrite(
        photo_path,
        frame
    )

    if not saved:

        print(
            "❌ Failed to save evidence"
        )

        return

    print()
    print(
        "📸 Evidence saved:",
        filename
    )

    # --------------------------------------------------------
    # SEND
    # --------------------------------------------------------

    send_report(

        name,

        confidence,

        photo_path,

        gps_lat,

        gps_lon
    )


# ============================================================
# YOLO THREAD
# ============================================================

def yolo_worker(model):

    global latest_detections
    global latest_detection_frame_id

    print()
    print(
        "🤖 YOLO worker started"
    )

    print(
        "🔍 Full-frame detection enabled"
    )

    print(
        "📐 Image size:",
        YOLO_SIZE
    )

    print(
        "🎯 Display confidence:",
        CONFIDENCE_THRESHOLD
    )

    print(
        "🚨 Send confidence (garbage only):",
        SEND_CONFIDENCE_THRESHOLD
    )

    last_processed_frame = -1

    last_inference_time = 0

    while not stop_event.is_set():

        now = time.time()

        # ----------------------------------------------------
        # INFERENCE TIMER
        # ----------------------------------------------------

        if (
            now - last_inference_time
            < YOLO_INTERVAL
        ):

            time.sleep(0.001)

            continue

        # ----------------------------------------------------
        # GET FRAME
        # ----------------------------------------------------

        frame, frame_id = get_latest_frame()

        if frame is None:

            time.sleep(0.005)

            continue

        # ----------------------------------------------------
        # DON'T PROCESS SAME FRAME
        # ----------------------------------------------------

        if frame_id == last_processed_frame:

            time.sleep(0.001)

            continue

        last_processed_frame = frame_id

        last_inference_time = now

        # ----------------------------------------------------
        # YOLO
        #
        # IMPORTANT:
        # NO CROPPING
        # NO ROI
        # FULL CAMERA FRAME
        # ALL CLASSES ARE DETECTED
        # ----------------------------------------------------

        try:

            results = model.predict(

                source=frame,

                conf=CONFIDENCE_THRESHOLD,

                imgsz=YOLO_SIZE,

                verbose=False,

                device="cpu"

            )

        except Exception as e:

            print(
                "❌ YOLO error:",
                e
            )

            time.sleep(0.1)

            continue

        # ----------------------------------------------------
        # DETECTIONS (all classes)
        # ----------------------------------------------------

        detections = []

        if results:

            result = results[0]

            if result.boxes is not None:

                for box in result.boxes:

                    confidence = float(
                        box.conf[0]
                    )

                    class_id = int(
                        box.cls[0]
                    )

                    name = str(
                        model.names[
                            class_id
                        ]
                    ).lower()

                    # Only keep if above display threshold
                    if confidence < CONFIDENCE_THRESHOLD:
                        continue

                    coords = (
                        box.xyxy[0]
                        .cpu()
                        .numpy()
                        .astype(int)
                    )

                    x1, y1, x2, y2 = coords

                    detections.append({
                        "name": name,
                        "confidence": confidence,
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2
                    })

        # ----------------------------------------------------
        # SAVE DETECTIONS (for display)
        # ----------------------------------------------------

        with detection_lock:

            latest_detections = detections

            latest_detection_frame_id = frame_id

        # ----------------------------------------------------
        # INCIDENT (only garbage)
        # ----------------------------------------------------

        # Filter garbage detections
        garbage_detections = [
            d for d in detections
            if d["name"] == TARGET_CLASS
        ]

        if garbage_detections:

            best_garbage = max(
                garbage_detections,
                key=lambda x: x["confidence"]
            )

            print(
                f"🗑️ GARBAGE DETECTED | "
                f"{best_garbage['confidence'] * 100:.1f}%"
            )

            # Send only if confidence >= SEND_CONFIDENCE_THRESHOLD
            if best_garbage["confidence"] >= SEND_CONFIDENCE_THRESHOLD:
                # Use the exact frame that YOLO processed.
                create_incident(
                    frame,
                    best_garbage["name"],
                    best_garbage["confidence"]
                )
            else:
                print(
                    f"   (below send threshold "
                    f"{SEND_CONFIDENCE_THRESHOLD*100:.0f}% – not uploaded)"
                )

    print(
        "🤖 YOLO worker stopped"
    )


# ============================================================
# DRAW DETECTIONS
# ============================================================

def draw_detections(
    frame,
    detections
):

    output = frame.copy()

    for detection in detections:

        x1 = detection["x1"]
        y1 = detection["y1"]
        x2 = detection["x2"]
        y2 = detection["y2"]

        confidence = detection["confidence"]
        name = detection["name"]

        # ----------------------------------------------------
        # GREEN BOX
        # ----------------------------------------------------

        cv2.rectangle(
            output,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            3
        )

        # ----------------------------------------------------
        # LABEL (class name + confidence)
        # ----------------------------------------------------

        label = (
            f"{name.upper()} "
            f"{confidence * 100:.1f}%"
        )

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.75
        thickness = 2

        text_size = cv2.getTextSize(
            label,
            font,
            font_scale,
            thickness
        )[0]

        text_width = text_size[0]
        text_height = text_size[1]

        # ----------------------------------------------------
        # KEEP LABEL INSIDE SCREEN
        # ----------------------------------------------------

        label_x = max(
            0,
            min(
                x1,
                output.shape[1] - text_width - 10
            )
        )

        label_y = max(
            text_height + 12,
            y1
        )

        # ----------------------------------------------------
        # GREEN LABEL BACKGROUND
        # ----------------------------------------------------

        cv2.rectangle(
            output,
            (label_x, label_y - text_height - 12),
            (label_x + text_width + 10, label_y),
            (0, 255, 0),
            -1
        )

        # ----------------------------------------------------
        # BLACK TEXT
        # ----------------------------------------------------

        cv2.putText(
            output,
            label,
            (label_x + 5, label_y - 5),
            font,
            font_scale,
            (0, 0, 0),
            thickness,
            cv2.LINE_AA
        )

    return output


# ============================================================
# DRAW INFORMATION
# ============================================================

def draw_status(frame):

    output = frame.copy()

    gps_lat, gps_lon = get_current_gps()

    height, width = output.shape[:2]

    # --------------------------------------------------------
    # TOP STATUS
    # --------------------------------------------------------

    status = (
        f"AI SMART BUS | "
        f"{BUS_ID}"
    )

    cv2.putText(
        output,
        status,
        (15, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    # --------------------------------------------------------
    # GPS
    # --------------------------------------------------------

    if gps_lat is not None and gps_lon is not None:
        gps_text = f"GPS: {gps_lat:.6f},{gps_lon:.6f}"
    else:
        gps_text = "GPS: Waiting..."

    cv2.putText(
        output,
        gps_text,
        (15, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    # --------------------------------------------------------
    # FULL FRAME
    # --------------------------------------------------------

    cv2.putText(
        output,
        "FULL FRAME DETECTION",
        (15, 90),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    # --------------------------------------------------------
    # QUIT
    # --------------------------------------------------------

    cv2.putText(
        output,
        "Press Q to quit",
        (15, height - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    return output


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("              🚍 AI SMART BUS")
    print("       🔍 FULL FRAME OBJECT DETECTION")
    print("       🗑️ GARBAGE INCIDENT UPLOAD ONLY")
    print("=" * 70)

    print(f"🚌 Bus ID       : {BUS_ID}")
    print(f"📱 Camera       : {CAMERA_URL}")
    print(f"🌐 Backend      : {BACKEND_URL}")
    print(f"🤖 Model        : {MODEL_PATH}")
    print(f"🎯 Display Conf : {CONFIDENCE_THRESHOLD * 100:.0f}%")
    print(f"🚨 Send Conf    : {SEND_CONFIDENCE_THRESHOLD * 100:.0f}%")
    print(f"📐 YOLO size    : {YOLO_SIZE}")
    print("🟩 Box          : GREEN")
    print("📊 Detection    : ALL CLASSES")
    print("📱 Aspect       : 19.5:9 supported")
    print("📸 Evidence     : ORIGINAL FRAME (garbage only)")
    print("🚫 ROI          : NONE")
    print("=" * 70)

    # ========================================================
    # LOAD MODEL
    # ========================================================

    model = load_model()

    # ========================================================
    # START THREADS
    # ========================================================

    camera_thread = threading.Thread(
        target=camera_worker,
        daemon=True
    )

    gps_thread = threading.Thread(
        target=gps_worker,
        daemon=True
    )

    yolo_thread = threading.Thread(
        target=yolo_worker,
        args=(model,),
        daemon=True
    )

    camera_thread.start()
    gps_thread.start()
    yolo_thread.start()

    print()
    print("🚀 AI SMART BUS STARTED")
    print("🎥 Camera: RUNNING")
    print("🤖 YOLO: RUNNING")
    print("📍 GPS: RUNNING")
    print("💓 Heartbeat: RUNNING")
    print()
    print("🟩 All objects shown with GREEN BOX + CONFIDENCE")
    print(f"🚨 Only garbage with confidence ≥ {SEND_CONFIDENCE_THRESHOLD*100:.0f}% will be sent to dashboard")
    print("⌨️ Press Q to quit")
    print("=" * 70)

    # ========================================================
    # DISPLAY LOOP
    # ========================================================

    display_delay = max(1, int(1000 / DISPLAY_FPS))

    display_count = 0
    display_fps = 0
    fps_timer = time.time()

    while not stop_event.is_set():

        # ----------------------------------------------------
        # FRAME
        # ----------------------------------------------------

        frame, frame_id = get_latest_frame()

        if frame is None:
            time.sleep(0.01)
            continue

        # ----------------------------------------------------
        # DETECTIONS
        # ----------------------------------------------------

        with detection_lock:
            detections = list(latest_detections)

        # ----------------------------------------------------
        # DRAW
        # ----------------------------------------------------

        annotated = draw_detections(frame, detections)
        annotated = draw_status(annotated)

        # ----------------------------------------------------
        # FPS
        # ----------------------------------------------------

        display_count += 1
        current_time = time.time()

        if current_time - fps_timer >= 1.0:
            display_fps = display_count / (current_time - fps_timer)
            display_count = 0
            fps_timer = current_time

        fps_text = f"Display FPS: {display_fps:.1f}"

        cv2.putText(
            annotated,
            fps_text,
            (max(15, annotated.shape[1] - 220), 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

        # ----------------------------------------------------
        # DETECTION COUNT
        # ----------------------------------------------------

        count_text = f"Objects: {len(detections)}"

        cv2.putText(
            annotated,
            count_text,
            (max(15, annotated.shape[1] - 220), 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

        # ----------------------------------------------------
        # DISPLAY
        # ----------------------------------------------------

        cv2.imshow(
            "AI Smart Bus - Full Frame Object Detection",
            annotated
        )

        # ----------------------------------------------------
        # Q
        # ----------------------------------------------------

        key = cv2.waitKey(display_delay) & 0xFF

        if key == ord("q"):
            break

    # ========================================================
    # STOP
    # ========================================================

    print()
    print("🛑 Stopping AI Smart Bus...")
    stop_event.set()
    time.sleep(1)
    cv2.destroyAllWindows()
    print()
    print("=" * 70)
    print("🚍 AI Smart Bus stopped.")
    print("=" * 70)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()