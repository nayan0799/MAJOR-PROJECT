import cv2

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("❌ Laptop camera could not be opened")
    exit()

print("✅ Laptop camera detected")

while True:
    ret, frame = camera.read()

    if not ret:
        print("❌ Could not read camera frame")
        break

    cv2.imshow("Laptop Camera Test", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

camera.release()
cv2.destroyAllWindows()