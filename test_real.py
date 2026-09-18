"""真机实测脚本：连接真实 BOSS 直聘，读取真实聊天记录

测试流程：
1. 启动浏览器（无头/有头）
2. 加载 Cookie 自动登录
3. 导航到聊天页面
4. 读取未读聊天列表
5. 逐个进入聊天，读取真实消息内容
6. 调用回复引擎生成回复（不实际发送，仅验证回复质量）
"""

import sys
import os
import json
import time
import logging

# 确保用项目 venv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from boss_bot.log_manager import setup_logging
setup_logging()
logger = logging.getLogger("real_test")

from boss_bot.page_handler import BossChatHandler
from boss_bot.reply_engine import ReplyEngine
from boss_bot.state_store import StateStore
from boss_bot.message_store import MessageStore


def run_real_test(headless: bool = True, dry_run: bool = True):
    """
    Args:
        headless: 无头模式
        dry_run: True=只读取消息和生成回复但不发送；False=实际发送回复
    """
    mode = "无头" if headless else "有头"
    action = "dry-run（不发送）" if dry_run else "实际发送"
    print(f"\n{'='*60}")
    print(f"  BOSS 直聘真机实测 - {mode}模式 - {action}")
    print(f"{'='*60}\n")

    # 1. 启动浏览器 + 登录
    print("[1] 启动浏览器并登录...")
    handler = BossChatHandler(headless=headless)
    logged_in = handler.login()
    if not logged_in:
        if not headless:
            print("  ⏳ 等待用户在浏览器中手动登录/完成安全验证...")
            if handler.wait_for_login_confirm(timeout=300):
                handler.go_to_chat()
                time.sleep(3)
                if not handler._is_login_page() and not handler._is_security_verify_page():
                    logged_in = True
        if not logged_in:
            print("  ❌ 登录失败！Cookie 可能已过期")
            handler.close()
            return False
    print("  ✅ 登录成功")

    # 2. 导航到聊天页面
    print("\n[2] 导航到聊天页面...")
    handler.go_to_chat()
    time.sleep(2)
    print(f"  当前URL: {handler.page.url}")

    # 3. 读取未读聊天列表
    print("\n[3] 读取未读聊天列表...")
    unread_chats = handler.get_unread_chats()
    if not unread_chats:
        print("  （无未读消息）")
    else:
        print(f"  发现 {len(unread_chats)} 个未读会话:")
        for i, chat in enumerate(unread_chats):
            print(f"    [{i}] {chat['name']} (未读{chat.get('unread_count',1)}条) - 预览: {chat.get('preview','')[:50]}")

    # 4. 读取所有聊天会话（不只是未读的）
    print("\n[4] 读取所有聊天会话列表...")
    all_chats = []
    try:
        result = handler.page.run_js('''(
            function() {
                var friendEls = document.querySelectorAll(".friend-content");
                var chats = [];
                for (var i = 0; i < friendEls.length; i++) {
                    var el = friendEls[i];
                    var nameEl = el.querySelector(".name-text");
                    var name = nameEl ? nameEl.textContent.trim() : "未知";
                    var previewEl = el.querySelector(".last-msg-text");
                    var preview = previewEl ? previewEl.textContent.trim() : "";
                    var badge = el.querySelector(".notice-badge");
                    var unread = badge && badge.offsetParent !== null && badge.textContent.trim();
                    chats.push({
                        index: i,
                        name: name,
                        preview: preview,
                        unread: unread ? parseInt(unread) : 0
                    });
                }
                return JSON.stringify(chats);
            }
        )()''', as_expr=True)
        if result:
            all_chats = json.loads(result)
        print(f"  共 {len(all_chats)} 个会话:")
        for chat in all_chats:
            unread_tag = f" [未读{chat['unread']}]" if chat['unread'] > 0 else ""
            print(f"    [{chat['index']}] {chat['name']}{unread_tag} - {chat['preview'][:60]}")
    except Exception as e:
        print(f"  读取会话列表失败: {e}")

    # 5. 逐个进入有未读消息的会话，读取真实消息
    print("\n[5] 进入会话读取真实消息...")
    reply_engine = ReplyEngine()
    msg_store = MessageStore()

    target_chats = unread_chats if unread_chats else all_chats[:3]  # 最多测3个

    if not target_chats:
        print("  没有可测试的会话")
        handler.close()
        return True

    for chat_info in target_chats[:3]:
        name = chat_info.get('name', '未知')
        print(f"\n  --- 会话: [{name}] ---")

        # 进入聊天
        if not handler.enter_chat(chat_info):
            print(f"  ❌ 进入会话失败")
            continue
        print(f"  ✅ 已进入会话")

        # 读取真实消息
        messages = handler.read_latest_messages(count=10)
        if not messages:
            print(f"  ❌ 未读取到消息")
            continue

        print(f"  读取到 {len(messages)} 条真实消息:")
        for msg in messages:
            sender = "对方" if msg.get('is_mine') == False else "我方"
            source = msg.get('source', '')
            source_tag = f" [{source}]" if source else ""
            text = msg.get('text', '')[:80]
            time_str = msg.get('time', '')
            print(f"    {sender}{source_tag} ({time_str}): {text}")

        # 获取上下文
        boss_name = handler.get_boss_name()
        job_name = handler.get_job_name()
        print(f"  BOSS名称: {boss_name}, 岗位: {job_name}")

        # 调用回复引擎生成回复（dry-run 不发送）
        latest_other_msg = None
        for msg in reversed(messages):
            if not msg.get("is_mine"):
                latest_other_msg = msg.get("text", "")
                break

        if not latest_other_msg:
            print(f"  最新消息是我方发的，无需回复")
            continue

        print(f"  对方最新消息: {latest_other_msg[:100]}")

        action, content, meta = reply_engine.get_reply(messages, boss_name, job_name, chat_name=name)
        print(f"  回复引擎决策: action={action}, source={meta.get('source','')}")
        if content:
            print(f"  生成回复内容: {content[:120]}")
        elif action == "resume":
            print(f"  决策: 发送简历")

        if not dry_run and action in ("text", "resume"):
            print(f"  >>> 实际发送回复...")
            if action == "text" and content:
                handler.send_text(content)
                print(f"  ✅ 已发送文字回复")
            elif action == "resume":
                handler.send_resume()
                print(f"  ✅ 已发送简历")
            time.sleep(2)

    # 6. 保存消息到 store
    print("\n[6] 消息已保存到 MessageStore")
    print(f"  messages/ 目录内容:")
    msg_dir = os.path.join(os.path.dirname(__file__), "messages")
    if os.path.exists(msg_dir):
        for f in os.listdir(msg_dir):
            fpath = os.path.join(msg_dir, f)
            if os.path.isfile(fpath):
                size = os.path.getsize(fpath)
                print(f"    {f} ({size} bytes)")

    # 清理
    print("\n[7] 关闭浏览器...")
    handler.close()
    print(f"\n{'='*60}")
    print(f"  {mode}模式真机实测完成")
    print(f"{'='*60}\n")
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="BOSS 直聘真机实测")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    parser.add_argument("--send", action="store_true", help="实际发送回复（默认 dry-run）")
    args = parser.parse_args()

    run_real_test(headless=args.headless, dry_run=not args.send)