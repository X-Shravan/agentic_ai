Model binaries are intentionally ignored by git to keep pull requests text-reviewable.

Copy the two files from branch/version1 or your local model export into this folder:
- models/yolo11n.pt      -> primary custom trained exam surveillance YOLO model
- models/yolov8n.pt      -> YOLOv8 nano baseline/fallback model

Optional backward-compatible names supported by the backend:
- models/best_exam_model.pt
- models/yolov8n_base.pt

Optional local embedding index:
- models/face_embeddings.pkl
