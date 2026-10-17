"""Keep the process alive when a slot or thread raises.

Windows 0xc0000409 (fast-fail) was seen when Qt aborted after an exception in a
worker callback that touched widgets. These hooks log, surface a dialog, and
enable faulthandler to a file in the log directory.
"""

from __future__ import annotations

import faulthandler
import logging
import sys
import threading
import traceback
from pathlib import Path

logger = logging.getLogger(__name__)

_fault_fh = None
_app_ref = None
_unhandled: list = []
_strict_tests = False


def install_crash_guards(log_dir: Path, app=None) -> Path:
    """Install sys/threading/Qt hooks and faulthandler. Returns fault log path."""
    global _fault_fh, _app_ref
    _app_ref = app
    log_dir.mkdir(parents=True, exist_ok=True)
    fault_path = log_dir / "fault.log"
    try:
        _fault_fh = open(fault_path, "a", encoding="utf-8")
        faulthandler.enable(file=_fault_fh, all_threads=True)
    except OSError as exc:
        logger.warning("faulthandler not enabled: %s", exc)

    sys.excepthook = _sys_hook
    if hasattr(threading, "excepthook"):
        threading.excepthook = _thread_hook

    try:
        from PySide6.QtCore import qInstallMessageHandler, QtMsgType

        def _qt_handler(mode, _ctx, message):
            level = {
                QtMsgType.QtFatalMsg: logging.CRITICAL,
                QtMsgType.QtCriticalMsg: logging.ERROR,
                QtMsgType.QtWarningMsg: logging.WARNING,
            }.get(mode, logging.INFO)
            logger.log(level, "Qt: %s", message)
            if mode == QtMsgType.QtFatalMsg:
                logger.critical("Qt fatal — see %s", fault_path)

        qInstallMessageHandler(_qt_handler)
    except Exception as exc:
        logger.debug("qInstallMessageHandler failed: %s", exc)

    logger.info("Crash guards installed; fault log %s", fault_path)
    return fault_path


def set_strict_test_mode(enabled: bool) -> None:
    """When True, unhandled slot exceptions are recorded for pytest to fail."""
    global _strict_tests
    _strict_tests = bool(enabled)
    _unhandled.clear()


def take_unhandled() -> list:
    items = list(_unhandled)
    _unhandled.clear()
    return items


def _format(exc_type, exc, tb) -> str:
    return "".join(traceback.format_exception(exc_type, exc, tb))


def _sys_hook(exc_type, exc, tb):
    text = _format(exc_type, exc, tb)
    logger.critical("Unhandled exception:\n%s", text)
    _unhandled.append((exc_type, exc, text))
    if _strict_tests:
        return
    _show_dialog(exc_type, exc, text)


def _thread_hook(args):
    text = _format(args.exc_type, args.exc_value, args.exc_traceback)
    logger.critical("Unhandled thread exception in %s:\n%s", args.thread, text)
    # Do not show a dialog from a random thread — Qt widgets are not thread-safe.


def _show_dialog(exc_type, exc, text: str) -> None:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = _app_ref or QApplication.instance()
        if app is None:
            return
        QMessageBox.critical(
            None,
            "CiscoMan error",
            f"{exc_type.__name__}: {exc}\n\nThe app is still running. "
            f"Details were written to the log folder.",
        )
    except Exception:
        logger.debug("Could not show crash dialog")
