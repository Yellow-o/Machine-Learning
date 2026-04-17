import base64
import csv
import hashlib
import time
from datetime import datetime
from pathlib import Path

import cv2


class EventStore:
    events_csv_header = [
        "event_id",
        "start_time",
        "end_time",
        "duration_sec",
        "driver_name",
        "peak_risk_conf",
        "trigger_seconds",
        "recover_seconds",
        "snapshot_count",
        "peak_snapshot_path",
        "start_snapshot_path",
        "end_snapshot_path",
    ]
    snapshots_csv_header = [
        "event_id",
        "capture_time",
        "snapshot_type",
        "risk_conf",
        "driver_name",
        "file_path",
    ]

    def __init__(self, logs_dir: Path):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)
        self.events_csv_path = self.logs_dir / "events.csv"
        self.snapshots_csv_path = self.logs_dir / "snapshots.csv"
        self.ensure_csv_headers()

    def ensure_csv_headers(self):
        if not self.events_csv_path.exists():
            with open(self.events_csv_path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(self.events_csv_header)

        if not self.snapshots_csv_path.exists():
            with open(self.snapshots_csv_path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(self.snapshots_csv_header)

    def capture_snapshot(self, current_event, frame, snapshot_type, risk_conf):
        if frame is None or current_event is None:
            return ""

        capture_ts = time.time()
        event_id = current_event["event_id"]
        filename = self.logs_dir / f"{event_id}_{snapshot_type}_{int(capture_ts * 1000)}.jpg"
        cv2.imwrite(str(filename), frame)

        capture_dt = datetime.fromtimestamp(capture_ts).strftime("%Y-%m-%d %H:%M:%S")
        with open(self.snapshots_csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                [
                    event_id,
                    capture_dt,
                    snapshot_type,
                    f"{risk_conf:.3f}",
                    current_event.get("driver_name", "Unknown"),
                    str(filename),
                ]
            )
        current_event["snapshots"].append(str(filename))
        print(f"疲劳截图({snapshot_type}): {filename}")
        return str(filename)

    def append_event_row(
        self,
        current_event,
        start_ts,
        end_ts,
        duration,
        risk_trigger_seconds,
        recover_seconds,
    ):
        start_dt = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d %H:%M:%S")
        end_dt = datetime.fromtimestamp(end_ts).strftime("%Y-%m-%d %H:%M:%S")

        with open(self.events_csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                [
                    current_event["event_id"],
                    start_dt,
                    end_dt,
                    f"{duration:.2f}",
                    current_event.get("driver_name", "Unknown"),
                    f"{current_event['peak_risk_conf']:.3f}",
                    f"{risk_trigger_seconds:.2f}",
                    f"{recover_seconds:.2f}",
                    len(current_event.get("snapshots", [])),
                    current_event.get("peak_snapshot_path", ""),
                    current_event.get("start_snapshot_path", ""),
                    current_event.get("end_snapshot_path", ""),
                ]
            )
        return start_dt, end_dt

    @staticmethod
    def build_snapshot_payload(snapshot_path, max_upload_snapshot_bytes):
        if not snapshot_path:
            return {}
        path = Path(snapshot_path)
        if not path.exists():
            return {}

        try:
            raw = path.read_bytes()
        except Exception as exc:
            print(f"读取截图失败，跳过上传: {exc}")
            return {}

        if not raw:
            return {}

        if len(raw) > max_upload_snapshot_bytes:
            img = cv2.imread(str(path))
            if img is not None:
                ok, encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok:
                    raw = encoded.tobytes()

        if len(raw) > max_upload_snapshot_bytes:
            print("截图过大，跳过上报截图内容")
            return {}

        digest = hashlib.sha256(raw).hexdigest()
        return {
            "snapshot_base64": base64.b64encode(raw).decode("ascii"),
            "snapshot_sha256": digest,
            "snapshot_filename": path.name,
        }

