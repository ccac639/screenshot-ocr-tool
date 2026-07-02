"""
去重模块（pHash + SSIM）
两层稳定机制第一层：过滤重复帧，防止滚动停滞。
"""

from PIL import Image
import numpy as np

try:
    from imagehash import phash, dhash
    _HAVE_IMAGEHASH = True
except ImportError:
    _HAVE_IMAGEHASH = False

try:
    from skimage.metrics import structural_similarity as ssim
    _HAVE_SKIMAGE = True
except ImportError:
    _HAVE_SKIMAGE = False


def calc_phash(img: Image.Image, hash_size: int = 16) -> "imagehash.ImageHash":
    """计算感知哈希（pHash）"""
    if _HAVE_IMAGEHASH:
        return phash(img, hash_size=hash_size)
    else:
        # fallback: 简易 hash
        import hashlib
        arr = np.array(img.convert("L").resize((32, 32)))
        return hashlib.md5(arr.tobytes()).hexdigest()


def calc_ssim(img_a: Image.Image, img_b: Image.Image) -> float:
    """
    计算结构相似度（SSIM）
    返回：0~1，1=完全相同
    """
    if _HAVE_SKIMAGE:
        a = np.array(img_a.convert("L"))
        b = np.array(img_b.convert("L"))
        if a.shape != b.shape:
            # resize 到相同尺寸
            b = np.array(img_b.convert("L").resize(a.shape[::-1]))
        score = ssim(a, b, data_range=255)
        return float(score)
    else:
        # fallback: MSE
        a = np.array(img_a.convert("L"), dtype=np.float32)
        b = np.array(img_b.convert("L").resize(a.shape[::-1]), dtype=np.float32)
        mse = np.mean((a - b) ** 2)
        if mse == 0:
            return 1.0
        return float(1.0 / (1.0 + mse / 255.0))


def frames_are_duplicate(img_a: Image.Image, img_b: Image.Image,
                        phash_threshold: int = 8,
                        ssim_threshold: float = 0.92) -> bool:
    """
    判断两帧是否重复（两层检测）。
    返回 True 表示「重复/极相似」，应跳过。
    """
    # 第一层：pHash（速度快）
    if _HAVE_IMAGEHASH:
        h_a = calc_phash(img_a)
        h_b = calc_phash(img_b)
        phash_dist = h_a - h_b
        if phash_dist <= phash_threshold:
            # 第二层：SSIM（更准）
            ssim_score = calc_ssim(img_a, img_b)
            return ssim_score >= ssim_threshold
        return False
    else:
        # fallback: 只用 SSIM
        return calc_ssim(img_a, img_b) >= ssim_threshold


def hash_distance(img_a: Image.Image, img_b: Image.Image) -> int:
    """返回两张图的 pHash 汉明距离"""
    if _HAVE_IMAGEHASH:
        return int(calc_phash(img_a) - calc_phash(img_b))
    return 0
