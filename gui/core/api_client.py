import json
import threading
import urllib.request


class BackendClient:
    def __init__(
        self, login_url, event_report_url, event_report_token="", session_report_url=""
    ):
        self.login_url = (login_url or "").strip()
        self.event_report_url = (event_report_url or "").strip()
        self.event_report_token = (event_report_token or "").strip()
        self.session_report_url = (session_report_url or "").strip()

    def login(self, login_id, password, timeout=5):
        body = json.dumps(
            {"login_id": login_id, "username": login_id, "password": password}
        ).encode("utf-8")
        req = urllib.request.Request(
            self.login_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        # v2 envelope: {code, message, data: {session: {user}}}
        if isinstance(payload, dict) and "code" in payload and "data" in payload:
            code = payload.get("code")
            if code != 0:
                return {
                    "ok": False,
                    "error": payload.get("message", "登录失败"),
                    "code": code,
                }
            user = (
                payload.get("data", {})
                .get("session", {})
                .get("user", {})
            )
            username = user.get("username", login_id)
            display_name = user.get("display_name", username)
            return {
                "ok": True,
                "username": username,
                "display_name": display_name,
                "role": user.get("role", ""),
                "raw": payload,
            }

        # v1 response passthrough: {ok, username, display_name, ...}
        return payload

    def report_event_async(self, payload, timeout=4):
        if not self.event_report_url:
            return

        def _send():
            try:
                body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    self.event_report_url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                if self.event_report_token:
                    req.add_header("X-DMS-Token", self.event_report_token)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if resp.status >= 300:
                        print(f"事件上报失败: HTTP {resp.status}")
            except Exception as exc:
                print(f"事件上报失败: {exc}")

        threading.Thread(target=_send, daemon=True).start()

    def report_session_async(self, payload, timeout=4):
        if not self.session_report_url:
            return

        def _send():
            try:
                body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    self.session_report_url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                if self.event_report_token:
                    req.add_header("X-DMS-Token", self.event_report_token)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if resp.status >= 300:
                        print(f"会话上报失败: HTTP {resp.status}")
            except Exception as exc:
                print(f"会话上报失败: {exc}")

        threading.Thread(target=_send, daemon=True).start()
