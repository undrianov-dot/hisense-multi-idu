"""Constants for the Hisense Multi-IDU integration."""
DOMAIN = "hisense_multi_idu"

# Конфигурация
CONF_HOST = "host"

# Интервалы обновления по умолчанию (секунды)
DEFAULT_SCAN_INTERVAL_CLIMATE = 10
DEFAULT_SCAN_INTERVAL_SENSOR = 30

# Индексы данных в массиве data[]
DATA_ONOFF = 28      # Состояние вкл/выкл (0=OFF, 1=ON)
DATA_MODE = 29       # Режим работы
DATA_FAN = 30        # Скорость вентилятора
DATA_SET_TEMP = 31   # Установленная температура
DATA_ERROR_CODE = 35 # Код ошибки
DATA_PIPE_TEMP = 38  # Температура трубки
DATA_ROOM_TEMP = 39  # ИСПРАВЛЕНО: Температура в помещении

# Коды режимов работы (из данных устройства)
MODE_COOL = 2        # Охлаждение
MODE_DRY = 4         # Осушение
MODE_FAN_ONLY = 8    # Вентилятор
MODE_HEAT = 16       # Обогрев
MODE_AUTO_DRY = 32   # Авто осушение
MODE_REFRESH = 256   # Освежение
MODE_SLEEP = 512     # Сон
MODE_HEAT_SUP = 1024 # Подогрев

# Коды скорости вентилятора (только основные)
FAN_AUTO = 1         # Авто
FAN_HIGH = 2         # Высокая
FAN_MID = 4          # Средняя
FAN_LOW = 8          # Низкая

MODE_MAP = {
    MODE_COOL: "cool",
    MODE_DRY: "dry",
    MODE_FAN_ONLY: "fan_only",
    MODE_HEAT: "heat",
    MODE_AUTO_DRY: "dry",
    MODE_REFRESH: "cool",
    MODE_SLEEP: "cool",
    MODE_HEAT_SUP: "heat"
}

# ВАЖНО: Исправленный MODE_REVERSE_MAP
MODE_REVERSE_MAP = {
    "cool": MODE_COOL,
    "dry": MODE_DRY,
    "fan_only": MODE_FAN_ONLY,
    "heat": MODE_HEAT
}

# Маппинг для скоростей вентилятора (только основные)
FAN_MAP = {
    FAN_AUTO: "auto",
    FAN_HIGH: "high",
    FAN_MID: "medium",
    FAN_LOW: "low"
}

FAN_REVERSE_MAP = {v: k for k, v in FAN_MAP.items()}

# Коды вертикальной жалюзи (louver / swing)
LOUVER_ANGLE_1 = 0
LOUVER_AUTO = 1
LOUVER_ANGLE_2 = 2
LOUVER_ANGLE_3 = 4
LOUVER_ANGLE_4 = 8
LOUVER_ANGLE_5 = 16
LOUVER_ANGLE_6 = 32
LOUVER_ANGLE_7 = 64
LOUVER_ANGLE_8 = 128

LOUVER_MAP = {
    LOUVER_AUTO: "auto",
    LOUVER_ANGLE_1: "angle_1",
    LOUVER_ANGLE_2: "angle_2",
    LOUVER_ANGLE_3: "angle_3",
    LOUVER_ANGLE_4: "angle_4",
    LOUVER_ANGLE_5: "angle_5",
    LOUVER_ANGLE_6: "angle_6",
    LOUVER_ANGLE_7: "angle_7",
    LOUVER_ANGLE_8: "angle_8",
}

LOUVER_REVERSE_MAP = {v: k for k, v in LOUVER_MAP.items()}



