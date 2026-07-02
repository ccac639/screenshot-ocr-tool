"""
日志工具模块 V2.1
为整个应用程序提供统一的日志记录功能。
"""

import os
import logging
import logging.handlers
from datetime import datetime, timedelta
from pathlib import Path

LOG_DIR = Path.home() / ".screenshot_ocr" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)-20s %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LOG_FILE_PREFIX = "screenshot_ocr"
MAX_LOG_DAYS = 7
MAX_LOG_SIZE = 10 * 1024 * 1024


def setup_logging(level=logging.DEBUG, console_level=logging.INFO, log_to_file=True):
    """初始化日志系统"""
    _cleanup_old_logs()
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    if log_to_file:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOG_DIR / f"{LOG_FILE_PREFIX}_{today}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=MAX_LOG_SIZE, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        print(f"[Logging] 日志文件: {log_file}")
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的logger"""
    return logging.getLogger(name)


def _cleanup_old_logs():
    """清理过期日志"""
    if not LOG_DIR.exists():
        return
    cutoff_date = datetime.now() - timedelta(days=MAX_LOG_DAYS)
    for log_file in LOG_DIR.glob(f"{LOG_FILE_PREFIX}_*.log*"):
        try:
            parts = log_file.stem.split("_")
            if len(parts) >= 2:
                date_str = parts[-1]
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff_date:
                    log_file.unlink()
        except (ValueError, IndexError):
            continue


__all__ = ["setup_logging", "get_logger", "LOG_DIR"]
