"""
BOSS 自动回复机器人 - 主入口

持续监控 BOSS 直聘聊天页面的未读消息，自动回复。

特性：
- 四级回复决策：关键词规则 → 意图识别 → AI（多轮上下文）→ 兜底
- 已处理消息持久化去重，重启不重复回复
- 简历每会话只发一次，发送失败自动降级
- 面试邀约/offer 等重要事件：通知 + 自动转人工暂停
- 统计数据持久化 + 结构化事件日志（logs/events_YYYYMMDD.jsonl）
- 登录失效/验证码健康检查
- 会话切换校验，防止读到错误会话的消息
"""

import logging
import signal
import sys
import time
from datetime import datetime

from config import (
    CHECK_INTERVAL, CONTEXT_MESSAGE_COUNT, PAUSE_ON_IMPORTANT, RESUME_SEND_ONCE,
)
from page_handler import BossChatHandler
from reply_engine import ReplyEngine
from state_store import StateStore
from stats import Stats
from notify import Notifier
from event_logger import get_event_logger
from message_store import MessageStore

# 配置日志（控制台简洁 + 文件详细 + JSONL 事件流）
from logging_setup import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

# 全局变量，用于优雅退出
running = True
handler = None


def signal_handler(sig, frame):
    """处理 Ctrl+C 信号，优雅退出"""
    global running
    logger.info("\n收到退出信号，正在关闭...")
    running = False


def process_chat(handler: BossChatHandler, reply_engine: ReplyEngine, chat_info: dict,
                 state: StateStore, stats: Stats, notifier: Notifier):
    """
    处理单个未读聊天：
    1. 进入聊天（带切换校验，防止读到错误会话的消息）
    2. 读取最近消息（多轮上下文）
    3. 去重检查
    4. 决定回复内容（规则/意图/AI）
    5. 重要事件通知 + 转人工
    6. 执行回复并记录
    """
    events = get_event_logger()
    msg_store = MessageStore()
    name = chat_info["name"]
    logger.info(f"--- 正在处理与 [{name}] 的聊天 ---")

    # 人工接管模式下不自动回复
    if state.is_paused():
        logger.info("人工接管模式中，跳过自动回复")
        events.event("skip", chat=name, reason="paused")
        return

    # 进入聊天（带校验：确认页面顶栏姓名与目标一致）
    if not handler.enter_chat(chat_info):
        logger.warning(f"会话 [{name}] 切换校验失败，本次跳过")
        events.event("skip", chat=name, reason="switch_verify_failed")
        return

    # 读取最近消息（用于多轮上下文）
    messages = handler.read_latest_messages(count=CONTEXT_MESSAGE_COUNT)
    if not messages:
        logger.info("未读取到消息，跳过")
        events.event("skip", chat=name, reason="no_messages")
        return

    # 找到最后一条对方发的消息（is_mine=False 表示对方）
    latest_other_msg = None
    for msg in reversed(messages):
        if not msg.get("is_mine"):
            latest_other_msg = msg.get("text", "")
            break

    if not latest_other_msg:
        logger.info("最新消息是自己发的，无需回复")
        events.event("skip", chat=name, reason="latest_is_mine")
        return

    logger.info(f"对方最新消息: {latest_other_msg}")

    # 去重：该消息已处理过（重启/重复通知保护）
    if state.was_handled(name, latest_other_msg):
        logger.info("该消息已处理过，跳过（防重复回复）")
        stats.record_skip()
        events.event("skip", chat=name, reason="duplicate", message=latest_other_msg[:120])
        return

    # 获取上下文信息
    boss_name = handler.get_boss_name()
    job_name = handler.get_job_name()

    # 通过回复引擎决定回复
    action, content, meta = reply_engine.get_reply(messages, boss_name, job_name, chat_name=name)

    # 重要事件：通知 + 可选转人工暂停
    if notifier.notify_if_important(latest_other_msg, chat_name=name,
                                    job_name=job_name, intent=meta.get("intent", "")):
        stats.record_important()
        if PAUSE_ON_IMPORTANT:
            state.pause(reason=f"收到重要消息: {latest_other_msg[:50]}", chat_name=name)
            notifier.send_notification(
                title="机器人已暂停，转人工模式",
                content="检测到重要消息，自动回复已暂停。在 Web 界面点击「恢复」或删除 bot_state.json 可恢复。",
                level="info",
            )
            logger.warning("已切换为人工接管模式，自动回复暂停")

    # 执行回复
    if action == "resume" and RESUME_SEND_ONCE and state.resume_sent(name):
        # 已发过简历：降级为文字提醒，不重复发送
        logger.info("该会话已发送过简历，降级为文字提醒")
        from config import RESUME_DUPLICATE_REPLY
        action, content = "text", RESUME_DUPLICATE_REPLY
        meta["source"] = "intent"

    if action == "resume":
        reply_engine.wait_human_delay()
        if handler.send_resume():
            state.mark_resume_sent(name)
            stats.record_reply(source=meta.get("source", "rule"), action="resume")
            events.event("send", chat=name, type="resume", ok=True)
            msg_store.append_message(name, {
                "text": "[简历已发送]",
                "is_mine": True,
                "source": "bot",
                "action": "resume",
                "time": datetime.now().strftime("%H:%M"),
            }, job_name)
        else:
            logger.warning("简历发送失败，降级为文字告知")
            from config import RESUME_UNAVAILABLE_REPLY
            reply_engine.wait_human_delay()
            handler.send_text(RESUME_UNAVAILABLE_REPLY)
            msg_store.append_message(name, {
                "text": RESUME_UNAVAILABLE_REPLY,
                "is_mine": True,
                "source": "bot",
                "action": "text_fallback",
                "time": datetime.now().strftime("%H:%M"),
            }, job_name)
            notifier.send_notification(
                title="简历发送失败",
                content=f"[{name}]（{job_name or '未知岗位'}）请求简历但发送失败（可能没有可发送的简历文件），已回复降级话术。请检查 BOSS 账号的简历设置。",
                level="warning",
            )
            stats.record_reply(source=meta.get("source", "rule"), action="skip")
            events.event("send", chat=name, type="resume", ok=False,
                         fallback="text", message=latest_other_msg[:120])
    elif action == "text" and content:
        reply_engine.wait_human_delay()
        if handler.send_text(content):
            stats.record_reply(source=meta.get("source", "rule"), action="text")
            events.event("send", chat=name, type="text", ok=True,
                         reply=content[:120], source=meta.get("source", ""))
            msg_store.append_message(name, {
                "text": content,
                "is_mine": True,
                "source": "bot",
                "action": "text",
                "reply_source": meta.get("source", ""),
                "time": datetime.now().strftime("%H:%M"),
            }, job_name)
        else:
            stats.record_reply(source=meta.get("source", "rule"), action="skip")
            events.event("send", chat=name, type="text", ok=False,
                         reply=content[:120], source=meta.get("source", ""))
    else:
        logger.info("无合适回复，跳过")
        stats.record_reply(source=meta.get("source", "default"), action="skip")
        events.event("skip", chat=name, reason="no_action",
                     message=latest_other_msg[:120])

    # 记录已处理（无论是否实际发送，避免对同一条消息反复决策）
    state.mark_handled(name, latest_other_msg, action or "none")
    reply_engine.record_reply()


def main():
    global running, handler

    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("=" * 50)
    logger.info("BOSS 自动回复机器人启动")
    logger.info("=" * 50)

    # 初始化
    handler = BossChatHandler()
    reply_engine = ReplyEngine()
    state = StateStore()
    stats = Stats()
    notifier = Notifier()
    events = get_event_logger()

    # 登录
    handler.login()
    handler.go_to_chat()

    logger.info(f"开始监控，每 {CHECK_INTERVAL} 秒检查一次未读消息...")
    logger.info("按 Ctrl+C 退出\n")

    # 主循环
    while running:
        try:
            # 健康检查：登录失效 / 验证码
            health = handler.check_health()
            if health == "need_login":
                logger.error("登录已失效，请重新登录！")
                notifier.send_notification("登录失效", "BOSS 直聘登录已失效，机器人无法继续工作，请重新登录。", "error")
                events.event("error", where="health", error="need_login")
                time.sleep(60)
                continue
            if health == "captcha":
                logger.warning("检测到安全验证/验证码，暂停 60 秒...")
                notifier.send_notification("安全验证", "检测到安全验证/验证码，请人工处理！", "warning")
                events.event("error", where="health", error="captcha")
                time.sleep(60)
                continue

            # 检查回复频率限制
            if not reply_engine.can_reply():
                logger.warning("已达到每小时回复上限，等待下一小时...")
                time.sleep(60)
                continue

            # 人工接管模式提示
            if state.is_paused():
                info = state.pause_info()
                logger.info(f"人工接管模式中（{info.get('reason', '')}），仅监控不回复...")

            # 获取未读聊天
            unread_chats = handler.get_unread_chats()

            if not unread_chats:
                pass
            else:
                logger.info(f"发现 {len(unread_chats)} 个未读会话")

                for chat_info in unread_chats:
                    if not running:
                        break
                    process_chat(handler, reply_engine, chat_info, state, stats, notifier)
                    reply_engine.wait_human_delay()

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"运行时错误: {e}", exc_info=True)
            events.event("error", where="main_loop", error=str(e)[:300])

        # 等待下一次检查
        if running:
            time.sleep(CHECK_INTERVAL)

    # 清理
    logger.info("正在关闭浏览器...")
    handler.close()
    events.close()
    logger.info("机器人已停止")


if __name__ == "__main__":
    main()
