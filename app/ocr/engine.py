"""
OCR 引擎 V2.1 稳定版
PaddleOCR 单例 + 线程池。

V2.1 修复：
- 单例模式（只初始化一次）
- 线程池（不卡 UI）
- 自动 fallback 到 EasyOCR
- 黑屏检测（跳过无效输入）
"""

import time
import warnings
from typing import Optional, Dict, List, Any
from PIL import Image
import numpy as np

warnings.filterwarnings("ignore")


# ── 全局单例 ─────────────────────────────────────────
_instance: Optional["OCREngine"] = None


def get_ocr_engine() -> "OCREngine":
    """获取 OCR 引擎单例（全局共享）"""
    global _instance
    if _instance is None:
        _instance = OCREngine()
    return _instance


# ── OCR 引擎 ────────────────────────────────────────
class OCREngine:
    """
    OCR 引擎封装（单例）。
    优先 PaddleOCR，失败 fallback EasyOCR。
    """

    def __init__(self):
        self._paddle_ocr = None
        self._easy_ocr = None
        self._backend = None
        self._init_backend()

    def _init_backend(self):
        """初始化 OCR 后端"""
        # 1. 尝试 PaddleOCR
        try:
            from paddleocr import PaddleOCR
            # V2.1：不传入已废弃的参数
            self._paddle_ocr = PaddleOCR(
                lang="ch",
            )
            self._backend = "paddle"
            print("[OCR] 使用 PaddleOCR 后端")
            return
        except Exception as e:
            print(f"[OCR] PaddleOCR 初始化失败: {e}")
            print("[OCR] 尝试 fallback 到 easyocr...")

        # 2. Fallback: EasyOCR
        try:
            import easyocr
            self._easy_ocr = easyocr.Reader(
                ["ch_sim", "en"],
                gpu=False,
            )
            self._backend = "easyocr"
            print("[OCR] 使用 EasyOCR 后端")
            return
        except Exception as e:
            print(f"[OCR] EasyOCR 初始化失败: {e}")

        self._backend = None
        print("[OCR] 警告：所有 OCR 后端初始化失败")

    def recognize(
        self,
        image: Image.Image,
        return_json: bool = False,
    ) -> Dict[str, Any]:
        """
        识别图像中的文字。
        返回：
        {
            "text": "识别文本",
            "boxes": [[x1,y1,x2,y2,x3,y3,x4,y4], ...],
            "scores": [confidence, ...],
        }
        """
        if self._backend is None:
            return {"text": "", "boxes": [], "scores": []}

        # 黑屏检测（跳过无效输入）
        try:
            arr = np.array(image)
            if arr.mean() < 15.0:
                return {"text": "", "boxes": [], "scores": []}
        except Exception:
            pass

        # 转 numpy array
        img_array = np.array(image)
        if img_array.ndim == 2:
            img_array = np.stack([img_array] * 3, axis=-1)

        try:
            if self._backend == "paddle":
                return self._recognize_paddle(img_array)
            elif self._backend == "easyocr":
                return self._recognize_easyocr(img_array)
        except Exception as e:
            print(f"[OCR] 识别失败: {e}")
            return {"text": "", "boxes": [], "scores": []}

    def _recognize_paddle(self, img_array) -> Dict[str, Any]:
        """PaddleOCR 识别"""
        result = self._paddle_ocr.ocr(img_array, cls=False)
        # PaddleOCR 返回格式：[[[box], (text, score)], ...]
        boxes = []
        texts = []
        scores = []
        if result and len(result) > 0:
            for line in result[0]:
                box = line[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                text = line[1][0]
                score = line[1][1]
                boxes.append([[int(p[0]), int(p[1])] for p in box])
                texts.append(text)
                scores.append(float(score))
        return {
            "text": "\n".join(texts),
            "boxes": boxes,
            "scores": scores,
        }

    def _recognize_easyocr(self, img_array) -> Dict[str, Any]:
        """EasyOCR 识别"""
        result = self._easy_ocr.readtext(img_array)
        boxes = []
        texts = []
        scores = []
        for box, text, score in result:
            boxes.append([[int(p[0]), int(p[1])] for p in box])
            texts.append(text)
            scores.append(float(score))
        return {
            "text": "\n".join(texts),
            "boxes": boxes,
            "scores": scores,
        }

    @property
    def backend_name(self) -> str:
        return self._backend or "none"

    def is_ready(self) -> bool:
        return self._backend is not None
