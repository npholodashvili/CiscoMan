"""Crash guards must install without aborting the process."""

import os
from pathlib import Path


def test_install_crash_guards(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ciscoman_gui.crash_guard import install_crash_guards

    app = QApplication.instance() or QApplication([])
    fault = install_crash_guards(tmp_path, app)
    assert Path(fault).is_file() or Path(fault).parent.is_dir()
    raise_ran = {"n": 0}

    def boom():
        raise_ran["n"] += 1
        raise RuntimeError("guard-test")

    try:
        boom()
    except RuntimeError:
        pass
    assert raise_ran["n"] == 1
