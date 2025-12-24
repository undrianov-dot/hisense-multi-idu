"""Constants for the Hisense Multi-IDU integration."""
DOMAIN = "hisense_multi_idu"

# Конфигурация
CONF_HOST = "host"

# Интервалы обновления по умолчанию (секунды)
DEFAULT_SCAN_INTERVAL_CLIMATE = 30
DEFAULT_SCAN_INTERVAL_SENSOR = 60

# Индексы данных в массиве data[]
DATA_ONOFF = 28      # Состояние вкл/выкл (0=OFF, 1=ON)
DATA_MODE = 29       # Режим работы
DATA_FAN = 30        # Скорость вентилятора
DATA_SET_TEMP = 31   # Установленная температура
DATA_ERROR_CODE = 35 # Код ошибки
DATA_ROOM_TEMP = 38  # Температура в помещении
DATA_PIPE_TEMP = 39  # Температура трубки

# Добавляем индексы для управления жалюзи
DATA_DAMPER_VERTICAL = 40   # Вертикальные жалюзи
DATA_DAMPER_HORIZONTAL = 41 # Горизонтальные жалюзи

# Коды режимов работы (из данных устройства)
MODE_COOL = 2        # Охлаждение
MODE_DRY = 4         # Осушение
MODE_FAN_ONLY = 8    # Вентилятор
MODE_HEAT = 16       # Обогрев
# Убрали MODE_AUTO = 1 - режим AUTO не используем
MODE_AUTO_DRY = 32   # Авто осушение
MODE_REFRESH = 256   # Освежение
MODE_SLEEP = 512     # Сон
MODE_HEAT_SUP = 1024 # Подогрев

# Коды скорости вентилятора (только основные)
FAN_AUTO = 1         # Авто
FAN_HIGH = 2         # Высокая
FAN_MID = 4          # Средняя
FAN_LOW = 8          # Низкая
# Убрали дополнительные скорости

# Коды положения жалюзи (примерные значения)
DAMPER_AUTO = 0      # Автоматическое движение
DAMPER_CLOSED = 1    # Закрыто
DAMPER_OPEN = 2      # Открыто
DAMPER_POSITION_1 = 3  # Позиция 1
DAMPER_POSITION_2 = 4  # Позиция 2
DAMPER_POSITION_3 = 5  # Позиция 3
DAMPER_SWING = 6    # Качание (свинг)
DAMPER_STOP = 0     # Остановка (если поддерживается)

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

# Маппинг для положения жалюзи
DAMPER_MAP = {
    DAMPER_AUTO: "auto",
    DAMPER_CLOSED: "closed",
    DAMPER_OPEN: "open",
    DAMPER_POSITION_1: "position_1",
    DAMPER_POSITION_2: "position_2",
    DAMPER_POSITION_3: "position_3",
    DAMPER_SWING: "swing"
}

DAMPER_REVERSE_MAP = {v: k for k, v in DAMPER_MAP.items()}

# Маппинг для режимов жалюзи в HomeKit через swing_mode
SWING_TO_DAMPER = {
    "off": DAMPER_CLOSED,
    "vertical": DAMPER_SWING,
    "horizontal": DAMPER_SWING,
    "both": DAMPER_SWING
}
