import asyncio
import logging
import random
import traceback
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page, Browser, ElementHandle

from .base import PlatformAction, getChromeExecutablePath, ActionResult, ActionResultItem

# 日志配置
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

width = 800
height = 600

douyin_page_home = 'https://www.douyin.com'


# 异步执行，发现就关闭登录面板
async def close_login_panel(page: Page, is_exit: bool):
    while True:
        try:
            # Playwright 推荐用 locator
            parent = await page.locator("#login-panel-new").element_handle()
            if parent:
                span_element = await parent.query_selector('svg')
                if span_element:
                    await span_element.click()
                    logger.info("关闭登录面板")
                    if is_exit:
                        break
        except Exception as e:
            logger.info(f"查找或关闭时出错: {e}")
        await asyncio.sleep(0.1)


async def run_work(keyword: str, page: Page, result: ActionResult, max_size: int):
    result.items = []

    # 设置分辨率
    await page.set_viewport_size({'width': width, 'height': height})

    # 打开首页
    await page.goto(douyin_page_home)

    # 关闭登录弹窗
    await close_login_panel(page, True)
    await asyncio.sleep(2)
    await page.goto('about:blank')
    await asyncio.sleep(0.3)
    await page.go_back()
    await close_login_panel(page, True)

    # 输入关键词
    input_element = await page.locator('[data-e2e="searchbar-input"]').element_handle(timeout=5000)
    if input_element:
        logger.info(f"搜索框输入: {keyword}")
        await input_element.click()
        await asyncio.sleep(0.5)
        await input_element.type(keyword, delay=30)
        await asyncio.sleep(1)
        await input_element.press('Enter')

    # 只看视频按钮
    video_btn = await page.locator(
        'xpath=//*[@id="search-content-area"]/div/div[1]/div[1]/div[1]/div/div/span[2]').element_handle(timeout=10000)
    if video_btn:
        logger.info("选择仅过滤视频")
        await video_btn.click()
        await asyncio.sleep(2)

    # 选择筛选时间
    where_btn = await page.locator(
        'xpath=//*[@id="search-content-area"]/div/div[1]/div[1]/div[1]/div[1]/div/div/span').element_handle(
        timeout=10000)
    if where_btn:
        logger.info("触发筛选按钮")
        await where_btn.hover()
        await asyncio.sleep(1.3)

        week_btn = await page.locator(
            'xpath=//*[@id="search-content-area"]/div/div[1]/div[1]/div[1]/div/div/div/div/div[2]/span[2]').element_handle(
            timeout=10000)
        if week_btn:
            logger.info("过滤最近1天视频")
            await week_btn.click()
            await asyncio.sleep(1.3)

        # 隐藏筛选弹窗
        await where_btn.click()

    # 获取列表
    scroll_list_element: ElementHandle = await page.locator(
        'xpath=//*[@id="search-result-container"]/div[2]/ul').element_handle(timeout=10000)
    if scroll_list_element:
        for _ in range(20):
            if await scroll_list_element.bounding_box() is None:
                await asyncio.sleep(0.5)

        # 模拟点击空白处
        logger.info("模拟点击空白处，获取焦点")
        box = await scroll_list_element.bounding_box()
        x = (box["x"] if box else 30) - random.randint(10, 20)
        y = (box["y"] if box else 166) + random.randint(10, 30)
        await page.mouse.click(x, y)

        # 记录当前加载项
        latest_li_len = len(await scroll_list_element.query_selector_all('li'))

        # 通过 PageDown 翻页
        for _ in range(999):
            await scroll_list_element.press('PageDown')
            await asyncio.sleep(0.8)
            now_li_len = len(await scroll_list_element.query_selector_all('li'))
            if now_li_len == latest_li_len:
                await asyncio.sleep(3)
                await scroll_list_element.press('PageDown')
                await asyncio.sleep(0.8)
                if len(await  scroll_list_element.query_selector_all('li')) == latest_li_len:
                    break
            latest_li_len = now_li_len
            logger.info('load items : ' + str(latest_li_len))
            if latest_li_len >= max_size:
                break

        # 获取所有标题与 url
        li_elements = await scroll_list_element.query_selector_all('li')
        li_elements = li_elements[:max_size]
        logger.info('total items : ' + str(len(li_elements)))
        for li in li_elements:
            try:
                a_element = await li.query_selector('a[href]')
                if a_element:
                    href = await a_element.get_attribute('href')
                    full_url = urljoin(page.url, href)

                    # 取 title
                    divs = await a_element.query_selector_all("div")
                    title = ""
                    if len(divs) > 15:
                        title = await divs[15].text_content()
                    logger.info(f"{title} -> {full_url}")
                    result.items.append(ActionResultItem(url=full_url, title=title))
            except Exception:
                continue

        # cookies
        cookies = await page.context.cookies()
        cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
        result.cookies = cookie_str


class DouyinPlatformAction(PlatformAction):

    async def action(self, keyword: str, cookies: str = None, *args, **kwargs) -> ActionResult:

        max_size: int = kwargs.get('max_size') or 999
        proxy: str = kwargs.get('proxy', None)

        chrome: list = getChromeExecutablePath()
        chrome_path = chrome[0] if chrome else None
        if chrome_path is None:
            raise RuntimeError("未找到可用的chrome")

        result: ActionResult = ActionResult()

        args_list = [
            '--incognito',
            '--disable-infobars',
            '--no-first-run',
            '--no-default-browser-check',
            f'--window-size={width},{height}',
            '--window-position=0,0'
        ]
        if proxy:
            args_list.append(f'--proxy-server=https={proxy}')

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                executable_path=chrome_path,
                args=args_list,
            )
            context = await browser.new_context()
            page = await context.new_page()

            # 设置 cookies
            if cookies:
                cookie_list = [
                    {'name': k, 'value': v, 'url': douyin_page_home}
                    for k, v in (item.strip().split('=', 1) for item in cookies.split(';') if '=' in item)
                ]
                await context.add_cookies(cookie_list)

            try:
                await run_work(keyword=keyword, page=page, result=result, max_size=max_size)
            except Exception as e:
                logger.error(e)
                logger.error("Traceback:\n%s", traceback.format_exc())
                result.success = False
                result.msg = traceback.format_exc()
            finally:
                await browser.close()

            return result
