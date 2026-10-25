"""Background repository scan for the desktop host.

Moved out of the retired widget window (``desktop/app.py``) so the shipped
web-based window keeps only the code it uses.
"""

from PySide6.QtCore import QObject, Signal, Slot

from drift_gate.desktop.service import PolicyMissingError, scan_repository


class ScanWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    policy_missing = Signal(str)  # repository root; emitted in addition to ``failed``

    def __init__(self, path: str, base: str):
        super().__init__()
        self.path = path
        self.base = base

    @Slot()
    def run(self):
        try:
            self.finished.emit(scan_repository(self.path, self.base))
        except PolicyMissingError as exc:
            self.policy_missing.emit(str(exc.repository))
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))
