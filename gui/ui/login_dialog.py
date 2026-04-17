import os
import urllib.error
import webbrowser
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

try:
    from core.api_client import BackendClient
    from core.config import load_app_config
except ImportError:
    from gui.core.api_client import BackendClient
    from gui.core.config import load_app_config


class LoginDialog(QDialog):
    @staticmethod
    def _resolve_path(path_value, base_dir):
        path = Path(path_value).expanduser()
        if not path.is_absolute():
            path = Path(base_dir) / path
        return path.resolve()

    @classmethod
    def _resolve_project_root(cls):
        env_root = os.getenv("DMS_PROJECT_ROOT", "").strip()
        if env_root:
            env_path = cls._resolve_path(env_root, Path.cwd())
            if env_path.exists():
                return env_path
        return Path(__file__).resolve().parents[2]

    @classmethod
    def _resolve_config_path(cls):
        project_root = cls._resolve_project_root()
        config_path_env = os.getenv("DMS_CONFIG_PATH", "").strip()
        if config_path_env:
            return cls._resolve_path(config_path_env, project_root)
        return Path(__file__).resolve().parents[1] / "config.yaml"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("驾驶监测系统登录")
        self.setMinimumWidth(420)

        self.app_config = load_app_config(self._resolve_config_path())
        self.web_portal_url = os.getenv(
            "DMS_WEB_PORTAL_URL",
            os.getenv("DMS_SIGNUP_PAGE_URL", self.app_config["signup_page_url"]),
        ).strip()
        self.backend_client = BackendClient(
            login_url=os.getenv("DMS_LOGIN_API_URL", self.app_config["login_api_url"]),
            event_report_url="",
            event_report_token="",
        )
        self.login_result = None

        self.setStyleSheet(
            """
            QWidget {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0d1423, stop: 1 #070b14
                );
                color: #e8f0ff;
                font-family: "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
            }
            QLabel { background: transparent; }
            QFrame#Card {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 rgba(22, 33, 54, 242),
                    stop: 1 rgba(17, 26, 42, 245)
                );
                border: 1px solid #243553;
                border-radius: 16px;
            }
            QLabel#Title {
                font-size: 32px;
                font-weight: 700;
                color: #e8f0ff;
            }
            QLabel#Hint {
                color: #8ca0bf;
                font-size: 14px;
            }
            QLineEdit {
                font-size: 18px;
                padding: 12px 14px;
                border: 1px solid #2b4065;
                border-radius: 10px;
                background: #10192a;
                color: #e8f0ff;
                selection-background-color: #1d8ff5;
                selection-color: #e8f0ff;
            }
            QLineEdit:focus { border: 1px solid #4dc4ff; }
            QPushButton {
                font-size: 16px;
                font-weight: 600;
                color: #ffffff;
                background: #1d8ff5;
                border: none;
                border-radius: 10px;
                padding: 12px;
            }
            QPushButton:hover { background: #35a4ff; }
            QPushButton#Secondary {
                color: #b8c6df;
                background: #111a2b;
                border: 1px solid #2b4065;
            }
            QPushButton#Secondary:hover {
                background: #1b2f56;
                color: #e8f0ff;
            }
            """
        )

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        title = QLabel("账号登录")
        title.setObjectName("Title")
        hint = QLabel("支持 UID 或手机号登录；如需新账号请点击“打开 Web 端”")
        hint.setObjectName("Hint")

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("UID账号或手机号")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("密码")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        login_btn = QPushButton("进入系统")
        login_btn.clicked.connect(self.handle_login)
        open_web_btn = QPushButton("打开 Web 端")
        open_web_btn.setObjectName("Secondary")
        open_web_btn.clicked.connect(self.open_web_portal)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addWidget(login_btn, 2)
        btn_row.addWidget(open_web_btn, 1)

        card_layout.addWidget(title)
        card_layout.addWidget(hint)
        card_layout.addWidget(self.username_input)
        card_layout.addWidget(self.password_input)
        card_layout.addLayout(btn_row)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.addWidget(card)
        self.setLayout(root_layout)

    def handle_login(self):
        login_id = self.username_input.text().strip()
        password = self.password_input.text()
        if not login_id or not password:
            QMessageBox.warning(self, "提示", "请输入 UID/手机号 和密码")
            return

        try:
            data = self.backend_client.login(
                login_id=login_id,
                password=password,
                timeout=5,
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                QMessageBox.warning(self, "登录失败", "用户名或密码错误")
            else:
                QMessageBox.critical(self, "登录失败", f"接口错误: HTTP {exc.code}")
            return
        except Exception as exc:
            QMessageBox.critical(self, "登录失败", f"无法连接后端: {exc}")
            return

        if not data.get("ok"):
            QMessageBox.warning(self, "登录失败", "账号验证失败")
            return

        self.login_result = {
            "username": data.get("username", login_id),
            "display_name": data.get("display_name", login_id),
            "role": data.get("role", ""),
        }
        self.accept()

    def open_web_portal(self):
        if not self.web_portal_url:
            QMessageBox.warning(self, "提示", "未配置 Web 端地址")
            return
        try:
            webbrowser.open(self.web_portal_url)
            QMessageBox.information(
                self,
                "入口说明",
                "已打开 Web 端入口，请在浏览器完成账号操作后回到此窗口登录。",
            )
        except Exception as exc:
            QMessageBox.critical(self, "打开失败", f"无法打开 Web 端地址: {exc}")
