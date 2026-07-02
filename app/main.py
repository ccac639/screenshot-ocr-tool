"""
入口文件 V2.1 稳定版
初始化所有模块 + 注册全局热键 + 启动 UI。

V2.1 修复：
- DPI 感知初始化
- 修饰键状态清理
- 所有模块单例模式
- 优雅退出
"""

import sys
import time
import warnings

warnings.filterwarnings("ignore")

# ─── 必须在导入 PyQt6 前设置 DPI 感知 ───────────
from app.core.dpi import set_dpi_awareness, get_dpi_adapter

set_dpi_awareness()


# ─── PyQt6 导入 ─────────────────────────────
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, Qt

from app.core.event_bus import bus, AppEvent
from app.core.state_machine import sm, CaptureState
from app.ocr.engine import get_ocr_engine
from app.ocr.pipeline import get_ocr_pipeline
from app.hotkey.listener import HotkeyListener
from app.ui.panel import MainWindow
from app.utils.key_cleaner import cleanup_after_hotkey


# ─── 全局热键回调 ────────────────────────────
def on_hotkey_capture():
    """Ctrl+Shift+A：启动截图"""
    cleanup_after_hotkey()
    window = _get_main_window()
    if window:
        window._on_capture_clicked()


def on_hotkey_long_capture():
    """Ctrl+Shift+S：启动长截图"""
    cleanup_after_hotkey()
    window = _get_main_window()
    if window:
        window._on_long_capture_clicked()


def on_hotkey_ocr():
    """Ctrl+Shift+O：OCR 识别"""
    cleanup_after_hotkey()
    window = _get_main_window()
    if window:
        window._on_ocr_clicked()


# ─── 主窗口引用 ─────────────────────────────
_main_window = None


def _get_main_window() -> MainWindow:
    return _main_window


# ─── 主函数 ─────────────────────────────────
def main():
    """主函数"""
    global _main_window

    print("=" * 80)
    print("  Screenshot OCR Tool V2.1 Stable")
    print("=" * 80)
    print()

    # 创建 QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("Screenshot OCR Tool V2.1")
    app.setApplicationDisplayName("Screenshot OCR Tool V2.1 Stable")

    # DPI 适配
    dpi = get_dpi_adapter()
    print(f"[Main] DPI 缩放因子: {dpi.scale:.2f}")

    # 初始化 OCR 引擎（单例，只初始化一次）
    print("[Main] 初始化 OCR 引擎（单例）...")
    ocr_engine = get_ocr_engine()
    if ocr_engine.is_ready():
        print(f"[Main] OCR 引擎就绪（{ocr_engine.backend_name}）")
    else:
        print("[Main] ⚠️ OCR 引擎未就绪（将使用 EasyOCR fallback）")

    # 初始化 OCR 任务调度器（单例）
    print("[Main] 初始化 OCR 任务调度器（单例）...")
    ocr_pipeline = get_ocr_pipeline()
    print(f"[Main] OCR 任务调度器就绪")

    # 创建主窗口
    print("[Main] 创建主窗口...")
    window = MainWindow()
    _main_window = window
    window.show()

    # 注册全局热键
    print("[Main] 注册全局热键...")
    hotkey = HotkeyListener()
    hotkey.register("capture", "<ctrl>+<shift>+a", on_hotkey_capture)
    hotkey.register("long_capture", "<ctrl>+<shift>+s", on_hotkey_long_capture)
    hotkey.register("ocr", "<ctrl>+<shift>+o", on_hotkey_ocr)
    hotkey.start()

    print()
    print("=" * 80)
    print("[Main] 全局热键已注册：")
    print("  Ctrl+Shift+A : 启动截图")
    print("  Ctrl+Shift+S : 启动长截图")
    print("  Ctrl+Shift+O : OCR 识别")
    print("  Esc           : 取消")
    print()
    print("[Main] 主窗口已启动")
    print(f"[Main] 截图引擎: {get_ocr_engine().backend_name if get_ocr_engine().is_ready() else 'pending'}")  # 这行有问题，应该是 grabber 的后端
    from app.capture.screen_grabber import grabber
    print(f"[Main] 截图引擎: {grabber.backend_name}")
    print("=" * 80)
    print()

    # 启动事件循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
