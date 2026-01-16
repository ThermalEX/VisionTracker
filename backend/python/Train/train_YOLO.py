from ultralytics import YOLO

def main():
    print("\n" + "="*70)
    print(" "*27 + "YOLO Training Start")
    print("="*70 + "\n")

    model = YOLO("yolo11n.pt")

    results = model.train(
        data="../DataCollection/data/dataset.yaml",
        epochs=50,
        imgsz=640,
        batch=16,
        workers=4,
        cache=False,
        project="runs/train_custom",
        name="exp",
        pretrained=True
    )

    # Final validation
    print("\n" + "="*70)
    print("Final Validation")
    print("="*70)
    model = YOLO("runs/train_custom/exp/weights/best.pt")
    model.val()

    best_model_path = "runs/train_custom/exp/weights/best.pt"
    print("\n" + "="*70)
    print(f"Training Complete! Best model: {best_model_path}")
    print("="*70 + "\n")

if __name__ == '__main__':
    main()
