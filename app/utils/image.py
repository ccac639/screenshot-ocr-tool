"""
图像处理工具
包含：图像拼接、去重检测、固定头部检测、重叠定位（v3 版）。
"""

from PIL import Image
import numpy as np


def pil_to_numpy(img: Image.Image) -> np.ndarray:
    """PIL Image -> numpy array (H, W, C) RGB"""
    if img.mode != "RGB":
        img = img.convert("RGB")
    return np.array(img)


def numpy_to_pil(arr: np.ndarray) -> Image.Image:
    """numpy array -> PIL Image"""
    return Image.fromarray(arr.astype(np.uint8))


def images_are_similar(img_a: Image.Image, img_b: Image.Image,
                       threshold: float = 0.97) -> bool:
    """判断两张图是否相似（pixel 级比较，threshold=相似像素比例）"""
    a = pil_to_numpy(img_a)
    b = pil_to_numpy(img_b)
    if a.shape != b.shape:
        return False
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16))
    # 允许单像素差异 ≤30 灰度值
    similar_pixels = (diff <= 30).sum()
    total_pixels = a.shape[0] * a.shape[1] * a.shape[2]
    return (similar_pixels / total_pixels) >= threshold


def detect_fixed_header_v3(frames: list, threshold: float = 3.0) -> int:
    """
    逐行扫描检测所有帧顶部相同的固定内容（如浏览器标签栏）。
    返回：需要裁剪掉的固定头部高度（像素），0 表示无。
    """
    if len(frames) < 2:
        return 0

    arrays = [pil_to_numpy(f) for f in frames]
    h = min(a.shape[0] for a in arrays)
    ref = arrays[0][:h, :, :]

    fixed_h = 0
    for row in range(h - 1):
        is_fixed = True
        ref_row = ref[row, :, :]
        for arr in arrays[1:]:
            if arr.shape[0] <= row:
                is_fixed = False
                break
            cur_row = arr[row, :, :]
            diff = np.abs(ref_row.astype(np.int16) - cur_row.astype(np.int16))
            if diff.mean() > threshold:
                is_fixed = False
                break
        if not is_fixed:
            break
        fixed_h = row + 1

    return fixed_h


def find_overlap_ssd(img_prev: np.ndarray, img_cur: np.ndarray,
                     search_range: int = 120) -> int:
    """
    在 img_cur 中搜索与 img_prev 底部最匹配的位置（SSD 平方差和最小）。
    先粗搜（step=2）定位，再精修（±15px）。
    返回：img_cur 中重叠起始行号（0=完全无重叠）。
    """
    ph, pw = img_prev.shape[:2]
    ch = img_cur.shape[0]
    overlap_max = min(ph // 2, ch, search_range)
    if overlap_max <= 0:
        return 0

    prev_bottom = img_prev[-overlap_max:, :, :]

    # 粗搜
    best_offset = 0
    best_ssd = float("inf")
    for offset in range(0, min(ch, overlap_max + 1), 2):
        cur_slice = img_cur[offset:offset + overlap_max, :, :]
        sz = min(prev_bottom.shape[0], cur_slice.shape[0])
        if sz == 0:
            break
        ssd = float(np.sum((prev_bottom[:sz, :, :] - cur_slice[:sz, :, :]) ** 2))
        if ssd < best_ssd:
            best_ssd = ssd
            best_offset = offset

    # 精修 ±15px
    fine_start = max(0, best_offset - 15)
    fine_end = min(ch, best_offset + 16)
    for offset in range(fine_start, fine_end):
        cur_slice = img_cur[offset:offset + overlap_max, :, :]
        sz = min(prev_bottom.shape[0], cur_slice.shape[0])
        if sz == 0:
            break
        ssd = float(np.sum((prev_bottom[:sz, :, :] - cur_slice[:sz, :, :]) ** 2))
        if ssd < best_ssd:
            best_ssd = ssd
            best_offset = offset

    return best_offset


def stitch_vertical(frames: list, overlap_remove: bool = True) -> Image.Image:
    """
    垂直拼接多帧，自动去除重叠部分。
    使用 detect_fixed_header_v3 + find_overlap_ssd。
    """
    if len(frames) == 0:
        raise ValueError("No frames to stitch")
    if len(frames) == 1:
        return frames[0]

    arrays = [pil_to_numpy(f) for f in frames]

    # 检测并裁剪固定头部
    fixed_h = detect_fixed_header_v3(frames) if len(frames) > 1 else 0

    result = arrays[0][fixed_h:, :, :]
    for i in range(1, len(arrays)):
        cur = arrays[i][fixed_h:, :, :]
        if overlap_remove:
            overlap = find_overlap_ssd(result, cur)
            if overlap > 0:
                cur = cur[overlap:, :, :]
        result = np.concatenate([result, cur], axis=0)

    return numpy_to_pil(result)


def image_to_bytes(pil_img: Image.Image, fmt: str = "PNG") -> bytes:
    """PIL Image -> bytes"""
    import io
    buf = io.BytesIO()
    pil_img.save(buf, format=fmt)
    return buf.getvalue()
