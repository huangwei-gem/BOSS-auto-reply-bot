"""
BOSS 自动回复机器人 - 页面操作模块

封装 DrissionPage 的所有页面操作。
CSS 选择器基于 BOSS 直聘聊天页面实际结构（已通过浏览器实测验证）。
支持 macOS / Windows / Linux 多平台自动检测系统 Chrome。
"""

import os
import sys
import time
import json
import logging
import platform
from typing import List, Optional, Dict
from pathlib import Path

from config import CHAT_URL, COOKIE_FILE
from browser_launcher import launch_browser, BrowserInstance

logger = logging.getLogger(__name__)

# 基础目录
BASE_DIR = Path(__file__).parent


class BossChatHandler:
    """BOSS 聊天页面操作处理器"""

    def __init__(self):
        self.browser: BrowserInstance = launch_browser()
        self.page = self.browser.page
        self._logged_in = False

    def login(self, timeout: int = 120):
        """
        检查登录状态，未登录则等待手动登录。
        登录后保存 cookies 以便下次自动登录。
        """
        # 先访问主站，确保 Cookie 作用域正确
        self.page.get("https://www.zhipin.com")
        time.sleep(2)

        # 处理首次访问弹窗（"我已登录" / "关闭"）
        self._dismiss_login_popup()

        # 尝试加载已保存的 cookies
        if self._load_cookies():
            self.page.get(CHAT_URL)
            time.sleep(3)
            if not self._is_login_page():
                logger.info("通过 Cookie 自动登录成功")
                self._logged_in = True
                return

        # 需要手动登录
        logger.info(f"需要登录，正在跳转到登录页面...（{timeout}秒内完成）")
        self.page.get("https://www.zhipin.com/web/user/?ka=header-login")
        logger.info("请在浏览器中手动登录 BOSS 直聘，登录后自动继续...")

        # 非交互式等待：轮询检查是否已登录
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(3)
            if not self._is_login_page():
                logger.info("登录成功！")
                self._save_cookies()
                self._logged_in = True
                return
            logger.debug("等待登录中...")

        raise TimeoutError(f"登录超时（{timeout}秒），请重试")

    def _dismiss_login_popup(self):
        """处理 BOSS 首页首次访问弹窗"""
        try:
            close_btn = self.page.ele("text=关闭", timeout=3)
            if close_btn:
                close_btn.click()
                logger.info("已关闭首页弹窗")
                time.sleep(0.5)
        except Exception:
            pass

    def _is_login_page(self) -> bool:
        """判断当前是否需要登录"""
        try:
            url = self.page.url or ""
            if "login" in url or "/web/user" in url:
                return True
            if "chat" in url or "geek" in url:
                # 检查是否有聊天列表
                result = self.page.run_js(
                    'document.querySelector(".friend-content") ? "ok" : "no"',
                    as_expr=True
                )
                return result != "ok"
            return True
        except Exception:
            return True

    def _save_cookies(self):
        """保存 cookies 到文件"""
        try:
            self.browser.save_cookies(COOKIE_FILE)
            logger.info(f"Cookie 已保存到 {COOKIE_FILE}")
        except Exception as e:
            logger.error(f"保存 Cookie 失败: {e}")

    def _load_cookies(self) -> bool:
        """从文件加载 cookies"""
        try:
            result = self.browser.load_cookies(COOKIE_FILE)
            if result:
                logger.info(f"已从 {COOKIE_FILE} 加载 Cookie")
            return result
        except Exception as e:
            logger.error(f"加载 Cookie 失败: {e}")
            return False

    def go_to_chat(self):
        """导航到聊天页面"""
        current_url = self.page.url or ""
        if CHAT_URL not in current_url:
            self.page.get(CHAT_URL)
            time.sleep(3)

    def get_unread_chats(self) -> List[Dict]:
        """
        获取所有未读聊天会话列表。

        实测 CSS（2026-09-09 浏览器验证）:
        - 聊天项容器: .friend-content（不是 ul[role='group'] > li[role='listitem']）
        - 未读标记: .notice-badge（在 .figure 内）
        - 名称: .name-text（在 .title-box .name-box 内）
        - 最后一条消息: .last-msg-text（在 .gray.last-msg 内）
        """
        self.go_to_chat()
        time.sleep(1)

        unread_chats = []
        try:
            # 用 JS 获取未读聊天信息（DrissionPage eles 对 li[role=listitem] 返回 0）
            result = self.page.run_js('''(
                function() {
                    var friendEls = document.querySelectorAll(".friend-content");
                    var unread = [];
                    for (var i = 0; i < friendEls.length; i++) {
                        var el = friendEls[i];
                        // 检查是否有未读标记
                        var badge = el.querySelector(".notice-badge");
                        if (!badge) continue;

                        var countText = badge.textContent.trim();
                        var count = countText ? parseInt(countText) || 1 : 1;

                        var nameEl = el.querySelector(".name-text");
                        var name = nameEl ? nameEl.textContent.trim() : "未知";

                        var previewEl = el.querySelector(".last-msg-text");
                        var preview = previewEl ? previewEl.textContent.trim() : "";

                        unread.push({
                            index: i,
                            name: name,
                            preview: preview,
                            unread_count: count
                        });
                    }
                    return JSON.stringify(unread);
                }
            )()''', as_expr=True)

            if result:
                unread_chats = json.loads(result)
                # 保存元素引用以便后续点击
            for chat in unread_chats:
                # 找到对应的 DOM 元素
                el = self.page.eles('.friend-content')[chat['index']]
                chat['element'] = el

        except Exception as e:
            logger.error(f"获取未读聊天列表失败: {e}")

        logger.info(f"发现 {len(unread_chats)} 个未读会话")
        return unread_chats

    def enter_chat(self, chat_info: dict):
        """点击进入某个聊天，等待聊天内容加载"""
        if 'element' in chat_info:
            chat_info['element'].click()
        else:
            # 用 JS 点击
            idx = chat_info.get('index', 0)
            self.page.run_js(
                f'document.querySelectorAll(".friend-content")[{idx}].click()',
                as_expr=True
            )
        time.sleep(3)

        # 等待输入框加载
        for _ in range(10):
            ready = self.page.run_js(
                'document.querySelector("#chat-input") ? "ready" : "not ready"',
                as_expr=True
            )
            if ready == 'ready':
                break
            time.sleep(0.5)

    def read_latest_messages(self, count: int = 5) -> List[Dict]:
        """
        读取当前聊天中最近的消息。

        实测 CSS（2026-09-09 浏览器验证）:
        - 消息项: .message-item（li 元素，不是 div）
        - 对方消息: .message-item.item-friend
        - 我方消息: .message-item（无 item-friend class）
        - 消息文字: .text-content
        - 时间: .item-time .time

        注意: DrissionPage 的 eles() 对 .message-item 返回 0，必须用 JS
        """
        messages = []
        try:
            result = self.page.run_js(f'''(
                function() {{
                    var items = document.querySelectorAll(".message-item");
                    var result = [];
                    var start = Math.max(0, items.length - {count});
                    for (var i = start; i < items.length; i++) {{
                        var item = items[i];
                        var textEl = item.querySelector(".text-content");
                        var timeEl = item.querySelector(".item-time .time");
                        var cls = item.className || "";
                        result.push({{
                            text: textEl ? textEl.textContent.trim() : "",
                            time: timeEl ? timeEl.textContent.trim() : "",
                            isFriend: cls.indexOf("item-friend") >= 0
                        }});
                    }}
                    return JSON.stringify(result);
                }}
            )()''', as_expr=True)

            if result:
                messages = json.loads(result)
        except Exception as e:
            logger.error(f"读取消息失败: {e}")

        return messages

    def get_boss_name(self) -> str:
        """获取当前聊天对象的名称"""
        try:
            result = self.page.run_js(
                'document.querySelector(".top-info-content .name-text") ? document.querySelector(".top-info-content .name-text").textContent.trim() : ""',
                as_expr=True
            )
            return result or ""
        except Exception:
            return ""

    def get_job_name(self) -> str:
        """获取当前聊天对应的岗位名称"""
        try:
            result = self.page.run_js(
                'document.querySelector(".chat-position-content .position-content") ? document.querySelector(".chat-position-content .position-content").textContent.trim() : ""',
                as_expr=True
            )
            return result or ""
        except Exception:
            return ""

    def send_text(self, text: str, retries: int = 3) -> bool:
        """
        在当前聊天中输入并发送文字消息。

        实测 CSS（2026-09-09 浏览器验证）:
        - 输入框: #chat-input.chat-input（contenteditable div）
        - 发送按钮: .btn-v2.btn-sure-v2.btn-send（注意有 disabled class 时不可点击）
        - 输入方式: textContent + dispatchEvent('input') 才能触发 Vue 响应
        """
        for attempt in range(1, retries + 1):
            try:
                # 转义特殊字符
                escaped_text = text.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')

                # 输入文字
                type_result = self.page.run_js(f'''(
                    function() {{
                        var input = document.querySelector("#chat-input");
                        if (!input) return "not found";
                        input.focus();
                        input.textContent = `{escaped_text}`;
                        input.dispatchEvent(new Event("input", {{bubbles: true}}));
                        return "typed";
                    }}
                )()''', as_expr=True)

                if type_result != 'typed':
                    logger.warning(f"输入框未找到（尝试 {attempt}/{retries}）")
                    time.sleep(1)
                    continue

                time.sleep(0.5)

                # 点击发送按钮
                send_result = self.page.run_js('''(
                    function() {
                        var btn = document.querySelector(".btn-send");
                        if (!btn) return "button not found";
                        if (btn.classList.contains("disabled")) return "button disabled";
                        btn.click();
                        return "sent";
                    }
                )()''', as_expr=True)

                if send_result == 'sent':
                    logger.info(f"已发送文字: {text[:30]}...")
                    time.sleep(0.5)
                    return True
                else:
                    logger.warning(f"发送按钮不可用（尝试 {attempt}/{retries}）: {send_result}")
                    time.sleep(1)

            except Exception as e:
                logger.error(f"发送文字失败（尝试 {attempt}/{retries}）: {e}")
                time.sleep(1)

        logger.error(f"发送文字最终失败: {text[:30]}...")
        return False

    def send_resume(self) -> bool:
        """
        点击发送简历按钮，选择简历并发送。

        实测 CSS（2026-09-09 浏览器验证）:
        - 发简历按钮: .toolbar-btn（文本以"发简历"开头）
        - 简历弹窗: .choose-resume-dialog
        - 简历列表: .resume-list .list-item
        - 简历名称: .resume-name
        - 发送按钮: .btn-v2.btn-sure-v2.btn-confirm（有 disabled class 时不可点击）
        """
        try:
            # 1. 点击"发简历"按钮
            self.page.run_js('''(
                function() {
                    var btns = document.querySelectorAll(".toolbar-btn");
                    for (var i = 0; i < btns.length; i++) {
                        if (btns[i].textContent.trim().indexOf("发简历") >= 0) {
                            btns[i].click();
                            return "clicked";
                        }
                    }
                    return "not found";
                }
            )()''', as_expr=True)
            time.sleep(2)

            # 2. 选择简历文件（点击第一个 .list-item）
            result = self.page.run_js('''(
                function() {
                    var items = document.querySelectorAll(".resume-list .list-item");
                    if (items.length > 0) {
                        items[0].click();
                        var name = items[0].querySelector(".resume-name");
                        return "selected: " + (name ? name.textContent.trim() : "unknown");
                    }
                    return "no resume found";
                }
            )()''', as_expr=True)
            logger.info(f"选择简历: {result}")
            time.sleep(1)

            if result and 'no resume' in str(result):
                logger.error("没有可发送的简历")
                return False

            # 3. 点击发送按钮
            result = self.page.run_js('''(
                function() {
                    var btn = document.querySelector(".btn-v2.btn-sure-v2.btn-confirm");
                    if (!btn) return "send button not found";
                    if (btn.classList.contains("disabled")) return "button disabled";
                    btn.disabled = false;
                    btn.classList.remove("disabled");
                    btn.click();
                    return "sent";
                }
            )()''', as_expr=True)
            logger.info(f"发送简历结果: {result}")
            time.sleep(3)
            return result and 'sent' in str(result)
        except Exception as e:
            logger.error(f"发送简历失败: {e}")
            return False

    def close(self):
        """关闭浏览器"""
        try:
            self.browser.quit()
            logger.info("浏览器已关闭")
        except Exception:
            pass
