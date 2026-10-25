"""Offscreen check for the optional subscription review dialog (kept from the retired widget-window tests)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication


def test_llm_dialog_does_not_send_until_requested(monkeypatch):
    from drift_gate.desktop.review_dialog import ReviewDialog
    from drift_gate.tests.test_subscription_review import scan
    _app = QApplication.instance() or QApplication([])
    calls = []
    monkeypatch.setattr("drift_gate.desktop.review_dialog.review_with_subscription", lambda *a, **k: calls.append(a))
    dialog = ReviewDialog(scan())
    try:
        assert dialog.worker is None
        assert calls == []
        assert "검사 자료" in dialog.preview.toPlainText()
    finally:
        dialog.close()
