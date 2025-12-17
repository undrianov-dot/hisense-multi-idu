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
MODE_AUTO = 1        # Авто (из веб-интерфейса)
MODE_AUTO_DRY = 32   # Авто осушение
MODE_REFRESH = 256   # Освежение
MODE_SLEEP = 512     # Сон
MODE_HEAT_SUP = 1024 # Подогрев

# Коды скорости вентилятора
FAN_AUTO = 1         # Авто
FAN_HIGH = 2         # Высокая
FAN_MID = 4          # Средняя
FAN_LOW = 8          # Низкая
FAN_S_HIGH = 16      # Сверхвысокая
FAN_S_LOW = 32       # Сверхнизкая
FAN_BREEZE = 64      # Бриз

# Маппинг для Home Assistant
MODE_MAP = {
    MODE_AUTO: "auto",
    MODE_COOL: "cool",
    MODE_DRY: "dry",
    MODE_FAN_ONLY: "fan_only",
    MODE_HEAT: "heat",
    MODE_AUTO_DRY: "auto_dry",
    MODE_REFRESH: "refresh",
    MODE_SLEEP: "sleep",
    MODE_HEAT_SUP: "heat_sup"
}

MODE_REVERSE_MAP = {v: k for k, v in MODE_MAP.items()}

FAN_MAP = {
    FAN_AUTO: "auto",
    FAN_HIGH: "high",
    FAN_MID: "medium",
    FAN_LOW: "low",
    FAN_S_HIGH: "s_high",
    FAN_S_LOW: "s_low",
    FAN_BREEZE: "breeze"
}

FAN_REVERSE_MAP = {v: k for k, v in FAN_MAP.items()}
