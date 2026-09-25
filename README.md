# AI Smart Bus — Phase 1 Fixed Prototype

Camera → YOLO → vehicle/road-hazard detection → GPS → FastAPI → SQLite → web dashboard.

## 1. Recommended Python
Use **Python 3.11**. Do not copy a Windows virtual environment from another computer; create a fresh `.venv`.

## 2. Install
Open PowerShell in this folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Start dashboard
```powershell
python -m uvicorn backend.main:app --reload
```
Open `http://127.0.0.1:8000`.

## 4. Test laptop webcam
In another terminal:
```powershell
.\.venv\Scripts\Activate.ps1
python -m ai.detector
```
Press `Q` to stop.

## 5. Phone camera
Set the phone IP before running:
```powershell
$env:SMARTBUS_PHONE_IP="192.168.1.25"
python yolo_phone_camera.py
```
Replace the example IP with the IP shown by your phone-camera app. Phone and laptop must be on the same Wi-Fi.

## 6. Custom garbage model
The package contains `models/custom/best.pt` as a **baseline copy of YOLO11n only**, so the expected file path exists and the application can start. It is **not a trained garbage detector**. The application checks the model class names and will not pretend that this baseline detects garbage.

To create a real garbage detector, annotate the included images first. See `DATASET_STATUS.md`, then run:
```powershell
python ai/train_custom.py
```
The trained weights will replace `models/custom/best.pt`.

## 7. Important fixes in this version
- Removed the machine-specific `labelimg-env` from the ZIP.
- All model paths are based on the project root, so running from another directory does not break them.
- Added `web/index.html`, so `/` opens the dashboard.
- Unified phone camera configuration through environment variables.
- Fixed the old `models/best.pt` vs `models/custom/best.pt` mismatch.
- Fixed the AI detector so it does not load a duplicate baseline model as a fake custom road model.
- Added Windows launcher `.bat` files.
- Added a dataset-status guide instead of inventing labels.
