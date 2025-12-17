DOMAIN = "hisense_multi_idu"

# Эти значения должны соответствовать твоему HiDom.
# Если у тебя другие коды — просто поменяешь цифры.
MODE_MAP = {
    "cool": 2,
    "dry": 4,
    "fan_only": 8,
    "heat": 16,
}
MODE_REVERSE_MAP = {v: k for k, v in MODE_MAP.items()}

FAN_MAP = {
    "low": 1,
    "medium": 2,
    "high": 3,
}
FAN_REVERSE_MAP = {v: k for k, v in FAN_MAP.items()}
