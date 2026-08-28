"""
BOSS 自动回复机器人 - 主入口

持续监控 BOSS 直聘聊天页面的未读消息，自动回复。
"""

import logging
import signal
import sys
import time

from config import CHECK_INTERVAL
from page_handler import BossChatHandler
from reply_engine import ReplyEngine

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# 全局变量，用于优雅退出
running = True
handler = None


def signal_handler(sig, frame):
    """处理 Ctrl+C 信号，优雅退出"""
    global running
    logger.info("\n收到退出信号，正在关闭...")
    running = False


def process_chat(handler: BossChatHandler, reply_engine: ReplyEngine, chat_info: dict):
    """
    处理单个未读聊天：
    1. 进入聊天
    2. 读取最新消息
    3. 决定回复内容
    4. 发送回复
    """
    name = chat_info["name"]
    logger.info(f"--- 正在处理与 [{name}] 的聊天 ---")

    # 进入聊天
    handler.enter_chat(chat_info)

    # 读取最近消息
    messages = handler.read_latest_messages(count=5)
    if not messages:
        logger.info("未读取到消息，跳过")
        return

    # 找到最后一条对方发的消息（不是自己发的）
    latest_other_msg = None
    for msg in reversed(messages):
        if not msg["is_mine"]:
            latest_other_msg = msg["text"]
            break

    if not latest_other_msg:
        logger.info("最新消息是自己发的，无需回复")
        return

    logger.info(f"对方最新消息: {latest_other_msg}")

    # 获取上下文信息
    boss_name = handler.get_boss_name()
    job_name = handler.get_job_name()

    # 通过回复引擎决定回复
    action, content = reply_engine.get_reply(latest_other_msg, boss_name, job_name)

    # 执行回复
    if action == "resume":
        reply_engine.wait_human_delay()
        handler.send_resume()
    elif action == "text" and content:
        reply_engine.wait_human_delay()
        handler.send_text(content)
    else:
        logger.info("无合适回复，跳过")

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

    # 登录
    handler.login()
    handler.go_to_chat()

    logger.info(f"开始监控，每 {CHECK_INTERVAL} 秒检查一次未读消息...")
    logger.info("按 Ctrl+C 退出\n")

    # 主循环
    while running:
        try:
            # 检查回复频率限制
            if not reply_engine.can_reply():
                logger.warning("已达到每小时回复上限，等待下一小时...")
                time.sleep(60)
                continue

            # 获取未读聊天
            unread_chats = handler.get_unread_chats()

            if not unread_chats:
                logger.debug("暂无未读消息")
            else:
                logger.info(f"发现 {len(unread_chats)} 个未读会话")

                for chat_info in unread_chats:
                    if not running:
                        break
                    process_chat(handler, reply_engine, chat_info)
                    reply_engine.wait_human_delay()

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"运行时错误: {e}", exc_info=True)

        # 等待下一次检查
        if running:
            time.sleep(CHECK_INTERVAL)

    # 清理
    logger.info("正在关闭浏览器...")
    handler.close()
    logger.info("机器人已停止")


if __name__ == "__main__":
    main()
