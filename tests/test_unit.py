"""
BOSS 自动回复机器人 - 单元测试套件

覆盖：意图分类 / 规则引擎 / 状态持久化 / 统计 / 通知 / 回复引擎 / 画像模板
运行: python tests/run_tests.py  （或 venv/bin/python -m unittest discover tests -v）
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

# 测试不依赖外部 AI
import os
os.environ["ENABLE_AI"] = "false"


class TestIntent(unittest.TestCase):
    """意图分类"""

    def test_invite_interview(self):
        from intent import classify
        cases = [
            "明天下午方便来公司面试吗？",
            "想邀您来公司聊聊",
            "我们想约个时间面试",
            "本周可以约个面试吗",
            "诚挚邀您参加视频面试",
        ]
        for c in cases:
            self.assertEqual(classify(c), "invite_interview", f"应识别为邀约: {c}")

    def test_ask_salary(self):
        from intent import classify
        cases = [
            "你们这边给的预算范围是多少呀？",
            "这个岗位薪资待遇怎么样？",
            "公司薪资给多少呢",
            "这个岗位最高能给到多少",
        ]
        for c in cases:
            self.assertEqual(classify(c), "ask_salary", f"应识别为问薪资: {c}")

    def test_ask_resume(self):
        from intent import classify
        for c in ["方便发一下简历吗？", "发个简历给我看看", "我想看看你的简历"]:
            self.assertEqual(classify(c), "ask_resume", f"应识别为要简历: {c}")

    def test_tell_salary(self):
        from intent import classify
        self.assertEqual(classify("我们薪资是12-15K，你看可以吗"), "tell_salary")

    def test_greeting(self):
        from intent import classify
        for c in ["您好", "你好呀", "在吗？", "hello", "早上好，", "在不在"]:
            self.assertEqual(classify(c), "greeting", f"应识别为问候: {c}")

    def test_ask_job_content(self):
        from intent import classify
        for c in ["这个岗位主要做什么呢？", "介绍下岗位职责", "日常工作内容是什么"]:
            self.assertEqual(classify(c), "ask_job_content", f"应识别为问工作内容: {c}")

    def test_contact_request(self):
        from intent import classify
        for c in ["加个微信吧", "方便留个联系方式吗", "你电话多少"]:
            self.assertEqual(classify(c), "contact_request", f"应识别为要联系方式: {c}")

    def test_other(self):
        from intent import classify
        self.assertEqual(classify("好的，我考虑一下"), "other")
        self.assertEqual(classify(""), "other")
        self.assertEqual(classify(None), "other")

    def test_priority(self):
        """邀约优先于薪资（一句话包含两者）"""
        from intent import classify
        self.assertEqual(classify("薪资多少都好说，明天来公司面试吧"), "invite_interview")


class TestRuleEngine(unittest.TestCase):
    """关键词规则直通"""

    def test_resume_action(self):
        from rules import RuleEngine
        engine = RuleEngine()
        self.assertEqual(engine.match("方便发一下简历吗？"), ("resume", None))

    def test_text_reply(self):
        from rules import RuleEngine
        engine = RuleEngine()
        action, content = engine.match("你们的薪资待遇怎么样")
        self.assertEqual(action, "text")
        self.assertIn("薪资", content)

    def test_no_match(self):
        from rules import RuleEngine
        engine = RuleEngine()
        self.assertIsNone(engine.match("好的我考虑一下"))

    def test_case_insensitive(self):
        from rules import RuleEngine
        engine = RuleEngine({"OFFER": "好的"})
        self.assertEqual(engine.match("OFFER"), ("text", "好的"))

    def test_question_context_no_false_match(self):
        """疑问/否定上下文不应触发动作（"是否投递过简历"≠要简历）"""
        from rules import RuleEngine
        engine = RuleEngine()
        self.assertIsNone(engine.match("同学好，请问是否公司官网投递过简历？"))
        self.assertIsNone(engine.match("不用发简历，等通知就好"))
        self.assertIsNone(engine.match("无需再发简历了"))
        self.assertIsNone(engine.match("你有没有收到我的简历呀"))
        # 正常请求仍然命中
        self.assertEqual(engine.match("请把简历发我一份"), ("resume", None))


class TestEventLogger(unittest.TestCase):
    """结构化事件日志"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bot_test_events_"))
        import event_logger
        self.event_logger = event_logger

    def test_event_written_as_jsonl(self):
        logger = self.event_logger.EventLogger(log_dir=self.tmp, enabled=True)
        logger.event("reply", chat="张三", intent="ask_salary", action="text")
        logger.event("send", chat="张三", type="text", ok=True)
        logger.close()
        files = list(self.tmp.glob("events_*.jsonl"))
        self.assertEqual(len(files), 1)
        lines = files[0].read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(len(lines), 2)
        rec = json.loads(lines[0])
        self.assertEqual(rec["kind"], "reply")
        self.assertEqual(rec["chat"], "张三")
        self.assertIn("ts", rec)

    def test_disabled_no_write(self):
        logger = self.event_logger.EventLogger(log_dir=self.tmp, enabled=False)
        logger.event("reply", chat="张三")
        self.assertEqual(list(self.tmp.glob("events_*.jsonl")), [])

    def test_get_event_logger_singleton(self):
        a = self.event_logger.get_event_logger()
        b = self.event_logger.get_event_logger()
        self.assertIs(a, b)


class TestAIRateLimit(unittest.TestCase):
    """AI 容错：限流重试、空 Key 跳过"""

    def test_is_rate_limit_error(self):
        from reply_engine import ReplyEngine
        engine = ReplyEngine.__new__(ReplyEngine)
        self.assertTrue(engine._is_rate_limit_error(Exception("Error code: 429 - limit")))
        self.assertTrue(engine._is_rate_limit_error(Exception("rate_limit_error: too fast")))
        self.assertFalse(engine._is_rate_limit_error(Exception("connection timeout")))

    def test_rate_limit_retry_then_success(self):
        """429 后等待重试一次，第二次成功"""
        import config
        from reply_engine import ReplyEngine
        engine = ReplyEngine()
        calls = {"n": 0}

        def fake_call(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise Exception("Error code: 429 - rate limit")
            return "重试成功回复"

        old_wait = config.AI_RATE_LIMIT_WAIT
        config.AI_RATE_LIMIT_WAIT = 0  # 测试不等待
        try:
            engine._call_chat = fake_call
            reply = engine._call_with_rate_limit_retry(None, "m", "msg", "", "", None, "test")
            self.assertEqual(reply, "重试成功回复")
            self.assertEqual(calls["n"], 2)
        finally:
            config.AI_RATE_LIMIT_WAIT = old_wait

    def test_rate_limit_two_fails_returns_none(self):
        import config
        from reply_engine import ReplyEngine
        engine = ReplyEngine()
        calls = {"n": 0}

        def fake_call(*a, **k):
            calls["n"] += 1
            raise Exception("429 too many")

        old_wait = config.AI_RATE_LIMIT_WAIT
        config.AI_RATE_LIMIT_WAIT = 0
        try:
            engine._call_chat = fake_call
            reply = engine._call_with_rate_limit_retry(None, "m", "msg", "", "", None, "test")
            self.assertIsNone(reply)
            self.assertEqual(calls["n"], 2)
        finally:
            config.AI_RATE_LIMIT_WAIT = old_wait

    def test_skip_main_api_when_keys_empty(self):
        """主 API Key 全空时直接走备用，不浪费时间"""
        import config
        from reply_engine import ReplyEngine
        old_main, old_backup = config.AI_API_KEYS, config.AI_BACKUP_API_KEYS
        config.AI_API_KEYS = ["", "", ""]
        config.AI_BACKUP_API_KEYS = ["backup_key"]
        try:
            engine = ReplyEngine()
            engine._call_chat = lambda *a, **k: "备用回复"
            reply = engine._ask_ai("测试消息", "HR", "岗位")
            self.assertEqual(reply, "备用回复")
        finally:
            config.AI_API_KEYS, config.AI_BACKUP_API_KEYS = old_main, old_backup


class TestStateStore(unittest.TestCase):
    """状态持久化"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bot_test_state_"))
        from state_store import StateStore
        self.StateStore = StateStore
        self.path = self.tmp / "state.json"

    def test_handled_dedup(self):
        store = self.StateStore(path=self.path)
        self.assertFalse(store.was_handled("张三", "你好"))
        store.mark_handled("张三", "你好", "text")
        self.assertTrue(store.was_handled("张三", "你好"))

    def test_dedup_per_chat(self):
        store = self.StateStore(path=self.path)
        store.mark_handled("张三", "你好", "text")
        self.assertFalse(store.was_handled("李四", "你好"))

    def test_dedup_per_message(self):
        store = self.StateStore(path=self.path)
        store.mark_handled("张三", "你好", "text")
        self.assertFalse(store.was_handled("张三", "在吗"))

    def test_resume_sent(self):
        store = self.StateStore(path=self.path)
        self.assertFalse(store.resume_sent("张三"))
        store.mark_resume_sent("张三")
        self.assertTrue(store.resume_sent("张三"))

    def test_pause_resume(self):
        store = self.StateStore(path=self.path)
        self.assertFalse(store.is_paused())
        store.pause(reason="测试", chat_name="张三")
        self.assertTrue(store.is_paused())
        self.assertEqual(store.pause_info()["reason"], "测试")
        self.assertTrue(store.resume())
        self.assertFalse(store.is_paused())
        self.assertFalse(store.resume())  # 再恢复返回 False

    def test_persistence_reload(self):
        store = self.StateStore(path=self.path)
        store.mark_handled("张三", "你好", "text")
        store.mark_resume_sent("张三")
        store.pause(reason="持久化测试")
        # 新实例从文件加载
        store2 = self.StateStore(path=self.path)
        self.assertTrue(store2.was_handled("张三", "你好"))
        self.assertTrue(store2.resume_sent("张三"))
        self.assertTrue(store2.is_paused())


class TestStats(unittest.TestCase):
    """统计持久化"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bot_test_stats_"))
        from stats import Stats
        self.Stats = Stats
        self.path = self.tmp / "stats.json"

    def test_record_reply(self):
        stats = self.Stats(path=self.path)
        stats.record_reply(source="rule", action="text")
        stats.record_reply(source="ai", action="resume")
        s = stats.summary()
        self.assertEqual(s["today"]["replies"], 2)
        self.assertEqual(s["today"]["by_source"]["rule"], 1)
        self.assertEqual(s["today"]["by_source"]["ai"], 1)
        self.assertEqual(s["today"]["by_action"]["text"], 1)
        self.assertEqual(s["today"]["by_action"]["resume"], 1)
        self.assertEqual(s["total"]["replies"], 2)

    def test_record_skip_and_important(self):
        stats = self.Stats(path=self.path)
        stats.record_skip()
        stats.record_important()
        s = stats.summary()
        self.assertEqual(s["today"]["skipped_duplicates"], 1)
        self.assertEqual(s["today"]["important_events"], 1)

    def test_persistence_reload(self):
        stats = self.Stats(path=self.path)
        stats.record_reply(source="intent", action="text")
        stats2 = self.Stats(path=self.path)
        self.assertEqual(stats2.total()["replies"], 1)


class TestNotifier(unittest.TestCase):
    """通知"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bot_test_notify_"))
        from notify import Notifier
        self.Notifier = Notifier
        self.path = self.tmp / "notifications.json"

    def test_is_important(self):
        n = self.Notifier(path=self.path)
        self.assertTrue(n.is_important("明天来公司聊聊吧"))
        self.assertTrue(n.is_important("恭喜你，发offer了", ""))
        self.assertTrue(n.is_important("随便聊聊", "invite_interview"))
        self.assertFalse(n.is_important("你好，在吗"))
        self.assertFalse(n.is_important("薪资多少"))

    def test_notify_writes_record(self):
        n = self.Notifier(path=self.path)
        hit = n.notify_if_important("明天下午方便来公司面试吗？", chat_name="赵总监", job_name="分析师")
        self.assertTrue(hit)
        records = n.records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["level"], "important")
        self.assertIn("赵总监", records[0]["content"])
        self.assertIn("面试", records[0]["content"])

    def test_not_important_no_record(self):
        n = self.Notifier(path=self.path)
        hit = n.notify_if_important("你好", chat_name="张三")
        self.assertFalse(hit)
        self.assertEqual(n.records(), [])

    def test_send_notification(self):
        n = self.Notifier(path=self.path)
        ok = n.send_notification("标题", "内容", "info")
        self.assertTrue(ok)
        self.assertEqual(n.records()[0]["title"], "标题")


class TestReplyEngine(unittest.TestCase):
    """回复引擎决策"""

    def setUp(self):
        from reply_engine import ReplyEngine
        self.engine = ReplyEngine()

    def test_rule_passthrough(self):
        action, content, meta = self.engine.get_reply("方便发一下简历吗？")
        self.assertEqual(action, "resume")
        self.assertEqual(meta["source"], "rule")

    def test_intent_salary(self):
        action, content, meta = self.engine.get_reply("你们这边给的预算范围是多少呀？")
        self.assertEqual(action, "text")
        self.assertEqual(meta["source"], "intent")
        self.assertEqual(meta["intent"], "ask_salary")
        self.assertIn("薪资", content)  # 画像渲染后的话术

    def test_intent_resume_action(self):
        action, content, meta = self.engine.get_reply("发个简历过来吧")
        self.assertEqual(action, "resume")
        self.assertEqual(meta["intent"], "ask_resume")

    def test_ai_fail_skip(self):
        """AI 失败时 skip（默认策略）"""
        import config
        from reply_engine import ReplyEngine
        old = config.AI_FAIL_ACTION
        config.AI_FAIL_ACTION = "skip"
        try:
            engine = ReplyEngine()
            engine._ask_ai = lambda *a, **k: None
            action, content, meta = engine.get_reply("这句话既没有规则也没有意图关键词呵呵呵")
            self.assertEqual(action, "none")
            self.assertIsNone(content)
        finally:
            config.AI_FAIL_ACTION = old

    def test_ai_fail_default(self):
        """AI 失败时按配置发默认话术"""
        import config
        from reply_engine import ReplyEngine
        old = config.AI_FAIL_ACTION
        config.AI_FAIL_ACTION = "default"
        try:
            engine = ReplyEngine()
            engine._ask_ai = lambda *a, **k: None
            action, content, meta = engine.get_reply("这句话既没有规则也没有意图关键词呵呵呵")
            self.assertEqual(action, "text")
            self.assertEqual(content, config.DEFAULT_REPLY)
        finally:
            config.AI_FAIL_ACTION = old

    def test_split_messages_compat(self):
        """兼容直接传字符串"""
        action, content, meta = self.engine.get_reply("在吗？")
        self.assertEqual(action, "text")
        self.assertEqual(meta["source"], "rule")

    def test_multi_turn_history(self):
        """多轮消息：取最后一条对方消息"""
        msgs = [
            {"text": "你好", "is_mine": False},
            {"text": "您好，很高兴认识", "is_mine": True},
            {"text": "你们预算多少呀", "is_mine": False},
        ]
        action, content, meta = self.engine.get_reply(msgs)
        self.assertEqual(meta["intent"], "ask_salary")

    def test_rate_limit(self):
        import config
        from reply_engine import ReplyEngine
        old = config.MAX_REPLIES_PER_HOUR
        config.MAX_REPLIES_PER_HOUR = 2
        try:
            engine = ReplyEngine()
            self.assertTrue(engine.can_reply())
            engine.record_reply()
            engine.record_reply()
            self.assertFalse(engine.can_reply())  # 达到上限
        finally:
            config.MAX_REPLIES_PER_HOUR = old


class TestProfileTemplate(unittest.TestCase):
    """画像加载与模板渲染"""

    def test_render_template(self):
        from config import render_template
        profile = {"salary_expectation": "15-20K", "position": "后端开发", "skills": ["Go", "MySQL"]}
        self.assertEqual(render_template("期望{salary}", profile), "期望15-20K")
        self.assertEqual(render_template("做{position}的", profile), "做后端开发的")
        self.assertEqual(render_template("会{skills}", profile), "会Go、MySQL")
        self.assertEqual(render_template("无占位符", profile), "无占位符")
        self.assertEqual(render_template("", profile), "")

    def test_load_user_profile(self):
        import config
        from config import load_user_profile, USER_PROFILE
        p = load_user_profile()
        self.assertIn("position", p)
        self.assertIn("salary_expectation", p)
        # 模块加载时已渲染
        self.assertIn(USER_PROFILE["salary_expectation"], config.SALARY_REPLY)

    def test_system_prompt_from_profile(self):
        from prompts import build_system_prompt
        prompt = build_system_prompt({
            "education": "硕士", "position": "算法", "skills": ["PyTorch"],
            "experience": "两段实习", "salary_expectation": "30K",
            "available_interview_time": "随时", "highlights": ["比赛获奖"],
        })
        self.assertIn("硕士", prompt)
        self.assertIn("算法", prompt)
        self.assertIn("PyTorch", prompt)
        self.assertIn("30K", prompt)
        self.assertIn("对话历史", prompt)

    def test_user_prompt_history(self):
        from prompts import build_user_prompt
        msgs = [
            {"text": "你好", "is_mine": False},
            {"text": "您好", "is_mine": True},
        ]
        p = build_user_prompt("李经理", "数据分析师", "预算多少", msgs)
        self.assertIn("李经理", p)
        self.assertIn("数据分析师", p)
        self.assertIn("对方: 你好", p)
        self.assertIn("我: 您好", p)
        self.assertIn("预算多少", p)


if __name__ == "__main__":
    unittest.main(verbosity=2)