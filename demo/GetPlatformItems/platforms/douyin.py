import asyncio
import random
from typing import Any

import pyppeteer_stealth
from pyppeteer import launch
from pyppeteer.page import Page

from .base import PlatformAction, getChromeExecutablePath

width = 1280
height = 800


# 异步执行，发现就关闭登录面板
async def close_login_panel(page: Page):
    while True:
        try:
            parent = await page.querySelector("#login-panel-new")
            if parent:
                span_element = await parent.querySelector('svg')
                if span_element:
                    await span_element.click()
                    print("关闭登录面板")
                    break  # 找到并关闭后退出循环
        except Exception as e:
            print(f"查找或关闭时出错: {e}")
        await asyncio.sleep(0.1)  # 周期检查


class DouyinPlatformAction(PlatformAction):

    async def action(self, keyword: str) -> list[dict[str, Any]]:
        chrome: list[str] = getChromeExecutablePath()
        chrome_path = chrome[0] if chrome else None
        if chrome_path is None:
            raise RuntimeError("未找到可用的chrome")

        browser = await launch(
            headless=False,  # 无头模式
            executablePath=chrome_path,  # chrome路径
            args=[
                '--incognito',  # 无痕
                '--disable-infobars', #取消提示正在被受控制
                '--disable-blink-features=AutomationControlled',
                f'--window-size={width},{height}'  # 这里设置窗口分辨率为1280x800
            ],
        )
        page: Page = await browser.newPage()

        # #增强，防止被检测到
        # await pyppeteer_stealth.stealth(page)

        await page.setViewport({'width': width, 'height': height, 'deviceScaleFactor': 1})

        # 打开新的页面
        await page.goto('https://www.douyin.com')

        # 开启一定有一个登录弹窗，如果这个窗口不关闭后面的任务执行不完成，所以在这里阻塞直到结束
        # asyncio.create_task(close_login_panel(page))
        await close_login_panel(page)

        # 输入框搜索关键词------------------------------
        input_element = await page.waitForSelector('[data-e2e="searchbar-input"]', timeout=5000)
        if input_element:
            print("找到了搜索输入框")
            await input_element.click()  # 有些页面要先激活一下输入框
            await asyncio.sleep(0.5)
            await input_element.type(keyword, {'delay': 30})
            await asyncio.sleep(1)
            await input_element.press('Enter')
            # await page.keyboard.press('Enter')

        # 选择仅过滤视频列表------------------------------
        video_btn = await page.waitForXPath('//*[@id="search-content-area"]/div/div[1]/div[1]/div[1]/div/div/span[2]',
                                            timeout=5000)
        if video_btn:
            print("选择仅过滤视频")
            await video_btn.click()

        # 选择过滤时间------------------------------
        where_btn = await page.waitForXPath('//*[@id="search-content-area"]/div/div[1]/div[1]/div/div/div/div/span',
                                            timeout=3000)
        if where_btn:
            print("触发筛选按钮")
            await page.evaluate('el => {'
                                'el.dispatchEvent(new MouseEvent("mouseenter", {bubbles: true}));'
                                'el.dispatchEvent(new MouseEvent("mouseover", {bubbles: true}));'
                                'el.dispatchEvent(new MouseEvent("mousemove", {bubbles: true}));'
                                '}', where_btn)
            await asyncio.sleep(1)
            # 过滤最近一周
            week_btn = await page.waitForXPath(
                '//*[@id="search-content-area"]/div/div[1]/div[1]/div[1]/div/div/div/div/div[2]/span[2]', timeout=3000)
            if week_btn:
                print("过滤最近1天视频")
                await week_btn.click()
                await asyncio.sleep(1)
                await where_btn.click()

        # 找到列表项
        scroll_list_element = await page.waitForSelector('[data-e2e="scroll-list"]', timeout=3000)
        if scroll_list_element:
            print("2秒后滚动")
            # 1. 获取元素的位置和尺寸
            # box = await scroll_list_element.boundingBox()
            # center_x = box['x'] + box['width'] / 2
            # center_y = box['y'] + box['height'] / 2
            #
            # # 在中心区域的 40% 范围内随机偏移
            # offset_x = (random.random() - 0.5) * box['width'] * 0.4
            # offset_y = (random.random() - 0.5) * box['height'] * 0.4
            #
            # target_x = center_x + offset_x
            # target_y = center_y + offset_y

            # 2. 鼠标移动到随机点并点击以聚焦
            # await page.mouse.move(target_x, target_y)
            # await asyncio.sleep(0.1)
            # await page.mouse.click(target_x, target_y)
            # await asyncio.sleep(0.2)
            #
            # # 3. 模拟下箭头键
            # await page.keyboard.press('ArrowDown')
            # await asyncio.sleep(0.3)  # 适当等待加载效果

            # 如果你想多次加载，可以循环多次
            for _ in range(10):
                box = await scroll_list_element.boundingBox()
                center_x = box['x'] + box['width'] / 2
                center_y = box['y'] + box['height'] / 2

                # 在中心区域的 40% 范围内随机偏移
                offset_x = (random.random() - 0.5) * box['width'] * 0.4
                offset_y = (random.random() - 0.5) * box['height'] * 0.4

                target_x = center_x + offset_x
                target_y = center_y + offset_y

                # 鼠标移动到目标点
                await page.mouse.move(target_x, target_y)
                await asyncio.sleep(0.1)
                print(target_x, target_y)


                await scroll_list_element.press('ArrowDown')
                await asyncio.sleep(0.3)

        await asyncio.sleep(300)  # 这里只是模拟其它操作（10分钟）
        await browser.close()

        return [
            {"url": "https://www.douyin.com/", "title": "test_title1"},
            {"url": "https://www.douyin.com/", "title": "test_title2"}
        ]
