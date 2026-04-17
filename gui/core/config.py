from pathlib import Path


DEFAULT_APP_CONFIG = {
    "camera_width": 1280,
    "camera_height": 720,
    "conf_threshold": 0.40,
    "iou_threshold": 0.50,
    "risk_frame_conf": 0.62,
    "risk_margin": 0.08,
    "risk_trigger_seconds": 2.2,
    "recover_seconds": 2.8,
    "capture_interval_sec": 5.0,
    "alarm_cooldown_sec": 4.0,
    "peak_snapshot_delta": 0.02,
    "risk_on_threshold": 0.68,
    "risk_off_threshold": 0.52,
    "alarm_ema_threshold": 0.77,
    "ema_alpha": 0.15,
    "trigger_vote_ratio": 0.70,
    "recover_vote_ratio": 0.30,
    "min_brightness": 35.0,
    "max_brightness": 235.0,
    "max_upload_snapshot_kb": 1200,
    # Backend endpoints
    "login_api_url": "http://localhost:8000/api/v2/auth/login",
    "event_report_api_url": "http://localhost:8000/api/events/report/",
    "session_report_api_url": "http://localhost:8000/api/sessions/report/",
    "signup_page_url": "http://localhost:5173/register",
    "ingest_token": "",
}


def write_default_config(path: Path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Driver Monitor 本地推理参数\n")
        f.write("# 修改后重启 GUI 生效\n")
        for key, value in DEFAULT_APP_CONFIG.items():
            f.write(f"{key}: {value}\n")


def parse_simple_yaml(path: Path):
    config = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            config[key.strip()] = value.strip().strip("'\"")
    return config


def load_app_config(path: Path):
    config = dict(DEFAULT_APP_CONFIG)
    if not path.exists():
        write_default_config(path)
        print(f"未发现配置文件，已创建默认配置: {path}")
        return config

    file_config = parse_simple_yaml(path)
    for key, default_value in DEFAULT_APP_CONFIG.items():
        if key not in file_config:
            continue
        value = file_config[key]
        try:
            if isinstance(default_value, int):
                config[key] = int(float(value))
            elif isinstance(default_value, float):
                config[key] = float(value)
            else:
                config[key] = value
        except (ValueError, TypeError):
            print(f"配置项无效，已使用默认值: {key}={default_value}")
    print(f"加载配置: {path}")
    return config
