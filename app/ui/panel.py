"""
主控制面板 V2.1 稳定版
Snipaste 风格 + 工业级稳定性修复。

V2.1 升级：
- DPI 感知界面
- 修饰键状态清理
- 新截图引擎（dxcam/mss）
- 新长截图引擎（三层稳定）
- 新 OCR 线程池（不卡 UI）
- 设置面板（滚动延迟/滚轮量）
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QStatusBar, QFileDialog,
    QGroupBox, QSpinBox, QDoubleSpinBox, QLabel as QL,
    QProgressBar, QMessageBox, QCheckBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QImage, QFont
from PIL import Image
import os
import time

from app.core.event_bus import bus, AppEvent
from app.core.state_machine import sm, CaptureState
from app.core.dpi import get_dpi_adapter
from app.capture.region_capture import RegionSelector
from app.capture.scroll_capture import ScrollCaptureEngine
from app.ocr.engine import get_ocr_engine
from app.ocr.pipeline import get_ocr_pipeline
from app.utils.key_cleaner import clear_all_modifier_keys, cleanup_after_hotkey
from app.utils.clipboard import copy_text, copy_image
from app.utils.image import image_to_bytes


class MainWindow(QMainWindow):
    """主窗口（控制面板）"""

    def __init__(self):
        super().__init__()
        self._dpi = get_dpi_adapter()
        self._current_img = None
        self._scroll_engine = ScrollCaptureEngine()
        self._ocr_engine = get_ocr_engine()
        self._ocr_pipeline = get_ocr_pipeline()
        self._region_selector = None
        self._capture_mode = None
        self._setup_ui()
        self._connect_events()
        self._init_ocr()

    def _setup_ui(self):
        self.setWindowTitle("Screenshot OCR Tool V2.1 Stable")
        self.setMinimumSize(900, 700)
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; color: #cccccc; }
            QPushButton {
                background-color: #2d2d2d;
                color: #cccccc;
                border: 1px solid #444;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #3d3d3d; }
            QPushButton:pressed { background-color: #1a1a1a; }
            QPushButton:disabled { color: #666; }
            QTextEdit {
                background-color: #252525;
                color: #cccccc;
                border: 1px solid #444;
                font-family: Consolas, monospace;
                font-size: 13px;
            }
            QLabel { color: #cccccc; }
            QGroupBox {
                color: #cccccc;
                border: 1px solid #444;
                margin-top: 10px;
            }
            QGroupBox:title {
                subcontrol-origin: margin;
                left: 10px;
            }
            QStatusBar { color: #888; }
        """)

        root = QVBoxLayout()
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        # 按钮栏
        bar = QHBoxLayout()
        self.btn_capture = QPushButton("📷 截图")
        self.btn_long = QPushButton("📜 长截图")
        self.btn_ocr = QPushButton("🔍 OCR")
        self.btn_copy = QPushButton("📋 复制文本")
        self.btn_save = QPushButton("💾 保存图片")
        self.btn_save_txt = QPushButton("📝 保存文本")

        bar.addWidget(self.btn_capture)
        bar.addWidget(self.btn_long)
        bar.addSpacing(20)
        bar.addWidget(self.btn_ocr)
        bar.addWidget(self.btn_copy)
        bar.addWidget(self.btn_save)
        bar.addWidget(self.btn_save_txt)
        bar.addStretch()
        root.addLayout(bar)

        # 截图预览
        self.preview = QLabel("预览区（截图后显示）")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(350)
        self.preview.setStyleSheet("""
            QLabel {
                background-color: #252525;
                border: 1px solid #444;
                color: #666;
                font-size: 14px;
            }
        """)
        root.addWidget(self.preview)

        # OCR 结果
        ocr_group = QGroupBox("OCR 结果")
        ocr_layout = QVBoxLayout()
        self.ocr_text = QTextEdit()
        self.ocr_text.setMaximumHeight(200)
        ocr_layout.addWidget(self.ocr_text)
        ocr_group.setLayout(ocr_layout)
        root.addWidget(ocr_group)

        # 设置面板
        settings_group = QGroupBox("⚙️ 长截图设置")
        settings_layout = QHBoxLayout()

        settings_layout.addWidget(QL("滚动延迟（秒）:"))
        self.spin_delay = QDoubleSpinBox()
        self.spin_delay.setRange(0.1, 3.0)
        self.spin_delay.setValue(0.35)
        self.spin_delay.setSingleStep(0.05)
        self.spin_delay.valueChanged.connect(self._on_delay_changed)
        settings_layout.addWidget(self.spin_delay)

        settings_layout.addWidget(QL("滚轮量:"))
        self.spin_wheel = QSpinBox()
        self.spin_wheel.setRange(-30, -1)
        self.spin_wheel.setValue(-10)
        self.spin_wheel.valueChanged.connect(self._on_wheel_changed)
        settings_layout.addWidget(self.spin_wheel)

        settings_layout.addWidget(QL("最大帧数:"))
        self.spin_max_frames = QSpinBox()
        self.spin_max_frames.setRange(20, 500)
        self.spin_max_frames.setValue(100)
        settings_layout.addWidget(self.spin_max_frames)

        settings_layout.addStretch()
        settings_group.setLayout(settings_layout)
        root.addWidget(settings_group)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status("就绪 | Ctrl+Shift+A 截图 | Ctrl+Shift+S 长截图")

    def _connect_events(self):
        self.btn_capture.clicked.connect(self._on_capture_clicked)
        self.btn_long.clicked.connect(self._on_long_capture_clicked)
        self.btn_ocr.clicked.connect(self._on_ocr_clicked)
        self.btn_copy.clicked.connect(self._on_copy_clicked)
        self.btn_save.clicked.connect(self._on_save_clicked)
        self.btn_save_txt.clicked.connect(self._on_save_txt_clicked)

        # OCR 管线信号
        self._ocr_pipeline.result_ready.connect(self._on_ocr_result)
        self._ocr_pipeline.error_occurred.connect(self._on_ocr_error)

        # 全局事件
        bus.subscribe(AppEvent.CAPTURE_DONE, self._on_capture_done)
        bus.subscribe(AppEvent.OCR_DONE, self._on_ocr_done)

    def _init_ocr(self):
        if self._ocr_engine.is_ready():
            self._update_status(f"OCR 引擎就绪（{self._ocr_engine.backend_name}）")
        else:
            self._update_status("⚠️ OCR 引擎未就绪")

    def _on_capture_clicked(self):
        self._start_capture(mode="normal")

    def _on_long_capture_clicked(self):
        self._start_capture(mode="long")

    def _start_capture(self, mode: str):
        """启动截图"""
        # V2.1：清理修饰键状态
        cleanup_after_hotkey()

        self._capture_mode = mode
        self._region_selector = RegionSelector()
        self._region_selector.region_selected.connect(self._on_region_selected)
        self._region_selector.cancelled.connect(self._on_capture_cancelled)
        self._region_selector.start()

    def _on_region_selected(self, x: int, y: int, w: int, h: int):
        """用户完成区域选择"""
        mode = self._capture_mode
        self._capture_mode = None

        if mode == "long":
            # 长截图：主窗口保持隐藏
            self._update_status("⏳ 长截图中...（请勿操作鼠标键盘）")
            self.ocr_text.setPlainText("正在长截图，自动滚动中...")

            # 在新线程中执行
            from PyQt6.QtCore import QThread
            self._long_thread = QThread()
            self._scroll_engine.cancel()  # 重置

            # 使用 QTimer 延迟执行（让窗口隐藏完成）
            QTimer.singleShot(300, lambda: self._do_long_capture(x, y, w, h))
        else:
            # 普通截图
            from PIL import ImageGrab
            img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            self._on_capture_finished(img)

    def _do_long_capture(self, x, y, w, h):
        """执行长截图（在工作线程中）"""
        try:
            self._scroll_engine.capture(
                x, y, w, h,
                max_frames=self.spin_max_frames.value(),
                progress_callback=self._on_scroll_progress,
                finish_callback=self._on_long_capture_finished,
                error_callback=self._on_capture_error,
            )
        except Exception as e:
            self._on_capture_error(str(e))

    def _on_scroll_progress(self, cur: int, total: int):
        """长截图进度回调"""
        self._update_status(f"⏳ 长截图中... {cur}/{total}")

    def _on_long_capture_finished(self, img: Image.Image):
        """长截图完成"""
        self._on_capture_finished(img)

    def _on_capture_finished(self, img: Image.Image):
        """截图完成"""
        self._current_img = img
        self._display_preview(img)
        self._update_status(f"✅ 截图完成 {img.width}x{img.height}")
        self.show()
        self.raise_()
        self.activateWindow()

    def _display_preview(self, img: Image.Image):
        """显示预览"""
        try:
            from PyQt6.QtGui import QImage
            if img.mode != "RGB":
                img = img.convert("RGB")
            data = img.tobytes("raw", "RGB")
            qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            label_size = self.preview.size()
            scaled = pixmap.scaled(
                label_size.width(), label_size.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview.setPixmap(scaled)
        except Exception as e:
            print(f"[UI] 预览显示失败: {e}")

    def _on_capture_cancelled(self):
        """截图取消"""
        self._capture_mode = None
        self._update_status("取消截图")

    def _on_capture_error(self, msg: str):
        """截图错误"""
        self._update_status(f"❌ 错误: {msg}")
        QMessageBox.critical(self, "错误", msg)
        self.show()

    def _on_ocr_clicked(self):
        """执行 OCR"""
        if self._current_img is None:
            QMessageBox.warning(self, "警告", "请先截图")
            return

        if not self._ocr_engine.is_ready():
            QMessageBox.warning(self, "警告", "OCR 引擎未就绪")
            return

        self._update_status("⏳ OCR 识别中...")
        self._ocr_pipeline.enqueue(self._current_img)

    def _on_ocr_result(self, task_id: int, result: dict):
        """OCR 结果回调"""
        text = result.get("text", "")
        self.ocr_text.setPlainText(text)
        self._update_status(f"✅ OCR 完成，共 {len(text)} 字符")

    def _on_ocr_error(self, task_id: int, error_msg: str):
        """OCR 错误回调"""
        self._update_status(f"❌ OCR 错误: {error_msg}")

    def _on_copy_clicked(self):
        """复制文本到剪贴板"""
        text = self.ocr_text.toPlainText()
        if text:
            copy_text(text)
            self._update_status("✅ 已复制到剪贴板")
        else:
            QMessageBox.warning(self, "警告", "没有可复制的文本")

    def _on_save_clicked(self):
        """保存图片"""
        if self._current_img is None:
            QMessageBox.warning(self, "警告", "请先截图")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "保存图片", "screenshot.png", "PNG (*.png);;JPEG (*.jpg)"
        )
        if path:
            self._current_img.save(path)
            self._update_status(f"✅ 已保存: {path}")

    def _on_save_txt_clicked(self):
        """保存文本"""
        text = self.ocr_text.toPlainText()
        if not text:
            QMessageBox.warning(self, "警告", "没有可保存的文本")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "保存文本", "ocr_result.txt", "Text (*.txt)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self._update_status(f"✅ 已保存: {path}")

    def _on_delay_changed(self, value: float):
        """滚动延迟变更"""
        self._scroll_engine.set_scroll_delay(value)

    def _on_wheel_changed(self, value: int):
        """滚轮量变更"""
        self._scroll_engine.set_wheel_amount(value)

    def _update_status(self, msg: str):
        """更新状态栏"""
        self.status_bar.showMessage(msg)

    def closeEvent(self, event):
        """关闭窗口"""
        self._scroll_engine.cancel()
        self._ocr_pipeline.clear_queue()
        event.accept()
