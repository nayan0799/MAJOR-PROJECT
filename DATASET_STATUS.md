# Dataset status

The included images are garbage/waste images. The dataset is configured for one class:

`0 = garbage`

The ZIP intentionally does **not** invent bounding-box annotations. Real YOLO `.txt` labels must be drawn around garbage in each image before training. Use LabelImg, CVAT, Roboflow, or another annotation tool.

Expected files:
- `datasets/road/images/train/<image>.*`
- `datasets/road/labels/train/<same-name>.txt`
- `datasets/road/images/val/<image>.*`
- `datasets/road/labels/val/<same-name>.txt`

Each YOLO line is:
`0 x_center y_center width height`
with coordinates normalized to 0–1.

After labels exist, run `python ai/train_custom.py`. It will create `models/custom/best.pt` from the trained weights.
