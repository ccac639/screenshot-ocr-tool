"""
区域截图模块
实现全屏半透明遮罩 + 鼠标拖拽选框。
"""

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QScreen
import sys


class RegionSelector(QWidget):
    """
    全屏半透明遮罩，支持鼠标拖拽选择区域。
    信号：
        region_selected(x, y, w, h)  -> 用户松开鼠标，返回选区
        cancelled()                    -> 用户按 Esc 或右键取消
    """
    region_selected = pyqtSignal(int, int, int, int)
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._start_pos = None
        self._end_pos = None
        self._active = False
        self._opacity = 0.35
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        # 全屏
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.setGeometry(geo)
        self.setStyleSheet("background-color: rgba(0,0,0,80);")

    def start(self):
        """启动选区（全屏显示遮罩）"""
        self._active = True
        self._start_pos = None
        self._end_pos = None
        self.showFullScreen()
        self.raise_()
        QApplication.setActiveWindow(self)

    def paintEvent(self, event):
        if not self._active or not self._start_pos:
            return
        painter = QPainter(self)
        # 选区矩形
        rect = self._get_rect()
        if rect:
            # 选区外半透明遮罩
            painter.fillRect(self.rect(), QColor(0, 0, 0, int(255 * self._opacity)))
            # 清除选区内遮罩（显示原画面）
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            # 选区边框
            pen = QPen(QColor(255, 64, 64), 2)
            painter.setPen(pen)
            painter.drawRect(rect)
            # 尺寸信息
            info = f"{rect.width()} x {rect.height()}"
            font = QFont("Arial", 12)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(rect.x(), rect.y() - 8, info)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.pos()
            self._end_pos = event.pos()
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.close()
            self.cancelled.emit()

    def mouseMoveEvent(self, event):
        if self._start_pos:
            self._end_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._start_pos:
            rect = self._get_rect()
            self.close()
            if rect and rect.width() > 5 and rect.height() > 5:
                self.region_selected.emit(rect.x(), rect.y(), rect.width(), rect.height())
            else:
                self.cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            self.cancelled.emit()

    def _get_rect(self):
        if not self._start_pos or not self._end_pos:
            return None
        return QRect(
            self._start_pos,
            self._end_pos,
        ).normalized()
