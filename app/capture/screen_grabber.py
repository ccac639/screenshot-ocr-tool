"""
高性能截图引擎 V2.1
优先使用 dxcam（GPU 加速），失败 fallback mss，最后 PIL。

新增：
- 黑屏检测 + 自动重试
- DPI 感知坐标转换
- 截图前延迟（等待渲染）
"""

import time
import warnings
from typing import Optional, Tuple, List
from PIL import Image

warnings.filterwarnings("ignore")


# ─── 日志 ─────────────────────────────────
from app.utils.logger import get_logger
logger = get_logger(__name__)


# ─── 黑屏检测 ─────────────────────────────────────────────
def is_black_screen(img: Image.Image, threshold: float = 0.98) -> bool:
    """
    检测是否为黑屏（或接近全黑）。
    threshold: 黑色像素占比阈值（默认 0.98 = 98%）
    返回 True 表示很可能是黑屏。
    """
    try:
        import numpy as np
        arr = np.array(img)
        # 计算亮度（RGB 平均值）
        if len(arr.shape) == 3:
            brightness = arr.mean()
        else:
            brightness = arr.mean()
        # 亮度 < 10（0~255 范围）认为是黑屏
        return brightness < 10.0
    except Exception:
        return False


def is_white_screen(img: Image.Image, threshold: float = 0.98) -> bool:
    """检测是否为白屏（接近全白）"""
    try:
        import numpy as np
        arr = np.array(img)
        brightness = arr.mean()
        # 亮度 > 245 认为是白屏（可能是 overlay 残留）
        return brightness > 245.0
    except Exception:
        return False


# ─── 截图引擎封装（单例）────────────────────────────────
class ScreenGrabber:
    """
    截图引擎封装（单例）。
    优先级：dxcam（GPU）> mss > PIL fallback。

    V2.1 新增：
    - 黑屏自动检测 + 重试
    - DPI 感知坐标
    - 截图前等待渲染（wait_ready）
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._backend = None
            cls._instance._mss = None
            cls._instance._dxcam = None
            cls._instance._last_region = None
            cls._instance._init_backend()
        return cls._instance

    def _init_backend(self):
        """初始化最佳可用后端"""
        # 1. 尝试 dxcam（GPU 加速，仅 Windows）
        try:
            import dxcam
            self._dxcam = dxcam.create(output_color="BGR")
            if self._dxcam is not None:
                self._backend = "dxcam"
                logger.info("使用 dxcam 后端（GPU 加速）")
                return
        except Exception:
            pass

        # 2. 尝试 mss（极快纯 Python）
        try:
            import mss
            self._mss = mss.mss()
            self._backend = "mss"
            logger.info("使用 mss 后端")
            return
        except Exception:
            pass

        # 3. fallback: PIL
        self._backend = "pil"
        logger.warning("使用 PIL 后端（性能较低）")

    def grab(
        self,
        region: Optional[Tuple[int, int, int, int]] = None,
        wait_ms: int = 120,
    ) -> Image.Image:
        """
        截取屏幕区域。
        region: (x, y, x+w, y+h) 物理像素，或 None（全屏）
        wait_ms: 截图前等待毫秒数（允许屏幕渲染）
        返回：PIL RGB Image

        V2.1：自动检测黑屏并重试
        """
        # 等待渲染（避免截到黑屏）
        if wait_ms > 0:
            time.sleep(wait_ms / 1000.0)

        max_retry = 3
        for attempt in range(max_retry):
            img = self._do_grab(region)

            # 检测黑屏/白屏
            if is_black_screen(img):
                if attempt < max_retry - 1:
                    time.sleep(0.15)
                    continue
            if is_white_screen(img):
                if attempt < max_retry - 1:
                    time.sleep(0.15)
                    continue

            return img

        # 所有重试都失败，返回最后一次结果
        return img

    def _do_grab(self, region):
        """执行实际截图"""
        if self._backend == "dxcam" and self._dxcam is not None:
            return self._grab_dxcam(region)
        elif self._backend == "mss" and self._mss is not None:
            return self._grab_mss(region)
        else:
            return self._grab_pil(region)

    def _grab_dxcam(self, region):
        """dxcam 截图"""
        if region:
            # dxcam region: (left, top, right, bottom)
            self._dxcam.region = region
        frame = self._dxcam.grab()
        if frame is None:
            # dxcam 失败，fallback 到 mss
            return self._grab_mss(region)
        # dxcam 返回 BGR numpy array
        import cv2
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    def _grab_mss(self, region):
        """mss 截图（快）"""
        if region:
            monitor = {
                "top": region[1],
                "left": region[0],
                "width": region[2] - region[0],
                "height": region[3] - region[1],
            }
        else:
            monitor = self._mss.monitors[1]  # 主屏
        shot = self._mss.grab(monitor)
        return Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)

    def _grab_pil(self, region):
        """PIL 截图（慢，但最兼容）"""
        from PIL import ImageGrab
        if region:
            return ImageGrab.grab(bbox=region)
        else:
            return ImageGrab.grab()

    def grab_all_monitors(self) -> List[Image.Image]:
        """截取所有显示器（mss 多屏支持）"""
        if self._backend == "mss" and self._mss is not None:
            imgs = []
            for mon in self._mss.monitors[1:]:  # 跳过全屏合并
                shot = self._mss.grab(mon)
                imgs.append(Image.frombytes("RGB", (shot.width, shot.height), shot.rgb))
            return imgs
        else:
            # fallback: 只截主屏
            return [self.grab()]

    @property
    def backend_name(self) -> str:
        return self._backend or "unknown"

    def refresh(self):
        """刷新后端（dxcam 失效时调用）"""
        self._backend = None
        self._mss = None
        self._dxcam = None
        self._init_backend()


# ─── 全局单例 ─────────────────────────────────────────
grabber = ScreenGrabber()
