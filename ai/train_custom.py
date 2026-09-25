from pathlib import Path
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "datasets" / "road" / "data.yaml"
RUNS = ROOT / "runs" / "detect"
OUT = ROOT / "models" / "custom" / "best.pt"

# IMPORTANT: YOLO training requires real .txt annotations. Do not train until labels exist.
label_files = list((ROOT / "datasets/road/labels/train").glob("*.txt")) + list((ROOT / "datasets/road/labels/val").glob("*.txt"))
if not label_files:
    raise SystemExit("No YOLO label .txt files found. Annotate the images first, then run this script again.")

model = YOLO(str(ROOT / "models/yolo11n.pt"))
model.train(data=str(DATA), epochs=50, imgsz=640, batch=8, project=str(RUNS), name="road_phase1")
best = RUNS / "road_phase1" / "weights" / "best.pt"
if best.exists():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(best.read_bytes())
    print(f"Saved trained model to: {OUT}")
