"""
全局事件总线（发布-订阅模式）
所有模块通过 EventBus 解耦通信。
"""

from enum import Enum, auto
from typing import Callable, Dict, List
import threading


class AppEvent(Enum):
    """应用事件枚举"""

    # 状态机事件
    STATE_CHANGED = auto()

    # 截图事件
    CAPTURE_STARTED = auto()
    REGION_SELECTED = auto()
    CAPTURE_CANCELLED = auto()
    FRAME_CAPTURED = auto()

    # 长截图事件
    SCROLL_STARTED = auto()
    SCROLL_FRAME = auto()
    SCROLL_FINISHED = auto()
    SCROLL_ERROR = auto()

    # 拼接事件
    STITCH_STARTED = auto()
    STITCH_PROGRESS = auto()
    STITCH_FINISHED = auto()

    # OCR 事件
    OCR_QUEUED = auto()
    OCR_STARTED = auto()
    OCR_PROGRESS = auto()
    OCR_FINISHED = auto()
    OCR_ERROR = auto()

    # UI 事件
    UI_SHOW_OVERLAY = auto()
    UI_HIDE_OVERLAY = auto()
    UI_UPDATE_PREVIEW = auto()
    UI_UPDATE_STATUS = auto()

    # 快捷键事件
    HOTKEY_CAPTURE = auto()
    HOTKEY_LONG_CAPTURE = auto()
    HOTKEY_OCR = auto()
    HOTKEY_CANCEL = auto()


class EventBus:
    """
    全局事件总线（单例）
    支持同步/异步订阅，线程安全。
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._subscribers: Dict[AppEvent, List[Callable]] = {}
                cls._instance._async_subscribers: Dict[AppEvent, List[Callable]] = {}
            return cls._instance

    def subscribe(self, event: AppEvent, callback: Callable):
        """订阅事件（同步，在发布线程执行）"""
        if event not in self._subscribers:
            self._subscribers[event] = []
        if callback not in self._subscribers[event]:
            self._subscribers[event].append(callback)

    def subscribe_async(self, event: AppEvent, callback: Callable):
        """订阅事件（异步，投递到 Qt 主线程）"""
        if event not in self._async_subscribers:
            self._async_subscribers[event] = []
        if callback not in self._async_subscribers[event]:
            self._async_subscribers[event].append(callback)

    def unsubscribe(self, event: AppEvent, callback: Callable):
        """取消订阅"""
        for d in (self._subscribers, self._async_subscribers):
            if event in d and callback in d[event]:
                d[event].remove(callback)

    def publish(self, event: AppEvent, *args, **kwargs):
        """发布事件（同步通知所有订阅者）"""
        # 同步订阅者
        for cb in self._subscribers.get(event, []):
            try:
                cb(*args, **kwargs)
            except Exception as e:
                print(f"[EventBus] 同步订阅者错误 {event.name}: {e}")
        # 异步订阅者（通过 Qt 信号投递）
        for cb in self._async_subscribers.get(event, []):
            try:
                cb(*args, **kwargs)
            except Exception as e:
                print(f"[EventBus] 异步订阅者错误 {event.name}: {e}")

    def clear(self):
        """清除所有订阅（测试用）"""
        self._subscribers.clear()
        self._async_subscribers.clear()


# 全局单例
bus = EventBus()
