# 截图+OCR+长截图工具

Python 3.10+ 桌面工具，功能类似 QQ截图/微信截图/Snipaste。

## 功能

- 区域截图（鼠标拖拽选框）
- 长截图（自动滚动拼接）
- OCR 文字识别（PaddleOCR / EasyOCR 自动 fallback）
- 全局快捷键控制
- 截图预览 + 编辑/复制/导出

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python -m app.main
```

## 快捷键

| 功能 | 快捷键 |
|------|---------|
| 启动截图 | Ctrl+Shift+A |
| 长截图 | Ctrl+Shift+S |
| OCR识别 | Ctrl+Shift+O |
| 取消截图 | Esc / 右键 |

## 依赖

- PyQt6
- PaddleOCR（优先） / EasyOCR（fallback）
- pynput（全局热键）
- Pillow、pyautogui、numpy

## 注意

- Windows 10/11 优先
- PaddleOCR 首次运行会自动下载中文模型（约 30MB），请保持联网
- 长截图时需要以管理员身份运行，否则全局热键可能注册失败
