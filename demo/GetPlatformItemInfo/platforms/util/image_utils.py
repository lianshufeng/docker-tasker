import os
import subprocess
import sys

import cv2


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

def find_and_click_image(template_path, threshold=0.8, screenshot_path='screen.png'):
    """
    在全屏截图中查找template_path指定的图片，并在该图片中心点击。
    参数:
        template_path (str): 模板图片路径
        threshold (float): 匹配相似度阈值，默认0.8
        screenshot_path (str): 截图保存路径
    返回:
        True 表示点击成功，False 表示未匹配到图片
    """

    # 1. 检查模板图片文件是否存在
    if not os.path.exists(template_path):
        print(f"模板图片未找到: {template_path}")
        return False

    # 2. 全屏截图
    screenshot = pyautogui.screenshot()
    screenshot.save(screenshot_path)

    # 3. 读取截图和模板
    img_rgb = cv2.imread(screenshot_path)
    template = cv2.imread(template_path)
    if img_rgb is None:
        print(f"无法读取截图文件: {screenshot_path}")
        return False
    if template is None:
        print(f"无法读取模板图片文件: {template_path}")
        return False
    h, w = template.shape[:2]

    # 4. 模板匹配
    res = cv2.matchTemplate(img_rgb, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    print(f"最大相似度: {max_val:.3f}")

    if max_val >= threshold:
        center_x = max_loc[0] + w // 2
        center_y = max_loc[1] + h // 2
        pyautogui.moveTo(center_x, center_y)
        pyautogui.click()
        print(f"已点击图片中心: ({center_x}, {center_y})")
        return True
    else:
        print("未找到相似度足够的图片")
        return False