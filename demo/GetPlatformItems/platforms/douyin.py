import asyncio
import logging
import os
import random
import time

import pyautogui
from pyppeteer import launch
from pyppeteer.browser import Browser
from pyppeteer.element_handle import ElementHandle
from pyppeteer.page import Page

from .base import PlatformAction, getChromeExecutablePath, ActionResult, ActionResultItem

# 日志配置，建议你根据生产环境实际需要调整
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

width = 800
height = 600

douyin_page_home = 'https://www.douyin.com'



async def cancel_xdg_open_button():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    img_path = os.path.join(script_dir, 'images', 'cancel_xdg_open_button.png')
    while True:
        try:
            location = pyautogui.locateOnScreen(img_path, confidence=0.85)  # 可调整置信度
            if location:
                x, y = pyautogui.center(location)
                pyautogui.moveTo(x, y, duration=0.1)
                pyautogui.click()
                print(f"已自动点击 '取消' 按钮，位置: ({x}, {y})")
                await asyncio.sleep(1)  # 点过后休息1秒，防止连点
            else:
                await asyncio.sleep(0.2)  # 没找到就快速重试
        except Exception as e:
            pass
        finally:
            await asyncio.sleep(0.2)



# 异步执行，发现就关闭登录面板
async def close_login_panel(page: Page, is_exit: bool):
    while True:
        try:
            parent = await page.querySelector("#login-panel-new")
            if parent:
                span_element = await parent.querySelector('svg')
                if span_element:
                    await span_element.click()
                    logger.info("关闭登录面板")
                    if is_exit:
                        break
        except Exception as e:
            logger.info(f"查找或关闭时出错: {e}")
        await asyncio.sleep(0.1)  # 周期检查


async def run_work(keyword: str, page: Page, result: ActionResult):
    result.items = []

    # #增强，防止被检测到
    # await pyppeteer_stealth.stealth(page)

    await page.setViewport({'width': width, 'height': height, 'deviceScaleFactor': 1})

    # 打开新的页面
    await page.goto(douyin_page_home)

    # 开启一定有一个登录弹窗，如果这个窗口不关闭后面的任务执行不完成，所以在这里阻塞直到结束
    await close_login_panel(page, True)

    # 异步线程关闭黄口
    # asyncio.create_task(close_login_panel(page, False))

    # 输入框搜索关键词------------------------------
    input_element = await page.waitForSelector('[data-e2e="searchbar-input"]', timeout=5000)
    if input_element:
        logger.info(f"搜索框输入: {keyword}")
        await input_element.click()  # 有些页面要先激活一下输入框
        await asyncio.sleep(0.5)
        await input_element.type(keyword, {'delay': 30})
        await asyncio.sleep(1)
        await input_element.press('Enter')

    # 选择仅过滤视频列表------------------------------
    video_btn = await page.waitForXPath('//*[@id="search-content-area"]/div/div[1]/div[1]/div[1]/div/div/span[2]',
                                        timeout=5000)
    if video_btn:
        logger.info("选择仅过滤视频")
        await video_btn.click()
        await asyncio.sleep(1)

    # 选择过滤时间------------------------------
    where_btn: ElementHandle = await page.waitForXPath(
        '//*[@id="search-content-area"]/div/div[1]/div[1]/div/div/div/div/span',
        timeout=3000)
    if where_btn:
        logger.info("触发筛选按钮")

        # await page.evaluate('el => {'
        #                     'el.dispatchEvent(new MouseEvent("mouseenter", {bubbles: true}));'
        #                     'el.dispatchEvent(new MouseEvent("mouseover", {bubbles: true}));'
        #                     'el.dispatchEvent(new MouseEvent("mousemove", {bubbles: true}));'
        #                     '}', where_btn)

        await where_btn.hover()
        await asyncio.sleep(1)

        # 过滤最近一周
        week_btn = await page.waitForXPath(
            '//*[@id="search-content-area"]/div/div[1]/div[1]/div[1]/div/div/div/div/div[2]/span[2]', timeout=3000)
        if week_btn:
            logger.info("过滤最近1天视频")
            await week_btn.click()
            await asyncio.sleep(1)

        # 隐藏筛选弹窗
        await where_btn.click()

    # 找到列表项
    scroll_list_element: ElementHandle = await page.waitForSelector('[data-e2e="scroll-list"]', timeout=3000)
    if scroll_list_element:

        # 模拟点击空白处，获取焦点
        scroll_list_element_content: dict = (await scroll_list_element.boxModel()).get('content')[0]
        x = scroll_list_element_content['x'] - random.randint(10, 20)
        y = scroll_list_element_content['y'] + random.randint(10, 30)
        await  page.mouse.click(x=x, y=y)

        # 记录当前加载项
        latest_li_len: int = len(await scroll_list_element.querySelectorAll('li'))

        # 通过翻页按钮按钮进行翻页操作
        for _ in range(120):
            await scroll_list_element.press('PageDown')
            await asyncio.sleep(0.8)  # 间隔时间等待加载
            now_li_len: int = len(await scroll_list_element.querySelectorAll('li'))
            # 如果刷新没有新视频
            if now_li_len == latest_li_len:
                await asyncio.sleep(3)
                await scroll_list_element.press('PageDown')
                await asyncio.sleep(0.8)  # 间隔时间等待加载
                if len(await scroll_list_element.querySelectorAll('li')) == latest_li_len:
                    break
            latest_li_len = now_li_len
            logger.info('load items : ' + str(latest_li_len))

        # 开始取出所有的标题与url
        li_elements: list[ElementHandle] = await scroll_list_element.querySelectorAll('li')
        logger.info('total items : ' + str(len(li_elements)))
        for li in li_elements:
            try:
                # 获取视频链接
                a_element: ElementHandle = await li.querySelector('a[href]')
                if a_element:
                    # 连接地址
                    href = await page.evaluate('(element) => element.href', a_element)

                    # 标题
                    # title_element = await a_element.querySelector('div > div:nth-child(2) > div > div:nth-child(1)')
                    # title = await page.evaluate('(element) => element.textContent', title_element)
                    title_element: ElementHandle = (await a_element.querySelectorAll("div"))[15]
                    title = await page.evaluate('(element) => element.textContent', title_element)
                    logger.info(f"{title} -> {href}")
                    result.items.append(ActionResultItem(url=href, title=title))
            except Exception as e:
                continue

        # 取出cookies
        # 获取所有 cookies
        cookies = await page.cookies()
        # 拼接成字符串
        cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
        result.cookies = cookie_str


class DouyinPlatformAction(PlatformAction):

    async def action(self, keyword: str, cookies: str = None) -> ActionResult:


        # 异步xdg_窗口
        asyncio.create_task(cancel_xdg_open_button())



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
                f'--window-size={width},{height}',  # 这里设置窗口分辨率
                '--window-position=0,0',  # 这里指定窗口起始坐标
            ],
            ignoreDefaultArgs=['--enable-automation'],  # 隐藏提示栏
        )
        page: Page = await browser.newPage()


        #  cookies
        if cookies is not None:
            # 需要恢复为 setCookie 用的格式
            cookie_list = [
                {'name': k, 'value': v, 'url': douyin_page_home}
                for k, v in (item.strip().split('=', 1) for item in cookies.split(';') if '=' in item)
            ]
            await page.setCookie(*cookie_list)

        try:
            await run_work(keyword=keyword, page=page, result=result)
        except Exception as e:
            logger.error(e)
        finally:
            await browser.close()

        return result
