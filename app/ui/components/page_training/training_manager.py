"""Training subprocess manager using QProcess."""

import os
import sys
import re
import json
import tempfile
from PyQt5.QtCore import QObject, QProcess, pyqtSignal


class TrainingManager(QObject):
    """Manages YOLO training as a subprocess via QProcess."""

    progress_updated = pyqtSignal(dict)   # {epoch, total, loss}
    map_updated = pyqtSignal(dict)        # {mAP50, mAP50_95}
    log_output = pyqtSignal(str)          # Raw stdout line
    training_finished = pyqtSignal(int)   # Exit code
    training_error = pyqtSignal(str)      # Error message

    # Regex patterns for parsing ultralytics output
    # Epoch line: "  5/100  4.14G  0.8456  0.9754  0.9123  142  640: 100%|..."
    _EPOCH_PATTERN = re.compile(
        r'\s*(\d+)/(\d+)\s+[\d.]+G?\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)'
    )
    # Validation mAP line: "all  2340  8500  0.856  0.612"
    _MAP_PATTERN = re.compile(
        r'\s*all\s+\d+\s+\d+\s+([\d.]+)\s+([\d.]+)'
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = None
        self._is_running = False
        self._config_path = None

    @property
    def is_running(self):
        return self._is_running

    def start_training(self, config_dict: dict):
        """Start training in a subprocess."""
        if self._is_running:
            self.training_error.emit("Training is already running.")
            return

        # Write config to temp JSON file
        self._config_path = os.path.join(tempfile.gettempdir(), "vt_train_config.json")
        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2)
        except Exception as e:
            self.training_error.emit(f"Failed to write config: {e}")
            return

        # Locate the runner script
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        ))))
        project_root = os.path.dirname(app_dir)
        runner_path = os.path.join(project_root, "backend", "python", "Train", "train_runner.py")

        if not os.path.exists(runner_path):
            self.training_error.emit(f"Runner script not found: {runner_path}")
            return

        # Create QProcess
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._onStdout)
        self._process.finished.connect(self._onFinished)
        self._process.errorOccurred.connect(self._onError)

        # Set working directory to Train folder
        train_dir = os.path.dirname(runner_path)
        self._process.setWorkingDirectory(train_dir)

        # Start process
        python_exe = sys.executable
        self._process.start(python_exe, [runner_path, self._config_path])
        self._is_running = True
        self.log_output.emit("Starting training subprocess...")

    def stop_training(self):
        """Terminate the training subprocess."""
        if self._process and self._process.state() == QProcess.Running:
            self.log_output.emit("Stopping training...")
            self._process.terminate()
            if not self._process.waitForFinished(5000):
                self._process.kill()
                self._process.waitForFinished(3000)
        self._is_running = False

    def _onStdout(self):
        """Parse stdout from the training subprocess."""
        if not self._process:
            return

        data = self._process.readAllStandardOutput()
        text = bytes(data).decode('utf-8', errors='replace')

        for line in text.split('\n'):
            # Progress bars use \r to overwrite; keep only the final segment
            if '\r' in line:
                segments = [s for s in line.split('\r') if s.strip()]
                if not segments:
                    continue
                line = segments[-1]

            stripped = line.strip()
            if not stripped:
                continue

            self.log_output.emit(line)

            # Try to parse epoch progress
            match = self._EPOCH_PATTERN.search(stripped)
            if match:
                epoch = int(match.group(1))
                total = int(match.group(2))
                box_loss = float(match.group(3))
                cls_loss = float(match.group(4))
                dfl_loss = float(match.group(5))
                total_loss = box_loss + cls_loss + dfl_loss
                self.progress_updated.emit({
                    "epoch": epoch,
                    "total": total,
                    "loss": total_loss,
                    "box_loss": box_loss,
                    "cls_loss": cls_loss,
                    "dfl_loss": dfl_loss,
                })
                continue

            # Try to parse mAP
            match = self._MAP_PATTERN.search(stripped)
            if match:
                self.map_updated.emit({
                    "mAP50": float(match.group(1)),
                    "mAP50_95": float(match.group(2)),
                })

    def _onFinished(self, exit_code, exit_status):
        """Handle subprocess completion."""
        self._is_running = False
        self.training_finished.emit(exit_code)

        # Clean up temp config
        if self._config_path and os.path.exists(self._config_path):
            try:
                os.remove(self._config_path)
            except OSError:
                pass

    def _onError(self, error):
        """Handle QProcess errors."""
        error_map = {
            QProcess.FailedToStart: "Failed to start training process",
            QProcess.Crashed: "Training process crashed",
            QProcess.Timedout: "Training process timed out",
            QProcess.WriteError: "Write error to training process",
            QProcess.ReadError: "Read error from training process",
        }
        msg = error_map.get(error, f"Unknown process error: {error}")
        self._is_running = False
        self.training_error.emit(msg)
