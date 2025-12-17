"""Constants for the Hisense Multi-IDU integration."""
DOMAIN = "hisense_multi_idu"

# Default scan intervals in seconds
DEFAULT_SCAN_INTERVAL_CLIMATE = 60
DEFAULT_SCAN_INTERVAL_SENSOR = 30

# Device API endpoints
API_METER_PATH = "/cgi/get_meter_pwr.shtml"
# Possibly endpoints for unit status (to be confirmed/adjusted if needed)
API_UNIT_STATUS_PATH = "/cgi/get_unit_status.cgi"

# Modes mapping between device and Home Assistant
MODE_MAP = {
    0: "auto",
    1: "cool",
    2: "dry",
    3: "fan",
    4: "heat"
}
# Fan speed mapping
FAN_MAP = {
    0: "auto",
    1: "low",
    2: "medium",
    3: "high"
}
