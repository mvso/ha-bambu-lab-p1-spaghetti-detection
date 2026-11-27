"""Constants of the Bambu Lab P1 - Spaghetti Detection integration."""

DOMAIN = "bambu_lab_p1_spaghetti_detection"

# Options of the built-in detection, set in the integration's own settings.
CONF_ENABLED = "enabled"
CONF_OBICO_HOST = "obico_host"
CONF_OBICO_TOKEN = "obico_auth_token"
CONF_HA_HOST = "home_assistant_host"
CONF_CAMERA = "camera"
CONF_CAMERA_2 = "camera_2"
CONF_PRINT_STATUS = "print_status_sensor"
CONF_STAGE = "stage_sensor"
CONF_LIGHT = "chamber_light"
CONF_AUTO_LIGHT = "auto_turn_on_light"
CONF_FREQUENCY = "detection_frequency"

# Seconds between two detection rounds. 60 is not possible for the same reason as in the blueprint.
FREQUENCIES = ("1", "5", "10", "30", "59")
DEFAULT_FREQUENCY = "5"

# The secret the ML server used to be shipped with. It is public, so the server refuses it.
PUBLIC_DEFAULT_TOKEN = "obico_api_secret"

# Fired when a failure is detected. Data: confidence (0 to 1) and camera (entity ID).
EVENT_FAILURE_DETECTED = f"{DOMAIN}_failure_detected"

# The values the detection keeps between rounds. They are the number entities of the integration.
NUMBER_KEYS = (
    "current_frame_number",
    "lifetime_frame_number",
    "ewm_mean",
    "adjusted_ewm_mean",
    "p",
    "normalized_p",
    "p_sum",
    "rolling_mean_diff",
    "rolling_mean_long",
    "rolling_mean_short",
    "thresh_warning",
    "thresh_failure",
)

# States of the status sensor.
STATUS_OFF = "off"
STATUS_WAITING = "waiting"
STATUS_WARMING_UP = "warming_up"
STATUS_MONITORING = "monitoring"
STATUS_ERROR = "error"
STATUSES = (STATUS_OFF, STATUS_WAITING, STATUS_WARMING_UP, STATUS_MONITORING, STATUS_ERROR)
