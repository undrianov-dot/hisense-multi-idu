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

# Коды режимов работы (из данных устройства) - ОСНОВНЫЕ
MODE_COOL = 2        # Охлаждение
MODE_DRY = 4         # Осушение
MODE_FAN_ONLY = 8    # Вентилятор
MODE_HEAT = 16       # Обогрев

# Коды скоростей вентилятора (только основные)
FAN_AUTO = 1         # Авто
FAN_HIGH = 2         # Высокая
FAN_MID = 4          # Средняя
FAN_LOW = 8          # Низкая

# Маппинг для Home Assistant - ТОЛЬКО ОСНОВНЫЕ РЕЖИМЫ
MODE_MAP = {
    MODE_COOL: "cool",
    MODE_DRY: "dry",
    MODE_FAN_ONLY: "fan_only",
    MODE_HEAT: "heat"
}

# ВАЖНО: Явно указываем обратный маппинг для ВСЕХ поддерживаемых режимов
MODE_REVERSE_MAP = {
    "cool": MODE_COOL,
    "dry": MODE_DRY,
    "fan_only": MODE_FAN_ONLY,
    "heat": MODE_HEAT
}

# Маппинг для скоростей вентилятора
FAN_MAP = {
    FAN_AUTO: "auto",
    FAN_HIGH: "high",
    FAN_MID: "medium",
    FAN_LOW: "low"
}

# Обратный маппинг для скоростей
FAN_REVERSE_MAP = {
    "auto": FAN_AUTO,
    "high": FAN_HIGH,
    "medium": FAN_MID,
    "low": FAN_LOW
}

# Статусы устройства
STATUS_ON = "on"
STATUS_OFF = "off"
STATUS_ALARM = "alarm"
STATUS_OFFLINE = "offline"
