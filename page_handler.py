"""
BOSS 自动回复机器人 - 页面操作模块

封装 DrissionPage 的所有页面操作。
CSS 选择器基于 BOSS 直聘聊天页面实际结构。
"""

import os
import time
import json
import logging
from typing import List, Optional, Dict
from pathlib import Path

from DrissionPage import ChromiumPage, ChromiumOptions
from config import CHAT_URL, COOKIE_FILE

logger = logging.getLogger(__name__)

# 便携浏览器路径（相对于本文件所在目录）
BASE_DIR = Path(__file__).parent
CHROME_PATH = str(BASE_DIR / "cloakbrowser-windows-x64" / "chrome.exe")
EXTENSION_PATH = str(BASE_DIR / "browser-skill-extension")


def _build_browser_options() -> ChromiumOptions:
    """构建浏览器配置：使用根目录的便携 Chrome + BrowserSkill 扩展"""
    options = ChromiumOptions()
    # 清除默认配置里可能残留的旧扩展路径
    options.remove_extensions()
    if Path(CHROME_PATH).exists():
        options.set_browser_path(CHROME_PATH)
    if Path(EXTENSION_PATH).exists():
        options.add_extension(EXTENSION_PATH)
    # 用户数据目录也放在根目录，保持登录状态
    user_data_dir = BASE_DIR / "browser-data"
    user_data_dir.mkdir(exist_ok=True)
    options.set_user_data_path(str(user_data_dir))
    return options


class BossChatHandler:
    """BOSS 聊天页面操作处理器"""

    def __init__(self):
        options = _build_browser_options()
        self.page = ChromiumPage(addr_or_opts=options)
        self._logged_in = False

    def login(self, timeout: int = 120):
        """
        检查登录状态，未登录则等待手动登录。
        登录后保存 cookies 以便下次自动登录。
        Args:
            timeout: 等待手动登录的超时时间（秒），默认120秒
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
        logger.info(f"需要登录，正在跳转到登录页面...（{timeout}秒内完成）")
        self.page.get("https://www.zhipin.com/web/user/?ka=header-login")
        logger.info(f"请在浏览器中手动登录 BOSS 直聘，登录后自动继续...")

        # 非交互式等待：轮询检查是否已登录
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(3)
            # 检查是否已跳转到登录后页面
            if not self._is_login_page():
                logger.info("登录成功！")
                self._save_cookies()
                self._logged_in = True
                return
            logger.debug("等待登录中...")

        raise TimeoutError(f"登录超时（{timeout}秒），请重试")

    def _is_login_page(self) -> bool:
        """判断当前是否需要登录"""
        try:
            # 如果当前URL包含 login 或 user，说明在登录页
            if 'login' in self.page.url or '/web/user' in self.page.url:
                return True
            # 如果能找到聊天列表且URL是chat页面，说明已登录
            if 'chat' in self.page.url:
                self.page.ele("ul[role='group']", timeout=3)
                return False
            return True
        except Exception:
            return True

    def _save_cookies(self):
        """保存 cookies 到文件"""
        try:
            cookies = self.page.cookies(all_info=True)
            with open(COOKIE_FILE, "w", encoding="utf-8") as f:
                json.dump(list(cookies), f, ensure_ascii=False, indent=2)
            logger.info(f"Cookie 已保存到 {COOKIE_FILE}")
        except Exception as e:
            logger.error(f"保存 Cookie 失败: {e}")

    def _load_cookies(self) -> bool:
        """从文件加载 cookies"""
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            # 使用 CDP Network.setCookie 逐个设置
            for cookie in cookies:
                self.page.run_js(
                    f"document.cookie = '{cookie['name']}={cookie['value']}; domain={cookie.get('domain', '')}; path=/;'"
                )
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
        """点击进入某个聊天，等待聊天内容加载"""
        chat_info["element"].click()
        time.sleep(2)  # 等待聊天内容加载
        # 等待输入框可用
        try:
            for _ in range(10):
                ready = self.page.run_js("""
                    const input = document.querySelector('#chat-input');
                    return input ? 'ready' : 'not ready';
                """)
                if ready == 'ready':
                    break
                time.sleep(0.5)
        except Exception:
            pass

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

    def send_text(self, text: str, retries: int = 3) -> bool:
        """
        在当前聊天中输入并发送文字消息。
        输入框: #chat-input.chat-input (contenteditable)
        发送按钮: .btn-send

        Args:
            text: 要发送的文字
            retries: 发送失败时的重试次数
        """
        for attempt in range(1, retries + 1):
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
                result = self.page.run_js("""
                    const sendBtn = document.querySelector('.btn-send');
                    if (sendBtn && !sendBtn.classList.contains('disabled')) {
                        sendBtn.click();
                        return 'sent';
                    }
                    return 'button disabled or not found';
                """)

                if result == 'sent':
                    logger.info(f"已发送文字: {text[:30]}...")
                    time.sleep(0.5)
                    return True
                else:
                    logger.warning(f"发送按钮不可用（尝试 {attempt}/{retries}），等待后重试...")
                    time.sleep(1)

            except Exception as e:
                logger.error(f"发送文字失败（尝试 {attempt}/{retries}）: {e}")
                time.sleep(1)

        logger.error(f"发送文字最终失败: {text[:30]}...")
        return False

    def send_resume(self) -> bool:
        """
        点击发送简历按钮，选择简历并发送。
        实际流程：
        1. 点击工具栏的"发简历"按钮，弹出菜单
        2. 在菜单中点击"附件上传"，打开文件选择对话框
        3. 选择简历文件（.docx/.pdf）
        4. 点击"发送"按钮
        """
        try:
            # 1. 点击"发简历"按钮打开菜单
            self.page.run_js("""
                const btns = document.querySelectorAll('.toolbar-btn');
                for (const btn of btns) {
                    if (btn.textContent.trim().startsWith('发简历')) {
                        btn.click();
                        return 'clicked';
                    }
                }
                return 'not found';
            """)
            time.sleep(1)

            # 2. 点击"附件上传"选项
            result = self.page.run_js("""
                const items = document.querySelectorAll('.nav-resume-box li');
                for (const item of items) {
                    if (item.textContent.includes('附件上传')) {
                        item.querySelector('a').click();
                        return 'clicked upload';
                    }
                }
                return 'upload option not found';
            """)
            logger.info(f"选择附件上传: {result}")
            time.sleep(2)  # 等待对话框打开

            # 3. 检查是否有限制弹窗（BOSS限制同时只能有3份附件）
            limit_dialog = self.page.run_js("""
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.textContent.trim() === '我知道了') {
                        btn.click();
                        return 'limit dialog dismissed';
                    }
                }
                return 'no limit dialog';
            """)
            if 'dismissed' in str(limit_dialog):
                logger.warning("BOSS平台限制：同时只能有3份附件文件，无法上传新简历")
                return False

            # 4. 在对话框中选择简历文件（在线编辑/附件简历）
            result = self.page.run_js("""
                // 查找对话框中的简历列表项
                const items = document.querySelectorAll('.resume-list-item, .upload-select-item, .dialog-body li');
                for (const item of items) {
                    const text = item.textContent;
                    if (text.includes('.docx') || text.includes('.pdf') || text.includes('简历')) {
                        item.click();
                        return 'selected: ' + text.substring(0, 30);
                    }
                }
                // 尝试直接找包含文件名的元素
                const allEles = document.querySelectorAll('.dialog-body *');
                for (const el of allEles) {
                    if (el.textContent.includes('.docx') || el.textContent.includes('.pdf')) {
                        el.click();
                        return 'selected file: ' + el.textContent.substring(0, 30);
                    }
                }
                return 'no resume found in dialog';
            """)
            logger.info(f"选择简历: {result}")
            time.sleep(0.5)

            # 5. 点击发送按钮（可能需要移除 disabled 类）
            result = self.page.run_js("""
                const sendBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === '发送');
                if (sendBtn) {
                    sendBtn.classList.remove('disabled');
                    sendBtn.disabled = false;
                    sendBtn.click();
                    return 'sent';
                }
                return 'send button not found';
            """)
            logger.info(f"发送简历结果: {result}")
            time.sleep(2)
            return 'sent' in str(result)
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
