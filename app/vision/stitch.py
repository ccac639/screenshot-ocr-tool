"""
图像拼接模块（Layer 3 输出）
使用 align 模块精准定位重叠位置，消除硬切痕迹。
"""

from PIL import Image
import numpy as np

from app.vision.dedup import frames_are_duplicate
from app.vision.align import find_overlap_offset, find_overlap_ssim


def stitch_vertical(frames: list, overlap_remove: bool = True,
                    search_height: int = 150) -> Image.Image:
    """
    垂直拼接多帧，自动去除重叠部分。
    
    算法：
      1. 检测并裁剪所有帧顶部相同的固定内容（如浏览器标签栏）
      2. 逐帧用 SSD/template matching 找最佳重叠偏移
      3. 只追加新内容部分（消除硬切）
    
    参数：
        frames: PIL Image 列表
        overlap_remove: 是否自动去除重叠
        search_height: 重叠搜索高度（像素）
    
    返回：拼接后的 PIL Image
    """
    if len(frames) == 0:
        raise ValueError("No frames to stitch")
    if len(frames) == 1:
        return frames[0]

    arrays = [np.array(f.convert("RGB")) for f in frames]

    # 检测固定头部（所有帧顶部相同的内容）
    fixed_h = _detect_fixed_header(arrays, threshold=3.0)
    if fixed_h > 0:
        print(f"[Stitch] 检测到固定头部 {fixed_h}px，已自动裁剪")

    # 从第一帧开始拼接
    result = arrays[0][fixed_h:, :, :]

    for i in range(1, len(arrays)):
        cur = arrays[i][fixed_h:, :, :]

        if overlap_remove and len(result) > 0:
            # 用 SSD 找最佳重叠偏移
            offset = find_overlap_offset(result, cur, search_height=search_height)
            if offset > 0:
                # 只追加非重叠部分
                cur = cur[offset:, :, :]
                if len(cur) == 0:
                    continue  # 完全重叠，跳过

        result = np.concatenate([result, cur], axis=0)

    return Image.fromarray(result.astype(np.uint8))


def _detect_fixed_header(arrays: list, threshold: float = 3.0) -> int:
    """
    逐行扫描检测所有帧顶部相同的固定内容。
    返回：需要裁剪掉的固定头部高度（像素）
    """
    if len(arrays) < 2:
        return 0

    h = min(a.shape[0] for a in arrays)
    if h < 10:
        return 0

    fixed_h = 0
    ref = arrays[0][:h, :, :]

    for row in range(h - 1):
        is_fixed = True
        ref_row = ref[row, :, :]

        for arr in arrays[1:]:
            if arr.shape[0] <= row:
                is_fixed = False
                break
            cur_row = arr[row, :, :]
            diff = np.abs(ref_row.astype(np.int16) - cur_row.astype(np.int16))
            if np.mean(diff) > threshold:
                is_fixed = False
                break

        if not is_fixed:
            break
        fixed_h = row + 1

    return fixed_h


def blend_seam(img_top: np.ndarray, img_bot: np.ndarray,
                offset: int, blend_px: int = 20) -> np.ndarray:
    """
    在拼接处做渐变融合（消除硬切痕迹）。
    返回融合后的 img_bot（从 offset 开始融合）。
    """
    if blend_px <= 0 or offset <= 0:
        return img_bot

    blend_h = min(blend_px, img_bot.shape[0] - offset)
    if blend_h <= 0:
        return img_bot

    # 渐变权重
    alpha = np.linspace(0, 1, blend_h).reshape(-1, 1, 1)

    top_region = img_top[-blend_h:, :, :].astype(np.float32)
    bot_region = img_bot[offset:offset + blend_h, :, :].astype(np.float32)

    blended = (1 - alpha) * top_region + alpha * bot_region

    result = img_bot.copy()
    result[offset:offset + blend_h, :, :] = blended.astype(np.uint8)
    return result
