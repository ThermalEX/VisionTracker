"""TensorRT engine export runner.

Non-interactive counterpart of frontend/python/export_tensorrt.py, invoked as
a subprocess by the Training page's export widget.

Usage:
    python export_runner.py <model_path> <imgsz> <half>

Where:
    model_path: absolute path to .pt file
    imgsz:     integer input size (e.g. 200, 384, 640)
    half:      "1"/"0" - whether to export FP16 (recommended)

The final engine file is renamed to "<base>_<imgsz>.engine" and sits next to
the .pt file.
"""

import os
import sys
import time


def _log(msg: str):
    print(msg, flush=True)


def export_to_tensorrt(model_path: str, imgsz: int, half: bool) -> str:
    _log(f"Model:      {model_path}")
    _log(f"Input size: {imgsz}x{imgsz}")
    _log(f"Precision:  {'FP16' if half else 'FP32'}")

    import torch  # imported late so early errors have clean messages
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available - TensorRT export requires a CUDA-enabled GPU.")
    _log(f"CUDA OK:    {torch.cuda.get_device_name(0)}")

    from ultralytics import YOLO
    _log("Loading model...")
    model = YOLO(model_path)

    _log("Exporting TensorRT engine (this may take several minutes)...")
    t0 = time.time()
    model.export(
        format="engine",
        half=half,
        dynamic=False,
        simplify=True,
        workspace=4,
        imgsz=imgsz,
    )
    _log(f"Engine built in {time.time() - t0:.1f}s")

    default_engine = model_path.replace(".pt", ".engine")
    base = model_path.replace(".pt", "")
    custom_engine = f"{base}_{imgsz}.engine"

    if os.path.exists(default_engine):
        if os.path.exists(custom_engine):
            os.remove(custom_engine)
        os.rename(default_engine, custom_engine)
        final_path = custom_engine
    else:
        final_path = default_engine

    size_mb = os.path.getsize(final_path) / 1024 / 1024
    _log(f"SUCCESS - engine saved: {final_path}")
    _log(f"File size:  {size_mb:.2f} MB")
    return final_path


def main():
    if len(sys.argv) < 4:
        _log("Usage: export_runner.py <model_path> <imgsz> <half>")
        sys.exit(2)

    model_path = sys.argv[1]
    try:
        imgsz = int(sys.argv[2])
    except ValueError:
        _log(f"Invalid imgsz: {sys.argv[2]}")
        sys.exit(2)
    half = sys.argv[3] not in ("0", "false", "False", "")

    if not os.path.exists(model_path):
        _log(f"ERROR - model file not found: {model_path}")
        sys.exit(1)

    try:
        export_to_tensorrt(model_path, imgsz, half)
    except Exception as e:  # noqa: BLE001
        _log(f"ERROR - export failed: {e}")
        _log("Possible causes: TensorRT not installed, CUDA version mismatch, insufficient GPU memory.")
        sys.exit(1)


if __name__ == "__main__":
    main()
