import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk


class InstallerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Vision Tracker Installer")
        self.root.geometry("820x620")
        self.root.minsize(760, 850)

        self.project_root = Path(__file__).resolve().parent
        self.requirements_path = self.project_root / "requirements.txt"
        self.main_py_path = self.project_root / "app" / "main.py"
        self.app_dir = self.project_root / "app"

        self.log_queue: "queue.Queue[str]" = queue.Queue()
        self.install_thread = None

        self.install_tensorrt = tk.BooleanVar(value=False)
        self.install_gpu_torch = tk.BooleanVar(value=True)
        self.installing = False
        self.detected_cuda_version = None
        self.detected_torch_cuda_tag = None
        self.cuda_status_var = tk.StringVar(value="CUDA not detected yet")

        self._build_ui()
        self._log(f"Project root: {self.project_root}")
        self._log(f"Source entry point: {self.main_py_path}")
        self._detect_cuda(update_log=True)
        self._set_status("Ready")
        self.root.after(100, self._poll_log_queue)

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.configure("Warning.TLabel", foreground="#C62828")
        except tk.TclError:
            pass

        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(
            outer,
            text="Vision Tracker Interactive Installer",
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(anchor=tk.W)

        subtitle = ttk.Label(
            outer,
            text=(
                "Install Python dependencies for this project. "
                "The real source entry point is app/main.py."
            ),
            wraplength=760,
        )
        subtitle.pack(anchor=tk.W, pady=(6, 14))

        warning_frame = ttk.LabelFrame(outer, text="Important", padding=12)
        warning_frame.pack(fill=tk.X, pady=(0, 14))

        ttk.Label(
            warning_frame,
            text="No CUDA: the program cannot run correctly.",
            style="Warning.TLabel",
            wraplength=760,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        ttk.Label(
            warning_frame,
            text="No TensorRT: .engine models cannot be used.",
            style="Warning.TLabel",
            wraplength=760,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(6, 0))

        info_frame = ttk.LabelFrame(outer, text="Entry Point", padding=12)
        info_frame.pack(fill=tk.X)

        info_text = (
            "Recommended run command:\n"
            "  python app/main.py\n\n"
            "If you want to run the script directly, enter the app folder and run main.py."
        )
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor=tk.W)

        option_frame = ttk.LabelFrame(outer, text="Install Options", padding=12)
        option_frame.pack(fill=tk.X, pady=(14, 0))

        cuda_row = ttk.Frame(option_frame)
        cuda_row.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(cuda_row, textvariable=self.cuda_status_var).pack(side=tk.LEFT)

        self.detect_cuda_button = ttk.Button(
            cuda_row,
            text="Detect CUDA",
            command=self.detect_cuda_clicked,
        )
        self.detect_cuda_button.pack(side=tk.RIGHT)

        ttk.Checkbutton(
            option_frame,
            text="Auto-install CUDA build of torch/torchvision when a supported CUDA version is detected",
            variable=self.install_gpu_torch,
        ).pack(anchor=tk.W, pady=(0, 8))

        ttk.Checkbutton(
            option_frame,
            text="Also try to install TensorRT (only needed for .engine models on supported NVIDIA environments)",
            variable=self.install_tensorrt,
        ).pack(anchor=tk.W)

        action_frame = ttk.Frame(outer)
        action_frame.pack(fill=tk.X, pady=(14, 0))

        self.install_button = ttk.Button(
            action_frame,
            text="Install Requirements",
            command=self.start_install,
        )
        self.install_button.pack(side=tk.LEFT)

        self.run_button = ttk.Button(
            action_frame,
            text="Run app/main.py",
            command=self.run_app,
        )
        self.run_button.pack(side=tk.LEFT, padx=(10, 0))

        self.open_main_button = ttk.Button(
            action_frame,
            text="Open app/main.py",
            command=self.open_main_py,
        )
        self.open_main_button.pack(side=tk.LEFT, padx=(10, 0))

        self.open_app_dir_button = ttk.Button(
            action_frame,
            text="Open app Folder",
            command=self.open_app_dir,
        )
        self.open_app_dir_button.pack(side=tk.LEFT, padx=(10, 0))

        progress_frame = ttk.Frame(outer)
        progress_frame.pack(fill=tk.X, pady=(14, 0))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.status_var).pack(anchor=tk.W)

        self.progress = ttk.Progressbar(progress_frame, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(8, 0))

        log_frame = ttk.LabelFrame(outer, text="Install Log", padding=12)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(14, 0))

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            state=tk.DISABLED,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        finish_frame = ttk.LabelFrame(outer, text="After Install", padding=12)
        finish_frame.pack(fill=tk.X, pady=(14, 0))

        ttk.Label(
            finish_frame,
            text=(
                "After installation you can use the buttons above to open app/main.py, "
                "open the app folder, or run app/main.py directly."
            ),
            wraplength=760,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

    def _set_status(self, text: str):
        self.status_var.set(f"Status: {text}")

    def _log(self, message: str):
        self.log_queue.put(message)

    def _append_log(self, message: str):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _poll_log_queue(self):
        while not self.log_queue.empty():
            self._append_log(self.log_queue.get())
        self.root.after(100, self._poll_log_queue)

    def start_install(self):
        if self.installing:
            return
        if not self.requirements_path.exists():
            messagebox.showerror("Missing File", f"Cannot find {self.requirements_path}")
            return

        self.installing = True
        self.install_button.configure(state=tk.DISABLED)
        self.progress.start(10)
        self._set_status("Installing")
        self._log("Starting installation...")

        self.install_thread = threading.Thread(target=self._install_worker, daemon=True)
        self.install_thread.start()

    def _install_worker(self):
        success = True
        try:
            if self.install_gpu_torch.get():
                cuda_version, cuda_tag = self._detect_cuda(update_log=True)
                if cuda_tag:
                    self._run_command(
                        [
                            sys.executable,
                            "-m",
                            "pip",
                            "install",
                            "--upgrade",
                            "--force-reinstall",
                            "torch",
                            "torchvision",
                            "--index-url",
                            f"https://download.pytorch.org/whl/{cuda_tag}",
                        ],
                        f"Installing CUDA torch build for CUDA {cuda_version} ({cuda_tag})",
                    )

                    self._verify_torch_cuda(expected_tag=cuda_tag)

                    filtered_requirements = self._create_filtered_requirements(exclude_torch=True)
                    try:
                        self._run_command(
                            [
                                sys.executable,
                                "-m",
                                "pip",
                                "install",
                                "-r",
                                filtered_requirements,
                            ],
                            "Installing requirements.txt without torch/torchvision",
                        )
                    finally:
                        try:
                            os.remove(filtered_requirements)
                        except OSError:
                            pass
                else:
                    self._run_command(
                        [
                            sys.executable,
                            "-m",
                            "pip",
                            "install",
                            "-r",
                            str(self.requirements_path),
                        ],
                        "Installing requirements.txt",
                    )
                    self._log("CUDA GPU torch install was skipped because no supported CUDA version was detected.")
            else:
                self._run_command(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "-r",
                        str(self.requirements_path),
                    ],
                    "Installing requirements.txt",
                )

            if self.install_tensorrt.get():
                self._run_command(
                    [sys.executable, "-m", "pip", "install", "tensorrt"],
                    "Installing optional TensorRT package",
                )

            self._log("")
            self._log("Installation completed.")
            self._log(f"Source entry point: {self.main_py_path}")
            self._log(f"Recommended command: {sys.executable} {self.main_py_path}")
        except Exception as exc:
            success = False
            self._log("")
            self._log(f"Installation failed: {exc}")

        self.root.after(0, lambda: self._finish_install(success))

    def _run_command(self, command: list[str], title: str):
        self._log("")
        self._log(f"[Step] {title}")
        self._log("[Command] " + " ".join(command))

        process = subprocess.Popen(
            command,
            cwd=self.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        assert process.stdout is not None
        for line in process.stdout:
            self._log(line.rstrip())

        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"{title} failed with exit code {return_code}")

    def detect_cuda_clicked(self):
        self._detect_cuda(update_log=True)

    def _detect_cuda(self, update_log: bool = False):
        version = self._read_cuda_version()
        tag = self._cuda_version_to_torch_tag(version)

        self.detected_cuda_version = version
        self.detected_torch_cuda_tag = tag

        if version and tag:
            message = f"Detected CUDA {version} -> torch wheel tag {tag}"
        elif version:
            message = f"Detected CUDA {version}, but no auto torch mapping is configured"
        else:
            message = "CUDA not detected. Installer will fall back to requirements.txt"

        self.cuda_status_var.set(message)
        if update_log:
            self._log(message)
        return version, tag

    def _read_cuda_version(self):
        candidates = [
            ["nvidia-smi"],
            ["nvcc", "--version"],
        ]

        for command in candidates:
            try:
                output = subprocess.check_output(
                    command,
                    cwd=self.project_root,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            except Exception:
                continue

            version = self._extract_cuda_version(output)
            if version:
                return version

        return None

    @staticmethod
    def _extract_cuda_version(text: str):
        patterns = [
            r"CUDA Version:\s*([0-9]+\.[0-9]+)",
            r"release\s+([0-9]+\.[0-9]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _cuda_version_to_torch_tag(version: str | None):
        if not version:
            return None
        if version.startswith("13."):
            return "cu130"
        if version.startswith("12.8"):
            return "cu128"
        if version.startswith("12.6"):
            return "cu126"
        if version.startswith("12.4"):
            return "cu124"
        return None

    def _create_filtered_requirements(self, exclude_torch: bool):
        with open(self.requirements_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        filtered = []
        for line in lines:
            stripped = line.strip()
            if exclude_torch and (
                stripped.startswith("torch>=")
                or stripped.startswith("torchvision>=")
                or stripped.startswith("torchaudio>=")
            ):
                continue
            filtered.append(line)

        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".txt",
            delete=False,
        )
        try:
            handle.writelines(filtered)
            return handle.name
        finally:
            handle.close()

    def _verify_torch_cuda(self, expected_tag: str):
        self._log("")
        self._log("[Step] Verifying torch CUDA runtime")

        command = [
            sys.executable,
            "-c",
            (
                "import torch; "
                "print('torch_version=' + str(torch.__version__)); "
                "print('torch_cuda=' + str(torch.version.cuda)); "
                "print('cuda_available=' + str(torch.cuda.is_available()))"
            ),
        ]

        process = subprocess.Popen(
            command,
            cwd=self.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        assert process.stdout is not None
        output_lines = []
        for line in process.stdout:
            line = line.rstrip()
            output_lines.append(line)
            self._log(line)

        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError("Torch CUDA verification failed")

        joined = "\n".join(output_lines)
        if "cuda_available=True" not in joined:
            raise RuntimeError(
                f"CUDA torch installation did not activate successfully for {expected_tag}. "
                "The environment still reports torch.cuda.is_available() == False."
            )

    def _finish_install(self, success: bool):
        self.installing = False
        self.install_button.configure(state=tk.NORMAL)
        self.progress.stop()

        if success:
            self._set_status("Completed")
            messagebox.showinfo(
                "Install Complete",
                "Dependencies installed.\n\n"
                "The source entry point is app/main.py.\n"
                "You can now use the 'Open app/main.py' button or run app/main.py directly.",
            )
        else:
            self._set_status("Failed")
            messagebox.showerror(
                "Install Failed",
                "Installation did not finish successfully.\n"
                "Check the log for details.",
            )

    def open_main_py(self):
        if not self.main_py_path.exists():
            messagebox.showerror("Missing File", f"Cannot find {self.main_py_path}")
            return
        self._open_path(self.main_py_path)

    def open_app_dir(self):
        if not self.app_dir.exists():
            messagebox.showerror("Missing Folder", f"Cannot find {self.app_dir}")
            return
        self._open_path(self.app_dir)

    def run_app(self):
        if not self.main_py_path.exists():
            messagebox.showerror("Missing File", f"Cannot find {self.main_py_path}")
            return
        try:
            subprocess.Popen(
                [sys.executable, str(self.main_py_path)],
                cwd=self.project_root,
            )
            self._log(f"Started: {sys.executable} {self.main_py_path}")
        except Exception as exc:
            messagebox.showerror("Run Failed", str(exc))

    def _open_path(self, path: Path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
            self._log(f"Opened: {path}")
        except Exception as exc:
            messagebox.showerror("Open Failed", str(exc))


def main():
    root = tk.Tk()
    ttk.Style().theme_use("vista" if sys.platform.startswith("win") else "clam")
    InstallerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
