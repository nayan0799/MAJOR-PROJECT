import os
import time
from datetime import datetime

import cv2
import requests
from ultralytics import YOLO


# ============================================================
# AI SMART BUS - YOLO PHONE CAMERA
# Garbage Detection + GPS + Evidence + FastAPI
# ============================================================


# ------------------------------------------------------------
# 1. PROJECT PATH
# ------------------------------------------------------------

ROOT = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------
# 2. PHONE CAMERA SETTINGS
# ------------------------------------------------------------

# Your phone IP
PHONE_IP = os.getenv(
    "SMARTBUS_PHONE_IP",
    "192.168.29.195"
)

# IP Webcam / phone camera port
PHONE_PORT = int(
    os.getenv(
        "SMARTBUS_PHONE_PORT",
        "8080"
    )
)


# Phone video URL
CAMERA_URL = os.getenv(
    "SMARTBUS_CAMERA_URL",
    f"http://{PHONE_IP}:{PHONE_PORT}/video"
)


# Phone GPS URL
GPS_URL = os.getenv(
    "SMARTBUS_GPS_URL",
    f"http://{PHONE_IP}:{PHONE_PORT}/gps"
)


# ------------------------------------------------------------
# 3. BACKEND SETTINGS
# ------------------------------------------------------------

BACKEND_BASE_URL = os.getenv(
    "SMARTBUS_BACKEND_URL",
    "http://127.0.0.1:8000"
)

INCIDENT_URL = BACKEND_BASE_URL + "/incidents"


# ------------------------------------------------------------
# 4. YOLO MODEL SETTINGS
# ------------------------------------------------------------

# Your trained custom model
CUSTOM_MODEL = os.path.join(
    ROOT,
    "models",
    "custom",
    "best.pt"
)


# Optional normal YOLO model
NORMAL_MODEL = os.path.join(
    ROOT,
    "models",
    "yolo11n.pt"
)


# ------------------------------------------------------------
# 5. DETECTION SETTINGS
# ------------------------------------------------------------

# Your current dataset contains only:
#
# 0 = garbage
#
TARGET_CLASSES = {
    "garbage"
}


# Minimum confidence
CONFIDENCE_THRESHOLD = 0.30


# Wait this many seconds before reporting
# another garbage detection
COOLDOWN_SECONDS = 10


# ------------------------------------------------------------
# 6. GPS SETTINGS
# ------------------------------------------------------------

# GPS will NOT be requested every video frame.
#
# Instead, GPS is requested once every 3 seconds.
GPS_UPDATE_SECONDS = 3


# ------------------------------------------------------------
# 7. EVIDENCE PHOTO SETTINGS
# ------------------------------------------------------------

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
# PRINT CONFIGURATION
# ============================================================

print()
print("=" * 60)
print("        AI SMART BUS - YOLO CAMERA")
print("=" * 60)

print(f"Phone IP       : {PHONE_IP}")
print(f"Phone Port     : {PHONE_PORT}")
print(f"Camera URL     : {CAMERA_URL}")
print(f"GPS URL        : {GPS_URL}")
print(f"Backend URL    : {INCIDENT_URL}")
print(f"Custom Model   : {CUSTOM_MODEL}")
print(f"Confidence     : {CONFIDENCE_THRESHOLD}")
print(f"Cooldown       : {COOLDOWN_SECONDS}s")
print("=" * 60)
print()


# ============================================================
# CHECK CAMERA URL
# ============================================================

if not CAMERA_URL:
    raise SystemExit(
        "ERROR: Camera URL is empty."
    )


# ============================================================
# MODEL LOADER
# ============================================================

def choose_model():

    # --------------------------------------------------------
    # First try custom trained model
    # --------------------------------------------------------

    if os.path.exists(CUSTOM_MODEL):

        print("Loading custom model...")
        print(CUSTOM_MODEL)

        try:

            model = YOLO(CUSTOM_MODEL)

            # Get class names
            names = {
                str(v).lower()
                for v in model.names.values()
            }

            print()
            print("Custom model classes:")
            print(names)
            print()

            # Check whether garbage exists
            if "garbage" in names:

                print("SUCCESS: Garbage class found.")
                print("Using trained custom model.")
                print()

                return model

            else:

                print(
                    "WARNING: 'garbage' class was not found "
                    "in best.pt."
                )

                print(
                    "Expected class:"
                )

                print("0 = garbage")

                print()

        except Exception as e:

            print(
                "ERROR loading custom model:"
            )

            print(e)

            print()


    # --------------------------------------------------------
    # Fallback model
    # --------------------------------------------------------

    if os.path.exists(NORMAL_MODEL):

        print(
            "WARNING: Using normal YOLO model."
        )

        print(
            "Normal YOLO will NOT detect your custom "
            "garbage class."
        )

        print()

        return YOLO(NORMAL_MODEL)


    # --------------------------------------------------------
    # No model
    # --------------------------------------------------------

    raise SystemExit(
        "\nERROR: No YOLO model found.\n\n"
        "Expected custom model:\n"
        f"{CUSTOM_MODEL}\n"
    )


# ============================================================
# PHONE GPS
# ============================================================

def get_phone_gps():

    if not GPS_URL:

        return None, None

    try:

        response = requests.get(
            GPS_URL,
            timeout=2
        )

        response.raise_for_status()

        data = response.json()

        # Try different common GPS field names
        latitude = data.get(
            "latitude",
            data.get("lat")
        )

        longitude = data.get(
            "longitude",
            data.get(
                "lon",
                data.get("lng")
            )
        )

        if latitude is None or longitude is None:

            return None, None

        latitude = float(latitude)
        longitude = float(longitude)

        return latitude, longitude

    except Exception as e:

        # GPS failure should NOT stop AI detection
        return None, None


# ============================================================
# SEND INCIDENT TO FASTAPI
# ============================================================

def send_report(
    kind,
    confidence,
    photo_path,
    latitude,
    longitude
):

    try:

        print()
        print("-" * 50)
        print("Sending incident to backend...")
        print(f"Type       : {kind}")
        print(f"Confidence : {confidence:.2f}")
        print(f"Latitude   : {latitude}")
        print(f"Longitude  : {longitude}")
        print(f"Photo      : {photo_path}")
        print("-" * 50)

        # ----------------------------------------------------
        # Prepare form data
        #
        # IMPORTANT:
        # Backend expects lat/lon
        # NOT latitude/longitude
        # ----------------------------------------------------

        data = {

            "type": kind,

            "confidence": confidence,

            "lat": latitude if latitude is not None else 0.0,

            "lon": longitude if longitude is not None else 0.0,

            "time": datetime.now().isoformat(),

            "status": "open"
        }


        # ----------------------------------------------------
        # Open evidence image
        # ----------------------------------------------------

        with open(
            photo_path,
            "rb"
        ) as image_file:

            files = {

                "photo": (
                    os.path.basename(photo_path),

                    image_file,

                    "image/jpeg"
                )
            }


            # ------------------------------------------------
            # Send POST request
            # ------------------------------------------------

            response = requests.post(

                INCIDENT_URL,

                data=data,

                files=files,

                timeout=10
            )


        # ----------------------------------------------------
        # Check response
        # ----------------------------------------------------

        if response.ok:

            print()
            print("SUCCESS: Incident sent to backend.")
            print(
                f"Backend status: {response.status_code}"
            )

            return True

        else:

            print()
            print(
                "ERROR: Backend rejected incident."
            )

            print(
                f"Status code: {response.status_code}"
            )

            print(
                f"Response: {response.text}"
            )

            return False


    except requests.exceptions.ConnectionError:

        print()
        print(
            "ERROR: Could not connect to FastAPI backend."
        )

        print(
            f"Make sure backend is running at:"
        )

        print(
            BACKEND_BASE_URL
        )

        return False


    except Exception as e:

        print()
        print(
            "ERROR sending report:"
        )

        print(e)

        return False


# ============================================================
# SAVE EVIDENCE PHOTO
# ============================================================

def save_evidence(
    frame,
    detection_name
):

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    filename = (
        f"{detection_name}_"
        f"{timestamp}.jpg"
    )

    photo_path = os.path.join(
        PHOTO_DIR,
        filename
    )

    success = cv2.imwrite(
        photo_path,
        frame
    )

    if success:

        print()
        print(
            "Evidence photo saved:"
        )

        print(
            photo_path
        )

        return photo_path

    else:

        print(
            "ERROR: Could not save evidence photo."
        )

        return None


# ============================================================
# LOAD YOLO
# ============================================================

model = choose_model()


# ============================================================
# DISPLAY MODEL INFORMATION
# ============================================================

print()
print("=" * 60)
print("YOLO MODEL READY")
print("=" * 60)

print(
    "Classes:"
)

for class_id, class_name in model.names.items():

    print(
        f"  {class_id} -> {class_name}"
    )

print("=" * 60)
print()


# ============================================================
# CONNECT TO PHONE CAMERA
# ============================================================

print(
    "Connecting to phone camera..."
)

print(
    CAMERA_URL
)

cap = cv2.VideoCapture(
    CAMERA_URL
)


# Some IP camera streams work better with this
cap.set(
    cv2.CAP_PROP_BUFFERSIZE,
    1
)


if not cap.isOpened():

    raise SystemExit(

        "\nERROR: Could not connect to phone camera.\n\n"

        f"Camera URL:\n"
        f"{CAMERA_URL}\n\n"

        "Check:\n"
        "1. Phone and laptop are on the same Wi-Fi.\n"
        "2. IP Webcam is running.\n"
        "3. Phone IP is correct.\n"
        "4. Port is 8080.\n"
        "5. Open the camera URL in your browser.\n"
    )


print()
print("=" * 60)
print("PHONE CAMERA CONNECTED")
print("=" * 60)
print()
print("AI garbage detection is starting...")
print()
print("Press Q to stop.")
print()


# ============================================================
# DETECTION STATE
# ============================================================

# Last time each object was reported
last_report = {}


# Current GPS
current_latitude = None
current_longitude = None


# Last GPS update time
last_gps_update = 0


# ============================================================
# MAIN LOOP
# ============================================================

try:

    while True:

        # ----------------------------------------------------
        # Read phone camera frame
        # ----------------------------------------------------

        ret, frame = cap.read()


        if not ret:

            print(
                "WARNING: Failed to receive video frame."
            )

            time.sleep(0.1)

            continue


        # ----------------------------------------------------
        # Update GPS every few seconds
        # ----------------------------------------------------

        current_time = time.time()


        if (
            current_time - last_gps_update
            >= GPS_UPDATE_SECONDS
        ):

            gps_lat, gps_lon = get_phone_gps()


            if (
                gps_lat is not None
                and gps_lon is not None
            ):

                current_latitude = gps_lat
                current_longitude = gps_lon

                print(
                    f"GPS: "
                    f"{current_latitude:.6f}, "
                    f"{current_longitude:.6f}"
                )

            else:

                # GPS unavailable
                #
                # Detection continues anyway.

                current_latitude = None
                current_longitude = None


            last_gps_update = current_time


        # ----------------------------------------------------
        # YOLO detection
        # ----------------------------------------------------

        results = model(
            frame,
            conf=CONFIDENCE_THRESHOLD,
            verbose=False
        )


        result = results[0]


        # ----------------------------------------------------
        # Draw detections
        # ----------------------------------------------------

        annotated = result.plot()


        # ----------------------------------------------------
        # Process detected objects
        # ----------------------------------------------------

        if result.boxes is not None:

            for box in result.boxes:

                # --------------------------------------------
                # Class ID
                # --------------------------------------------

                class_id = int(
                    box.cls[0]
                )


                # --------------------------------------------
                # Confidence
                # --------------------------------------------

                confidence = float(
                    box.conf[0]
                )


                # --------------------------------------------
                # Class name
                # --------------------------------------------

                class_name = str(
                    model.names[class_id]
                ).lower()


                # --------------------------------------------
                # Only garbage
                # --------------------------------------------

                if class_name not in TARGET_CLASSES:

                    continue


                # --------------------------------------------
                # Check confidence
                # --------------------------------------------

                if confidence < CONFIDENCE_THRESHOLD:

                    continue


                # --------------------------------------------
                # Cooldown
                # --------------------------------------------

                now = time.time()

                last_time = last_report.get(
                    class_name,
                    0
                )


                if (
                    now - last_time
                    < COOLDOWN_SECONDS
                ):

                    continue


                # --------------------------------------------
                # Garbage detected
                # --------------------------------------------

                print()
                print("🚨 GARBAGE DETECTED")
                print(
                    f"Confidence: "
                    f"{confidence:.2%}"
                )


                # --------------------------------------------
                # Save evidence photo
                # --------------------------------------------

                photo_path = save_evidence(
                    frame,
                    class_name
                )


                if photo_path is None:

                    continue


                # --------------------------------------------
                # Send to FastAPI
                # --------------------------------------------

                sent = send_report(

                    kind=class_name,

                    confidence=confidence,

                    photo_path=photo_path,

                    latitude=current_latitude,

                    longitude=current_longitude
                )


                # --------------------------------------------
                # Update cooldown only after processing
                # --------------------------------------------

                last_report[class_name] = now


                if sent:

                    print(
                        "Incident successfully recorded."
                    )

                else:

                    print(
                        "Incident photo saved locally, "
                        "but backend upload failed."
                    )


        # ----------------------------------------------------
        # Add system information to screen
        # ----------------------------------------------------

        cv2.putText(

            annotated,

            "AI SMART BUS",

            (20, 35),

            cv2.FONT_HERSHEY_SIMPLEX,

            1,

            (0, 255, 0),

            2
        )


        cv2.putText(

            annotated,

            "Garbage Detection",

            (20, 70),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.7,

            (255, 255, 255),

            2
        )


        # ----------------------------------------------------
        # GPS display
        # ----------------------------------------------------

        if (
            current_latitude is not None
            and current_longitude is not None
        ):

            gps_text = (
                f"GPS: "
                f"{current_latitude:.5f}, "
                f"{current_longitude:.5f}"
            )

        else:

            gps_text = "GPS: unavailable"


        cv2.putText(

            annotated,

            gps_text,

            (20, 105),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.55,

            (255, 255, 255),

            2
        )


        # ----------------------------------------------------
        # Show camera
        # ----------------------------------------------------

        cv2.imshow(

            "AI Smart Bus - Garbage Detection",

            annotated
        )


        # ----------------------------------------------------
        # Press Q to quit
        # ----------------------------------------------------

        key = cv2.waitKey(1) & 0xFF


        if key == ord("q"):

            print()
            print(
                "Stopping AI Smart Bus camera..."
            )

            break


# ============================================================
# CLEANUP
# ============================================================

except KeyboardInterrupt:

    print()
    print(
        "Camera stopped by user."
    )


finally:

    cap.release()

    cv2.destroyAllWindows()

    print()
    print("=" * 60)
    print("AI SMART BUS CAMERA STOPPED")
    print("=" * 60)