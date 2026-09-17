"""
BOSS 自动回复机器人 - 诊断工具

用法:
    python -m boss_bot.diagnose              # 查看诊断报告
    python -m boss_bot.diagnose --errors     # 只看错误
    python -m boss_bot.diagnose --today      # 查看今日事件统计
    python -m boss_bot.diagnose --clear      # 清除错误记录
"""
import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="BOSS Bot 诊断工具")
    parser.add_argument("--errors", action="store_true", help="只显示错误")
    parser.add_argument("--today", action="store_true", help="今日事件统计")
    parser.add_argument("--clear", action="store_true", help="清除错误记录")
    parser.add_argument("--log", type=str, help="查看指定日志文件 (bot/browser/ai/reply/web/errors)")
    parser.add_argument("--tail", type=int, default=50, help="显示最后 N 行 (默认 50)")
    parser.add_argument("--watch", type=str, metavar="NAME",
                        help="实时监控日志文件 (bot/browser/ai/reply/web/errors)")
    parser.add_argument("--interval", type=float, default=2.0, help="刷新间隔秒 (默认 2)")
    args = parser.parse_args()

    from boss_bot.config import LOG_DIR
    log_dir = Path(LOG_DIR)
    today = date.today().strftime("%Y%m%d")

    if args.clear:
        _clear_errors(log_dir)
        return

    if args.watch:
        _watch_log(log_dir, args.watch, args.interval)
        return

    if args.log:
        _show_log(log_dir, args.log, today, args.tail)
        return

    if args.today:
        _show_today_events(log_dir, today)
        return

    if args.errors:
        _show_errors(log_dir)
        return

    # 默认：完整诊断报告
    _show_full_report(log_dir, today)


def _clear_errors(log_dir: Path):
    """清除错误记录"""
    errors_json = log_dir / "errors.json"
    if errors_json.exists():
        errors_json.unlink()
        print("[OK] 错误记录已清除")
    else:
        print("无错误记录")


def _show_log(log_dir: Path, name: str, date_str: str, tail: int):
    """显示指定日志文件"""
    log_file = log_dir / f"{name}_{date_str}.log"
    if not log_file.exists():
        print(f"日志文件不存在: {log_file}")
        # 尝试找其他日期
        files = sorted(log_dir.glob(f"{name}_*.log"), reverse=True)
        if files:
            log_file = files[0]
            print(f"使用最近的日志: {log_file.name}")
        else:
            return

    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    print(f"=== {log_file.name} (最后 {tail} 行 / 共 {len(lines)} 行) ===")
    for line in lines[-tail:]:
        print(line)


def _show_today_events(log_dir: Path, date_str: str):
    """显示今日事件统计"""
    events_file = log_dir / f"events_{date_str}.jsonl"
    if not events_file.exists():
        print(f"今日无事件记录: {events_file}")
        return

    events = []
    with open(events_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    print(f"=== 今日事件统计 ({date_str}) ===")
    print(f"总事件数: {len(events)}")
    print()

    # 按类型统计
    kind_counter = Counter(e.get("kind", "unknown") for e in events)
    print("事件类型分布:")
    for kind, count in kind_counter.most_common():
        print(f"  {kind:15s}: {count}")

    # AI 调用统计
    ai_calls = [e for e in events if e.get("kind") == "ai_call"]
    if ai_calls:
        print()
        print("AI 调用统计:")
        ok_count = sum(1 for e in ai_calls if e.get("ok"))
        fail_count = len(ai_calls) - ok_count
        print(f"  总计: {len(ai_calls)}")
        print(f"  成功: {ok_count}")
        print(f"  失败: {fail_count}")
        if ai_calls:
            latencies = [e.get("latency_ms", 0) for e in ai_calls if e.get("latency_ms")]
            if latencies:
                print(f"  平均延迟: {sum(latencies)/len(latencies):.0f}ms")

    # 回复统计
    replies = [e for e in events if e.get("kind") == "reply"]
    if replies:
        print()
        print("回复决策统计:")
        source_counter = Counter(e.get("source", "unknown") for e in replies)
        for source, count in source_counter.most_common():
            print(f"  {source:10s}: {count}")

    # 发送统计
    sends = [e for e in events if e.get("kind") == "send"]
    if sends:
        print()
        print("发送统计:")
        ok_count = sum(1 for e in sends if e.get("ok"))
        print(f"  成功: {ok_count}")
        print(f"  失败: {len(sends) - ok_count}")


def _watch_log(log_dir: Path, name: str, interval: float):
    """实时监控日志文件（类似 tail -f）"""
    import time
    today = date.today().strftime("%Y%m%d")
    log_file = log_dir / f"{name}_{today}.log"
    if not log_file.exists():
        print(f"日志文件不存在: {log_file}")
        return

    print(f"=== 实时监控 {log_file.name} (Ctrl+C 退出) ===")
    # 先显示已有内容
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    for line in lines[-20:]:
        print(line)
    print(f"\n--- 等待新日志 (刷新间隔 {interval}s) ---\n")

    last_size = log_file.stat().st_size
    try:
        while True:
            time.sleep(interval)
            if not log_file.exists():
                continue
            current_size = log_file.stat().st_size
            if current_size > last_size:
                with open(log_file, "r", encoding="utf-8") as f:
                    f.seek(last_size)
                    new_content = f.read()
                for line in new_content.strip().split("\n"):
                    if line:
                        print(line)
                last_size = current_size
    except KeyboardInterrupt:
        print("\n已退出监控")


def _show_errors(log_dir: Path):
    """显示错误记录"""
    errors_json = log_dir / "errors.json"
    if not errors_json.exists():
        print("无错误记录")
        return

    with open(errors_json, "r", encoding="utf-8") as f:
        errors = json.load(f)

    print(f"=== 错误记录 (共 {len(errors)} 条) ===")
    for e in errors[-20:]:
        print(f"[{e['ts']}] {e['logger']}.{e['func']}:{e['line']}")
        print(f"  {e['message'][:120]}")
        if e.get("exception"):
            print(f"  Exception: {e['exception'][:120]}")
        print()


def _show_full_report(log_dir: Path, date_str: str):
    """显示完整诊断报告"""
    print("=" * 60)
    print("BOSS Auto-Reply Bot - 诊断报告")
    print("=" * 60)
    print(f"日期: {date_str}")
    print(f"日志目录: {log_dir}")
    print()

    # 日志文件
    print("--- 今日日志文件 ---")
    total_size = 0
    for name in ["bot", "browser", "ai", "reply", "web", "errors"]:
        log_file = log_dir / f"{name}_{date_str}.log"
        if log_file.exists():
            size = log_file.stat().st_size
            total_size += size
            print(f"  {name:10s} : {size/1024:>8.1f} KB")
    print(f"  {'总计':10s} : {total_size/1024:>8.1f} KB")

    if total_size == 0:
        print("  （今日暂无日志）")

    print()

    # 错误摘要
    errors_json = log_dir / "errors.json"
    if errors_json.exists():
        with open(errors_json, "r", encoding="utf-8") as f:
            errors = json.load(f)

        recent_24h = len([e for e in errors if _is_recent(e["ts"])])
        print("--- 错误统计 ---")
        print(f"  总计: {len(errors)} 条")
        print(f"  最近24h: {recent_24h} 条")

        if errors:
            mod_counter = Counter(e.get("module", "unknown") for e in errors[-100:])
            print("  按模块分布:")
            for mod, count in mod_counter.most_common(5):
                print(f"    {mod}: {count}")

        print()
        print("--- 最近 5 条错误 ---")
        for e in errors[-5:]:
            print(f"  [{e['ts']}] {e['logger']}.{e['func']}:{e['line']}")
            print(f"    {e['message'][:100]}")
    else:
        print("--- 无错误记录 ---")

    print()
    print("=" * 60)
    print("常用命令:")
    print("  查看主日志:     python -m boss_bot.diagnose --log bot")
    print("  查看浏览器日志: python -m boss_bot.diagnose --log browser")
    print("  查看 AI 日志:   python -m boss_bot.diagnose --log ai")
    print("  查看错误日志:   python -m boss_bot.diagnose --errors")
    print("  今日事件统计:   python -m boss_bot.diagnose --today")
    print("=" * 60)


def _is_recent(ts_str: str, hours: int = 24) -> bool:
    """判断时间戳是否在指定小时内"""
    from datetime import datetime
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - dt).total_seconds() < hours * 3600
    except Exception:
        return False


if __name__ == "__main__":
    main()
