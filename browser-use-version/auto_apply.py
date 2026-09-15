"""
BOSS 一键投递机器人 - browser-use 版本

使用 Playwright（browser-use 的底层引擎）实现自动投递。
流程：加载 cookie → 搜索岗位 → 浏览列表 → 逐个点击"立即沟通" → 发送消息
支持多账号：通过 AccountManager 切换不同账号的 cookie

当需要 AI 驱动的智能操作时，可使用 browser_use.Agent（它会自行管理浏览器）。
本模块的 BrowserUseEngine 直接用 Playwright API，避免 browser-use 0.13 在
macOS headless 下 CDP WebSocket 不稳定的问题。
"""

import asyncio
import logging
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from account_manager import AccountManager

sys.path.insert(0, os.path.dirname(__file__))
from config import (
    CITY, JOB_KEYWORD, SCROLL_TIMES, SCROLL_DELAY,
    MIN_DELAY, MAX_DELAY, MAX_APPLIES, APPLY_MESSAGE,
    BASE_URL, CITY_CODES
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class BrowserUseEngine:
    """Playwright 引擎封装，支持多账号 cookie"""

    def __init__(self, account_id: str = None, headless: bool = False):
        self._account_mgr = AccountManager()
        self._account_id = account_id or self._account_mgr.get_default_account()
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def start(self):
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        self._context = await self._browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        self._page = await self._context.new_page()
        logger.info("Playwright 引擎已启动")

    async def inject_cookies(self, cookies: list = None) -> bool:
        if not cookies:
            if self._account_id:
                cookies = self._account_mgr.load_cookie(self._account_id)
            if not cookies:
                logger.warning("没有可用的 cookie 数据")
                return False
        pw_cookies = []
        for c in cookies:
            pc = {'name': c.get('name', ''), 'value': c.get('value', '')}
            if c.get('domain'):
                pc['domain'] = c['domain']
                pc['path'] = c.get('path', '/')
            else:
                pc['url'] = 'https://www.zhipin.com'
            if c.get('secure'): pc['secure'] = True
            if c.get('httpOnly'): pc['httpOnly'] = True
            pw_cookies.append(pc)
        await self._context.add_cookies(pw_cookies)
        logger.info(f"注入 {len(pw_cookies)} 个 cookie (账号: {self._account_id})")
        return True

    async def save_cookies(self) -> list:
        cookies = await self._context.cookies()
        if cookies and self._account_id:
            self._account_mgr.save_cookie(self._account_id, cookies)
            logger.info(f"已保存 {len(cookies)} 个 cookie 到账号 {self._account_id}")
        return cookies

    async def navigate(self, url: str):
        await self._page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(2)

    async def evaluate(self, js: str):
        return await self._page.evaluate(js)

    async def scroll_bottom(self):
        await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(SCROLL_DELAY)

    async def screenshot(self, path: str):
        await self._page.screenshot(path=path)

    async def close(self):
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning(f"关闭引擎时异常: {e}")
        logger.info("Playwright 引擎已关闭")


class AutoApply:
    """一键投递主逻辑"""

    def __init__(self, account_id: str = None, headless: bool = False):
        self.engine = BrowserUseEngine(account_id, headless)
        self.applied_count = 0
        self.failed_count = 0

    def get_city_code(self, city: str) -> int:
        code = CITY_CODES.get(city)
        if not code:
            logger.error(f"不支持的城市: {city}，支持: {list(CITY_CODES.keys())}")
            return 0
        return code

    async def search_jobs(self, city: str, keyword: str) -> list:
        code = self.get_city_code(city)
        if not code:
            return []

        await self.engine.inject_cookies()

        url = f"{BASE_URL}/web/geek/jobs?query={keyword}&city={code}"
        await self.engine.navigate(url)

        for i in range(SCROLL_TIMES):
            await self.engine.scroll_bottom()
            logger.info(f"滚动加载 {i+1}/{SCROLL_TIMES}")

        js = """
        () => {
            const cards = document.querySelectorAll('.job-card-box');
            return Array.from(cards).map((c, i) => ({
                index: i,
                name: c.querySelector('.job-name')?.textContent?.trim() || '',
                salary: c.querySelector('.job-salary')?.textContent?.trim() || '',
                company: c.querySelector('.boss-name')?.textContent?.trim() || '',
                location: c.querySelector('.company-location')?.textContent?.trim() || ''
            }));
        }
        """
        result = await self.engine.evaluate(js)
        logger.info(f"共找到 {len(result)} 个岗位")
        return result

    async def apply_to_job(self, job_index: int) -> bool:
        try:
            js_click = f"""
            () => {{
                const cards = document.querySelectorAll('.job-card-box');
                if (cards[{job_index}]) {{
                    cards[{job_index}].querySelector('.job-name').click();
                    return 'clicked';
                }}
                return 'not found';
            }}
            """
            result = await self.engine.evaluate(js_click)
            logger.info(f"进入岗位详情: {result}")
            await asyncio.sleep(2)

            js_chat = """
            () => {
                const btn = document.querySelector('.op-btn.op-btn-chat');
                if (btn) {
                    if (btn.textContent.includes('继续沟通')) return 'already';
                    btn.click();
                    return 'ok';
                }
                return 'not found';
            }
            """
            result = await self.engine.evaluate(js_chat)
            logger.info(f"点击立即沟通: {result}")
            if 'already' in str(result):
                logger.info("已沟通过，跳过")
                return False
            await asyncio.sleep(2)

            msg = APPLY_MESSAGE.replace("'", "\\'").replace("\n", "\\n")
            js_type = f"""
            () => {{
                const input = document.querySelector('#chat-input');
                if (input) {{
                    input.focus();
                    input.textContent = '{msg}';
                    input.dispatchEvent(new Event('input', {{bubbles: true}}));
                    return 'typed';
                }}
                return 'not found';
            }}
            """
            await self.engine.evaluate(js_type)
            await asyncio.sleep(0.5)

            for attempt in range(3):
                js_send = """
                () => {
                    const btn = document.querySelector('.btn-send');
                    if (btn && !btn.classList.contains('disabled')) {
                        btn.click();
                        return 'sent';
                    }
                    return 'disabled';
                }
                """
                result = await self.engine.evaluate(js_send)
                if 'sent' in str(result):
                    logger.info("发送消息成功")
                    return True
                logger.warning(f"发送按钮不可用，重试 {attempt+1}/3...")
                await asyncio.sleep(1)

            logger.error("发送消息最终失败")
            return False

        except Exception as e:
            logger.error(f"投递失败: {e}")
            return False

    async def go_back_to_list(self):
        await self.engine.evaluate("window.history.back()")
        await asyncio.sleep(2)

    async def run(self, city: str = None, keyword: str = None, max_applies: int = None):
        city = city or CITY
        keyword = keyword or JOB_KEYWORD
        max_applies = max_applies or MAX_APPLIES

        logger.info("=" * 50)
        logger.info(f"BOSS 一键投递开始 (browser-use/Playwright 版)")
        logger.info(f"账号: {self.engine._account_id} | 城市: {city} | 岗位: {keyword} | 最大投递: {max_applies}")
        logger.info("=" * 50)

        await self.engine.start()

        try:
            jobs = await self.search_jobs(city, keyword)
            if not jobs:
                logger.error("未找到岗位，退出")
                return

            for i, job in enumerate(jobs[:max_applies]):
                logger.info(f"\n--- 投递 {i+1}/{min(len(jobs), max_applies)} ---")
                logger.info(f"岗位: {job.get('name', '')} | 薪资: {job.get('salary', '')} | 公司: {job.get('company', '')}")

                success = await self.apply_to_job(i)
                if success:
                    self.applied_count += 1
                    logger.info(f"投递成功: {job.get('name', '')}")
                else:
                    self.failed_count += 1
                    logger.error(f"投递失败: {job.get('name', '')}")

                await self.go_back_to_list()
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                logger.info(f"等待 {delay:.1f} 秒...")
                await asyncio.sleep(delay)

            logger.info("\n" + "=" * 50)
            logger.info(f"投递完成！成功: {self.applied_count} | 失败: {self.failed_count}")
            logger.info("=" * 50)

        finally:
            await self.engine.save_cookies()
            await self.engine.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="BOSS 一键投递机器人 (browser-use 版)")
    parser.add_argument("--account", default=None, help="账号 ID")
    parser.add_argument("--city", default=CITY, help="目标城市")
    parser.add_argument("--keyword", default=JOB_KEYWORD, help="岗位关键词")
    parser.add_argument("--max", type=int, default=MAX_APPLIES, help="最大投递数")
    parser.add_argument("--headless", action="store_true", help="无头模式（服务器部署用）")
    args = parser.parse_args()

    auto = AutoApply(account_id=args.account, headless=args.headless)
    asyncio.run(auto.run(city=args.city, keyword=args.keyword, max_applies=args.max))


if __name__ == "__main__":
    main()
