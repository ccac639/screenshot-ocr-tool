"""
OCR 线程池 V2.1 稳定版
使用 QThread + 线程池，确保 OCR 不阻塞 UI。

V2.1 修复：
- 单例引擎（只初始化一次）
- 任务队列（截图 → 队列 → Worker Thread → UI）
- 非阻塞回调
- 错误恢复
"""

import time
import warnings
from typing import Optional, Callable, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QRunnable, QThreadPool
from PIL import Image

warnings.filterwarnings("ignore")

from app.ocr.engine import get_ocr_engine


# ── OCR Worker（QRunnable）───────────────────────────────
class OCRWorker(QRunnable):
    """
    OCR 工作线程（QRunnable）。
    在 QThreadPool 中执行，不阻塞 UI。
    """

    def __init__(
        self,
        image: Image.Image,
        task_id: int,
        callback: Callable[[int, Dict[str, Any]], None],
        error_callback: Callable[[int, str], None],
    ):
        super().__init__()
        self._image = image
        self._task_id = task_id
        self._callback = callback
        self._error_callback = error_callback

    def run(self):
        """执行 OCR 识别"""
        try:
            engine = get_ocr_engine()
            result = engine.recognize(self._image)
            if self._callback:
                self._callback(self._task_id, result)
        except Exception as e:
            if self._error_callback:
                self._error_callback(self._task_id, str(e))


# ── OCR 任务调度器 ───────────────────────────────────
class OCRPipeline(QObject):
    """
    OCR 任务调度器（单例）。
    管理任务队列 + 线程池。
    """

    # 信号
    result_ready = pyqtSignal(int, dict)  # task_id, result
    error_occurred = pyqtSignal(int, str)  # task_id, error_msg
    queue_size_changed = pyqtSignal(int)  # queue_size

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._thread_pool = QThreadPool.globalInstance()
        self._thread_pool.setMaxThreadCount(2)  # 最多 2 个 OCR 线程
        self._task_counter = 0
        self._queue_size = 0
        self._initialized = True
        print(f"[OCR Pipeline] 初始化完成，最大线程数：{self._thread_pool.maxThreadCount()}")

    def enqueue(self, image: Image.Image) -> int:
        """
        将 OCR 任务加入队列。
        返回：任务 ID（用于回调识别）
        """
        self._task_counter += 1
        task_id = self._task_counter
        self._queue_size += 1
        self.queue_size_changed.emit(self._queue_size)

        worker = OCRWorker(
            image,
            task_id,
            self._on_result,
            self._on_error,
        )
        self._thread_pool.start(worker)
        return task_id

    def _on_result(self, task_id: int, result: Dict[str, Any]):
        """OCR 完成回调"""
        self._queue_size = max(0, self._queue_size - 1)
        self.queue_size_changed.emit(self._queue_size)
        self.result_ready.emit(task_id, result)

    def _on_error(self, task_id: int, error_msg: str):
        """OCR 错误回调"""
        self._queue_size = max(0, self._queue_size - 1)
        self.queue_size_changed.emit(self._queue_size)
        self.error_occurred.emit(task_id, error_msg)

    def clear_queue(self):
        """清空任务队列"""
        self._thread_pool.clear()
        self._queue_size = 0
        self.queue_size_changed.emit(0)

    def wait_for_done(self, timeout_ms: int = 5000):
        """等待所有任务完成"""
        self._thread_pool.waitForDone(timeout_ms)

    @property
    def queue_size(self) -> int:
        return self._queue_size

    @property
    def is_busy(self) -> bool:
        return self._queue_size > 0


# ── 全局单例 ─────────────────────────────────────────
_pipeline: Optional[OCRPipeline] = None


def get_ocr_pipeline() -> OCRPipeline:
    """获取 OCR 任务调度器单例"""
    global _pipeline
    if _pipeline is None:
        _pipeline = OCRPipeline()
    return _pipeline
