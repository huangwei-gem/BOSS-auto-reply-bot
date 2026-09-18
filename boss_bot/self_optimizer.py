"""
BOSS 自动回复机器人 - 自我优化迭代（自进化）

分析保存的消息数据，根据回复效果自动优化提示词和回复框架。
类似 Hermes/Raven 的自进化机制：
1. 收集消息交互数据（对方反应：继续聊/不再回复/重要事件）
2. 对比人工回复 vs 机器回复的差异，学习人工回复的优点
3. 用 AI 生成优化建议，自动更新系统提示词规则和话术模板
4. 持续迭代——每次优化后跟踪效果变化，形成正向反馈循环
"""

import json
import logging
import os
import threading
from datetime import datetime, date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_FALLBACK_KEY = os.environ.get("AI_FALLBACK_KEY", "")
_FALLBACK_MODEL = os.environ.get("AI_FALLBACK_MODEL", "deepseek-flash")
_FALLBACK_URL = os.environ.get("AI_FALLBACK_BASE_URL", "https://api.deepseek.com")


class SelfOptimizer:
    """自我优化迭代器：分析消息数据，自动优化提示词"""

    def __init__(self, base_dir=None):
        from boss_bot.config import BASE_DIR
        self.base_dir = Path(base_dir) if base_dir else Path(BASE_DIR)
        self.messages_dir = self.base_dir / "messages"
        self.overrides_path = self.base_dir / "config_overrides.json"
        self.optimization_log = self.base_dir / "logs" / "optimization_log.jsonl"
        self._lock = threading.Lock()

    def analyze_and_optimize(self) -> dict:
        """分析所有消息数据，生成优化建议并应用"""
        with self._lock:
            analysis = self._collect_stats()
            suggestions = self._generate_suggestions(analysis)
            if suggestions:
                self._apply_suggestions(suggestions)
                self._log_optimization(analysis, suggestions)
            return {"analysis": analysis, "suggestions": suggestions}

    def _collect_stats(self) -> dict:
        """收集所有会话的交互统计数据，区分人工回复和机器回复"""
        stats = {
            "total_chats": 0,
            "total_messages": 0,
            "bot_replies": 0,
            "human_replies": 0,
            "chats_with_followup": 0,
            "chats_no_followup": 0,
            "important_events": 0,
            "resume_requests": 0,
            "resume_sent": 0,
            "by_source": {"rule": 0, "intent": 0, "ai": 0, "default": 0},
            "problematic_replies": [],
            "good_replies": [],
            "followup_rate": 0,
            "human_vs_bot": [],
        }

        if not self.messages_dir.exists():
            return stats

        for path in self.messages_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                msgs = data.get("messages", [])
                chat_name = data.get("chat_name", path.stem)
                job_name = data.get("job_name", "")
                stats["total_chats"] += 1
                stats["total_messages"] += len(msgs)

                for i, msg in enumerate(msgs):
                    is_bot = msg.get("source") == "bot"
                    is_human = msg.get("is_mine") and not is_bot and msg.get("text", "").strip()

                    if is_bot:
                        stats["bot_replies"] += 1
                        source = msg.get("reply_source", "default")
                        stats["by_source"][source] = stats["by_source"].get(source, 0) + 1

                        has_followup = False
                        for j in range(i + 1, len(msgs)):
                            if not msgs[j].get("is_mine"):
                                has_followup = True
                                break

                        reply_text = msg.get("text", "")[:80]
                        if has_followup:
                            stats["chats_with_followup"] += 1
                            stats["good_replies"].append({
                                "chat": chat_name,
                                "reply": reply_text,
                                "source": source,
                            })
                        else:
                            stats["chats_no_followup"] += 1
                            if i == len(msgs) - 1:
                                stats["problematic_replies"].append({
                                    "chat": chat_name,
                                    "reply": reply_text,
                                    "source": source,
                                })

                    elif is_human:
                        stats["human_replies"] += 1
                        prev_msg_text = ""
                        for j in range(i - 1, -1, -1):
                            if not msgs[j].get("is_mine"):
                                prev_msg_text = msgs[j].get("text", "")[:120]
                                break

                        stats["human_vs_bot"].append({
                            "chat": chat_name,
                            "job": job_name[:40],
                            "trigger": prev_msg_text,
                            "human_reply": msg.get("text", "")[:120],
                        })

                    if msg.get("action") == "resume":
                        stats["resume_requests"] += 1
                        if msg.get("text", "").startswith("[简历已发送"):
                            stats["resume_sent"] += 1

            except Exception as e:
                logger.debug(f"分析消息文件失败 {path}: {e}")

        total_bot = stats["chats_with_followup"] + stats["chats_no_followup"]
        stats["followup_rate"] = (
            stats["chats_with_followup"] / total_bot if total_bot > 0 else 0
        )

        stats["problematic_replies"] = stats["problematic_replies"][:20]
        stats["good_replies"] = stats["good_replies"][:20]
        stats["human_vs_bot"] = stats["human_vs_bot"][:30]

        return stats

    def _generate_suggestions(self, analysis: dict) -> list:
        """根据分析结果生成启发式优化建议"""
        suggestions = []

        followup_rate = analysis.get("followup_rate", 0)
        problematic = analysis.get("problematic_replies", [])
        good = analysis.get("good_replies", [])

        if followup_rate < 0.3 and analysis["bot_replies"] >= 5:
            suggestions.append({
                "type": "system_rules",
                "reason": f"回复有效率仅 {followup_rate:.0%}（{analysis['chats_with_followup']}/{analysis['bot_replies']} 条回复后对方继续聊）",
                "addition": "\n11. 回复要更有针对性，直接回应对方的问题或需求，避免泛泛而谈",
            })

        by_source = analysis.get("by_source", {})
        total_source = sum(by_source.values())
        if total_source > 0 and by_source.get("default", 0) / total_source > 0.4:
            suggestions.append({
                "type": "system_rules",
                "reason": f"默认兜底回复占比 {by_source['default']}/{total_source} 过高，说明规则和意图覆盖不足",
                "addition": "\n12. 对于无法分类的消息，主动询问对方的具体需求，而不是发送通用回复",
            })

        if by_source.get("ai", 0) > 0 and followup_rate > 0.5:
            ai_good = sum(1 for r in good if r.get("source") == "ai")
            ai_total = by_source.get("ai", 0)
            if ai_good / ai_total > 0.6:
                suggestions.append({
                    "type": "enable_ai",
                    "reason": f"AI 回复效果好（{ai_good}/{ai_total} 条后对方继续聊），建议启用 AI",
                })

        if analysis["resume_requests"] >= 3:
            success_rate = analysis["resume_sent"] / analysis["resume_requests"]
            if success_rate < 0.5:
                suggestions.append({
                    "type": "resume_reply",
                    "reason": f"简历发送成功率仅 {success_rate:.0%}，建议优化降级话术",
                    "new_template": "您好，我的简历已经在 BOSS 平台上更新了，您可以直接在平台上查看我的在线简历，有任何问题随时沟通~",
                })

        return suggestions

    def _apply_suggestions(self, suggestions: list):
        """应用优化建议到配置覆盖文件"""
        overrides = {}
        if self.overrides_path.exists():
            try:
                with open(self.overrides_path, "r", encoding="utf-8") as f:
                    overrides = json.load(f)
            except Exception:
                pass

        changed = False

        for s in suggestions:
            if s["type"] == "system_rules":
                current_rules = overrides.get("system_rules", "")
                addition = s["addition"].strip()
                # 防堆积：超过 800 字不再追加
                if len(current_rules) + len(addition) > 800:
                    logger.warning(f"[自我优化] system_rules 已达上限，跳过: {s['reason'][:40]}")
                    continue
                if addition not in current_rules:
                    overrides["system_rules"] = current_rules + s["addition"]
                    changed = True
                    logger.info(f"[自我优化] 更新系统提示词: {s['reason']}")

            elif s["type"] == "enable_ai":
                logger.info(f"[自我优化] 建议启用 AI: {s['reason']}")

            elif s["type"] == "resume_reply":
                rt = overrides.get("reply_templates", {})
                rt["RESUME_UNAVAILABLE_REPLY"] = s["new_template"]
                overrides["reply_templates"] = rt
                changed = True
                logger.info(f"[自我优化] 更新简历降级话术: {s['reason']}")

            elif s["type"] == "reply_template":
                # template_key 白名单校验：必须是 config.py 实际引用的 key
                VALID_KEYS = {"SALARY_REPLY", "INTERVIEW_TIME_REPLY", "JOB_CONTENT_REPLY",
                              "GREETING_REPLY", "DEFAULT_REPLY", "RESUME_DUPLICATE_REPLY",
                              "RESUME_UNAVAILABLE_REPLY"}
                if s.get("template_key") not in VALID_KEYS:
                    logger.warning(f"[自我优化] 跳过非法模板 key '{s.get('template_key')}': {s['reason'][:40]}")
                    continue
                rt = overrides.get("reply_templates", {})
                rt[s["template_key"]] = s["new_template"]
                overrides["reply_templates"] = rt
                changed = True
                logger.info(f"[自我优化] 更新话术模板 {s['template_key']}: {s['reason']}")

            elif s["type"] == "new_rule":
                keyword = (s.get("keyword") or "").strip()
                reply = (s.get("reply") or "").strip()
                # keyword 必须是对方消息中可能出现的关键词（2-12 字）
                if not keyword or len(keyword) > 12:
                    logger.warning(f"[自我优化] 跳过非法规则关键词 '{keyword[:20]}': {s['reason'][:40]}")
                    continue
                # 回复文本长度限制
                if not reply or len(reply) > 200:
                    logger.warning(f"[自我优化] 跳过非法规则回复文本: {s['reason'][:40]}")
                    continue
                rules = overrides.get("reply_rules", {})
                rules[keyword] = reply
                overrides["reply_rules"] = rules
                changed = True
                logger.info(f"[自我优化] 新增规则 '{keyword}': {s['reason']}")

        if changed:
            try:
                with open(self.overrides_path, "w", encoding="utf-8") as f:
                    json.dump(overrides, f, ensure_ascii=False, indent=2)
                logger.info("[自我优化] 配置覆盖已保存")
            except Exception as e:
                logger.error(f"[自我优化] 保存配置失败: {e}")

    def _log_optimization(self, analysis: dict, suggestions: list):
        """记录优化日志"""
        self.optimization_log.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "analysis": {
                "total_chats": analysis["total_chats"],
                "bot_replies": analysis["bot_replies"],
                "human_replies": analysis.get("human_replies", 0),
                "followup_rate": analysis["followup_rate"],
                "by_source": analysis["by_source"],
            },
            "suggestions": [{"type": s["type"], "reason": s["reason"]} for s in suggestions],
        }
        try:
            with open(self.optimization_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"优化日志写入失败: {e}")

    def get_optimization_history(self, limit: int = 20) -> list:
        """获取优化历史记录"""
        if not self.optimization_log.exists():
            return []
        try:
            lines = self.optimization_log.read_text(encoding="utf-8").strip().split("\n")
            records = []
            for line in lines[-limit:]:
                if line.strip():
                    records.append(json.loads(line))
            return records
        except Exception:
            return []

    def _get_api_candidates(self) -> list:
        """获取所有可用 API 候选 [(key, url, model), ...]（来自模型池，失败时轮换）"""
        import boss_bot.config as config
        candidates = [
            (p["key"], p["url"], p["model"])
            for p in config.AI_PROVIDERS
            if p.get("key")
        ]
        if _FALLBACK_KEY:
            candidates.append((_FALLBACK_KEY, _FALLBACK_URL, _FALLBACK_MODEL))
        return candidates

    def _ai_analyze(self, analysis: dict) -> list:
        """用 AI 分析人工回复 vs 机器回复的差异，生成精准优化建议（自进化核心）

        对比逻辑：
        - 人工回复（is_mine=True, source != "bot"）：用户在暂停模式下手动回复的消息
        - 机器回复（source == "bot"）：机器人自动回复的消息
        - AI 分析人工回复的优点（语气、策略、针对性），生成优化建议让机器回复更接近人工水平
        """
        try:
            from openai import OpenAI
        except ImportError:
            logger.warning("未安装 openai 库，跳过 AI 分析")
            return []

        human_samples = analysis.get("human_vs_bot", [])
        problematic = analysis.get("problematic_replies", [])
        good = analysis.get("good_replies", [])

        if not human_samples and not problematic:
            return []

        system_prompt = """你是 BOSS 直聘自动回复机器人的优化专家。你的任务是对比"人工回复"和"机器回复"的差异，找出人工回复的优点，生成具体的优化建议让机器回复更接近人工水平。

分析维度：
1. 语气和礼貌度：人工回复是否更自然、更真诚？
2. 针对性：人工回复是否更直接回应对方的具体问题？
3. 行动导向：人工回复是否包含具体行动（如"我马上投递""稍后确认"）？
4. 信息密度：人工回复是否提供了更多有用信息？
5. 称呼使用：人工回复是否称呼对方姓名，拉近距离？

输出 JSON 格式：
{
  "suggestions": [
    {
      "type": "system_rules" | "reply_template" | "new_rule",
      "reason": "优化原因（引用具体的人工回复 vs 机器回复对比）",
      "addition": "新增的系统提示词规则（type=system_rules 时必填）",
      "template_key": "要修改的话术模板名（type=reply_template 时必填）",
      "new_template": "改进后的话术（type=reply_template 时必填）",
      "keyword": "新规则关键词（type=new_rule 时必填）",
      "reply": "新规则回复内容（type=new_rule 时必填）"
    }
  ]
}

硬性约束（违反的建议会被丢弃）：
- template_key 只能从以下白名单选择：SALARY_REPLY, INTERVIEW_TIME_REPLY, JOB_CONTENT_REPLY, GREETING_REPLY, DEFAULT_REPLY, RESUME_DUPLICATE_REPLY, RESUME_UNAVAILABLE_REPLY
- keyword 必须是对方消息中可能出现的短关键词（2-12 个字，如"内推""薪资范围""什么时候方便"），不能是自造的概念词
- 所有生成的话术/规则文本中禁止出现任何具体人名（如样本中的称呼），保持通用性；称呼由 AI 回复时根据对话上下文自行添加
- new_rule 的 reply 是当对方消息包含 keyword 时直接发送的文本，必须是自然、可直接发送的回复

注意：
- 只输出 JSON，不要其他文字
- 每条建议必须有具体的、可执行的内容，不要泛泛而谈
- 优先分析人工回复明显优于机器回复的场景
- 如果没有人工回复样本，则分析效果差的机器回复，给出改进建议"""

        user_prompt = f"""回复有效率: {analysis['followup_rate']:.0%}
机器回复总数: {analysis.get('bot_replies', 0)}
人工回复总数: {analysis.get('human_replies', 0)}
回复来源分布: {analysis.get('by_source', {})}

"""
        if human_samples:
            user_prompt += "人工回复样本（学习目标）:\n"
            for s in human_samples[:10]:
                user_prompt += f"  对方说: {s['trigger']}\n  人工回: {s['human_reply']}\n  ---\n"

        if problematic:
            user_prompt += "\n效果差的机器回复（需要改进）:\n"
            for s in problematic[:5]:
                user_prompt += f"  回复: {s['reply']} (来源: {s['source']})\n"

        if good:
            user_prompt += "\n效果好的机器回复（保持）:\n"
            for s in good[:5]:
                user_prompt += f"  回复: {s['reply']} (来源: {s['source']})\n"

        user_prompt += "\n请分析数据并给出具体的优化建议。"

        from . import ai_client
        candidates = self._get_api_candidates()
        if not candidates:
            logger.warning("[AI分析] 未配置任何 API Key，跳过 AI 分析")
            return []

        # 轮换候选 API，单个失败快速切换下一个
        last_err = None
        for key, url, model in candidates:
            try:
                client = ai_client.make_client(key, url, timeout=25)
                response = client.chat.completions.create(
                    model=model,
                    max_tokens=1500,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                content = (response.choices[0].message.content or "").strip()

                import re
                if not content:
                    raise ValueError(f"模型未返回正文（finish_reason={response.choices[0].finish_reason}）")
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
                elif not content.startswith("{"):
                    # 兜底：提取首个 { 到最后一个 } 之间的内容
                    brace = re.search(r'\{.*\}', content, re.DOTALL)
                    if brace:
                        content = brace.group(0)

                result = json.loads(content)
                return self._sanitize_suggestions(result.get("suggestions", []))
            except Exception as e:
                last_err = e
                logger.warning(f"[AI分析] {model} 失败: {type(e).__name__}, 切换下一个候选")
        logger.error(f"AI 分析失败（所有候选 API）: {last_err}")
        return []

    @staticmethod
    def _sanitize_suggestions(suggestions: list) -> list:
        """清洗 AI 建议：去除硬编码人名（防过拟合）、丢弃残缺建议"""
        import re
        # 中文姓名称呼模式：X先生/X女士/X总/X同学/X老师/X经理（X 为 1-3 个汉字）
        _NAME_RE = re.compile(r'([\u4e00-\u9fa5]{1,3})(先生|女士|同学|老师|经理|总)')
        cleaned = []
        for s in suggestions:
            if not isinstance(s, dict) or not s.get("type"):
                continue
            # 清洗所有文本字段中的人名："好的，侯先生，..." -> "好的，..."
            for field in ("addition", "new_template", "reply"):
                if s.get(field):
                    s[field] = _NAME_RE.sub('', s[field]).replace('，，', '，').replace('，，', '，')
            # system_rules 的 addition 通常以 "\nN. " 开头的规则编号，人名清洗后仍可用
            cleaned.append(s)
        return cleaned

    def evolve(self) -> dict:
        """自进化入口 — 规则分析 + AI 分析 + 自动应用"""
        with self._lock:
            analysis = self._collect_stats()

            rule_suggestions = self._generate_suggestions(analysis)

            ai_suggestions = []
            if analysis["bot_replies"] >= 3 or analysis.get("human_replies", 0) >= 1:
                ai_suggestions = self._ai_analyze(analysis)

            all_suggestions = rule_suggestions + ai_suggestions

            if all_suggestions:
                self._apply_suggestions(all_suggestions)
                self._log_optimization(analysis, all_suggestions)

            return {
                "analysis": {
                    "total_chats": analysis["total_chats"],
                    "bot_replies": analysis["bot_replies"],
                    "human_replies": analysis.get("human_replies", 0),
                    "followup_rate": analysis["followup_rate"],
                    "by_source": analysis["by_source"],
                },
                "rule_suggestions": len(rule_suggestions),
                "ai_suggestions": len(ai_suggestions),
                "total_suggestions": len(all_suggestions),
                "applied": len(all_suggestions) > 0,
            }


# ===================== 定时自动进化调度器 =====================

_AUTO_EVOLVE_INTERVAL = int(os.environ.get("AUTO_EVOLVE_INTERVAL", "3600"))
_auto_evolve_thread: Optional[threading.Thread] = None
_auto_evolve_stop = threading.Event()
_auto_evolve_last_result = {"last_run": "", "result": None}


def start_auto_evolve(interval: int = None) -> threading.Thread:
    """启动定时自动进化后台线程（幂等，重复调用不会启动多个）"""
    global _auto_evolve_thread
    if _auto_evolve_thread is not None and _auto_evolve_thread.is_alive():
        return _auto_evolve_thread

    _auto_evolve_stop.clear()
    interval = interval or _AUTO_EVOLVE_INTERVAL

    def _loop():
        logger.info(f"[自动进化] 已启动，每 {interval} 秒迭代一次")
        while not _auto_evolve_stop.wait(interval):
            try:
                opt = SelfOptimizer()
                result = opt.evolve()
                _auto_evolve_last_result["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                _auto_evolve_last_result["result"] = result
                logger.info(
                    f"[自动进化] 完成: 规则建议 {result['rule_suggestions']} 条, "
                    f"AI 建议 {result['ai_suggestions']} 条, "
                    f"回复有效率 {result['analysis']['followup_rate']:.0%}"
                )
            except Exception as e:
                logger.error(f"[自动进化] 迭代失败: {e}")

    _auto_evolve_thread = threading.Thread(target=_loop, daemon=True, name="auto-evolve")
    _auto_evolve_thread.start()
    return _auto_evolve_thread


def stop_auto_evolve():
    """停止定时自动进化"""
    _auto_evolve_stop.set()


def get_auto_evolve_status() -> dict:
    """获取自动进化状态"""
    return {
        "running": _auto_evolve_thread is not None and _auto_evolve_thread.is_alive(),
        "interval": _AUTO_EVOLVE_INTERVAL,
        **_auto_evolve_last_result,
    }
