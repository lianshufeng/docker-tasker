from typing import Any

import asyncio
import logging
import random

from pyppeteer import launch
from pyppeteer.element_handle import ElementHandle
from pyppeteer.page import Page
from pyppeteer.browser import Browser

from .base import PlatformAction, getChromeExecutablePath, ActionResult, ActionResultItem

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

width = 800
height = 600

async def get_page_list(page: Page, result: ActionResult):
    scroll_list_element: ElementHandle = await page.waitForSelector('[class="video-list row"]', timeout=3000)

    if scroll_list_element:
        await scroll_list_element.press('PageDown')
        await scroll_list_element.press('PageDown')
        await scroll_list_element.press('PageDown')
        await scroll_list_element.press('PageDown')
        await asyncio.sleep(0.5)

        row_lists = await scroll_list_element.querySelectorAll('[class*="video-list-item"]')
        num = 1
        print("当页数量： %d" % len(row_lists))
        for row in row_lists:
            try:
                a_element: ElementHandle = await row.querySelector('a[href]')
                if a_element:

                    # 视频地址
                    href = await page.evaluate('(element) => element.href', a_element)

                    title = ''
                    title_element = await row.querySelector('[class="bili-video-card__info--tit"]')
                    if title_element:
                        title = await page.evaluate('(element) => element.title', title_element)

                    logger.info(f"结果：{num} {title} -> {href}")
                    result.items.append(ActionResultItem(url=href, title=title))
                num += 1
            except Exception as e:
                logger.error(e)
                continue

async def run_work(keyword: str, page: Page, result: ActionResult):
    result.items = []

    await page.setViewport({'width': width, 'height': height, 'deviceScaleFactor': 1})

    url = "https://search.bilibili.com/video?keyword={}&pubtime_begin_s=1748448000&pubtime_end_s=1748534399&order=pubdate".format(
        keyword)
    await page.goto(url)
    print("打开网站")

    await get_page_list(page, result) # 得到当前页数据

    if len(result.items) > 0:
        while True:
            print("翻页")
            page_div = await page.querySelector('[class="vui_pagenation--btns"]')
            if page_div:
                buts = await page_div.querySelectorAll('button')
                if len(buts) > 1:
                    next_but = buts[len(buts) - 1]
                    class_name = await page.evaluate('(element) => element.className', next_but)
                    if class_name and class_name.find('vui_button--disabled') == -1:  # 下一页能点击
                        await next_but.click()  # 翻页
                        await asyncio.sleep(2)
                        await get_page_list(page, result)
                    else:
                        break
                else:
                    break
            else:
                break

    # 取出cookies
    # 获取所有 cookies
    cookies = await page.cookies()
    # 拼接成字符串
    cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
    result.cookies = cookie_str


class BPlatformAction(PlatformAction):

    async def action(self, keyword: str, cookies: str = None) -> ActionResult:
        chrome: list[str] = getChromeExecutablePath()
        chrome_path = chrome[0] if chrome else None
        if chrome_path is None:
            raise RuntimeError("未找到可用的chrome")

        # 保存的结果集
        result: ActionResult = ActionResult()

        browser: Browser = await launch(
            headless=False,  # 无头模式
            executablePath=chrome_path,  # chrome路径
            args=[
                '--incognito',  # 无痕
                '--disable-infobars',  # 取消提示正在被受控制
                '--disable-blink-features=AutomationControlled',
                f'--window-size={width},{height}'  # 这里设置窗口分辨率为1280x800
            ],
            ignoreDefaultArgs=['--enable-automation'],  # 隐藏提示栏
        )
        page: Page = await browser.newPage()

        #  cookies
        if cookies is not None:
            # 需要恢复为 setCookie 用的格式
            cookie_list = [
                {'name': k, 'value': v, 'url': 'https://search.bilibili.com/'}
                for k, v in (item.strip().split('=', 1) for item in cookies.split(';') if '=' in item)
            ]
            await page.setCookie(*cookie_list)

        try:
            await run_work(keyword=keyword, page=page, result=result)
        except Exception as e:
            logger.error('error: ',e)
        finally:
            await browser.close()
        return result
