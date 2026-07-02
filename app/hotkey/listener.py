"""
全局快捷键模块
使用 pynput 实现全局热键（不依赖窗口焦点）。
"""

from pynput import keyboard
import threading


class HotkeyListener:
    """
    全局热键监听器（pynput GlobalHotKeys 封装）。
    支持：
      register(name, key_combo, callback)
      start() / stop()
    """

    def __init__(self):
        self._bindings = {}
        self._callbacks = {}
        self._listener = None
        self._running = False

    def register(self, name: str, key_combo: str, callback):
        """
        注册热键。
        key_combo 格式（pynput GlobalHotKeys 格式）：
          "<ctrl>+<shift>+a"
          "<ctrl>+c"
          "<esc>"
        """
        self._bindings[name] = key_combo
        self._callbacks[name] = callback

    def unregister(self, name: str):
        """注销热键"""
        self._bindings.pop(name, None)
        self._callbacks.pop(name, None)

    def start(self):
        """启动监听（后台线程）"""
        if self._running:
            return
        if not self._bindings:
            print("[Hotkey] 没有注册任何热键")
            return

        bindings = {
            combo: self._make_callback(cb)
            for combo, cb in zip(
                self._bindings.values(), self._callbacks.values()
            )
        }

        try:
            self._listener = keyboard.GlobalHotKeys(bindings)
            t = threading.Thread(target=self._listener.run, daemon=True)
            t.start()
            self._running = True
            print(f"[Hotkey] 已启动，监听 {len(bindings)} 个热键")
        except Exception as e:
            print(f"[Hotkey] 启动失败: {e}")

    def stop(self):
        """停止监听"""
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
        self._running = False
        print("[Hotkey] 已停止")

    def _make_callback(self, func):
        """包装回调函数（pynput 要求无参 callable）"""
        return func
