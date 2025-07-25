import logging
from datetime import datetime
import os
import subprocess
import sys

import cv2
import numpy as np

# 日志配置
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)



def set_display_xauth():
    if sys.platform.startswith("win"):
        return
    # 只要没设，就查找并设置
    if 'DISPLAY' not in os.environ or not os.environ['DISPLAY']:
        out = subprocess.getoutput(
            "ps aux | grep '[X]vfb' | awk '{for(i=1;i<=NF;i++) if($i ~ /^:[0-9]+$/) {gsub(\":\",\"\",$i); print $i}}'"
        )
        if out.strip():
            os.environ['DISPLAY'] = f":{out.strip()}"
    if 'XAUTHORITY' not in os.environ or not os.environ['XAUTHORITY']:
        out = subprocess.getoutput(
            "ps aux | grep '[X]vfb' | grep -oP '(?<=-auth )[^ ]+'"
        )
        if out.strip():
            os.environ['XAUTHORITY'] = out.strip()


# 优先设置环境变量
set_display_xauth()

import pyautogui


def find_and_click_image(template_path, threshold=0.8):
    """
    在屏幕截图中查找 template_path 指定的图像，并点击其中心点（无需保存截图到磁盘）。
    """
    # 检查模板是否存在
    if not os.path.exists(template_path):
        print(f"模板图片未找到: {template_path}")
        return False

    # 内存中获取截图 (PIL 格式)
    screenshot_pil = pyautogui.screenshot()

    # 转为 OpenCV 格式（numpy array, BGR）
    screenshot_cv = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)

    # 加载模板图像
    template = cv2.imread(template_path)
    if template is None:
        print(f"无法读取模板图片: {template_path}")
        return False
    h, w = template.shape[:2]

    # 模板匹配
    res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    logging.info(f"[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 查询屏幕图片 : {template_path} , 相似度: {max_val:.3f}/{threshold}")

    if max_val >= threshold:
        center_x = max_loc[0] + w // 2
        center_y = max_loc[1] + h // 2
        pyautogui.moveTo(center_x, center_y)
        pyautogui.click()
        logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 点击位置 : ({center_x}, {center_y}) 来自模板: {template_path}")
        return True
    else:
        return False
