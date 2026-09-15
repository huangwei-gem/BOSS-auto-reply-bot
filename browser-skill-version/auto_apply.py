"""
BOSS 一键投递机器人 - browser-skill 版本

使用 bsk CLI（浏览器插件）实现自动投递。
流程：搜索岗位 → 浏览列表 → 逐个点击"立即沟通" → 发送消息 → 发简历
"""

import subprocess
import random
import time
import logging
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from account_manager import AccountManager

sys.path.insert(0, os.path.dirname(__file__))
from config import (
    CITY, JOB_KEYWORD, SCROLL_TIMES, SCROLL_DELAY,
    MIN_DELAY, MAX_DELAY, MAX_APPLIES, APPLY_MESSAGE,
    BASE_URL, CITY_CODES
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("auto_apply.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


class BSKEngine:
    """bsk CLI 命令封装"""

    def __init__(self, session_id: str, account_id: str = None):
        self.session = session_id
        self._account_mgr = AccountManager()
        self._account_id = account_id or self._account_mgr.get_default_account()

    def inject_cookies(self, cookies: list = None) -> bool:
        """通过 bsk evaluate 注入 cookie 到当前浏览器会话"""
        if not cookies:
            if self._account_id:
                cookies = self._account_mgr.load_cookie(self._account_id)
            if not cookies:
                logger.warning("没有可用的 cookie 数据")
                return False

        js_lines = []
        for c in cookies:
            name = c.get("name", "")
            value = c.get("value", "")
            domain = c.get("domain", ".zhipin.com")
            path = c.get("path", "/")
            secure = "true" if c.get("secure") else "false"
            http_only = "true" if c.get("httpOnly") else "false"
            js_lines.append(
                f'document.cookie="{name}={value}; domain={domain}; path={path};'
                f' secure={secure}; SameSite=None"'
            )
        js = ";".join(js_lines)
        result = self.evaluate(js)
        logger.info(f"注入 {len(cookies)} 个 cookie: {result[:50]}")
        return True

    def save_cookies(self) -> list:
        """通过 bsk evaluate 获取当前页面的 cookie"""
        result = self.evaluate("document.cookie")
        cookies = []
        if result:
            for item in result.strip().split(";"):
                item = item.strip()
                if "=" in item:
                    name, _, value = item.partition("=")
                    cookies.append({
                        "name": name.strip(),
                        "value": value.strip(),
                        "domain": ".zhipin.com",
                        "path": "/",
                    })
        if cookies and self._account_id:
            self._account_mgr.save_cookie(self._account_id, cookies)
            logger.info(f"已保存 {len(cookies)} 个 cookie 到账号 {self._account_id}")
        return cookies

    def run(self, cmd: str, timeout: int = 30) -> str:
        """执行 bsk 命令"""
        full_cmd = f"bsk {cmd} --session {self.session}"
        logger.debug(f"执行: {full_cmd}")
        try:
            result = subprocess.run(
                full_cmd, shell=True, capture_output=True,
                text=True, encoding='utf-8', timeout=timeout
            )
            output = result.stdout + result.stderr
            return output
        except subprocess.TimeoutExpired:
            logger.error(f"命令超时: {cmd}")
            return ""
        except Exception as e:
            logger.error(f"命令失败: {e}")
            return ""

    def navigate(self, url: str):
        logger.info(f"导航到: {url}")
        self.run(f'navigate "{url}"', timeout=60)
        time.sleep(2)

    def snapshot(self) -> str:
        return self.run("snapshot")

    def click(self, ref: str):
        logger.info(f"点击: {ref}")
        self.run(f"click {ref}")
        time.sleep(1)

    def evaluate(self, js: str) -> str:
        """执行 JS，使用列表参数避免 shell 引号问题"""
        import shlex
        # 压缩 JS 为单行
        js_one_line = js.replace("\n", " ").replace("\r", "").strip()
        cmd = f"bsk evaluate \"{js_one_line}\" --session {self.session}"
        logger.debug(f"执行: {cmd[:100]}...")
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, encoding='utf-8', timeout=30
            )
            return result.stdout + result.stderr
        except Exception as e:
            return ""

    def scroll_bottom(self):
        self.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(SCROLL_DELAY)


class AutoApply:
    """一键投递主逻辑"""

    def __init__(self, session_id: str, account_id: str = None):
        self.bsk = BSKEngine(session_id, account_id)
        self.applied_count = 0
        self.failed_count = 0

    def get_city_code(self, city: str) -> int:
        """获取城市代码"""
        code = CITY_CODES.get(city)
        if not code:
            logger.error(f"不支持的城市: {city}，支持的城市: {list(CITY_CODES.keys())}")
            return 0
        return code

    def search_jobs(self, city: str, keyword: str) -> list:
        """搜索岗位并获取列表"""
        code = self.get_city_code(city)
        if not code:
            return []

        # 先注入 cookie（如果有）
        self.bsk.inject_cookies()

        url = f"{BASE_URL}/web/geek/jobs?query={keyword}&city={code}"
        self.bsk.navigate(url)
        time.sleep(2)

        # 滚动加载更多岗位
        for i in range(SCROLL_TIMES):
            self.bsk.scroll_bottom()
            logger.info(f"滚动加载 {i+1}/{SCROLL_TIMES}")

        # 获取岗位列表
        js = """
        (function() {
            const cards = document.querySelectorAll('.job-card-box');
            return JSON.stringify(Array.from(cards).map((c, i) => ({
                index: i,
                name: c.querySelector('.job-name')?.textContent?.trim() || '',
                salary: c.querySelector('.job-salary')?.textContent?.trim() || '',
                company: c.querySelector('.boss-name')?.textContent?.trim() || '',
                location: c.querySelector('.company-location')?.textContent?.trim() || ''
            })));
        })()
        """
        result = self.bsk.evaluate(js)
        try:
            jobs = json.loads(result.strip())
            logger.info(f"共找到 {len(jobs)} 个岗位")
            return jobs
        except Exception as e:
            logger.error(f"解析岗位列表失败: {e}")
            return []

    def apply_to_job(self, job_index: int) -> bool:
        """投递单个岗位"""
        try:
            # 点击岗位进入详情页
            js_click = f"""
            (function() {{
                const cards = document.querySelectorAll('.job-card-box');
                if (cards[{job_index}]) {{
                    cards[{job_index}].querySelector('.job-name').click();
                    return 'clicked job {job_index}';
                }}
                return 'not found';
            }})()
            """
            result = self.bsk.evaluate(js_click)
            logger.info(f"进入岗位详情: {result}")
            time.sleep(2)

            # 点击"立即沟通"
            js_chat = """
            (function() {
                const btn = document.querySelector('.op-btn.op-btn-chat');
                if (btn) {
                    btn.click();
                    return 'clicked communicate';
                }
                return 'not found';
            })()
            """
            result = self.bsk.evaluate(js_chat)
            logger.info(f"点击立即沟通: {result}")
            time.sleep(2)

            # 返回岗位列表（沟通已建立，无需额外发消息）
            # BOSS的"立即沟通"会自动建立对话
            return True

        except Exception as e:
            logger.error(f"投递失败: {e}")
            return False

    def is_already_applied(self, job_index: int) -> bool:
        """检测岗位是否已经投递过（已建立沟通）"""
        try:
            js = f"""
            (function() {{
                const cards = document.querySelectorAll('.job-card-box');
                if (cards[{job_index}]) {{
                    const btn = cards[{job_index}].querySelector('.op-btn.op-btn-chat');
                    // 如果按钮文字是"继续沟通"说明已经投递过
                    if (btn && btn.textContent.includes('继续沟通')) {{
                        return 'already';
                    }}
                    return 'new';
                }}
                return 'not found';
            }})()
            """
            result = self.bsk.evaluate(js)
            return 'already' in result
        except Exception:
            return False

    def apply_to_job_with_message(self, job_index: int) -> bool:
        """投递单个岗位（发送消息版本）"""
        try:
            # 检查是否已经投递过
            if self.is_already_applied(job_index):
                logger.info("该岗位已投递过，跳过")
                return False

            # 点击岗位进入详情页
            js_click = f"""
            (function() {{
                const cards = document.querySelectorAll('.job-card-box');
                if (cards[{job_index}]) {{
                    cards[{job_index}].querySelector('.job-name').click();
                    return 'clicked';
                }}
                return 'not found';
            }})()
            """
            self.bsk.evaluate(js_click)
            time.sleep(2)

            # 点击"立即沟通"
            result = self.bsk.evaluate("""
                (function() {
                    const btn = document.querySelector('.op-btn.op-btn-chat');
                    if (btn) {
                        if (btn.textContent.includes('继续沟通')) {
                            return 'already_communicated';
                        }
                        btn.click();
                        return 'ok';
                    }
                    return 'not found';
                })()
            """)
            if 'already_communicated' in result:
                logger.info("已沟通过，跳过")
                return False
            time.sleep(2)

            # 进入刚建立的聊天
            self.bsk.evaluate("""
                (function() {
                    const items = document.querySelectorAll('ul[role="group"] > li[role="listitem"]');
                    if (items[0]) { items[0].querySelector('.friend-content').click(); return 'ok'; }
                    return 'not found';
                })()
            """)
            time.sleep(2)

            # 发送自我介绍消息
            msg = APPLY_MESSAGE.replace("'", "\\'").replace("\n", "\\n")
            self.bsk.evaluate(f"""
                (function() {{
                    const input = document.querySelector('#chat-input');
                    if (input) {{
                        input.focus();
                        input.textContent = '{msg}';
                        input.dispatchEvent(new Event('input', {{bubbles: true}}));
                        return 'typed';
                    }}
                    return 'not found';
                }})()
            """)
            time.sleep(0.5)

            # 点击发送（带重试）
            for attempt in range(3):
                result = self.bsk.evaluate("""
                    (function() {
                        const btn = document.querySelector('.btn-send');
                        if (btn && !btn.classList.contains('disabled')) {
                            btn.click();
                            return 'sent';
                        }
                        return 'disabled';
                    })()
                """)
                if 'sent' in result:
                    logger.info(f"发送消息成功")
                    return True
                logger.warning(f"发送按钮不可用，重试 {attempt+1}/3...")
                time.sleep(1)

            logger.error("发送消息最终失败")
            return False

        except Exception as e:
            logger.error(f"投递失败: {e}")
            return False

    def go_back_to_list(self):
        """返回岗位列表"""
        self.bsk.evaluate("window.history.back()")
        time.sleep(2)

    def run(self, city: str = None, keyword: str = None, max_applies: int = None):
        """运行一键投递"""
        city = city or CITY
        keyword = keyword or JOB_KEYWORD
        max_applies = max_applies or MAX_APPLIES

        logger.info("=" * 50)
        logger.info(f"BOSS 一键投递开始")
        logger.info(f"城市: {city} | 岗位: {keyword} | 最大投递数: {max_applies}")
        logger.info("=" * 50)

        # 1. 搜索岗位
        jobs = self.search_jobs(city, keyword)
        if not jobs:
            logger.error("未找到岗位，退出")
            return

        # 2. 逐个投递
        for i, job in enumerate(jobs[:max_applies]):
            logger.info(f"\n--- 投递 {i+1}/{min(len(jobs), max_applies)} ---")
            logger.info(f"岗位: {job.get('name', '')}")
            logger.info(f"薪资: {job.get('salary', '')}")
            logger.info(f"公司: {job.get('company', '')}")

            # 投递
            success = self.apply_to_job_with_message(i)

            if success:
                self.applied_count += 1
                logger.info(f"✅ 投递成功: {job.get('name', '')}")
            else:
                self.failed_count += 1
                logger.error(f"❌ 投递失败: {job.get('name', '')}")

            # 返回列表
            self.go_back_to_list()

            # 随机延迟
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            logger.info(f"等待 {delay:.1f} 秒...")
            time.sleep(delay)

        # 3. 统计
        logger.info("\n" + "=" * 50)
        logger.info(f"投递完成！成功: {self.applied_count} | 失败: {self.failed_count}")
        logger.info("=" * 50)


def main():
    """主入口"""
    import argparse

    parser = argparse.ArgumentParser(description="BOSS 一键投递机器人")
    parser.add_argument("--session", required=True, help="bsk 会话 ID")
    parser.add_argument("--account", default=None, help="账号 ID（使用该账号的 cookie）")
    parser.add_argument("--city", default=CITY, help="目标城市")
    parser.add_argument("--keyword", default=JOB_KEYWORD, help="岗位关键词")
    parser.add_argument("--max", type=int, default=MAX_APPLIES, help="最大投递数")
    args = parser.parse_args()

    auto = AutoApply(args.session, account_id=args.account)
    auto.run(city=args.city, keyword=args.keyword, max_applies=args.max)


if __name__ == "__main__":
    main()
