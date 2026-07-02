"""
插件接口（预留扩展）
未来支持：翻译插件、小说结构分析、AI 摘要、自动分类。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class PluginBase(ABC):
    """
    插件基类
    所有插件必须继承此类并实现对应钩子方法。
    """

    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        pass

    @abstractmethod
    def version(self) -> str:
        """插件版本"""
        pass

    def on_capture(self, img: "Image.Image") -> None:
        """
        截图完成后回调。
        参数：img - 截取的 PIL Image
        """
        pass

    def on_ocr(self, text: str, result: Dict) -> None:
        """
        OCR 完成后回调。
        参数：
            text   - OCR 纯文本结果
            result - OCR 结构化结果（含 boxes / confidence）
        """
        pass

    def on_ui_ready(self, main_window: "MainWindow") -> None:
        """
        UI 初始化完成后回调。
        可在此添加自定义按钮/菜单。
        """
        pass

    def cleanup(self) -> None:
        """插件卸载/退出时清理"""
        pass


class PluginManager:
    """
    插件管理器（单例）
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._plugins: List[PluginBase] = []
        return cls._instance

    def register(self, plugin: PluginBase):
        """注册插件"""
        self._plugins.append(plugin)
        print(f"[Plugin] 已注册插件: {plugin.name()} v{plugin.version()}")

    def unregister(self, plugin: PluginBase):
        """注销插件"""
        if plugin in self._plugins:
            plugin.cleanup()
            self._plugins.remove(plugin)

    def emit_capture(self, img: "Image.Image"):
        """触发 on_capture 钩子"""
        for p in self._plugins:
            try:
                p.on_capture(img)
            except Exception as e:
                print(f"[Plugin] {p.name()}.on_capture 错误: {e}")

    def emit_ocr(self, text: str, result: Dict):
        """触发 on_ocr 钩子"""
        for p in self._plugins:
            try:
                p.on_ocr(text, result)
            except Exception as e:
                print(f"[Plugin] {p.name()}.on_ocr 错误: {e}")

    def emit_ui_ready(self, main_window):
        """触发 on_ui_ready 钩子"""
        for p in self._plugins:
            try:
                p.on_ui_ready(main_window)
            except Exception as e:
                print(f"[Plugin] {p.name()}.on_ui_ready 错误: {e}")

    def list_plugins(self) -> List[str]:
        """列出所有已注册插件"""
        return [p.name() for p in self._plugins]


# 全局单例
plugin_mgr = PluginManager()
