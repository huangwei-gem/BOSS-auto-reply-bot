"""
Flask 版机器人主循环

与 main.py 共享核心逻辑，但通过 Flask app context 共享状态。
启动后由 Web 界面控制，而非命令行。
"""
import logging
import time
from datetime import datetime

from boss_bot.config import CHECK_INTERVAL, CONTEXT_MESSAGE_COUNT, PAUSE_ON_IMPORTANT, RESUME_SEND_ONCE
from boss_bot.page_handler import BossChatHandler
from boss_bot.reply_engine import ReplyEngine
from boss_bot.state_store import StateStore
from boss_bot.stats import Stats
from boss_bot.notify import Notifier
from boss_bot.event_logger import get_event_logger
from boss_bot.message_store import MessageStore

logger = logging.getLogger("bot")


def run_bot_loop(app):
    """
    机器人主循环（在 Flask 后台线程运行）

    Args:
        app: Flask 应用实例，用于访问 app context 中的共享状态
    """
    with app.app_context():
        bot_state = app.config["BOT_STATE"]
        events = get_event_logger()

        handler = BossChatHandler(headless=bot_state.get("headless", False))
        app.config["_BOT_HANDLER"] = handler

        engine = ReplyEngine()
        state = StateStore()
        stats = Stats()
        notifier = Notifier()

        try:
            # 登录
            logger.info("正在检查登录状态...")
            logged_in = handler.login()
            if logged_in:
                bot_state["logged_in"] = True
                bot_state["needs_login"] = False
                logger.info("登录成功")
            else:
                bot_state["needs_login"] = True
                bot_state["logged_in"] = False
                logger.info("等待用户在浏览器登录后点击「我已登录」按钮...")
                if not handler.wait_for_login_confirm(timeout=300):
                    logger.error("登录超时")
                    bot_state["running"] = False
                    return
                bot_state["needs_login"] = False
                bot_state["logged_in"] = True
                logger.info("用户已确认登录，Cookie 已保存")

            # 主循环
            while bot_state["running"]:
                try:
                    # 健康检查
                    health = handler.check_health()
                    if health == "need_login":
                        logger.error("登录已失效，请重新登录！")
                        notifier.send_notification("登录失效", "BOSS 直聘登录已失效，请重新登录。", "error")
                        bot_state["logged_in"] = False
                        bot_state["needs_login"] = True
                        time.sleep(30)
                        continue
                    if health == "captcha":
                        logger.warning("检测到安全验证/验证码，暂停 60 秒...")
                        notifier.send_notification("安全验证", "检测到安全验证/验证码，请人工处理！", "warning")
                        time.sleep(60)
                        continue

                    # 频率限制
                    if not engine.can_reply():
                        logger.warning("已达到每小时回复上限，等待...")
                        time.sleep(60)
                        continue

                    # 人工接管模式
                    if state.is_paused():
                        info = state.pause_info()
                        logger.info(f"人工接管模式中（{info.get('reason', '')}），仅监控不回复...")

                    # 获取未读聊天
                    handler.go_to_chat()
                    unread_chats = handler.get_unread_chats()
                    bot_state["last_check"] = datetime.now().strftime("%H:%M:%S")

                    if unread_chats:
                        logger.info(f"发现 {len(unread_chats)} 个未读会话")

                        for chat_info in unread_chats:
                            if not bot_state["running"]:
                                break

                            name = chat_info["name"]
                            bot_state["current_chat"] = name

                            if state.is_paused():
                                logger.info("人工接管模式中，跳过自动回复")
                                events.event("skip", chat=name, reason="paused")
                                break

                            _process_single_chat(
                                handler, engine, state, stats, notifier, events,
                                chat_info, bot_state, CONTEXT_MESSAGE_COUNT,
                                PAUSE_ON_IMPORTANT, RESUME_SEND_ONCE
                            )

                            engine.wait_human_delay()

                    bot_state["current_chat"] = None

                except Exception as e:
                    logger.error(f"运行时错误: {e}")

                time.sleep(CHECK_INTERVAL)

        except Exception as e:
            logger.error(f"机器人异常: {e}")
        finally:
            handler.close()
            bot_state["running"] = False
            logger.info("机器人已停止")


def _process_single_chat(handler, engine, state, stats, notifier, events,
                         chat_info, bot_state, context_count,
                         pause_on_important, resume_send_once):
    """处理单个聊天会话（提取为独立函数，避免嵌套过深）"""
    name = chat_info["name"]
    logger.info(f"处理与 [{name}] 的聊天")

    # 进入聊天（带切换校验）
    if not handler.enter_chat(chat_info):
        logger.warning(f"会话 [{name}] 切换校验失败，本次跳过")
        events.event("skip", chat=name, reason="switch_verify_failed")
        return

    # 读取消息
    messages = handler.read_latest_messages(context_count)
    if not messages:
        logger.info("未读取到消息，跳过")
        events.event("skip", chat=name, reason="no_messages")
        return

    # 找最后一条对方发的消息
    latest = None
    for msg in reversed(messages):
        if not msg.get("is_mine"):
            latest = msg.get("text", "")
            break

    if not latest:
        logger.info("最新消息是自己发的，无需回复")
        events.event("skip", chat=name, reason="latest_is_mine")
        return

    logger.info(f"对方消息: {latest[:50]}...")

    # 去重检查
    if state.was_handled(name, latest):
        logger.info("该消息已处理过，跳过")
        stats.record_skip()
        events.event("skip", chat=name, reason="duplicate", message=latest[:120])
        return

    boss_name = handler.get_boss_name()
    job_name = handler.get_job_name()

    # 获取回复
    action, content, meta = engine.get_reply(messages, boss_name, job_name, chat_name=name)

    # 重要事件：通知 + 可选转人工
    if notifier.notify_if_important(latest, chat_name=name, job_name=job_name,
                                    intent=meta.get("intent", "")):
        stats.record_important()
        if pause_on_important:
            state.pause(reason=f"收到重要消息: {latest[:50]}", chat_name=name)
            notifier.send_notification("机器人已暂停，转人工模式",
                                       "检测到重要消息，自动回复已暂停。", "info")
            logger.warning("已切换为人工接管模式")

    # 简历去重降级
    if action == "resume" and resume_send_once and state.resume_sent(name):
        from boss_bot.config import RESUME_DUPLICATE_REPLY
        logger.info("该会话已发送过简历，降级为文字提醒")
        action, content = "text", RESUME_DUPLICATE_REPLY
        meta["source"] = "intent"

    # 执行回复
    msg_store = MessageStore()

    if action == "resume":
        engine.wait_human_delay()
        if handler.send_resume():
            state.mark_resume_sent(name)
            stats.record_reply(source=meta.get("source", "rule"), action="resume")
            bot_state["total_resumes"] = bot_state.get("total_resumes", 0) + 1
            events.event("send", chat=name, type="resume", ok=True)
            logger.info("已发送简历")
            msg_store.append_message(name, {
                "text": "[简历已发送]",
                "time": datetime.now().strftime("%H:%M"),
                "is_mine": True, "source": "bot", "action": "resume",
                "reply_source": meta.get("source", "rule"),
            }, job_name=job_name or "")
        else:
            from boss_bot.config import RESUME_UNAVAILABLE_REPLY
            logger.warning("简历发送失败，降级为文字告知")
            engine.wait_human_delay()
            handler.send_text(RESUME_UNAVAILABLE_REPLY)
            msg_store.append_message(name, {
                "text": RESUME_UNAVAILABLE_REPLY,
                "time": datetime.now().strftime("%H:%M"),
                "is_mine": True, "source": "bot", "action": "text",
                "reply_source": "fallback",
            }, job_name=job_name or "")
            notifier.send_notification("简历发送失败",
                f"[{name}]（{job_name or '未知岗位'}）请求简历但发送失败，请检查 BOSS 账号的简历设置。",
                "warning")
            stats.record_reply(source=meta.get("source", "rule"), action="skip")
            events.event("send", chat=name, type="resume", ok=False,
                         fallback="text", message=latest[:120])
    elif action == "text" and content:
        engine.wait_human_delay()
        if handler.send_text(content):
            stats.record_reply(source=meta.get("source", "rule"), action="text")
            bot_state["total_replies"] = bot_state.get("total_replies", 0) + 1
            events.event("send", chat=name, type="text", ok=True,
                         reply=content[:120], source=meta.get("source", ""))
            logger.info(f"已回复: {content[:30]}...")
            msg_store.append_message(name, {
                "text": content,
                "time": datetime.now().strftime("%H:%M"),
                "is_mine": True, "source": "bot", "action": "text",
                "reply_source": meta.get("source", "rule"),
            }, job_name=job_name or "")
        else:
            stats.record_reply(source=meta.get("source", "rule"), action="skip")
            events.event("send", chat=name, type="text", ok=False, reply=content[:120])
    else:
        logger.info("无合适回复，跳过")
        stats.record_reply(source=meta.get("source", "default"), action="skip")
        events.event("skip", chat=name, reason="no_action", message=latest[:120])

    # 记录已处理
    state.mark_handled(name, latest, action or "none")
    engine.record_reply()
