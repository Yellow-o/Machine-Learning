from collections import deque


class RiskEngine:
    def __init__(self, app_config):
        # Thresholds and hysteresis settings.
        self.risk_frame_conf = app_config["risk_frame_conf"]
        self.risk_margin = app_config["risk_margin"]
        self.risk_trigger_seconds = app_config["risk_trigger_seconds"]
        self.recover_seconds = app_config["recover_seconds"]
        self.capture_interval_sec = app_config["capture_interval_sec"]
        self.alarm_cooldown_sec = app_config["alarm_cooldown_sec"]
        self.risk_on_threshold = app_config["risk_on_threshold"]
        self.risk_off_threshold = app_config["risk_off_threshold"]
        self.alarm_ema_threshold = app_config["alarm_ema_threshold"]
        self.ema_alpha = app_config["ema_alpha"]
        self.trigger_vote_ratio = app_config["trigger_vote_ratio"]
        self.recover_vote_ratio = app_config["recover_vote_ratio"]

        # Runtime state.
        self.risk_counter = 0
        self.safe_counter = 0
        self.risk_streak = 0
        self.safe_streak = 0
        self.risk_duration_sec = 0.0
        self.safe_duration_sec = 0.0
        self.alarm_on = False
        self.last_alarm_end_ts = 0.0
        self.last_capture_time = 0.0
        self.risk_ema = 0.0
        self.safe_ema = 0.0
        self.vote_window = deque(maxlen=30)

    def mark_snapshot_time(self, now):
        self.last_capture_time = now

    def step(self, now, delta_t, best_risk_conf, best_safe_conf, frame_quality_ok):
        frame_risk_candidate = (
            frame_quality_ok
            and best_risk_conf >= self.risk_frame_conf
            and best_risk_conf >= (best_safe_conf + self.risk_margin)
        )

        if frame_quality_ok:
            self.risk_ema = (1.0 - self.ema_alpha) * self.risk_ema + self.ema_alpha * best_risk_conf
            self.safe_ema = (1.0 - self.ema_alpha) * self.safe_ema + self.ema_alpha * best_safe_conf
        else:
            self.risk_ema *= 0.95
            self.safe_ema *= 0.95

        frame_risk_vote = (
            frame_quality_ok
            and self.risk_ema >= self.risk_on_threshold
            and self.risk_ema >= (self.safe_ema + self.risk_margin)
            and frame_risk_candidate
        )
        self.vote_window.append(1 if frame_risk_vote else 0)
        vote_ratio = (
            sum(self.vote_window) / len(self.vote_window) if len(self.vote_window) > 0 else 0.0
        )
        enough_votes = len(self.vote_window) >= 10
        cooldown_active = (now - self.last_alarm_end_ts) < self.alarm_cooldown_sec
        trigger_ready = enough_votes and vote_ratio >= self.trigger_vote_ratio and not cooldown_active
        recover_ready = (
            enough_votes
            and vote_ratio <= self.recover_vote_ratio
            and self.risk_ema <= self.risk_off_threshold
        )

        if trigger_ready:
            self.risk_counter += 1
            self.safe_counter = 0
            self.risk_streak += 1
            self.safe_streak = 0
            self.risk_duration_sec += delta_t
            self.safe_duration_sec = 0.0
        elif recover_ready:
            self.safe_counter += 1
            if self.risk_counter > 0:
                self.risk_counter -= 1
            self.safe_streak += 1
            self.risk_streak = 0
            self.safe_duration_sec += delta_t
            self.risk_duration_sec = 0.0
        else:
            self.risk_duration_sec = max(0.0, self.risk_duration_sec - delta_t * 0.5)
            self.safe_duration_sec = max(0.0, self.safe_duration_sec - delta_t * 0.5)

        warning_text = "正常"
        alarm_started = False
        alarm_ended = False
        update_peak = False

        if self.risk_duration_sec >= self.risk_trigger_seconds:
            if not self.alarm_on:
                self.alarm_on = True
                alarm_started = True

            warning_text = (
                "疲劳"
                if (best_risk_conf >= 0.85 or self.risk_ema >= self.alarm_ema_threshold)
                else "注意"
            )
            update_peak = True
        elif self.safe_duration_sec >= self.recover_seconds:
            if self.alarm_on:
                self.alarm_on = False
                alarm_ended = True
                self.last_alarm_end_ts = now
            warning_text = "正常"
        elif self.alarm_on:
            warning_text = "注意"

        periodic_snapshot = False
        if self.alarm_on and (now - self.last_capture_time >= self.capture_interval_sec):
            periodic_snapshot = True
            self.last_capture_time = now

        return {
            "warning_text": warning_text,
            "alarm_started": alarm_started,
            "alarm_ended": alarm_ended,
            "update_peak": update_peak,
            "periodic_snapshot": periodic_snapshot,
        }

