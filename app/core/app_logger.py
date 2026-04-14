"""Small application-wide log signal helper."""

from __future__ import annotations

from PyQt5.QtCore import QObject, pyqtSignal


class _AppLogger(QObject):
    message = pyqtSignal(str, str)

    def log(self, message: str, level: str = "INFO"):
        self.message.emit(str(message), str(level).upper())

    def info(self, message: str):
        self.log(message, "INFO")

    def success(self, message: str):
        self.log(message, "SUCCESS")

    def warn(self, message: str):
        self.log(message, "WARN")

    def error(self, message: str):
        self.log(message, "ERROR")


AppLogger = _AppLogger()
