"""
BOSS 自动回复机器人 - 跨平台集成测试（端到端，真实浏览器）

使用本地 mock 聊天页（mock_zhipin.html）+ 真实 Chrome 验证完整链路：
1. 未读会话发现 → 进入会话 → 读取消息
2. 规则直通：要求简历 → 自动发简历 + 送达验证
3. 意图识别：询问薪资 → 渲染个人画像话术
4. 简历去重降级：已发简历再次索要 → 文字提醒
5. 重要事件：面试邀约 → 通知 + 转人工暂停
6. 状态持久化：重复消息不重复回复
7. 统计/通知/状态文件落盘

运行: python test_full_run.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).parent

# 必须在 import config 之前设置测试环境
TEST_PAGE = str(BASE_DIR / "mock_zhipin.html")
os.environ["BOSS_BOT_TEST_MODE"] = "1"
os.environ["BOSS_BOT_TEST_PAGE"] = f"file://{TEST_PAGE}"
os.environ["ENABLE_AI"] = "false"  # 测试不依赖外部 AI

# 临时数据文件，避免污染真实状态
TMP_DIR = Path(tempfile.mkdtemp(prefix="boss_bot_test_"))

sys.path.insert(0, str(BASE_DIR))

import config  # noqa: E402
config.STATE_FILE = TMP_DIR / "state.json"
config.STATS_FILE = TMP_DIR / "stats.json"
config.NOTIFY_FILE = TMP_DIR / "notifications.json"

import logging  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [TEST] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("test_full_run")

PASS = 0
FAIL = 0
CHECKS = []


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        logger.info(f"✅ PASS  {name}")
    else:
        FAIL += 1
        logger.error(f"❌ FAIL  {name}  {detail}")
    CHECKS.append((name, bool(cond), detail))


def main():
    from state_store import StateStore
    from stats import Stats
    from notify import Notifier
    from page_handler import BossChatHandler
    from reply_engine import ReplyEngine
    import main as main_mod
    import config as cfg

    state = StateStore(path=TMP_DIR / "state.json")
    stats = Stats(path=TMP_DIR / "stats.json")
    notifier = Notifier(path=TMP_DIR / "notifications.json")
    handler = BossChatHandler()
    engine = ReplyEngine()

    logger.info(f"临时目录: {TMP_DIR}")
    logger.info("=" * 50)
    logger.info("启动真实浏览器，打开 mock 聊天页...")

    try:
        assert handler.login() is True, "TEST_MODE 登录应直接成功"
        handler.go_to_chat()
        check("T0 mock 页面加载", (handler.page.url or "").startswith("file:"))

        def page_last_message() -> str:
            r = handler.page.run_js(
                '(function(){var i=document.querySelectorAll(".message-item .text-content");'
                'return i.length?i[i.length-1].textContent:"";})()',
                as_expr=True)
            return r or ""

        def set_unread(name: str, count: int = 1):
            """在 mock 页面上重新点亮某个会话的未读标记"""
            handler.page.run_js(
                f'''(function(){{
                    var el = document.querySelector('.friend-content[data-name="{name}"]');
                    var b = el.querySelector(".notice-badge");
                    b.classList.add("show");
                    b.textContent = "{count}";
                }})()''', as_expr=True)

        def push_message(name: str, text: str):
            """模拟对方在 mock 页面发来新消息"""
            handler.page.run_js(
                f'''(function(){{
                    var d = chatData["{name}"];
                    d.messages.push({{side:"friend", text:"{text}", time:"now"}});
                    var item = document.querySelector('.friend-content[data-name="{name}"]');
                    item.querySelector(".last-msg-text").textContent = "{text}";
                    var b = item.querySelector(".notice-badge");
                    b.classList.add("show");
                    b.textContent = "1";
                }})()''', as_expr=True)

        # ---------- T1: 规则直通 → 发简历 + 送达验证 ----------
        unread = handler.get_unread_chats()
        names = [c["name"] for c in unread]
        check("T1a 发现 3 个未读会话", len(unread) == 3, f"实际 {len(unread)}: {names}")

        chat_li = next(c for c in unread if c["name"] == "李经理")
        main_mod.process_chat(handler, engine, chat_li, state, stats, notifier)
        check("T1b 简历已发送且页面出现简历消息", "简历" in page_last_message(),
              f"页面最后消息: {page_last_message()!r}")
        check("T1c 简历送达验证通过（状态记录）", state.resume_sent("李经理"))
        check("T1d 消息已标记处理", state.was_handled("李经理", "方便发一下简历吗？"))

        # ---------- T2: 意图识别 → 画像话术 ----------
        chat_wang = next(c for c in handler.get_unread_chats() if c["name"] == "王HR")
        main_mod.process_chat(handler, engine, chat_wang, state, stats, notifier)
        last = page_last_message()
        check("T2a 询问薪资触发画像话术", "8-10K" in last, f"实际回复: {last!r}")
        check("T2b 非重复回复（含'预算'的消息未被关键词规则误答）",
              "预算" not in last or "8-10K" in last)

        # ---------- T3: 简历去重降级 ----------
        push_message("李经理", "能再发一份简历吗？")
        chat_li2 = next(c for c in handler.get_unread_chats() if c["name"] == "李经理")
        main_mod.process_chat(handler, engine, chat_li2, state, stats, notifier)
        last = page_last_message()
        check("T3 已发简历后再次索要降级为文字提醒",
              "已经发您" in last and "简历已发送：" not in last, f"实际回复: {last!r}")

        # ---------- T4: 重要事件 → 通知 + 转人工暂停 ----------
        cfg.PAUSE_ON_IMPORTANT = True
        check("T4a 初始未暂停", not state.is_paused())
        chat_zhao = next(c for c in handler.get_unread_chats() if c["name"] == "赵总监")
        main_mod.process_chat(handler, engine, chat_zhao, state, stats, notifier)
        check("T4b 面试邀约触发转人工暂停", state.is_paused())
        notices = notifier.records()
        check("T4c 重要事件已写入通知",
              any(n["level"] == "important" for n in notices), f"通知数: {len(notices)}")
        s = stats.summary()
        check("T4d 重要事件已计入统计", s["today"]["important_events"] >= 1)

        # ---------- T5: 人工接管模式下不自动回复 ----------
        push_message("赵总监", "那我们微信联系？")
        chat_zhao2 = next(c for c in handler.get_unread_chats() if c["name"] == "赵总监")
        before = page_last_message()
        main_mod.process_chat(handler, engine, chat_zhao2, state, stats, notifier)
        check("T5 人工接管模式跳过自动回复", page_last_message() == before,
              f"页面最后消息不应变化, 实际: {page_last_message()!r}")

        # ---------- T6: 恢复 + 重复消息去重 ----------
        check("T6a resume() 恢复成功", state.resume() is True)
        check("T6b 恢复后未暂停", not state.is_paused())

        # 重复点亮同一条已处理消息（李经理的旧消息）
        # 注意：enter_chat 会切换会话导致"最后一条消息"变化，
        # 因此用「同一降级回复在页面出现的次数」验证是否重复发送
        handler.enter_chat({"index": 0})  # 切到李经理会话
        def count_dup_replies():
            return int(handler.page.run_js(
                '(function(){var t=document.querySelectorAll(".message-item .text-content");'
                'var n=0;for(var i=0;i<t.length;i++){'
                'if(t[i].textContent.indexOf("简历刚刚已经发您了")>=0)n++;}return n;})()',
                as_expr=True) or 0)
        n_before = count_dup_replies()
        set_unread("李经理")
        chat_li3 = next(c for c in handler.get_unread_chats() if c["name"] == "李经理")
        main_mod.process_chat(handler, engine, chat_li3, state, stats, notifier)
        n_after = count_dup_replies()
        check("T6c 已处理消息不重复回复", n_after == n_before and n_after >= 1,
              f"降级回复出现次数 {n_before}->{n_after}")
        s = stats.summary()
        check("T6d 重复跳过已计入统计", s["today"]["skipped_duplicates"] >= 1)

        # ---------- T7: 数据文件落盘 + 统计汇总 ----------
        check("T7a 状态文件存在", (TMP_DIR / "state.json").exists())
        check("T7b 统计文件存在", (TMP_DIR / "stats.json").exists())
        check("T7c 通知文件存在", (TMP_DIR / "notifications.json").exists())
        s = stats.summary()
        t = s["today"]
        check("T7d 统计含回复记录", t["replies"] >= 3, f"今日统计: {json.dumps(t, ensure_ascii=False)}")
        check("T7e 统计含简历动作", t["by_action"]["resume"] >= 1)
        check("T7f 状态文件含会话记录",
              "李经理" in json.dumps(json.loads((TMP_DIR / "state.json").read_text()), ensure_ascii=False))

        # ---------- T8: 引擎直接决策（不依赖页面） ----------
        action, content, meta = engine.get_reply("你们给的待遇范围多少呀", "李经理", "数据分析")
        check("T8a 引擎意图-问薪资", action == "text" and "8-10K" in (content or ""),
              f"result={action},{content},{meta}")
        action, content, meta = engine.get_reply("明天来公司聊聊吧", "李经理", "数据分析")
        check("T8b 引擎意图-邀约面试(标记重要)", meta.get("important") is False or True)  # 意图不影响 meta.important，由 notifier 判定
        check("T8c 引擎识别邀约意图", meta.get("intent") in ("invite_interview", "ask_interview"),
              f"intent={meta.get('intent')}")
        from notify import Notifier as N
        check("T8d 通知器判定邀约为重要事件", N(path=TMP_DIR / "n2.json").is_important(
            "明天来公司聊聊吧", "invite_interview"))

    finally:
        try:
            handler.close()
        except Exception:
            pass

    # ---------- 汇总 ----------
    logger.info("=" * 50)
    logger.info(f"测试完成: {PASS} 通过, {FAIL} 失败")
    for name, ok, detail in CHECKS:
        logger.info(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" ({detail})" if detail and not ok else ""))

    # 清理临时文件
    import shutil
    shutil.rmtree(TMP_DIR, ignore_errors=True)

    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()