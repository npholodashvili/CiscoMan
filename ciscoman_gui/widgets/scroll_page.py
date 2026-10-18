"""Scroll container that keeps a page at its natural size.

Wrapping a page in ``ScrollPage`` means that when the window is shorter (or
narrower) than the page needs, a scrollbar appears instead of Qt squeezing
labels, fields and buttons until they are clipped. When there is spare room
the page still stretches to fill the window, so tables and logs keep growing.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QFrame, QScrollArea, QWidget


class ScrollPage(QScrollArea):
    """A frameless, resizable scroll area around a single page widget."""

    def __init__(self, page: QWidget, parent: QWidget | None = None):
        super().__init__(parent)
        self.page = page
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setWidget(page)
        self._pending = False
        page.installEventFilter(self)
        self._sync_minimum()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.page and event.type() in (QEvent.LayoutRequest, QEvent.Show):
            self._schedule_sync()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._schedule_sync()

    def _schedule_sync(self) -> None:
        if not self._pending:
            self._pending = True
            QTimer.singleShot(0, self._sync_minimum)

    def _sync_minimum(self) -> None:
        """Never let the page get shorter than its layout's natural height."""
        self._pending = False
        layout = self.page.layout()
        if layout is None:
            return
        hint = layout.sizeHint()
        width = max(self.viewport().width(), layout.minimumSize().width())
        height = hint.height()
        if layout.hasHeightForWidth():
            height = max(height, layout.heightForWidth(width))
        if self.page.minimumHeight() != height:
            self.page.setMinimumHeight(height)
