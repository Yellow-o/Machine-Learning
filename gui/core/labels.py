def risk_type(label):
    text = str(label).lower()
    risk_words = {
        "drowsy",
        "sleep",
        "sleepy",
        "yawn",
        "fatigue",
        "danger",
        "distract",
        "drink",
        "phone",
        "smoke",
        "text",
        "call",
    }
    safe_words = {"awake", "safe", "normal", "focused", "attentive"}
    if any(w in text for w in risk_words):
        return "risk"
    if any(w in text for w in safe_words):
        return "safe"
    return "unknown"


def event_type_from_label(label):
    _ = str(label).lower()
    return "fatigue"
