import cv2
from ultralytics import YOLO

model = YOLO("models/custom/best.pt")

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Camera NOT FOUND")
    exit()

print("Camera started. Press Q to quit.")

while True:
    ret, frame = cap.read()

    if not ret:
        print("Failed to read camera")
        break

    results = model.predict(frame, conf=0.25, verbose=False)

    annotated = results[0].plot()

    cv2.imshow("AI Smart Bus - Garbage Detection", annotated)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()