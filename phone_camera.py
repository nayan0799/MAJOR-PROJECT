import cv2

# Phone IP Webcam address
PHONE_CAMERA = "http://192.168.29.63:8080/video"

cap = cv2.VideoCapture(PHONE_CAMERA)

if not cap.isOpened():
    print("❌ Could not connect to phone camera")
    print("Check:")
    print("1. Phone and laptop are on the same Wi-Fi")
    print("2. IP Webcam server is running")
    print("3. IP address is correct")
    exit()

print("✅ Phone camera connected!")

while True:
    ret, frame = cap.read()

    if not ret:
        print("❌ Failed to receive video")
        break

    cv2.imshow("AI Smart Bus - Phone Camera", frame)

    # Press Q to quit
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()