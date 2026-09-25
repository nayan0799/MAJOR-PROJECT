import os
import cv2
import time
from datetime import datetime
from ultralytics import YOLO


# ==========================================
# PHONE CAMERA
# ==========================================

PHONE_IP = os.getenv("SMARTBUS_PHONE_IP", "")
PHONE_CAMERA_URL = os.getenv("SMARTBUS_CAMERA_URL") or (f"http://{PHONE_IP}:8080/video" if PHONE_IP else "")

# IMPORTANT:
# Change the IP above to your phone's IP.


# ==========================================
# YOLO MODEL
# ==========================================

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model = YOLO(os.path.join(ROOT, "models", "yolo11n.pt"))


# ==========================================
# CAMERA
# ==========================================

if not PHONE_CAMERA_URL:
    raise SystemExit("Set SMARTBUS_PHONE_IP or SMARTBUS_CAMERA_URL first.")
cap = cv2.VideoCapture(PHONE_CAMERA_URL)


if not cap.isOpened():

    print("❌ Could not connect to phone camera")

    print(
        "Check the phone IP and make sure "
        "the camera server is running."
    )

    exit()


print("✅ Mobile camera connected")
print("🤖 YOLO person detection started")
print("Press Q to stop")


# ==========================================
# EVIDENCE FOLDER
# ==========================================

import os

os.makedirs("evidence", exist_ok=True)


# ==========================================
# DETECTION COOLDOWN
# ==========================================

last_capture = 0

COOLDOWN = 5


# ==========================================
# MAIN LOOP
# ==========================================

while True:

    success, frame = cap.read()

    if not success:

        print("❌ Failed to read phone camera")

        break


    # ======================================
    # YOLO DETECTION
    # ======================================

    results = model(
        frame,
        verbose=False
    )


    person_detected = False

    best_confidence = 0


    # ======================================
    # PROCESS DETECTIONS
    # ======================================

    for result in results:

        if result.boxes is None:
            continue


        for box in result.boxes:

            class_id = int(
                box.cls[0]
            )

            confidence = float(
                box.conf[0]
            )


            class_name = model.names[
                class_id
            ]


            # PERSON
            if (
                class_name == "person"
                and confidence >= 0.50
            ):

                person_detected = True

                best_confidence = max(
                    best_confidence,
                    confidence
                )


    # ======================================
    # DRAW YOLO BOXES
    # ======================================

    annotated_frame = results[0].plot()


    # ======================================
    # PERSON DETECTED
    # ======================================

    if person_detected:

        cv2.putText(
            annotated_frame,

            f"PERSON DETECTED "
            f"{best_confidence * 100:.1f}%",

            (20, 40),

            cv2.FONT_HERSHEY_SIMPLEX,

            1,

            (0, 255, 0),

            2
        )


        # ==================================
        # AUTOMATIC PHOTO
        # ==================================

        current_time = time.time()


        if (
            current_time - last_capture
            > COOLDOWN
        ):

            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )


            filename = (
                f"evidence/"
                f"person_{timestamp}.jpg"
            )


            cv2.imwrite(
                filename,
                frame
            )


            print()
            print("🚨 PERSON DETECTED")
            print(
                f"Confidence: "
                f"{best_confidence * 100:.1f}%"
            )
            print(
                f"📸 Photo saved: "
                f"{filename}"
            )


            last_capture = current_time


    else:

        cv2.putText(
            annotated_frame,

            "Scanning...",

            (20, 40),

            cv2.FONT_HERSHEY_SIMPLEX,

            1,

            (255, 255, 255),

            2
        )


    # ======================================
    # SHOW VIDEO
    # ======================================

    cv2.imshow(
        "AI Smart Bus - Mobile Camera",
        annotated_frame
    )


    # ======================================
    # PRESS Q TO EXIT
    # ======================================

    key = cv2.waitKey(1) & 0xFF


    if key == ord("q"):

        break


# ==========================================
# CLEANUP
# ==========================================

cap.release()

cv2.destroyAllWindows()

print("🛑 Detection stopped")