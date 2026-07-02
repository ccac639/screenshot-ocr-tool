"""
主窗口 UI
PyQt6 实现，深色极简风格，包含截图预览、OCR结果、设置面板。
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QMessageBox,
    QStatusBar, QFileDialog,
    QGroupBox, QSpinBox, QDoubleSpinBox, QLabel as QL,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QImage, QFont
from PIL import Image, ImageGrab
import os, time


class LongCaptureThread(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, x, y, w, h, delay=0.8, wheel_delta=-10, max_frames=200, mode="wheel"):
        super().__init__()
        self.x, self.y, self.w, self.h = x, y, w, h
        self.delay = delay
        self.wheel_delta = wheel_delta
        self.max_frames = max_frames
        self.mode = mode

    def run(self):
        try:
            from app.utils.image import stitch_vertical, images_are_similar
            import pyautogui, time

            # 激活目标窗口
            cx = self.x + self.w // 2
            cy = self.y + self.h // 2
            pyautogui.click(x=cx, y=cy)
            time.sleep(0.3)

            frames = []
            prev_img = None
            dup_streak = 0

            # 第一帧
            img = ImageGrab.grab(bbox=(self.x, self.y, self.x+self.w, self.y+self.h))
            frames.append(img)
            prev_img = img

            for i in range(1, self.max_frames):
                self.progress.emit(i, self.max_frames)
                if self.mode == "pagedown":
                    pyautogui.press("pagedown")
                else:
                    pyautogui.scroll(self.wheel_delta)
                time.sleep(self.delay)
                img = ImageGrab.grab(bbox=(self.x, self.y, self.x+self.w, self.y+self.h))
                if prev_img and images_are_similar(prev_img, img, threshold=0.965):
                    dup_streak += 1
                    if dup_streak >= 5:
                        break
                    continue
                else:
                    dup_streak = 0
                frames.append(img)
                prev_img = img

            result = stitch_vertical(frames, overlap_remove=True)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._current_img = None
        self._ocr_engine = None
        self._capture_mode = None
        self._long_thread = None
        self._setup_ui()
        self._init_ocr()

    def _setup_ui(self):
        self.setWindowTitle("截图 + OCR 工具")
        self.setMinimumSize(700, 500)
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; color: #cccccc; }
            QPushButton { background-color: #2d2d2d; color: #cccccc;
                         border: 1px solid #444; padding: 6px 12px; border-radius: 4px; }
            QPushButton:hover { background-color: #3d3d3d; }
            QPushButton:pressed { background-color: #1a1a1a; }
            QTextEdit { background-color: #252526; color: #d4d4d4; border: 1px solid #444; }
            QLabel { color: #cccccc; }
            QGroupBox { color: #cccccc; border: 1px solid #444; margin-top: 8px; }
            QSpinBox, QDoubleSpinBox { background-color: #252526; color: #cccccc; border: 1px solid #444; }
        """)
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # 按钮栏
        bar = QHBoxLayout()
        self.btn_capture = QPushButton("📷 截图")
        self.btn_long = QPushButton("📜 长截图")
        self.btn_ocr = QPushButton("🔍 OCR")
        self.btn_copy = QPushButton("📋 复制文本")
        self.btn_save = QPushButton("💾 保存图片")
        for b in [self.btn_capture, self.btn_long, self.btn_ocr,
                   self.btn_copy, self.btn_save]:
            bar.addWidget(b)
        bar.addStretch()
        root.addLayout(bar)

        # 设置面板
        settings = QGroupBox("⚙️ 长截图设置")
        s_layout = QHBoxLayout(settings)
        s_layout.addWidget(QL("滚动延迟(s):"))
        self.spin_delay = QDoubleSpinBox()
        self.spin_delay.setRange(0.3, 3.0)
        self.spin_delay.setValue(0.8)
        self.spin_delay.setSingleStep(0.1)
        s_layout.addWidget(self.spin_delay)
        s_layout.addWidget(QL("滚轮量:"))
        self.spin_wheel = QSpinBox()
        self.spin_wheel.setRange(-20, -1)
        self.spin_wheel.setValue(-10)
        s_layout.addWidget(self.spin_wheel)
        s_layout.addWidget(QL("最大帧:"))
        self.spin_max = QSpinBox()
        self.spin_max.setRange(20, 500)
        self.spin_max.setValue(200)
        s_layout.addWidget(self.spin_max)
        s_layout.addStretch()
        root.addWidget(settings)

        # 预览 + OCR 结果
        body = QHBoxLayout()
        self.preview = QLabel("预览区域")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(300, 300)
        self.preview.setStyleSheet("border: 1px solid #444;")
        body.addWidget(self.preview, 1)
        self.ocr_text = QTextEdit()
        self.ocr_text.setPlaceholderText("OCR 结果将显示在这里...")
        self.ocr_text.setMaximumHeight(400)
        body.addWidget(self.ocr_text, 1)
        root.addLayout(body)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status("就绪")

        # 信号
        self.btn_capture.clicked.connect(self.on_btn_capture)
        self.btn_long.clicked.connect(self.on_btn_long_capture)
        self.btn_ocr.clicked.connect(self.on_btn_ocr)
        self.btn_copy.clicked.connect(self.on_btn_copy)
        self.btn_save.clicked.connect(self.on_btn_save)

    def _init_ocr(self):
        try:
            from app.ocr.engine import OCREngine
            self._ocr_engine = OCREngine()
        except Exception as e:
            self._update_status(f"OCR 初始化失败: {e}")

    def _update_status(self, msg: str):
        self.status_bar.showMessage(msg)

    def on_btn_capture(self):
        self._start_region("normal")

    def on_btn_long_capture(self):
        self._start_region("long")

    def _start_region(self, mode: str):
        self._capture_mode = mode
        self.hide()
        QTimer.singleShot(300, self._do_show_selector)

    def _do_show_selector(self):
        from app.capture.region import RegionSelector
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self.on_region_selected)
        self._selector.cancelled.connect(self.on_capture_cancelled)
        self._selector.start()

    def on_region_selected(self, x, y, w, h):
        mode = self._capture_mode
        self._capture_mode = None
        if mode == "long":
            self._update_status("⏳ 长截图中...（请勿操作鼠标键盘）")
            self.ocr_text.setPlainText("正在长截图，自动滚动中...")
            delay = self.spin_delay.value()
            wheel = self.spin_wheel.value()
            maxf = self.spin_max.value()
            thread = LongCaptureThread(x, y, w, h, delay=delay, wheel_delta=wheel, max_frames=maxf)
            thread.progress.connect(
                lambda c, t: self._update_status(f"⏳ 长截图中... {c}/{t}")
            )
            thread.finished.connect(self.on_long_capture_finished)
            thread.error.connect(self.on_capture_error)
            thread.start()
            self._long_thread = thread
        else:
            img = ImageGrab.grab(bbox=(x, y, x+w, y+h))
            self.on_capture_finished(img)

    def on_capture_cancelled(self):
        self._capture_mode = None
        self.show()
        self._update_status("已取消")

    def on_capture_error(self, msg: str):
        self.show()
        self._update_status(f"错误: {msg}")
        QMessageBox.warning(self, "错误", msg)

    def on_capture_finished(self, img):
        self._current_img = img
        self._display_preview(img)
        self.show()
        self._update_status(f"截图完成 {img.size[0]}x{img.size[1]}")

    def on_long_capture_finished(self, img):
        self._current_img = img
        self._display_preview(img)
        self.show()
        self._update_status(f"长截图完成 {img.size[0]}x{img.size[1]}")

    def _display_preview(self, img):
        from PyQt6.QtGui import QPixmap
        data = img.tobytes("raw", "RGB")
        qimg = QImage(data, img.size[0], img.size[1], QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        label_size = self.preview.size()
        scaled = pixmap.scaled(
            label_size.width(), label_size.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(scaled)

    def on_btn_ocr(self):
        if not self._current_img:
            QMessageBox.warning(self, "提示", "请先截图")
            return
        if not self._ocr_engine or not self._ocr_engine.is_ready():
            QMessageBox.warning(self, "提示", "OCR 引擎未就绪")
            return
        self._update_status("⏳ OCR 识别中...")
        try:
            text, _ = self._ocr_engine.recognize(self._current_img)
            self.ocr_text.setPlainText(f"【OCR结果】\n{'='*30}\n{text}\n{'='*30}")
            self._update_status("OCR 完成")
        except Exception as e:
            self._update_status(f"OCR 失败: {e}")
            QMessageBox.warning(self, "OCR 失败", str(e))

    def on_btn_copy(self):
        text = self.ocr_text.toPlainText()
        if not text:
            return
        try:
            from app.utils.clipboard import copy_text
            copy_text(text)
            self._update_status("已复制到剪贴板")
        except Exception:
            QApplication.clipboard().setText(text)

    def on_btn_save(self):
        if not self._current_img:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存图片", "screenshot.png", "PNG (*.png);;JPEG (*.jpg)")
        if path:
            self._current_img.save(path)
            self._update_status(f"已保存: {path}")
