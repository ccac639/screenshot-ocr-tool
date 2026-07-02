"""
剪贴板工具
支持复制文本到系统剪贴板（PyQt6 实现）。
"""

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QMimeData
    _HAVE_QT = True
except ImportError:
    _HAVE_QT = False


def copy_text(text: str) -> bool:
    """复制文本到剪贴板"""
    if not _HAVE_QT:
        return False
    try:
        app = QApplication.instance()
        if app is None:
            return False
        mime = QMimeData()
        mime.setText(text)
        app.clipboard().setMimeData(mime)
        return True
    except Exception:
        return False


def copy_image(pil_img) -> bool:
    """复制 PIL Image 到剪贴板"""
    if not _HAVE_QT:
        return False
    try:
        from PyQt6.QtGui import QImage, QPixmap
        from PIL.ImageQt import ImageQt
        app = QApplication.instance()
        if app is None:
            return False
        qimg = ImageQt(pil_img)
        mime = QMimeData()
        mime.setImageData(qimg)
        app.clipboard().setMimeData(mime)
        return True
    except Exception:
        return False
