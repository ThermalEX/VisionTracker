"""
Vision Tracker - Setup Script

Install all dependencies:
    pip install -e .

For CUDA support (PyTorch with GPU):
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu130
    pip install -e .
"""

from setuptools import setup, find_packages

setup(
    name="vision-tracker",
    version="1.0.0",
    description="Real-time Object Detection and Tracking System",
    author="Your Name",
    python_requires=">=3.10",
    packages=find_packages(),
    install_requires=[
        # UI Framework (siui is bundled in app/siui)
        "PyQt5>=5.15.10",
        "typing-extensions>=4.12.0",
        "python-dateutil>=2.9.0",

        # Deep Learning
        "ultralytics>=8.3.0",
        "torch>=2.0.0",
        "torchvision>=0.15.0",

        # Computer Vision
        "opencv-python>=4.8.0",
        "numpy>=1.24.0",

        # Screen Capture
        "mss>=9.0.0",
        "pyautogui>=0.9.54",
        "pygetwindow>=0.0.9",

        # Input Control
        "keyboard>=0.13.5",
        "pywin32>=306; sys_platform == 'win32'",

        # Utilities
        "pillow>=10.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "vision-tracker=app.main:main",
        ],
    },
)
