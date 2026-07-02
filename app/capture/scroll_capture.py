"""
长截图引擎 V2.1 稳定版
工业级稳定性修复。

V2.1 修复：
- 滚动稳定控制器（防错位）
- Ctrl 状态清理（防屏幕放大）
- 黑屏检测 + 自动重试
- 自适应滚动延迟
- 三层稳定机制（去重 + 对齐 + 滚动控制）
"""

import time
import warnings
from typing import Optional, Callable, Tuple
from PIL import Image

warnings.filterwarnings("ignore")

from app.core.event_bus import bus, AppEvent
from app.core.state_machine import sm, CaptureState
from app.core.dpi import get_dpi_adapter
from app.capture.screen_grabber import grabber
from app.utils.key_cleaner import clear_all_modifier_keys, prepare_for_scroll, prepare_for_capture
from app.vision.dedup import is_duplicate_phash, is_duplicate_ssim
from app.vision.align import find_overlap_offset
from app.vision.stitch import stitch_frames_v2


# ─── 滚动稳定控制器 ─────────────────────────────────────
class ScrollController:
    """
    滚动稳定控制器。
    负责：发送滚动命令 + 等待渲染 + 检测失败。
    """

    def __init__(self):
        self._scroll_delay = 0.35  # 默认滚动延迟（秒）
        self._wheel_amount = -10  # 每次滚动量（负数=向下）
        self._adaptive = True  # 自适应延迟
        self._last_scroll_time = 0

    def scroll(self, dx: int = 0, dy: int = -10, delay: float = None):
        """
        执行滚动操作。
        dx/dy: 滚动量（dy 负数=向下）
        delay: 自定义延迟（None=使用默认值）
        """
        # V2.1：滚动前清理修饰键（防屏幕放大）
        prepare_for_scroll()

        # 执行滚动
        try:
            import pyautogui
            # 使用 scroll 而不是 press('pagedown')，更可控
            pyautogui.scroll(dy, dx)
        except Exception:
            try:
                import pyautogui
                pyautogui.press('pagedown')
            except Exception:
                pass

        # 等待渲染
        actual_delay = delay if delay is not None else self._scroll_delay
        time.sleep(actual_delay)

        # V2.1：滚动后再次清理（防残留）
        clear_all_modifier_keys()

    def set_delay(self, delay: float):
        """设置滚动延迟"""
        self._scroll_delay = max(0.1, min(delay, 3.0))

    def set_wheel_amount(self, amount: int):
        """设置滚动量"""
        self._wheel_amount = max(-30, min(amount, -1))

    @property
    def delay(self) -> float:
        return self._scroll_delay

    @property
    def wheel_amount(self) -> int:
        return self._wheel_amount


# ─── 长截图主引擎 ───────────────────────────────────────
class ScrollCaptureEngine:
    """
    长截图引擎 V2.1 稳定版。

    三层稳定机制：
    1. 去重层（pHash + SSIM）
    2. 重叠对齐层（template matching）
    3. 滚动控制器（稳定滚动 + 状态清理）
    """

    def __init__(self):
        self._dpi = get_dpi_adapter()
        self._controller = ScrollController()
        self._frames: list[Image.Image] = []
        self._canceled = False

    def capture(
        self,
        x: int, y: int, w: int, h: int,
        max_frames: int = 100,
        progress_callback: Optional[Callable] = None,
        finish_callback: Optional[Callable] = None,
        error_callback: Optional[Callable] = None,
    ):
        """
        执行长截图。

        参数：
        x, y, w, h: 截图区域（物理像素）
        max_frames: 最大帧数
        progress_callback: 进度回调 (current, total)
        finish_callback: 完成回调 (Image)
        error_callback: 错误回调 (error_msg)
        """
        self._frames = []
        self._canceled = False

        try:
            # 切换到滚动模式
            sm.transition(CaptureState.SCROLLING)

            # 第一帧
            frame = self._grab_frame(x, y, w, h)
            if frame is None:
                raise RuntimeError("第一帧截图失败（黑屏或截图引擎失败）")
            self._frames.append(frame)

            dup_count = 0
            adaptive_delay = self._controller.delay

            for i in range(1, max_frames):
                if self._canceled:
                    break

                # 滚动
                self._controller.scroll(
                    dy=self._controller.wheel_amount,
                    delay=adaptive_delay,
                )

                # 截图
                frame = self._grab_frame(x, y, w, h)
                if frame is None:
                    continue

                # 去重检测
                if self._is_duplicate(frame):
                    dup_count += 1
                    if dup_count >= 4:  # 连续4帧重复 → 结束
                        break
                    continue
                else:
                    dup_count = 0

                # 添加到帧列表
                self._frames.append(frame)

                # 进度回调
                if progress_callback:
                    progress_callback(i, max_frames)

                # 自适应延迟（如果页面渲染慢，增加延迟）
                if self._controller._adaptive and i > 0 and i % 10 == 0:
                    adaptive_delay = min(adaptive_delay + 0.05, 1.5)

            # 拼接
            sm.transition(CaptureState.STITCHING)
            result = stitch_frames_v2(self._frames)

            sm.transition(CaptureState.DONE)
            if finish_callback:
                finish_callback(result)

        except Exception as e:
            sm.transition(CaptureState.IDLE)
            if error_callback:
                error_callback(str(e))

    def _grab_frame(self, x, y, w, h):
        """截取一帧（带黑屏检测）"""
        prepare_for_capture()
        img = grabber.grab(region=(x, y, x + w, y + h), wait_ms=100)
        if img is None:
            return None
        # 黑屏检测
        try:
            import numpy as np
            arr = np.array(img)
            if arr.mean() < 10.0:
                time.sleep(0.2)
                img = grabber.grab(region=(x, y, x + w, y + h), wait_ms=150)
        except Exception:
            pass
        return img

    def _is_duplicate(self, frame: Image.Image) -> bool:
        """判断是否与上一帧重复"""
        if len(self._frames) < 1:
            return False
        prev = self._frames[-1]
        # pHash 去重
        if is_duplicate_phash(prev, frame, threshold=8):
            return True
        # SSIM 去重
        if is_duplicate_ssim(prev, frame, threshold=0.96):
            return True
        return False

    def cancel(self):
        """取消长截图"""
        self._canceled = True

    def set_scroll_delay(self, delay: float):
        """设置滚动延迟"""
        self._controller.set_delay(delay)

    def set_wheel_amount(self, amount: int):
        """设置滚动量"""
        self._controller.set_wheel_amount(amount)
