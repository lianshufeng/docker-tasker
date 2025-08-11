import asyncio
import json
import logging
import os
import random
import re
import shutil
import sys
import time
import traceback
from urllib.parse import urlparse

import requests

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from ..util.image_utils import find_and_click_image

# 日志配置
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

width = 800
height = 600

douyin_page_home = 'https://www.douyin.com'

user_counter = {}

# 常见插件库
PLUGIN_LIB = [
    {"name": "Chrome PDF Plugin", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
    {"name": "Chrome PDF Viewer", "filename": "mhjfbmdgcfjbbpaeojofohoefgiehjai", "description": ""},
    {"name": "Native Client", "filename": "internal-nacl-plugin", "description": ""},
    {"name": "Widevine Content Decryption Module", "filename": "widevinecdmadapter.dll",
     "description": "Enables Widevine licenses for playback of HTML audio/video content."},
    {"name": "Shockwave Flash", "filename": "pepflashplayer.dll", "description": "Shockwave Flash 32.0 r0"}
]


async def make_browser_context(browser: Browser) -> BrowserContext:
    # ---- 基础参数 ----
    CHROME_VERSION = f'{random.randint(130, 139)}.0.0.0'  # 修改为 137.0.0.0 版本
    user_agent = f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{CHROME_VERSION} Safari/537.36'
    width, height = 1920, 1080
    locale = "zh-CN"
    timezone = "Asia/Shanghai"

    # ---- 随机插件 ----
    n = random.randint(3, 4)
    plugins = random.sample(PLUGIN_LIB, n)
    plugins_js = json.dumps(plugins, ensure_ascii=False)

    # ---- 构造所有补丁脚本 ----
    # Object.defineProperty(navigator, 'language', {{get: () = > '{locale}'}});
    patch_js = f"""
    // ---- navigator属性补丁 ----
    Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});
    Object.defineProperty(navigator, 'platform', {{get: () => 'Win32'}});
    Object.defineProperty(navigator, 'oscpu', {{get: () => 'Windows NT 10.0; Win64; x64'}});
    Object.defineProperty(navigator, 'languages', {{get: () => ['zh-CN', 'zh', 'en']}});
    // ---- plugins补丁 ----
    (function () {{
      const fakePluginArray = {plugins_js};
      fakePluginArray.item = function(i) {{ return this[i]; }};
      fakePluginArray.namedItem = function(name) {{
        return this.find(plugin => plugin.name === name) || null;
      }};
      fakePluginArray.refresh = function() {{ return undefined; }};
      Object.defineProperty(fakePluginArray, 'length', {{
        get: function() {{ return fakePluginArray.length; }}
      }});
      Object.defineProperty(navigator, 'plugins', {{
        get: function() {{ return fakePluginArray; }},
        configurable: true
      }});
    }})();
    """

    # 随机生成当前版本往前20个的版本号
    page = await browser.new_page()
    ua = await page.evaluate("() => navigator.userAgent")
    print(f"原始 UA: {ua}")
    match = re.search(r'Chrome/(\d+)\.', ua)
    if not match:
        raise Exception("无法识别Chrome版本！")
    current_version = int(match.group(1))
    print(f"当前浏览器主版本号: {current_version}")
    ua_list = []
    for v in range(current_version - 20, current_version):
        new_ua = re.sub(r'Chrome/\d+\.', f'Chrome/{v}.', ua)
        ua_list.append(new_ua)
    random_ua = random.choice(ua_list)
    print(f"随机选中的UA: {random_ua}")
    await page.close()

    # ---- 创建context并注入补丁 ----
    context = await browser.new_context(
        user_agent=random_ua,
    )
    # await context.add_init_script(patch_js)
    return context


# 异步执行，发现就关闭登录面板
async def close_login_panel(page: Page, is_exit: bool, timeout: float = 20.0) -> bool:
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            logger.info(f"超时{timeout}秒，退出关闭登录面板流程")
            return False
        try:
            # Playwright 推荐用 locator
            parent = await page.locator("#login-panel-new").element_handle(timeout=timeout / 2 * 1000)
            if parent:
                span_element = await parent.query_selector('svg')
                if span_element:
                    await span_element.click()
                    logger.info("关闭登录面板")
                    if is_exit:
                        return True
        except Exception as e:
            logger.info(f"查找或关闭时出错: {e}")
        await asyncio.sleep(0.1)


async def run_work(context: BrowserContext, ai_url: str, max_chat_count: int):
    page = await context.new_page()

    # 打开首页（可跳过）
    await page.goto("https://www.baidu.com")
    await asyncio.sleep(0.2)

    # 打开 Douyin 主页
    await page.goto("https://www.douyin.com/")
    # 弹窗加载时间
    await asyncio.sleep(9)
    # 找到取消按钮并点击
    find_and_click_image("res/cancel_button.png", threshold=0.9)

    async def loop_close_xdg_open_window_handel():
        while True:
            await close_xdg_open_window_handel()
            await asyncio.sleep(1)

    asyncio.create_task(loop_close_xdg_open_window_handel())
    # await page.locator("text=取消").wait_for()
    # await page.locator("text=取消").click()
    locator = page.locator("text=私信")
    await locator.wait_for(timeout=9000)
    await locator.click()
    # 等待私信窗口出现
    await page.locator('[data-e2e="listDlg-container"]').wait_for()
    message_entry = page.locator('[data-e2e="listDlg-container"]')
    await asyncio.sleep(3)
    # 查找所有有未读消息标记（红点）的会话
    red_dot_items = message_entry.locator('[x-semi-prop="count"]')

    if await red_dot_items.count() > 0:
        # 点击第一个未读会话
        await red_dot_items.nth(0).click()
    else:
        print("无未读消息")
        return

    while True:
        await asyncio.sleep(2)
        # 获取所有消息容器

        message_blocks = page.locator(
            '//div[contains(@style, "display: flex") and contains(@style, "justify-content")]')
        message_count = await message_blocks.count()
        message_texts = []

        for i in range(message_count):
            msg = message_blocks.nth(i)
            style = await msg.evaluate("el => el.getAttribute('style')")

            if style and "justify-content: space-between" in style:
                # await msg.text_content()
                # # 查找文字内容
                # if '暂不支持该消息类型' in await msg.text_content():
                #     continue
                # else:
                #

                text_locator = msg.locator("pre")
                if await text_locator.count() > 0:
                    content = await text_locator.text_content()
                    if content:
                        print(content.strip())
                        message_texts.append(content.strip())
            else:
                # 未满足条件，触发回复操作
                if len(message_texts) > 0:
                    async with context.expect_page() as new_page_info:
                        await page.locator("div.txZU3UOS").click()
                    new_page = await new_page_info.value
                    current_url = new_page.url
                    user_id = urlparse(current_url).path.strip("/").split("/")[1]

                    if get_user_count(user_id) > max_chat_count:
                        print("超出会话次数")
                    else:
                        data = {
                            "uid": user_id,
                            "messages": message_texts
                        }
                        response = requests.post(ai_url, json=data)
                        # 解析响应为 JSON 对象
                        res_json = response.json()

                        # 提取 content 内的数据
                        is_reply = res_json["content"]["isReply"]
                        message = res_json["content"]["message"]
                        print("回复消息:", message)
                        # if is_reply:
                        await page.bring_to_front()
                        editor = page.locator('div[role="textbox"][aria-describedby^="placeholder-"]')
                        await editor.click()
                        await editor.type(message)

                        send_btn = page.locator("span.PygT7Ced.e2e-send-msg-btn")
                        await send_btn.click()
                        await asyncio.sleep(1)
                        add_user_event(user_id)
                break  # 当前会话结束，进入下一个

        # 尝试进入下一个红点会话
        next_item = page.locator('div.K_ckXK2o').locator('[x-semi-prop="count"]')

        if await next_item.count() > 0:
            await next_item.nth(0).click()
        else:
            print("无更多会话，结束循环")
            break

async def close_xdg_open_window_handel():
    find_and_click_image('res/cancel_button.png', threshold=0.9)
    pass


def add_user_event(user_id):
    """给用户ID计数 +1"""
    if user_id in user_counter:
        user_counter[user_id] += 1
    else:
        user_counter[user_id] = 1


def get_user_count(user_id):
    """获取用户ID当前的计数"""
    return user_counter.get(user_id, 0)


def getChromeExecutablePath() -> list[str]:
    chrome_paths = []

    if sys.platform.startswith('win'):
        # 常见的 Windows 安装路径
        possible_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        # 在 PATH 环境变量中查找
        chrome_in_path = shutil.which("chrome")
        if chrome_in_path:
            chrome_paths.append(chrome_in_path)

        for path in possible_paths:
            if os.path.exists(path):
                chrome_paths.append(path)
    else:
        # Linux
        candidates = [
            "google-chrome",
            "google-chrome-stable",
            "chromium-browser",
            "chromium"
        ]
        for candidate in candidates:
            chrome_path = shutil.which(candidate)
            if chrome_path:
                chrome_paths.append(chrome_path)

    # 去重
    return list(dict.fromkeys(chrome_paths))


# 抖音发送消息
async def douyin_reply_message(proxy: str, cookies: str, ai_url: str, max_chat_count: int, *args, **kwargs):
    chrome: list = getChromeExecutablePath()
    chrome_path = chrome[0] if chrome else None
    if chrome_path is None:
        raise RuntimeError("未找到可用的chrome")

    args_list = [
        '--incognito',
        '--disable-infobars',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-features=ExternalProtocolDialog'
    ]
    if proxy:
        args_list.append(f'--proxy-server=https={proxy}')

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            executable_path=chrome_path,
            args=args_list,
        )
        context: BrowserContext = await make_browser_context(browser)

        # 设置 cookies
        if cookies:
            cookie_list = [
                {
                    'name': k,
                    'value': v,
                    'domain': '.douyin.com',  # 设置为整个主域
                    'path': '/'  # 通常需要设置 path
                }
                for k, v in (item.strip().split('=', 1) for item in cookies.split(';') if '=' in item)
            ]
            await context.add_cookies(cookie_list)

        try:
            return await run_work(context=context, ai_url=ai_url, max_chat_count=max_chat_count)
        except Exception as e:
            logger.error(e)
            logger.error("Traceback:\n%s", traceback.format_exc())
            return [False, traceback.format_exc()]
        finally:
            await browser.close()

    return [False, '未知错误']
