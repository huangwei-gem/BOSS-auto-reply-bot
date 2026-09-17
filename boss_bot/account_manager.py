"""
BOSS 自动回复机器人 - 多账号管理

每个账号有独立的数据目录：accounts/{account_id}/
  - cookies.json
  - bot_state.json
  - bot_stats.json
  - notifications.json
  - messages/
  - config_overrides.json (可选，账号级配置覆盖)

支持同时运行多个浏览器实例，每个账号独立配置和状态。
"""

import json
import os
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ACCOUNTS_DIR = Path(__file__).parent / "accounts"
ACCOUNTS_INDEX = ACCOUNTS_DIR / "index.json"


class AccountManager:
    """多账号管理器"""

    def __init__(self):
        ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._accounts = self._load_index()

    def _load_index(self) -> dict:
        try:
            if ACCOUNTS_INDEX.exists():
                with open(ACCOUNTS_INDEX, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {"accounts": {}, "default": None}

    def _save_index(self):
        try:
            with open(ACCOUNTS_INDEX, "w", encoding="utf-8") as f:
                json.dump(self._accounts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存账号索引失败: {e}")

    def _account_dir(self, account_id: str) -> Path:
        d = ACCOUNTS_DIR / account_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "messages").mkdir(exist_ok=True)
        return d

    def list_accounts(self) -> list:
        with self._lock:
            result = []
            for aid, info in self._accounts.get("accounts", {}).items():
                d = self._account_dir(aid)
                cookie_file = d / "cookies.json"
                cookie_exists = cookie_file.exists()
                cookie_count = 0
                if cookie_exists:
                    try:
                        with open(cookie_file, "r", encoding="utf-8") as f:
                            cookie_count = len(json.load(f))
                    except Exception:
                        pass
                result.append({
                    "id": aid,
                    "name": info.get("name", aid),
                    "created_at": info.get("created_at", ""),
                    "last_active": info.get("last_active", ""),
                    "is_default": aid == self._accounts.get("default"),
                    "running": info.get("running", False),
                    "logged_in": info.get("logged_in", False) or cookie_exists,
                    "cookie_count": cookie_count,
                    "cookie_exists": cookie_exists,
                })
            result.sort(key=lambda x: x.get("last_active", ""), reverse=True)
            return result

    def create_account(self, name: str, account_id: str = None) -> dict:
        with self._lock:
            if not account_id:
                account_id = name.lower().replace(" ", "_")[:30]
            if account_id in self._accounts.get("accounts", {}):
                return {"success": False, "message": "账号 ID 已存在"}

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._accounts.setdefault("accounts", {})[account_id] = {
                "name": name,
                "created_at": now,
                "last_active": now,
                "running": False,
                "logged_in": False,
            }
            if not self._accounts.get("default"):
                self._accounts["default"] = account_id
            self._save_index()
            self._account_dir(account_id)
            logger.info(f"创建账号: {name} (id={account_id})")
            return {"success": True, "id": account_id}

    def delete_account(self, account_id: str) -> dict:
        with self._lock:
            if account_id not in self._accounts.get("accounts", {}):
                return {"success": False, "message": "账号不存在"}
            del self._accounts["accounts"][account_id]
            if self._accounts.get("default") == account_id:
                remaining = list(self._accounts.get("accounts", {}).keys())
                self._accounts["default"] = remaining[0] if remaining else None
            self._save_index()
        try:
            import shutil
            shutil.rmtree(ACCOUNTS_DIR / account_id, ignore_errors=True)
        except Exception:
            pass
        logger.info(f"删除账号: {account_id}")
        return {"success": True}

    def set_default(self, account_id: str) -> dict:
        with self._lock:
            if account_id not in self._accounts.get("accounts", {}):
                return {"success": False, "message": "账号不存在"}
            self._accounts["default"] = account_id
            self._save_index()
            return {"success": True}

    def update_status(self, account_id: str, running: bool = None,
                      logged_in: bool = None):
        with self._lock:
            acct = self._accounts.get("accounts", {}).get(account_id)
            if not acct:
                return
            if running is not None:
                acct["running"] = running
            if logged_in is not None:
                acct["logged_in"] = logged_in
            acct["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._save_index()

    def get_account_dir(self, account_id: str) -> Path:
        return self._account_dir(account_id)

    def get_default_account(self) -> Optional[str]:
        return self._accounts.get("default")

    def get_account_info(self, account_id: str) -> dict:
        with self._lock:
            return dict(self._accounts.get("accounts", {}).get(account_id, {}))

    def save_cookie(self, account_id: str, cookies: list) -> dict:
        """保存账号的 cookie 数据"""
        with self._lock:
            if account_id not in self._accounts.get("accounts", {}):
                return {"success": False, "message": "账号不存在"}
            d = self._account_dir(account_id)
            cookie_file = d / "cookies.json"
            try:
                with open(cookie_file, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)
                acct = self._accounts["accounts"][account_id]
                acct["logged_in"] = True
                acct["cookie_count"] = len(cookies)
                acct["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._save_index()
                logger.info(f"账号 {account_id} cookie 已保存 ({len(cookies)} 个)")
                return {"success": True, "cookie_count": len(cookies)}
            except Exception as e:
                logger.error(f"保存 cookie 失败: {e}")
                return {"success": False, "message": str(e)}

    def load_cookie(self, account_id: str) -> list:
        """加载账号的 cookie 数据"""
        with self._lock:
            if account_id not in self._accounts.get("accounts", {}):
                return []
            d = self._account_dir(account_id)
            cookie_file = d / "cookies.json"
            if not cookie_file.exists():
                return []
            try:
                with open(cookie_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载 cookie 失败: {e}")
                return []

    def get_cookie_status(self, account_id: str) -> dict:
        """获取账号 cookie 状态"""
        with self._lock:
            if account_id not in self._accounts.get("accounts", {}):
                return {"exists": False}
            d = self._account_dir(account_id)
            cookie_file = d / "cookies.json"
            if not cookie_file.exists():
                return {"exists": False}
            try:
                with open(cookie_file, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                return {
                    "exists": True,
                    "count": len(cookies),
                    "size": cookie_file.stat().st_size,
                    "modified": datetime.fromtimestamp(cookie_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                }
            except Exception:
                return {"exists": False}

    def switch_account(self, account_id: str) -> dict:
        """切换当前活跃账号"""
        with self._lock:
            if account_id not in self._accounts.get("accounts", {}):
                return {"success": False, "message": "账号不存在"}
            self._accounts["default"] = account_id
            acct = self._accounts["accounts"][account_id]
            acct["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._save_index()
            logger.info(f"切换到账号: {account_id}")
            return {"success": True, "account_id": account_id}

    def get_active_cookie_file(self) -> str:
        """获取当前活跃账号的 cookie 文件路径"""
        default = self._accounts.get("default")
        if not default:
            return str(BASE_DIR / "zhipin_cookies.json")
        d = self._account_dir(default)
        cookie_file = d / "cookies.json"
        if cookie_file.exists():
            return str(cookie_file)
        return str(BASE_DIR / "zhipin_cookies.json")

    def get_data_paths(self, account_id: str) -> dict:
        """获取账号所有数据文件路径"""
        d = self._account_dir(account_id)
        return {
            "cookie_file": str(d / "cookies.json"),
            "state_file": str(d / "bot_state.json"),
            "stats_file": str(d / "bot_stats.json"),
            "notify_file": str(d / "notifications.json"),
            "messages_dir": str(d / "messages"),
            "overrides_file": str(d / "config_overrides.json"),
            "account_dir": str(d),
        }