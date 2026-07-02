"""
重叠对齐模块（Layer 2 稳定机制）
上一帧 bottom 区域 vs 下一帧 top 区域
template matching 找最佳匹配偏移。
"""

from PIL import Image
import numpy as np


def find_overlap_offset(img_prev: np.ndarray, img_cur: np.ndarray,
                         search_height: int = 150,
                         fine_range: int = 20) -> int:
    """
    在 img_cur 中搜索与 img_prev 底部最匹配的位置。
    
    算法：
      1. 取 img_prev 底部 search_height 像素（bottom_region）
      2. 在 img_cur 顶部 0~search_height*2 范围内滑动搜索
      3. 用 SSD（平方差和）找最佳匹配
      4. 在粗匹配位置 ±fine_range 内精修
    
    返回：img_cur 中重叠起始行号（0=完全无重叠）
    """
    ph, pw = img_prev.shape[:2]
    ch = img_cur.shape[0]
    
    # 取 prev 底部区域
    bottom_h = min(search_height, ph // 2)
    if bottom_h <= 0:
        return 0
    prev_bottom = img_prev[-bottom_h:, :, :]
    
    # 搜索范围：cur 的顶部 0~bottom_h*2 行
    search_max = min(ch, bottom_h * 2)
    if search_max <= 0:
        return 0
    
    # 粗搜（step=2 加速）
    best_offset = 0
    best_ssd = float("inf")
    
    for offset in range(0, search_max, 2):
        cur_slice = img_cur[offset:offset + bottom_h, :, :]
        sz = min(prev_bottom.shape[0], cur_slice.shape[0])
        if sz == 0:
            break
        # SSD（平方差和）
        ssd = float(np.sum(
            (prev_bottom[:sz, :, :].astype(np.int32) - 
             cur_slice[:sz, :, :].astype(np.int32)) ** 2
        ))
        if ssd < best_ssd:
            best_ssd = ssd
            best_offset = offset
    
    # 精修 ±fine_range
    fine_start = max(0, best_offset - fine_range)
    fine_end = min(ch, best_offset + fine_range + 1)
    for offset in range(fine_start, fine_end):
        cur_slice = img_cur[offset:offset + bottom_h, :, :]
        sz = min(prev_bottom.shape[0], cur_slice.shape[0])
        if sz == 0:
            break
        ssd = float(np.sum(
            (prev_bottom[:sz, :, :].astype(np.int32) - 
             cur_slice[:sz, :, :].astype(np.int32)) ** 2
        ))
        if ssd < best_ssd:
            best_ssd = ssd
            best_offset = offset
    
    return best_offset


def find_overlap_ssim(img_prev: np.ndarray, img_cur: np.ndarray,
                       search_height: int = 150) -> int:
    """
    用 SSIM 找最佳重叠偏移（更准但更慢）。
    仅当 imagehash + skimage 可用时使用。
    """
    try:
        from skimage.metrics import structural_similarity as ssim
        ph, pw = img_prev.shape[:2]
        ch = img_cur.shape[0]
        bottom_h = min(search_height, ph // 2)
        if bottom_h <= 0:
            return 0
        
        prev_bottom = img_prev[-bottom_h:, :, :].astype(np.float32)
        best_offset = 0
        best_ssim = -1.0
        
        for offset in range(0, min(ch, bottom_h * 2)):
            cur_slice = img_cur[offset:offset + bottom_h, :, :].astype(np.float32)
            sz = min(prev_bottom.shape[0], cur_slice.shape[0])
            if sz == 0:
                break
            # 转灰度算 SSIM
            pb_gray = np.mean(prev_bottom[:sz, :, :], axis=2)
            cs_gray = np.mean(cur_slice[:sz, :, :], axis=2)
            score = ssim(pb_gray, cs_gray, data_range=255.0)
            if score > best_ssim:
                best_ssim = score
                best_offset = offset
        
        return best_offset
    except Exception:
        return find_overlap_offset(img_prev, img_cur, search_height)


def compute_overlap_region(img_a: Image.Image, img_b: Image.Image,
                           overlap_px: int = 100) -> float:
    """
    计算两张图重叠区域的相似度（0~1）。
    用于判断是否已到底部。
    """
    a = np.array(img_a.convert("RGB"), dtype=np.float32)
    b = np.array(img_b.convert("RGB").resize((img_a.width, img_a.height)), 
                  dtype=np.float32)
    if overlap_px > a.shape[0]:
        overlap_px = a.shape[0] // 2
    
    region_a = a[-overlap_px:, :, :]
    region_b = b[-overlap_px:, :, :]
    mse = np.mean((region_a - region_b) ** 2)
    # 转成相似度
    if mse == 0:
        return 1.0
    return float(1.0 / (1.0 + mse / (255.0 ** 2)))
