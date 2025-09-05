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

from playwright.async_api import async_playwright, Page, Browser, BrowserContext, JSHandle

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


# 检查当前用户是否登录状态
async def check_user_login(page: Page) -> list[bool | str]:
    locator = await page.query_selector_all(
        '//*[@id="douyin-header-menuCt"]//a[@href="//www.douyin.com/user/self"]')
    if len(locator) > 0:
        return [True, '']
    else:
        return [False, '未登录']


# 检查好友是否存在
async def check_friend_user_exist(page: Page) -> list[bool | str]:
    error_page = page.locator('[data-e2e="error-page"]')
    error_page_count = await page.locator('[data-e2e="error-page"]').count()
    if error_page_count > 0:
        error_page = await error_page.nth(0).element_handle(timeout=1000)
        return [False, (await error_page.inner_text()).strip()]
    else:
        return [True, '']


# 检查发送私信状态,必须用于发消息之后监测
async def check_send_message_state(page: Page) -> list[bool | str]:
    msg_content_locator = page.locator('xpath=//*[@id="messageContent"]/div/div[3]').locator(
        'div[data-e2e="msg-item-content"]')

    # 取出数据 msg
    msg_items = msg_content_locator.locator('> div').nth(0).locator('> div')

    # 取出div数量
    div_count = await msg_items.count()

    # 如果只有一个则说明大概率是发送成功了
    if div_count == 1:
        return [True, '']
    else:
        error_handle = await msg_items.nth(div_count - 1).element_handle(timeout=1000)
        msg_error_text: str = (await error_handle.inner_text()).strip()

        # 判断是不是有其失败的提示
        error_tips = page.locator('//*[@id="messageContent"]/div/div[3]/div[3]')
        error_tips_count = await error_tips.count()
        if error_tips_count > 0:
            msg_error_text+="\n"+ (await error_tips.inner_text()).strip()

        return [False, msg_error_text]  # 如果只有一个则说明大概率是发送成功了


async def run_work(context: BrowserContext, uid: str, message: str) -> list[bool | str]:
    # 首页
    page = await context.new_page()

    # 设置分辨率
    # await page.set_viewport_size({'width': width, 'height': height})

    # 打开首页
    await page.goto("https://www.baidu.com")
    await asyncio.sleep(0.2)
    await page.goto(douyin_page_home)  # 抖音主页

    # 点击我的
    # user_self = await page.locator('.tab-user_self').element_handle(timeout=10000)
    # await user_self.click()
    await asyncio.sleep(random.randint(1500, 3000) / 1000)
    await page.reload()
    await asyncio.sleep(random.randint(1500, 4000) / 1000)

    # 检查是否登录状态
    isLogin, err = await check_user_login(page)
    if isLogin is not True:
        return [isLogin, err]

    # 访问好友
    # friend_page = await context.new_page()
    # friend_page = page
    await page.goto(f"https://www.douyin.com/user/{uid}?from_tab_name=main")
    await asyncio.sleep(random.randint(500, 2000) / 1000)

    async def find_semi_button_and_input_message(current: int, max_try: int) -> list[bool | str]:
        try:
            # 找到取消按钮并点击
            find_and_click_image("res/cancel_button.png", threshold=0.9)

            # 检查好友是否存在

            isExist, err = await check_friend_user_exist(page)
            if isExist is not True:
                return [isExist, err]

            # 点击发送私信的按钮
            semi_button = await page.locator('span.semi-button-content:has-text("私信")').first.element_handle(
                timeout=10000)
            if semi_button is None:
                return [False, '未找到私信按钮']

            # 鼠标悬停
            await semi_button.hover()
            # 等待小动画（可选）
            await page.wait_for_timeout(random.randint(300, 800))
            # 触发点击
            await semi_button.click(force=True)

            # 发送消息
            msg_input = await page.locator('[data-e2e="msg-input"]').element_handle(timeout=3000)
            await asyncio.sleep(random.randint(600, 1500) / 1000)
            await msg_input.type(message, delay=random.randint(150, 400))

            # 找到取消按钮并点击
            find_and_click_image("res/cancel_button.png", threshold=0.9)

            # 发送消息
            await msg_input.press('Enter')
            logger.info("发送完成")

            # 延迟判断,是否发送成功
            await asyncio.sleep(random.randint(2500, 5000) / 1000)
            return await check_send_message_state(page)

        except Exception as e:
            logger.info(f"尝试触发私信功能 - {current}/{max_try}")
            logger.error(e)
            await asyncio.sleep(1)
            if current <= max_try:
                return await find_semi_button_and_input_message(current=current + 1, max_try=max_try)
            else:
                return [False, '补偿发送私信失败']

    # 触发 私信按钮 , 触发输入框输入内容
    return await find_semi_button_and_input_message(1, 6)


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
async def douyin_send_message(proxy: str, cookies: str, uid: str, message: str, *args, **kwargs) -> list[bool | str]:
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
            # 定义需要忽略的字段（冗余/高风险/埋点相关）
            exclude_keys={
                "__ac_signature",
                "gd_random",
                "sdk_source_info",
                "bit_env",
                "gulu_source_res",
                "passport_auth_mix_state",
                "__security_mc_1_s_sdk_sign_data_key_web_protect",
                "__security_mc_1_s_sdk_crypt_sdk",
                "__security_mc_1_s_sdk_cert_key",
                "__security_server_data_status",
                "biz_trace_id",
                "ttwid",
                "odin_tt",
                "FOLLOW_NUMBER_YELLOW_POINT_INFO",
                "FOLLOW_LIVE_POINT_INFO",
                "WallpaperGuide",
                "volume_info",
                "download_guide",
                "EnhanceDownloadGuide"
            }

            cookie_list = []
            for item in cookies.split(";"):
                if "=" not in item:
                    continue
                k, v = item.strip().split("=", 1)
                if k in exclude_keys:
                    continue
                cookie_list.append({
                    "name": k,
                    "value": v,
                    "domain": ".douyin.com",  # 设置为整个主域
                    "path": "/"  # 通常需要设置 path
                })

            await context.add_cookies(cookie_list)

        try:
            return await run_work(context=context, uid=uid, message=message)
        except Exception as e:
            logger.error(e)
            logger.error("Traceback:\n%s", traceback.format_exc())
            return [False, traceback.format_exc()]
        finally:
            await browser.close()

    return [False, '未知错误']
