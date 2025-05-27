import asyncio
from typing import Any

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
                    # break  # 找到并关闭后退出循环
        except Exception as e:
            print(f"查找或关闭时出错: {e}")
        await asyncio.sleep(1)  # 每1s检查一次


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
                f'--window-size={width},{height}'  # 这里设置窗口分辨率为1280x800
            ],
        )
        page: Page = await browser.newPage()
        await page.setViewport({'width': width, 'height': height, 'deviceScaleFactor': 1})

        # 打开新的页面
        await page.goto('https://www.douyin.com')

        # 启动异步任务去关闭弹窗
        close_panel_task = asyncio.create_task(close_login_panel(page))

        # 找到输入框
        input_element = await page.waitForSelector('[data-e2e="searchbar-input"]',timeout=3000)
        if input_element:
            print("找到了搜索输入框")
            await input_element.click()  # 有些页面要先激活一下输入框
            await asyncio.sleep(0.3)
            await input_element.type(keyword, {'delay': 200})
            await asyncio.sleep(0.3)
            await input_element.press('Enter')




        # 你的主逻辑，可以等待弹窗被关闭或做别的事


        await asyncio.sleep(600)  # 这里只是模拟其它操作（10分钟）
        await browser.close()

        return [
            {"url": "https://www.douyin.com/", "title": "test_title1"},
            {"url": "https://www.douyin.com/", "title": "test_title2"}
        ]
