import os
import shutil
import sys

from pydantic import BaseModel


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


class ActionResultItem(BaseModel):
    title: str
    url: str


class ActionResult(BaseModel):

    # 是否成功
    success: bool = True
    # 消息
    msg: str = None

    cookies: str = None

    items: list[ActionResultItem] = None


class PlatformAction(BaseModel):
    # 执行任务
    async def action(self, keyword: str, cookies: str = None, *args, **kwargs) -> ActionResult:
        pass
