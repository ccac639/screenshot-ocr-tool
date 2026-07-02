"""
DPI 统一适配器
解决 Windows 高 DPI 缩放导致坐标错位的核心问题。

核心策略：
1. 设置进程 DPI 感知模式为 PER_MONITOR_AWARE_V2
2. 所有坐标统一转换为物理像素
3. 截图时也使用物理像素范围
"""

import ctypes
import ctypes.wintypes
import warnings
from typing import Tuple, Optional

warnings.filterwarnings("ignore")


# ─── Windows DPI 感知设置 ───────────────────────────────────────────
def set_dpi_awareness():
    """
    设置当前进程为 DPI 感知模式。
    必须在创建窗口/截图前调用！
    """
    try:
        # Windows 10/11: SetProcessDpiAwarenessContext
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
    except Exception:
        try:
            # Windows 8.1+: SetProcessDpiAwareness
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                # Windows 7+: SetProcessDPIAware
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


# ─── DPI 缩放因子获取 ─────────────────────────────────────────────
def get_dpi_scale() -> float:
    """
    获取当前主显示器的 DPI 缩放因子。
    返回：缩放因子（1.0 = 100%, 1.25 = 125%, 1.5 = 150%...）
    """
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        # tkinter 返回的是缩放后的像素
        scale = root.winfo_fpixels('1i') / 96.0
        root.destroy()
        return scale
    except Exception:
        try:
            # 使用 Windows API
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
            ctypes.windll.user32.ReleaseDC(0, hdc)
            return dpi / 96.0
        except Exception:
            return 1.0


# ─── 坐标转换 ─────────────────────────────────────────────────────
class DPIAdapter:
    """
    DPI 坐标适配器。

    使用方式：
        adapter = DPIAdapter()
        # 逻辑坐标 → 物理坐标（用于截图）
        px, py, pw, ph = adapter.to_physical(lx, ly, lw, lh)
        # 物理坐标 → 逻辑坐标（用于显示）
        lx, ly, lw, lh = adapter.to_logical(px, py, pw, ph)
    """

    def __init__(self):
        self.scale = get_dpi_scale()
        self.inv_scale = 1.0 / self.scale if self.scale > 0 else 1.0

    def to_physical(self, x: int, y: int, w: int, h: int) -> Tuple[int, int, int, int]:
        """
        逻辑坐标（Qt/Windows 报告的坐标）→ 物理像素（截图用的坐标）
        在高 DPI 屏幕上，逻辑坐标 < 物理像素，需要放大。
        """
        return (
            int(x * self.scale),
            int(y * self.scale),
            int(w * self.scale),
            int(h * self.scale),
        )

    def to_logical(self, x: int, y: int, w: int, h: int) -> Tuple[int, int, int, int]:
        """
        物理像素 → 逻辑坐标（用于 UI 显示）
        """
        return (
            int(x * self.inv_scale),
            int(y * self.inv_scale),
            int(w * self.inv_scale),
            int(h * self.inv_scale),
        )

    def scale_rect(self, rect: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
        """快捷方法：(x, y, w, h) → 放大到物理像素"""
        return self.to_physical(*rect)

    def unscale_rect(self, rect: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
        """快捷方法：(x, y, w, h) → 缩小到逻辑坐标"""
        return self.to_logical(*rect)


# ─── 全局单例 ─────────────────────────────────────────────────────
_adapter: Optional[DPIAdapter] = None


def get_dpi_adapter() -> DPIAdapter:
    """获取全局 DPI 适配器单例"""
    global _adapter
    if _adapter is None:
        set_dpi_awareness()
        _adapter = DPIAdapter()
    return _adapter


def reset_dpi_adapter():
    """重置 DPI 适配器（屏幕设置变更后调用）"""
    global _adapter
    set_dpi_awareness()
    _adapter = DPIAdapter()
