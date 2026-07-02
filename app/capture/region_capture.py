"""
区域截图模块 V2.1 稳定版
Snipaste 风格 + 工业级稳定性修复。

V2.1 修复：
- overlay 安全模式（截图前隐藏，避免黑屏）
- DPI 坐标转换（高缩放屏幕不错位）
- Ctrl 状态清理（防止屏幕放大）
- 黑屏检测 + 自动重试
"""

import time
from typing import Optional

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QRect, pyqtSignal, QPoint, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QCursor, QPixmap

from PIL import Image

from app.core.event_bus import bus, AppEvent
from app.core.state_machine import sm, CaptureState
from app.core.dpi import get_dpi_adapter
from app.capture.screen_grabber import grabber
from app.utils.key_cleaner import clear_all_modifier_keys, prepare_for_capture


class RegionSelector(QWidget):
    """
    全屏半透明遮罩，支持鼠标拖拽选择区域。
    Snipaste 风格：半透明暗色遮罩，选区高亮。

    V2.1 稳定修复：
    - 截图前隐藏 overlay（避免截到自己）
    - DPI 坐标转换
    - Ctrl 状态清理
    - 黑屏检测 + 重试
    """

    region_selected = pyqtSignal(int, int, int, int)
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._start_pos = None
        self._end_pos = None
        self._active = False
        self._full_screenshot = None
        self._magnifier_pos = None
        self._dpi = get_dpi_adapter()
        self._setup_ui()

    def _setup_ui(self):
        # 无边框 + 置顶 + 工具窗口（不在任务栏显示）
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.MaximizeUsingFullscreenGeometryHint
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # 全屏
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.setGeometry(geo)

    def start(self):
        """启动选区（先截全屏作为背景）"""
        # V2.1：先清理 Ctrl/Alt 状态（防止屏幕放大）
        clear_all_modifier_keys()

        # 隐藏自身再截图（避免截到自己）
        self.hide()
        QApplication.processEvents()
        time.sleep(0.08)

        # V2.1：截图前准备（清理修饰键 + 等待渲染）
        prepare_for_capture()

        # 截取全屏（带黑屏检测）
        max_retry = 3
        for attempt in range(max_retry):
            self._full_screenshot = grabber.grab(wait_ms=100)
            # 检测黑屏
            if self._is_black_or_white(self._full_screenshot):
                if attempt < max_retry - 1:
                    time.sleep(0.15)
                    continue
            break

        self._active = True
        self._start_pos = None
        self._end_pos = None

        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        QApplication.setActiveWindow(self)

    def _is_black_or_white(self, img: Image.Image) -> bool:
        """检测黑屏或白屏"""
        try:
            import numpy as np
            arr = np.array(img)
            if len(arr.shape) == 3:
                brightness = arr.mean()
            else:
                brightness = arr.mean()
            return brightness < 10.0 or brightness > 245.0
        except Exception:
            return False

    def paintEvent(self, event):
        if not self._active or not self._full_screenshot:
            return
        painter = QPainter(self)

        # 绘制全屏背景（稍微变暗）
        qimg = self._pil_to_qimg(self._full_screenshot)
        painter.drawImage(0, 0, qimg)

        # 半透明暗色遮罩
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        rect = self._get_rect()
        if rect and rect.width() > 5 and rect.height() > 5:
            # 清除选区内遮罩（显示原画面）
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

            # 选区边框（红色）
            pen = QPen(QColor(255, 64, 64), 2)
            painter.setPen(pen)
            painter.drawRect(rect)

            # 尺寸信息
            info = f"{rect.width()} x {rect.height()}"
            font = QFont("Consolas", 12)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255))
            tx = rect.x()
            ty = rect.y() - 10 if rect.y() > 20 else rect.y() + rect.height() + 18
            painter.drawText(tx, ty, info)

            # 绘制8个控制点
            self._draw_handles(painter, rect)

        # 放大镜
        if self._magnifier_pos and self._full_screenshot:
            self._draw_magnifier(painter, self._magnifier_pos)

    def _draw_handles(self, painter, rect):
        """绘制选区四个角和边中点"""
        s = 6
        pen = QPen(QColor(255, 255, 255), 2)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 64, 64))
        points = [
            (rect.x(), rect.y()),
            (rect.x() + rect.width(), rect.y()),
            (rect.x(), rect.y() + rect.height()),
            (rect.x() + rect.width(), rect.y() + rect.height()),
        ]
        for px, py in points:
            painter.drawRect(px - s // 2, py - s // 2, s, s)

    def _draw_magnifier(self, painter, pos):
        """绘制放大镜（跟随鼠标）"""
        mx, my = pos.x(), pos.y()
        radius = 60
        zoom = 2

        # 从全屏截图取区域
        left = max(0, mx - radius // zoom)
        top = max(0, my - radius // zoom)
        right = min(self._full_screenshot.width, mx + radius // zoom)
        bottom = min(self._full_screenshot.height, my + radius // zoom)

        if right > left and bottom > top:
            region = self._full_screenshot.crop((left, top, right, bottom))
            region = region.resize((radius * 2, radius * 2), Image.LANCZOS)

            qimg = self._pil_to_qimg(region)
            painter.drawImage(mx + 20, my + 20, qimg)

            # 十字线
            pen = QPen(QColor(255, 0, 0, 150), 1)
            painter.setPen(pen)
            painter.drawLine(mx + 20 + radius, my + 20, mx + 20 + radius, my + 20 + radius * 2)
            painter.drawLine(mx + 20, my + 20 + radius, mx + 20 + radius * 2, my + 20 + radius)

    def _pil_to_qimg(self, img):
        from PyQt6.QtGui import QImage
        if img.mode != "RGB":
            img = img.convert("RGB")
        data = img.tobytes("raw", "RGB")
        return QImage(data, img.width, img.height, QImage.Format.Format_RGB888)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # V2.1：按下前清理修饰键状态
            clear_all_modifier_keys()
            self._start_pos = event.pos()
            self._end_pos = event.pos()
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.close()
            self.cancelled.emit()

    def mouseMoveEvent(self, event):
        if self._start_pos:
            self._end_pos = event.pos()
            self._magnifier_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._start_pos:
            rect = self._get_rect()
            # V2.1：关闭前清理修饰键状态
            clear_all_modifier_keys()
            self.close()
            if rect and rect.width() > 5 and rect.height() > 5:
                # V2.1：坐标转换（逻辑坐标 → 物理像素）
                x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
                px, py, pw, ph = self._dpi.to_physical(x, y, w, h)
                self.region_selected.emit(px, py, pw, ph)
            else:
                self.cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            clear_all_modifier_keys()
            self.close()
            self.cancelled.emit()

    def _get_rect(self):
        if not self._start_pos or not self._end_pos:
            return None
        return QRect(self._start_pos, self._end_pos).normalized()
