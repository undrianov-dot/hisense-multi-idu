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

# Коды режимов работы (из данных устройства)
MODE_COOL = 2        # Охлаждение
MODE_DRY = 4         # Осушение
MODE_FAN_ONLY = 8    # Вентилятор
MODE_HEAT = 16       # Обогрев
MODE_AUTO = 1        # Авто (из веб-интерфейса) - НЕ ИСПОЛЬЗУЕМ
MODE_AUTO_DRY = 32   # Авто осушение
MODE_REFRESH = 256   # Освежение
MODE_SLEEP = 512     # Сон
MODE_HEAT_SUP = 1024 # Подогрев

# Коды скорости вентилятора (ТОЛЬКО ОСНОВНЫЕ)
FAN_AUTO = 1         # Авто
FAN_HIGH = 2         # Высокая
FAN_MID = 4          # Средняя
FAN_LOW = 8          # Низкая

# Маппинг для Home Assistant (ТОЛЬКО ОСНОВНЫЕ РЕЖИМЫ - БЕЗ AUTO)
MODE_MAP = {
    MODE_COOL: "cool",
    MODE_DRY: "dry",
    MODE_FAN_ONLY: "fan_only",
    MODE_HEAT: "heat"
}

MODE_REVERSE_MAP = {v: k for k, v in MODE_MAP.items()}

# Маппинг для скоростей вентилятора (ТОЛЬКО ОСНОВНЫЕ)
FAN_MAP = {
    FAN_AUTO: "auto",
    FAN_HIGH: "high",
    FAN_MID: "medium",
    FAN_LOW: "low"
}

FAN_REVERSE_MAP = {v: k for k, v in FAN_MAP.items()}
