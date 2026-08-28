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

    def __init__(self, session_id: str):
        self.session = session_id

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
        return self.run(f'evaluate "{js}"')

    def scroll_bottom(self):
        self.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(SCROLL_DELAY)


class AutoApply:
    """一键投递主逻辑"""

    def __init__(self, session_id: str):
        self.bsk = BSKEngine(session_id)
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

    def apply_to_job_with_message(self, job_index: int) -> bool:
        """投递单个岗位（发送消息版本）"""
        try:
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
            self.bsk.evaluate("""
                (function() {
                    const btn = document.querySelector('.op-btn.op-btn-chat');
                    if (btn) { btn.click(); return 'ok'; }
                    return 'not found';
                })()
            """)
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

            # 点击发送
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
            logger.info(f"发送消息: {result}")
            return True

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
    parser.add_argument("--city", default=CITY, help="目标城市")
    parser.add_argument("--keyword", default=JOB_KEYWORD, help="岗位关键词")
    parser.add_argument("--max", type=int, default=MAX_APPLIES, help="最大投递数")
    args = parser.parse_args()

    auto = AutoApply(args.session)
    auto.run(city=args.city, keyword=args.keyword, max_applies=args.max)


if __name__ == "__main__":
    main()
