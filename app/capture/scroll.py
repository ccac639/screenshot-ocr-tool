"""
全局键盘监听模块
使用 pynput 监听全局快捷键，不依赖窗口焦点。
"""

from PyQt6.QtCore import QObject, pyqtSignal, QThread
from PIL import ImageGrab
import pyautogui
import time


def _activate_region(x: int, y: int, w: int, h: int):
    """点击区域中心，把焦点切回目标窗口"""
    cx = x + w // 2
    cy = y + h // 2
    pyautogui.click(x=cx, y=cy)
    time.sleep(0.25)


def _do_scroll(mode: str, wheel_delta: int):
    """执行一次滚动"""
    if mode == "pagedown":
        pyautogui.press("pagedown")
    else:
        pyautogui.scroll(wheel_delta)


class LongCaptureThread(QThread):
    """
    长截图后台线程（QThread 版本）
    信号：
      progress(int, int)  -> 当前帧/最大帧
      finished(PIL.Image) -> 完成，返回拼接结果
      error(str)           -> 出错，返回错误信息
    """
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        x: int, y: int, w: int, h: int,
        delay: float = 0.8,
        wheel_delta: int = -10,
        max_frames: int = 200,
        mode: str = "wheel",
    ):
        super().__init__()
        self.x, self.y, self.w, self.h = x, y, w, h
        self.delay = delay
        self.wheel_delta = wheel_delta
        self.max_frames = max_frames
        self.mode = mode  # "wheel" or "pagedown"

    def run(self):
        try:
            from app.utils.image import (
                pil_to_numpy, stitch_vertical,
                detect_fixed_header_v3, find_overlap_ssd, images_are_similar,
            )

            # 1. 点击激活目标窗口
            _activate_region(self.x, self.y, self.w, self.h)
            time.sleep(0.3)

            frames = []
            prev_arr = None
            dup_streak = 0
            DUP_STREAK = 5
            DUP_THRESHOLD = 0.965

            # 2. 第一帧
            img = ImageGrab.grab(bbox=(self.x, self.y,
                                          self.x + self.w, self.y + self.h))
            frames.append(img)
            prev_arr = pil_to_numpy(img)

            for i in range(1, self.max_frames):
                self.progress.emit(i, self.max_frames)

                # 滚动
                _do_scroll(self.mode, self.wheel_delta)
                time.sleep(self.delay)

                img = ImageGrab.grab(
                    bbox=(self.x, self.y,
                          self.x + self.w, self.y + self.h))

                # 去重检测
                if prev_arr is not None:
                    cur_arr = pil_to_numpy(img)
                    if images_are_similar(
                        Image.fromarray(prev_arr),
                        img,
                        threshold=DUP_THRESHOLD,
                    ):
                        dup_streak += 1
                        if dup_streak >= DUP_STREAK:
                            break
                        continue
                    else:
                        dup_streak = 0

                frames.append(img)
                prev_arr = pil_to_numpy(img)

            # 3. 拼接
            result = stitch_vertical(frames, overlap_remove=True)
            self.finished.emit(result)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))
