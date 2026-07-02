"""
截图流程状态机
严格管理：IDLE → SELECT_REGION → CAPTURING → SCROLLING → STITCHING → OCR_PROCESSING → DONE
"""

from enum import Enum, auto
from typing import Optional, Callable, Dict
from app.core.event_bus import bus, AppEvent


class CaptureState(Enum):
    """截图状态枚举"""
    IDLE = auto()
    SELECT_REGION = auto()
    CAPTURING = auto()
    SCROLLING = auto()
    STITCHING = auto()
    OCR_PROCESSING = auto()
    DONE = auto()
    CANCELLED = auto()
    ERROR = auto()


class StateMachine:
    """
    截图流程状态机（单例）
    所有状态转换必须通过本类，禁止模块自行修改状态。
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._state = CaptureState.IDLE
            cls._instance._context: Dict = {}
            cls._instance._transition_callbacks: Dict[CaptureState, List[Callable]] = {}
        return cls._instance

    @property
    def state(self) -> CaptureState:
        return self._state

    @property
    def context(self) -> Dict:
        return self._context

    def set_context(self, **kwargs):
        """设置上下文数据（如 region, frames, result_img 等）"""
        self._context.update(kwargs)

    def clear_context(self):
        self._context.clear()

    def register_callback(self, state: CaptureState, cb: Callable):
        """注册进入某状态时的回调"""
        if state not in self._transition_callbacks:
            self._transition_callbacks[state] = []
        self._transition_callbacks[state].append(cb)

    def can_transition(self, target: CaptureState) -> bool:
        """检查状态转换是否合法"""
        rules = {
            CaptureState.IDLE: [CaptureState.SELECT_REGION, CaptureState.CANCELLED],
            CaptureState.SELECT_REGION: [CaptureState.CAPTURING, CaptureState.CANCELLED],
            CaptureState.CAPTURING: [CaptureState.SCROLLING, CaptureState.STITCHING, CaptureState.CANCELLED, CaptureState.ERROR],
            CaptureState.SCROLLING: [CaptureState.STITCHING, CaptureState.CANCELLED, CaptureState.ERROR],
            CaptureState.STITCHING: [CaptureState.OCR_PROCESSING, CaptureState.DONE, CaptureState.ERROR],
            CaptureState.OCR_PROCESSING: [CaptureState.DONE, CaptureState.ERROR],
            CaptureState.DONE: [CaptureState.IDLE],
            CaptureState.CANCELLED: [CaptureState.IDLE],
            CaptureState.ERROR: [CaptureState.IDLE],
        }
        return target in rules.get(self._state, [])

    def transition(self, target: CaptureState, **context_kwargs) -> bool:
        """执行状态转换（会发布 EVENT"""
        if not self.can_transition(target):
            print(f"[StateMachine] 非法转换: {self._state.name} → {target.name}")
            return False

        old = self._state
        self._state = target
        if context_kwargs:
            self._context.update(context_kwargs)

        # 触发回调
        for cb in self._transition_callbacks.get(target, []):
            try:
                cb(old, target, self._context)
            except Exception as e:
                print(f"[StateMachine] 回调错误: {e}")

        # 发布事件
        bus.publish(AppEvent.STATE_CHANGED, old, target, self._context)
        print(f"[StateMachine] {old.name} → {target.name}")
        return True

    def cancel(self):
        """取消当前流程"""
        if self._state != CaptureState.IDLE:
            self.transition(CaptureState.CANCELLED)
            self.clear_context()
            self.transition(CaptureState.IDLE)

    def reset(self):
        """重置到 IDLE"""
        self._state = CaptureState.IDLE
        self.clear_context()


# 全局单例
sm = StateMachine()
