
from ultralytics import YOLO
import os, yaml, shutil, time
from pathlib import Path

# ─────────────────────────────────────────────
# ⚙️  CONFIGURATION — Edit these as needed
# ─────────────────────────────────────────────

CONFIG = {
    # Model: yolo11n (fastest/CPU), yolo11s, yolo11m (recommended), yolo11l, yolo11x
    "model": "yolo11n.pt",

    # Path to your dataset YAML
    "data": "final_dataset/data.yaml",

    # Training hyperparameters
    "epochs": 100,
    "imgsz": 640,
    "batch": 16,           # Lower to 8 if you get CUDA out-of-memory
    "workers": 4,

    # Confidence thresholds
    "conf": 0.45,
    "iou": 0.45,

    # Device: "cpu", "0" (GPU 0), "0,1" (multi-GPU)
    "device": "cpu",         # Change to "cpu" if no GPU

    # Output
    "project": "runs/train",
    "name": "exam_surveillance_v1",
    "save_period": 10,     # Save checkpoint every N epochs

    # Augmentation (good for exam hall variation)
    "augment": True,
    "hsv_h": 0.015,
    "hsv_s": 0.7,
    "hsv_v": 0.4,
    "flipud": 0.0,         # No vertical flip (exam halls are upright)
    "fliplr": 0.5,
    "mosaic": 1.0,
    "mixup": 0.1,
}

# ─────────────────────────────────────────────
# 📋  STEP 1: Verify dataset structure
# ─────────────────────────────────────────────

def verify_dataset():
    print("\n" + "="*60)
    print("📋 STEP 1: Verifying dataset structure...")
    print("="*60)

    base = Path("final_dataset")
    required = [
        base / "train" / "images",
        base / "train" / "labels",
        base / "valid" / "images",
        base / "valid" / "labels",
        base / "test"  / "images",
        base / "test"  / "labels",
        base / "data.yaml",
    ]

    all_ok = True
    for path in required:
        exists = path.exists()
        status = "✅" if exists else "❌"
        print(f"  {status}  {path}")
        if not exists:
            all_ok = False

    if not all_ok:
        print("\n❌ Dataset structure is incomplete!")
        print("   Make sure final_dataset/data.yaml exists.")
        print("   See the data.yaml template in the README.")
        raise FileNotFoundError("Dataset structure incomplete.")

    # Count files
    splits = ["train", "valid", "test"]
    print("\n📊 Dataset file counts:")
    for split in splits:
        #imgs = list((base / split / "images").glob("."))
        imgs = list((base / split / "images").glob("*.*"))
        lbls = list((base / split / "labels").glob("*.txt"))
        print(f"  {split:6s} → {len(imgs):4d} images | {len(lbls):4d} labels")

    # Validate data.yaml
    with open(base / "data.yaml") as f:
        cfg = yaml.safe_load(f)
    print(f"\n📝 data.yaml:")
    print(f"  Classes ({cfg['nc']}): {cfg['names']}")
    print("\n✅ Dataset verification complete!\n")


# ─────────────────────────────────────────────
# 🚀  STEP 2: Train the model
# ─────────────────────────────────────────────

def train():
    print("="*60)
    print("🚀 STEP 2: Starting YOLOv11 Training...")
    print("="*60)
    print(f"  Model:   {CONFIG['model']}")
    print(f"  Epochs:  {CONFIG['epochs']}")
    print(f"  ImgSz:   {CONFIG['imgsz']}")
    print(f"  Batch:   {CONFIG['batch']}")
    print(f"  Device:  {CONFIG['device']}")
    print(f"  Output:  {CONFIG['project']}/{CONFIG['name']}")
    print()

    # Load model (downloads pretrained weights if needed)
    model = YOLO(CONFIG["model"])

    start = time.time()

    # Train
    results = model.train(
        data      = CONFIG["data"],
        epochs    = CONFIG["epochs"],
        imgsz     = CONFIG["imgsz"],
        batch     = CONFIG["batch"],
        workers   = CONFIG["workers"],
        device    = CONFIG["device"],
        conf      = CONFIG["conf"],
        iou       = CONFIG["iou"],
        project   = CONFIG["project"],
        name      = CONFIG["name"],
        save_period = CONFIG["save_period"],
        augment   = CONFIG["augment"],
        hsv_h     = CONFIG["hsv_h"],
        hsv_s     = CONFIG["hsv_s"],
        hsv_v     = CONFIG["hsv_v"],
        flipud    = CONFIG["flipud"],
        fliplr    = CONFIG["fliplr"],
        mosaic    = CONFIG["mosaic"],
        mixup     = CONFIG["mixup"],
        patience  = 20,        # Early stopping if no improvement for 20 epochs
        exist_ok  = True,
        pretrained = True,
        verbose   = True,
    )

    elapsed = time.time() - start
    print(f"\n⏱️  Training completed in {elapsed/60:.1f} minutes")
    return results


# ─────────────────────────────────────────────
# 📊  STEP 3: Validate the trained model
# ─────────────────────────────────────────────

def validate(weights_path):
    print("\n" + "="*60)
    print("📊 STEP 3: Validating trained model on validation set...")
    print("="*60)

    model = YOLO(weights_path)
    metrics = model.val(
        data    = CONFIG["data"],
        imgsz   = CONFIG["imgsz"],
        conf    = CONFIG["conf"],
        iou     = CONFIG["iou"],
        device  = CONFIG["device"],
    )

    print("\n📈 Validation Results:")
    print(f"  mAP@50:      {metrics.box.map50:.4f}")
    print(f"  mAP@50-95:   {metrics.box.map:.4f}")
    print(f"  Precision:   {metrics.box.mp:.4f}")
    print(f"  Recall:      {metrics.box.mr:.4f}")

    return metrics


# ─────────────────────────────────────────────
# 🧪  STEP 4: Test on test split
# ─────────────────────────────────────────────

def test_model(weights_path):
    print("\n" + "="*60)
    print("🧪 STEP 4: Running inference on test set...")
    print("="*60)

    model = YOLO(weights_path)
    model.val(
        data    = CONFIG["data"],
        split   = "test",
        imgsz   = CONFIG["imgsz"],
        conf    = CONFIG["conf"],
        device  = CONFIG["device"],
        save    = True,          # Saves annotated images
        project = "runs/test",
        name    = CONFIG["name"],
    )
    print(f"\n✅ Test results saved to: runs/test/{CONFIG['name']}/")


# ─────────────────────────────────────────────
# 📦  STEP 5: Export trained model
# ─────────────────────────────────────────────

def export_model(weights_path):
    print("\n" + "="*60)
    print("📦 STEP 5: Exporting model...")
    print("="*60)

    model = YOLO(weights_path)

    # Export to ONNX (cross-platform, works on CPU)
    print("  → Exporting to ONNX...")
    model.export(format="onnx", imgsz=CONFIG["imgsz"])

    # Export to OpenVINO (Intel CPU optimized — matches your models/openvino/ folder)
    print("  → Exporting to OpenVINO...")
    model.export(format="openvino", imgsz=CONFIG["imgsz"])

    print(f"\n✅ Models exported next to {weights_path}")
    print("   Copy .onnx and openvino/ folder to your models/ directory.")


# ─────────────────────────────────────────────
# 📋  STEP 6: Print summary
# ─────────────────────────────────────────────

def print_summary(weights_path):
    print("\n" + "="*60)
    print("🎉 TRAINING PIPELINE COMPLETE")
    print("="*60)
    print(f"  Best weights:  {weights_path}")
    print(f"  Training logs: {CONFIG['project']}/{CONFIG['name']}/")
    print(f"  Test results:  runs/test/{CONFIG['name']}/")
    print()
    print("  Next steps:")
    print("  1. Copy best.pt → models/yolo11n.pt  (or your chosen name)")
    print("  2. Copy .onnx  → models/yolo11n.onnx")
    print("  3. Copy openvino/ → models/openvino/")
    print("  4. Run:  python main.py")
    print("="*60 + "\n")


# ─────────────────────────────────────────────
# ▶️  MAIN
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# ▶️  MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    try:
        # Step 1: Verify
        verify_dataset()

        # Step 2: Train
        results = train()

        # Best weights path
        best_weights = Path(CONFIG["project"]) / CONFIG["name"] / "weights" / "best.pt"

        # Step 3: Validate
        validate(str(best_weights))

        # Step 4: Test
        test_model(str(best_weights))

        # Step 5: Export
        export_model(str(best_weights))

        # Step 6: Summary
        print_summary(str(best_weights))

    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("   Please check your dataset structure and data.yaml file.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        raise