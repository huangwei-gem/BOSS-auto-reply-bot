"""跨平台浏览器启动器

macOS: 手动启动 Chrome（临时配置文件）+ Chromium 连接
Windows: 直接使用 ChromiumPage
"""

import os
import sys
import time
import json
import subprocess
import platform
import shutil
import socket
import tempfile
import logging
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

logger = logging.getLogger("browser_launcher")

_IS_MACOS = platform.system().lower() == "darwin"
_IS_WINDOWS = platform.system().lower() == "windows"


def _detect_default_browser() -> str:
    """检测系统默认浏览器，返回 'chrome' / 'edge' / 'chromium' / '' """
    try:
        if _IS_MACOS:
            # 读取 LaunchServices plist 获取默认 http 处理程序
            import plistlib
            plist_path = os.path.expanduser(
                "~/Library/Preferences/com.apple.LaunchServices/com.apple.launchservices.secure.plist"
            )
            if not os.path.isfile(plist_path):
                plist_path = os.path.expanduser(
                    "~/Library/Preferences/com.apple.LaunchServices.plist"
                )
            if os.path.isfile(plist_path):
                with open(plist_path, "rb") as f:
                    plist = plistlib.load(f)
                handlers = plist.get("LSHandlers", [])
                for h in handlers:
                    if h.get("LSHandlerURLScheme") == "http":
                        bundle_id = h.get("LSHandlerAllRolesAllTypes", "").lower()
                        if "chrome" in bundle_id:
                            return "chrome"
                        if "edge" in bundle_id:
                            return "edge"
                        if "chromium" in bundle_id:
                            return "chromium"
                        break

        elif _IS_WINDOWS:
            # 读注册表获取默认浏览器 ProgId
            import winreg
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"
                )
                progid, _ = winreg.QueryValueEx(key, "ProgId")
                winreg.CloseKey(key)
                progid = progid.lower()
                if "chrome" in progid:
                    return "chrome"
                if "edge" in progid:
                    return "edge"
                if "chromium" in progid:
                    return "chromium"
            except Exception:
                pass

        else:
            # Linux: xdg-mime 查询默认浏览器
            try:
                result = subprocess.run(
                    ["xdg-mime", "query", "default", "x-scheme-handler/http"],
                    capture_output=True, text=True, timeout=5
                )
                desktop = result.stdout.strip().lower()
                if "chrome" in desktop:
                    return "chrome"
                if "edge" in desktop:
                    return "edge"
                if "chromium" in desktop:
                    return "chromium"
            except Exception:
                pass

    except Exception:
        pass
    return ""


def detect_available_browsers() -> dict:
    """检测系统上安装了哪些浏览器，返回 {名称: 路径}"""
    found = {}

    if _IS_MACOS:
        checks = {
            "chrome": '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            "edge": '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
            "chromium": '/Applications/Chromium.app/Contents/MacOS/Chromium',
        }
    elif _IS_WINDOWS:
        checks = {
            "chrome": [
                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
            ],
            "edge": [
                r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
            ],
            "chromium": [],
        }
    else:
        checks = {
            "chrome": shutil.which('google-chrome') or shutil.which('google-chrome-stable') or "",
            "edge": shutil.which('microsoft-edge') or shutil.which('microsoft-edge-stable') or "",
            "chromium": shutil.which('chromium') or shutil.which('chromium-browser') or "",
        }

    for name, paths in checks.items():
        if isinstance(paths, str):
            paths = [paths] if paths else []
        for p in paths:
            if p and os.path.isfile(p):
                found[name] = p
                break

    # Windows 额外用 which 兜底
    if _IS_WINDOWS and not found:
        for name, cmd in (("chrome", "chrome"), ("edge", "msedge")):
            p = shutil.which(cmd)
            if p:
                found[name] = p

    return found


# 用户手动选择的浏览器（运行时缓存）
_preferred_browser: str = ""


def set_preferred_browser(name: str):
    """设置用户偏好的浏览器"""
    global _preferred_browser
    _preferred_browser = name


def _find_chrome_path() -> str:
    """自动查找浏览器路径，优先使用用户选择的，其次系统默认"""
    available = detect_available_browsers()
    if not available:
        return ""

    # 1. 用户手动选择的
    if _preferred_browser and _preferred_browser in available:
        return available[_preferred_browser]

    # 2. 系统默认浏览器
    default = _detect_default_browser()
    if default in available:
        return available[default]

    # 3. 按优先级兜底
    for key in ("chrome", "edge", "chromium"):
        if key in available:
            return available[key]

    return ""


def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """检查端口是否开放"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> bool:
    """等待端口开放"""
    start = time.time()
    while time.time() - start < timeout:
        if _is_port_open(host, port):
            return True
        time.sleep(0.5)
    return False


def _get_ws_url(host: str, port: int, retries: int = 5) -> str:
    """从 /json/version 获取 WebSocket URL"""
    for attempt in range(retries):
        try:
            resp = urlopen(f'http://{host}:{port}/json/version', timeout=3)
            data = json.loads(resp.read())
            ws_url = data.get('webSocketDebuggerUrl', '')
            if ws_url:
                return ws_url
        except (URLError, OSError, json.JSONDecodeError) as e:
            logger.debug(f"获取 ws_url 第{attempt+1}次失败: {e}")
            time.sleep(1)
    return ""


def _find_free_port() -> int:
    """找一个空闲端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class BrowserInstance:
    """浏览器实例封装"""

    def __init__(self, chrome_page=None, chromium=None, tab=None, process=None):
        self._page = chrome_page
        self._chromium = chromium
        self._tab = tab
        self._process = process

    def _get_active(self):
        if self._page is not None:
            return self._page
        return self._tab

    def ele(self, selector, timeout=None):
        obj = self._get_active()
        if timeout is not None:
            return obj.ele(selector, timeout=timeout)
        return obj.ele(selector)

    def eles(self, selector, timeout=None):
        obj = self._get_active()
        if timeout is not None:
            return obj.eles(selector, timeout=timeout)
        return obj.eles(selector)

    def get(self, url):
        return self._get_active().get(url)

    @property
    def url(self):
        return self._get_active().url

    @property
    def title(self):
        return self._get_active().title

    def run_js(self, script, *args):
        return self._get_active().run_js(script, *args)

    def cookies(self, all_info=False):
        return self._get_active().cookies(all_info=all_info)

    def quit(self):
        """关闭浏览器"""
        try:
            if self._page is not None:
                self._page.quit()
            elif self._chromium is not None:
                self._chromium.quit()
        except Exception as e:
            logger.warning(f"关闭浏览器异常: {e}")
        finally:
            if self._process is not None:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=5)
                except Exception:
                    try:
                        self._process.kill()
                    except Exception:
                        pass

    @property
    def page(self):
        """返回当前活动页面"""
        return self._get_active()


def launch_browser(port: int = 0) -> BrowserInstance:
    """启动浏览器（跨平台）

    Args:
        port: 调试端口（0 表示自动选择）

    Returns:
        BrowserInstance: 浏览器实例
    """
    chrome_path = _find_chrome_path()
    if not chrome_path or not os.path.isfile(chrome_path):
        raise FileNotFoundError("未找到 Chrome/Chromium，请先安装 Google Chrome")

    if _IS_MACOS:
        return _launch_macos(chrome_path, port or _find_free_port())
    else:
        return _launch_windows(chrome_path)


def _launch_macos(chrome_path: str, port: int) -> BrowserInstance:
    """macOS: 用临时配置文件启动 Chrome + WebSocket 连接"""

    # 使用临时用户数据目录（不影响用户主 Chrome）
    user_data_dir = os.path.join(tempfile.gettempdir(), f"boss_bot_chrome_{port}")
    os.makedirs(user_data_dir, exist_ok=True)

    args = [
        f'--remote-debugging-port={port}',
        '--no-sandbox',
        '--disable-gpu',
        '--disable-dev-shm-usage',
        '--disable-extensions',
        f'--user-data-dir={user_data_dir}',
        '--remote-allow-origins=*',
        '--window-size=1280,800',
    ]

    logger.info(f"macOS: 启动 Chrome (port={port}, profile={user_data_dir})")

    proc = subprocess.Popen(
        [chrome_path] + args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not _wait_for_port('127.0.0.1', port, timeout=15):
        proc.kill()
        raise RuntimeError(f"Chrome 启动失败（端口 {port} 未响应）")

    ws_url = _get_ws_url('127.0.0.1', port)
    if not ws_url:
        proc.kill()
        raise RuntimeError("无法获取 Chrome WebSocket URL")

    from DrissionPage._base.chromium import Chromium
    from DrissionPage import ChromiumOptions

    co = ChromiumOptions()
    co.ws_address = ws_url

    try:
        chromium = Chromium(co)
    except Exception as e:
        proc.kill()
        raise RuntimeError(f"连接 Chrome 失败: {e}")

    tab = chromium.new_tab()
    logger.info(f"macOS: Chrome 连接成功 (PID={proc.pid})")

    return BrowserInstance(chromium=chromium, tab=tab, process=proc)


def _launch_windows(chrome_path: str) -> BrowserInstance:
    """Windows: 使用原生 ChromiumPage"""

    from DrissionPage import ChromiumPage, ChromiumOptions

    co = ChromiumOptions()
    co.set_browser_path(chrome_path)
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--window-size=1280,800')

    page = ChromiumPage(co)
    logger.info("Windows: ChromiumPage 启动成功")

    return BrowserInstance(chrome_page=page)
