"""
修饰键状态清理器
解决 pyautogui 操作后 Ctrl/Alt/Shift 状态残留导致屏幕放大等问题。

核心问题：
- 截图时 Ctrl 被按住 → Windows 放大镜激活（屏幕放大）
- 滚动时 Alt 被按住 → 窗口拖拽模式激活
- 必须确保所有修饰键在操作后释放
"""

import time
import warnings

warnings.filterwarnings("ignore")


# ─── Windows API 方式（最可靠）────────────────────────────
def clear_modifier_keys_win():
    """
    使用 Windows API 释放所有修饰键。
    最可靠的方式，直接操作底层键盘状态。
    """
    try:
        import ctypes
        from ctypes import wintypes

        # 按键扫描码（Windows API）
        KEYEVENTF_KEYUP = 0x0002
        KEYEVENTF_EXTENDEDKEY = 0x0001

        # 修饰键列表（虚拟键码）
        modifier_keys = [
            0x10,  # VK_SHIFT
            0x11,  # VK_CONTROL
            0x12,  # VK_MENU (Alt)
            0x5B,  # VK_LWIN (左 Win)
            0x5C,  # VK_RWIN (右 Win)
        ]

        for vk in modifier_keys:
            ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

        time.sleep(0.02)
        return True
    except Exception:
        return False


# ─── pyautogui 方式（备用）────────────────────────────────
def clear_modifier_keys_pyautogui():
    """
    使用 pyautogui 释放所有修饰键。
    作为 Windows API 的备用方案。
    """
    try:
        import pyautogui
        keys_to_release = ["ctrl", "alt", "shift", "win"]
        for key in keys_to_release:
            try:
                pyautogui.keyUp(key)
            except Exception:
                pass
        time.sleep(0.02)
        return True
    except Exception:
        return False


# ─── 组合方式（推荐）────────────────────────────────────
def clear_all_modifier_keys():
    """
    清除所有修饰键状态（组合方式，最可靠）。
    先尝试 Windows API，失败则 fallback 到 pyautogui。
    """
    ok = clear_modifier_keys_win()
    if not ok:
        clear_modifier_keys_pyautogui()
    time.sleep(0.03)


# ─── 上下文管理器 ─────────────────────────────────────
class ModifierKeyContext:
    """
    修饰键状态上下文管理器。
    进入时记录状态，退出时恢复。

    使用方式：
        with ModifierKeyContext():
            pyautogui.press("pagedown")
    """

    def __enter__(self):
        # 进入前清除所有修饰键状态
        clear_all_modifier_keys()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 退出后再次清除（防止操作过程中残留）
        clear_all_modifier_keys()
        return False


# ─── 滚动前准备 ───────────────────────────────────────
def prepare_for_scroll():
    """
    滚动前准备（清除修饰键 + 等待稳定）。
    必须在每次滚动操作前调用。
    """
    clear_all_modifier_keys()
    time.sleep(0.05)


def prepare_for_capture():
    """
    截图前准备（清除修饰键 + 等待渲染）。
    必须在每次截图操作前调用。
    """
    clear_all_modifier_keys()
    time.sleep(0.08)


# ─── 全局快捷键后清理 ─────────────────────────────────
def cleanup_after_hotkey():
    """
    全局快捷键触发后清理。
    防止快捷键本身（Ctrl+Shift+A）的按键状态残留。
    """
    time.sleep(0.1)
    clear_all_modifier_keys()
