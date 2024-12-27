"""Constants for the Control4 Amplifier integration."""
from typing import Final

DOMAIN: Final = "control4_amplifier"

# SSDP Constants
ATTR_MANUFACTURER = "Control4"
ATTR_MODEL = "C4-8AMP1-B"
ATTR_ST = "c4:v1_8chanamp"
ATTR_MAC_ADDRESS = "mac_address"

# Config Constants
CONF_PORT = "port"
CONF_INPUTS = "inputs"
CONF_OUTPUTS = "outputs"

DEFAULT_PORT = 8750
DEFAULT_NAME = "Control4 Amplifier"

# Number of inputs/outputs
NUM_ANALOG_INPUTS = 4
NUM_DIGITAL_INPUTS = 2
NUM_OUTPUTS = 4

DEFAULT_INPUT_LABELS = {
    1: "Analog Input 1",
    2: "Analog Input 2",
    3: "Analog Input 3",
    4: "Analog Input 4",
    5: "Digital Input 1",
    6: "Digital Input 3",
}

DEFAULT_OUTPUT_LABELS = {
    1: "Output 1",
    2: "Output 2",
    3: "Output 3",
    4: "Output 4",
}

# Command Constants
CMD_OUTPUT = "c4.amp.out"
CMD_DIGITAL = "c4.amp.digital"
CMD_VOLUME = "c4.amp.chvol"
CMD_BALANCE = "c4.amp.balance"
CMD_INPUT_GAIN = "c4.amp.ingain"
CMD_BASS = "c4.amp.bass"
CMD_TREBLE = "c4.amp.treble"

# Value Ranges
GAIN_MIN = -6
GAIN_MAX = 0
BALANCE_MIN = -10  # L10
BALANCE_MAX = 10   # R10
TONE_MIN = -12
TONE_MAX = 12