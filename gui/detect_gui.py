"""
PyQt driver monitoring GUI (rewritten)
Reference behavior: AhmedSaleh627 Driver-Monitoring-System style
"""

import os
import sys
import time
import uuid
from pathlib import Path

import cv2
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from ultralytics import YOLO

try:
    from core.api_client import BackendClient
    from core.config import load_app_config
    from core.event_store import EventStore
    from core.labels import event_type_from_label, risk_type
    from core.risk_engine import RiskEngine
    from ui.login_dialog import LoginDialog
except ImportError:
    # Allow both: `python gui/detect_gui.py` and `python -m gui.detect_gui`.
    from gui.core.api_client import BackendClient
    from gui.core.config import load_app_config
    from gui.core.event_store import EventStore
    from gui.core.labels import event_type_from_label, risk_type
    from gui.core.risk_engine import RiskEngine
    from gui.ui.login_dialog import LoginDialog


def draw_text_with_background(
    frame,
    text,
    position,
    font=cv2.FONT_HERSHEY_SIMPLEX,
    scale=0.65,
    text_color=(255, 255, 255),
    background_color=(0, 0, 0),
    border_color=(0, 255, 0),
    thickness=2,
    padding=6,
):
    """Draw legible label text on frame."""
    (text_w, text_h), baseline = cv2.getTextSize(text, font, scale, thickness)
    x, y = position
    cv2.rectangle(
        frame,
        (x - padding, y - text_h - padding),
        (x + text_w + padding, y + baseline + padding),
        background_color,
        cv2.FILLED,
    )
    cv2.rectangle(
        frame,
        (x - padding, y - text_h - padding),
        (x + text_w + padding, y + baseline + padding),
        border_color,
        2,
    )
    cv2.putText(frame, text, (x, y), font, scale, text_color, thickness, cv2.LINE_AA)


class DriverMonitor(QWidget):
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
            print(f"[WARN] DMS_PROJECT_ROOT 不存在，回退默认路径: {env_path}")
        return Path(__file__).resolve().parents[1]

    def __init__(self, account_username, account_display_name):
        super().__init__()
        self.setWindowTitle("智能驾驶监测系统")
        self.setMinimumSize(1080, 760)

        # Paths
        self.project_root = self._resolve_project_root()
        self.gui_dir = Path(__file__).resolve().parent
        logs_dir_env = os.getenv("DMS_LOGS_DIR", "").strip()
        self.logs_dir = (
            self._resolve_path(logs_dir_env, self.project_root)
            if logs_dir_env
            else self.project_root / "logs"
        )
        self.logs_dir.mkdir(exist_ok=True)
        config_path_env = os.getenv("DMS_CONFIG_PATH", "").strip()
        self.config_path = (
            self._resolve_path(config_path_env, self.project_root)
            if config_path_env
            else self.gui_dir / "config.yaml"
        )
        self.app_config = load_app_config(self.config_path)
        self.account_username = account_username
        self.account_display_name = account_display_name
        self.backend_client = BackendClient(
            login_url=os.getenv("DMS_LOGIN_API_URL", self.app_config["login_api_url"]),
            event_report_url=os.getenv(
                "DMS_EVENT_API_URL", self.app_config["event_report_api_url"]
            ),
            event_report_token=os.getenv(
                "DMS_INGEST_TOKEN", self.app_config["ingest_token"]
            ),
            session_report_url=os.getenv(
                "DMS_SESSION_API_URL", self.app_config["session_report_api_url"]
            ),
        )
        self.event_store = EventStore(self.logs_dir)

        # Model: prefer trained best.pt
        model_candidates = []
        model_path_env = os.getenv("DMS_MODEL_PATH", "").strip()
        if model_path_env:
            model_candidates.append(
                self._resolve_path(model_path_env, self.project_root)
            )
        model_candidates.extend(
            [
                self.project_root / "models" / "best.pt",
                self.project_root
                / "runs"
                / "detect"
                / "train3"
                / "weights"
                / "best.pt",
                self.project_root / "yolov8n.pt",
            ]
        )
        model_path = next((p for p in model_candidates if p.exists()), None)
        if model_path is None:
            raise FileNotFoundError(
                "未找到模型，请设置 DMS_MODEL_PATH 或放置 models/best.pt"
            )
        self.model = YOLO(str(model_path))
        self.model_names = self.model.names
        print(f"加载模型: {model_path}")
        print(f"模型类别: {self.model_names}")

        # Camera
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.app_config["camera_width"])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.app_config["camera_height"])

        # UI
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
                border-radius: 14px;
            }
            QLabel#Title {
                font-size: 28px;
                font-weight: 700;
                color: #e8f0ff;
                padding: 2px 2px 8px 2px;
            }
            QLabel#Video {
                background: #0b1323;
                border: 1px solid #2b4065;
                border-radius: 12px;
            }
            QLabel#Meta {
                color: #8ca0bf;
                font-size: 13px;
            }
            QLabel#Info {
                color: #b8c6df;
                font-size: 16px;
            }
            QLabel#Status {
                color: #4dc4ff;
                font-size: 17px;
                font-weight: 600;
            }
            QLabel#Warning {
                font-size: 20px;
                font-weight: 700;
                padding: 12px 14px;
                border-radius: 10px;
                border: 1px solid #2c6048;
                background: #10281f;
                color: #39d98a;
            }
            """
        )

        self.title_label = QLabel("智能驾驶监测系统")
        self.title_label.setObjectName("Title")

        self.image_label = QLabel()
        self.image_label.setObjectName("Video")
        self.image_label.setMinimumSize(640, 360)
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.model_label = QLabel(f"模型：{Path(model_path).name}")
        self.model_label.setObjectName("Meta")
        self.model_label.hide()

        self.status_label = QLabel("检测状态：初始化中...")
        self.status_label.setObjectName("Status")
        self.status_label.setWordWrap(True)

        self.warning_label = QLabel("疲劳状态：正常")
        self.warning_label.setObjectName("Warning")

        self.account_label = QLabel(
            f"当前账号：{self.account_display_name}（{self.account_username}）"
        )
        self.account_label.setObjectName("Meta")

        self.driver_label = QLabel("提示：当前状态稳定，请继续保持")
        self.driver_label.setObjectName("Info")

        self.stats_label = QLabel("统计：疲劳 0 次 | 疲劳时长 0.0s | 驾驶时长 0.0s")
        self.stats_label.setObjectName("Info")
        self.stats_label.setWordWrap(True)

        left_card = QFrame()
        left_card.setObjectName("Card")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)
        left_layout.addWidget(self.image_label)
        left_layout.addWidget(self.model_label)

        right_card = QFrame()
        right_card.setObjectName("Card")
        right_card.setMinimumWidth(280)
        right_card.setMaximumWidth(380)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(14)
        right_layout.addWidget(self.warning_label)
        right_layout.addWidget(self.status_label)
        right_layout.addWidget(self.account_label)
        right_layout.addWidget(self.driver_label)
        right_layout.addWidget(self.stats_label)
        right_layout.addStretch(1)

        self.right_card = right_card
        self.content_layout = QHBoxLayout()
        self.content_layout.setSpacing(16)
        self.content_layout.addWidget(left_card, 5)
        self.content_layout.addWidget(right_card, 2)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(self.title_label)
        layout.addLayout(self.content_layout)
        self.setLayout(layout)
        self._adjust_responsive_layout()

        # Runtime state
        self.conf_threshold = self.app_config["conf_threshold"]
        self.iou_threshold = self.app_config["iou_threshold"]
        self.prev_time = time.time()
        self.last_best_risk_conf = 0.0
        self.last_best_label = "NoDetection"
        self.risk_engine = RiskEngine(self.app_config)
        self.risk_trigger_seconds = self.risk_engine.risk_trigger_seconds
        self.recover_seconds = self.risk_engine.recover_seconds
        self.peak_snapshot_delta = self.app_config["peak_snapshot_delta"]
        # Store events under human-readable name; UID remains in account_username.
        self.current_driver = self.account_display_name or self.account_username

        # Frame quality gate: currently only brightness is enforced.
        self.min_brightness = self.app_config["min_brightness"]
        self.max_brightness = self.app_config["max_brightness"]
        self.max_upload_snapshot_bytes = int(
            self.app_config["max_upload_snapshot_kb"] * 1024
        )

        # Session/event logging
        self.session_alarm_count = 0
        self.session_alarm_seconds = 0.0
        self.session_id = (
            f"{self.account_username}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
        )
        self.session_start_ts = time.time()
        self.current_event = None
        self._start_driving_session()
        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def _adjust_responsive_layout(self):
        if self.width() < 1200:
            self.content_layout.setDirection(QHBoxLayout.Direction.TopToBottom)
            self.right_card.setMaximumWidth(16777215)
        else:
            self.content_layout.setDirection(QHBoxLayout.Direction.LeftToRight)
            self.right_card.setMaximumWidth(520)

    def resizeEvent(self, event):  # pyright: ignore[reportIncompatibleMethodOverride]
        self._adjust_responsive_layout()
        super().resizeEvent(event)

    def _class_name(self, cls_id):
        if isinstance(self.model_names, dict):
            return self.model_names.get(cls_id, "unknown")
        if isinstance(self.model_names, list) and 0 <= cls_id < len(self.model_names):
            return self.model_names[cls_id]
        return "unknown"

    def _build_snapshot_payload(self, snapshot_path):
        return self.event_store.build_snapshot_payload(
            snapshot_path=snapshot_path,
            max_upload_snapshot_bytes=self.max_upload_snapshot_bytes,
        )

    def _report_event_to_backend(self, payload):
        self.backend_client.report_event_async(payload=payload, timeout=4)

    def _start_driving_session(self):
        payload = {
            "action": "start",
            "source_session_id": self.session_id,
            "account_username": self.account_username,
            "start_time": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(self.session_start_ts)
            ),
            "source": "gui",
        }
        self.backend_client.report_session_async(payload=payload, timeout=4)

    def _end_driving_session(self):
        end_ts = time.time()
        payload = {
            "action": "end",
            "source_session_id": self.session_id,
            "account_username": self.account_username,
            "end_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_ts)),
            "duration_sec": round(max(0.0, end_ts - self.session_start_ts), 2),
            "source": "gui",
        }
        self.backend_client.report_session_async(payload=payload, timeout=4)

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return

        now = time.time()
        delta_t = max(1e-3, now - self.prev_time)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        frame_quality_ok = self.min_brightness <= brightness <= self.max_brightness

        # YOLO predict: same style as reference project
        results = self.model.predict(
            frame,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            verbose=False,
        )
        result = results[0]

        best_risk_conf = 0.0
        best_safe_conf = 0.0
        best_label = "NoDetection"
        best_conf = 0.0

        if result.boxes is not None and len(result.boxes) > 0:
            boxes_xyxy = result.boxes.xyxy
            labels = result.boxes.cls
            confs = result.boxes.conf

            for box, label_id, conf in zip(boxes_xyxy, labels, confs):
                x1, y1, x2, y2 = map(int, box.tolist())
                conf = float(conf.item())
                label_name = self._class_name(int(label_id.item()))
                rtype = risk_type(label_name)

                if rtype == "risk":
                    color = (0, 0, 255)
                    if conf > best_risk_conf:
                        best_risk_conf = conf
                else:
                    color = (0, 255, 0)
                    if conf > best_safe_conf:
                        best_safe_conf = conf

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                draw_text_with_background(
                    frame=frame,
                    text=f"{label_name}, Conf {conf * 100:.1f}%",
                    position=(x1, max(30, y1 - 8)),
                    border_color=color,
                )

                if conf > best_conf:
                    best_conf = conf
                    best_label = label_name
        self.last_best_label = best_label

        self.last_best_risk_conf = best_risk_conf
        engine_state = self.risk_engine.step(
            now=now,
            delta_t=delta_t,
            best_risk_conf=best_risk_conf,
            best_safe_conf=best_safe_conf,
            frame_quality_ok=frame_quality_ok,
        )
        warning_text = engine_state["warning_text"]
        if engine_state["alarm_started"]:
            self._start_event(frame)
        if engine_state["update_peak"]:
            self._update_event_peak(frame)
        if engine_state["alarm_ended"]:
            self._end_event(frame)
        if engine_state["periodic_snapshot"] and self.risk_engine.alarm_on:
            self._capture_snapshot(frame, "periodic", best_risk_conf)

        # FPS
        fps = 1.0 / max(1e-6, now - self.prev_time)
        self.prev_time = now
        cv2.putText(
            frame,
            f"FPS: {fps:.1f}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 0),
            2,
            cv2.LINE_AA,
        )

        # UI text
        self.status_label.setText(f"检测状态：{best_label}")
        if warning_text == "疲劳":
            self.driver_label.setText("提示：请立即靠边停车并休息")
        elif warning_text == "注意":
            self.driver_label.setText("提示：请集中注意力，必要时尽快休息")
        else:
            self.driver_label.setText("提示：当前状态稳定，请继续保持")
        self.warning_label.setText(f"疲劳状态：{warning_text}")
        if warning_text == "疲劳":
            self.warning_label.setStyleSheet(
                "font-size: 20px; font-weight: 700; padding: 12px 14px; "
                "border-radius: 10px; border: 1px solid #6f2e2e; "
                "background: #2a1418; color: #ff8a8a;"
            )
        elif warning_text == "注意":
            self.warning_label.setStyleSheet(
                "font-size: 20px; font-weight: 700; padding: 12px 14px; "
                "border-radius: 10px; border: 1px solid #69532c; "
                "background: #2c2415; color: #ffcc70;"
            )
        else:
            self.warning_label.setStyleSheet(
                "font-size: 20px; font-weight: 700; padding: 12px 14px; "
                "border-radius: 10px; border: 1px solid #2c6048; "
                "background: #10281f; color: #39d98a;"
            )
        self.stats_label.setText(
            "统计：疲劳 "
            f"{self.session_alarm_count} 次 | 疲劳时长 {self.session_alarm_seconds:.1f}s | "
            f"驾驶时长 {max(0.0, now - self.session_start_ts):.1f}s"
        )

        # Show image
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        qt_img = QImage(rgb_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_img).scaled(
            self.image_label.width(),
            self.image_label.height(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(pixmap)

    def closeEvent(self, event):  # pyright: ignore[reportIncompatibleMethodOverride]
        self.timer.stop()
        self._end_driving_session()
        if self.cap.isOpened():
            self.cap.release()
        if self.risk_engine.alarm_on:
            self._end_event()
        super().closeEvent(event)

    def _capture_snapshot(self, frame, snapshot_type, risk_conf):
        return self.event_store.capture_snapshot(
            current_event=self.current_event,
            frame=frame,
            snapshot_type=snapshot_type,
            risk_conf=risk_conf,
        )

    def _start_event(self, frame=None):
        self.current_event = {
            "event_id": int(time.time() * 1000),
            "start_time_ts": time.time(),
            "driver_name": self.current_driver,
            "peak_risk_conf": self.last_best_risk_conf,
            "source_label": self.last_best_label,
            "snapshots": [],
            "start_snapshot_path": "",
            "peak_snapshot_path": "",
            "end_snapshot_path": "",
        }
        self.current_event["start_snapshot_path"] = self._capture_snapshot(
            frame, "start", self.last_best_risk_conf
        )
        self.current_event["peak_snapshot_path"] = self.current_event[
            "start_snapshot_path"
        ]
        self.risk_engine.mark_snapshot_time(time.time())

    def _update_event_peak(self, frame=None):
        if self.current_event is None:
            return
        if (
            self.last_best_risk_conf
            >= self.current_event["peak_risk_conf"] + self.peak_snapshot_delta
        ):
            self.current_event["peak_risk_conf"] = self.last_best_risk_conf
            self.current_event["source_label"] = self.last_best_label
            peak_path = self._capture_snapshot(frame, "peak", self.last_best_risk_conf)
            if peak_path:
                self.current_event["peak_snapshot_path"] = peak_path

    def _end_event(self, frame=None):
        if self.current_event is None:
            return
        end_snapshot_path = self._capture_snapshot(
            frame, "end", self.last_best_risk_conf
        )
        if end_snapshot_path:
            self.current_event["end_snapshot_path"] = end_snapshot_path

        end_ts = time.time()
        start_ts = self.current_event["start_time_ts"]
        duration = max(0.0, end_ts - start_ts)
        self.session_alarm_count += 1
        self.session_alarm_seconds += duration
        driver_name = self.current_event.get("driver_name", "Unknown")

        start_dt, end_dt = self.event_store.append_event_row(
            current_event=self.current_event,
            start_ts=start_ts,
            end_ts=end_ts,
            duration=duration,
            risk_trigger_seconds=self.risk_trigger_seconds,
            recover_seconds=self.recover_seconds,
        )
        report_payload = {
            "event_id": str(self.current_event["event_id"]),
            "account_username": self.account_username,
            "source_session_id": self.session_id,
            "start_time": start_dt,
            "end_time": end_dt,
            "duration_sec": round(duration, 2),
            "driver_name": driver_name,
            "source_label": self.current_event.get("source_label", ""),
            "event_type": event_type_from_label(
                self.current_event.get("source_label", "")
            ),
            "peak_risk_conf": round(self.current_event["peak_risk_conf"], 3),
            "trigger_frames": int(self.risk_trigger_seconds * 10),
            "recover_frames": int(self.recover_seconds * 10),
            "snapshot_path": self.current_event.get("peak_snapshot_path", ""),
        }
        report_payload.update(
            self._build_snapshot_payload(
                self.current_event.get("peak_snapshot_path", "")
            )
        )
        self._report_event_to_backend(report_payload)
        self.risk_engine.alarm_on = False
        self.current_event = None


def main():
    app = QApplication(sys.argv)
    login_dialog = LoginDialog()
    if (
        login_dialog.exec() != QDialog.DialogCode.Accepted
        or not login_dialog.login_result
    ):
        return
    window = DriverMonitor(
        account_username=login_dialog.login_result["username"],
        account_display_name=login_dialog.login_result["display_name"],
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
