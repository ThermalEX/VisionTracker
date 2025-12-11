from ultralytics import YOLO
import os

def main():
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

    #训练完成后，自动加载 best 12.10.pt 模型并进行一次完整验证（可选但推荐）
    print("✅ Beginning final verification with best 12.10.pt...")
    model = YOLO("runs/train_custom/exp/weights/best 12.10.pt")
    model.val()

    best_model_path = "runs/train_custom/exp/weights/best 12.10.pt"
    print(f"✅ Training complete! Best model saved：{best_model_path}")

if __name__ == '__main__':
    main()
