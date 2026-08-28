"""
BOSS 自动回复机器人 - 页面操作模块

封装 DrissionPage 的所有页面操作。
CSS 选择器基于 BOSS 直聘聊天页面实际结构。
"""

import time
import json
import logging
from typing import List, Optional, Dict

from DrissionPage import ChromiumPage
from config import CHAT_URL, COOKIE_FILE

logger = logging.getLogger(__name__)


class BossChatHandler:
    """BOSS 聊天页面操作处理器"""

    def __init__(self):
        self.page = ChromiumPage()
        self._logged_in = False

    def login(self):
        """
        检查登录状态，未登录则等待手动登录。
        登录后保存 cookies 以便下次自动登录。
        """
        # 先尝试加载已保存的 cookies
        if self._load_cookies():
            self.page.get(CHAT_URL)
            time.sleep(2)
            if not self._is_login_page():
                logger.info("通过 Cookie 自动登录成功")
                self._logged_in = True
                return

        # 需要手动登录
        logger.info("需要登录，正在跳转到登录页面...")
        self.page.get("https://www.zhipin.com/web/user/?ka=header-login")
        input("请在浏览器中手动登录 BOSS 直聘，登录完成后按回车继续...")

        # 保存登录状态
        self._save_cookies()
        self._logged_in = True
        logger.info("登录成功，Cookie 已保存")

    def _is_login_page(self) -> bool:
        """判断当前是否需要登录"""
        try:
            # 如果能找到聊天列表，说明已登录
            self.page.ele("ul[role='group']", timeout=3)
            return False
        except Exception:
            return True

    def _save_cookies(self):
        """保存 cookies 到文件"""
        try:
            cookies = self.page.cookies()
            with open(COOKIE_FILE, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            logger.info(f"Cookie 已保存到 {COOKIE_FILE}")
        except Exception as e:
            logger.error(f"保存 Cookie 失败: {e}")

    def _load_cookies(self) -> bool:
        """从文件加载 cookies"""
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            self.page.set_cookies(cookies)
            logger.info(f"已从 {COOKIE_FILE} 加载 Cookie")
            return True
        except FileNotFoundError:
            logger.info("未找到保存的 Cookie，需要手动登录")
            return False
        except Exception as e:
            logger.error(f"加载 Cookie 失败: {e}")
            return False

    def go_to_chat(self):
        """导航到聊天页面"""
        if self.page.url != CHAT_URL:
            self.page.get(CHAT_URL)
            time.sleep(2)

    def get_unread_chats(self) -> List[Dict]:
        """
        获取所有未读聊天会话列表。
        选择器: ul[role='group'] > li[role='listitem']
        未读标记: .notice-badge
        """
        self.go_to_chat()
        time.sleep(1)

        unread_chats = []
        try:
            chat_items = self.page.eles("ul[role='group'] > li[role='listitem']")
            for item in chat_items:
                # 检查是否有未读标记
                try:
                    badge = item.ele(".notice-badge", timeout=1)
                    count_text = badge.text.strip()
                    count = int(count_text) if count_text else 1
                except Exception:
                    continue  # 没有未读标记，跳过

                # 获取聊天名称
                try:
                    name = item.ele(".name-text", timeout=1).text.strip()
                except Exception:
                    name = "未知"

                # 获取消息预览
                try:
                    preview = item.ele(".last-msg-text", timeout=1).text.strip()
                except Exception:
                    preview = ""

                # 获取可点击区域
                try:
                    click_area = item.ele(".friend-content", timeout=1)
                except Exception:
                    click_area = item

                unread_chats.append({
                    "element": click_area,
                    "name": name,
                    "preview": preview,
                    "unread_count": count
                })

        except Exception as e:
            logger.error(f"获取未读聊天列表失败: {e}")

        logger.info(f"发现 {len(unread_chats)} 个未读会话")
        return unread_chats

    def enter_chat(self, chat_info: dict):
        """点击进入某个聊天"""
        chat_info["element"].click()
        time.sleep(1.5)

    def read_latest_messages(self, count: int = 5) -> List[Dict]:
        """
        读取当前聊天中最近的消息。
        选择器: .message-item
        对方的消息: .message-item.item-friend
        消息文字: .text-content
        时间: .item-time .time
        """
        messages = []
        try:
            msg_elements = self.page.eles(".message-item")
            recent = msg_elements[-count:] if len(msg_elements) > count else msg_elements

            for msg in recent:
                try:
                    text = msg.ele(".text-content", timeout=1).text.strip()
                except Exception:
                    text = ""

                # 判断是否是自己发的（没有 item-friend 类就是自己发的）
                is_mine = "item-friend" not in (msg.attr("class") or "")

                try:
                    time_text = msg.ele(".item-time .time", timeout=1).text.strip()
                except Exception:
                    time_text = ""

                messages.append({
                    "text": text,
                    "is_mine": is_mine,
                    "time": time_text
                })
        except Exception as e:
            logger.error(f"读取消息失败: {e}")

        return messages

    def get_boss_name(self) -> str:
        """获取当前聊天对象的名称"""
        try:
            return self.page.ele(".top-info-content .name-text", timeout=3).text.strip()
        except Exception:
            return ""

    def get_job_name(self) -> str:
        """获取当前聊天对应的岗位名称"""
        try:
            return self.page.ele(".chat-position-content .position-content", timeout=3).text.strip()
        except Exception:
            return ""

    def send_text(self, text: str):
        """
        在当前聊天中输入并发送文字消息。
        输入框: #chat-input.chat-input (contenteditable)
        发送按钮: .btn-send
        """
        try:
            # 用 JS 输入文字（contenteditable 需要用 textContent）
            self.page.run_js(f"""
                const input = document.querySelector('#chat-input');
                if (input) {{
                    input.focus();
                    input.textContent = `{text}`;
                    input.dispatchEvent(new Event('input', {{bubbles: true}}));
                    return 'typed';
                }}
                return 'not found';
            """)
            time.sleep(0.5)

            # 点击发送按钮
            self.page.run_js("""
                const sendBtn = document.querySelector('.btn-send');
                if (sendBtn && !sendBtn.classList.contains('disabled')) {
                    sendBtn.click();
                    return 'sent';
                }
                return 'button disabled or not found';
            """)
            logger.info(f"已发送文字: {text[:30]}...")
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"发送文字失败: {e}")
            return False

    def send_resume(self) -> bool:
        """
        点击发送简历按钮，选择简历并发送。
        流程：
        1. 点击工具栏的"发简历"按钮，弹出选择框
        2. 在对话框中选择简历文件（点击文件名按钮）
        3. 点击"发送"按钮（需要先用 JS 移除 disabled 类）
        """
        try:
            # 1. 点击"发简历"按钮
            self.page.run_js("""
                const btns = document.querySelectorAll('.toolbar-btn');
                for (const btn of btns) {
                    if (btn.textContent.includes('发简历')) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            """)
            time.sleep(1)

            # 2. 在对话框中选择简历（选择"黄维简历.docx"或第一个）
            self.page.run_js("""
                // 找到包含"黄维简历"的按钮并点击
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.textContent.includes('黄维简历')) {
                        btn.click();
                        return 'selected 黄维简历';
                    }
                }
                // 如果没找到，点击第一个简历按钮
                const resumeBtns = Array.from(btns).filter(b => b.textContent.includes('.docx'));
                if (resumeBtns.length > 0) {
                    resumeBtns[0].click();
                    return 'selected first resume';
                }
                return 'no resume found';
            """)
            time.sleep(0.5)

            # 3. 点击发送按钮（移除 disabled 类后点击）
            result = self.page.run_js("""
                const sendBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === '发送');
                if (sendBtn) {
                    sendBtn.classList.remove('disabled');
                    sendBtn.click();
                    return 'sent';
                }
                return 'send button not found';
            """)
            logger.info(f"发送简历结果: {result}")
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"发送简历失败: {e}")
            return False

    def close(self):
        """关闭浏览器"""
        try:
            self.page.quit()
            logger.info("浏览器已关闭")
        except Exception:
            pass
