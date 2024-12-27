# Control4 Audio Matrix Amplifier Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

This integration provides control for Control4 Audio Matrix Amplifiers in Home Assistant.

**Disclaimer: this was almost entirely written by Claude, so although tested, needs fleshing out.**

## Features

- Control of 4 outputs with independent:
    - Volume control
    - Source selection
    - Balance adjustment (L10 to R10)
    - Bass adjustment (-12 to +12)
    - Treble adjustment (-12 to +12)
- 6 logical inputs mapped to 4 physical inputs:
    - 4 analog inputs
    - 2 digital inputs (shared with analog inputs 1 and 3)
- Individual gain control for each physical input (-6 to 0)

## Installation

### HACS (Recommended)

1. Add this repository (https://github.com/calcinai/hass-control4-amplifier) to HACS as a custom repository:
    - Open HACS
    - Click on the three dots in the top right corner
    - Select "Custom repositories"
    - Add the repository URL: https://github.com/calcinai/hass-control4-amplifier
    - Select category: "Integration"
    - Click "Add"
2. Click "Download" on the Control4 Amplifier integration
3. Restart Home Assistant

### Manual Installation

1. Download the latest release from https://github.com/calcinai/hass-control4-amplifier
2. Copy the `control4_amplifier` folder to your `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Go to Settings -> Devices & Services
2. Click "Add Integration"
3. Search for "Control4 Amplifier"
4. Follow the configuration steps

## Entities Created

For each amplifier:

### Media Players
- One master media player entity
- Four output media player entities (one per output)

### Number Entities
- Input Gains (4 entities, one per physical input)
- Output Controls (per output):
    - Balance
    - Bass
    - Treble

## Usage

### Media Player Controls
- Power on/off
- Volume control
- Source selection

### Audio Controls
All audio controls are exposed as number entities with a range of -12 to +12:
- Input Gain: Adjusts the gain for each physical input
- Balance: Adjusts left/right balance for each output
- Bass: Controls bass level for each output
- Treble: Controls treble level for each output

## Input Mapping

The integration maps 6 logical inputs to 4 physical inputs:
- Logical Input 1: Analog Input 1
- Logical Input 2: Analog Input 2
- Logical Input 3: Analog Input 3
- Logical Input 4: Analog Input 4
- Logical Input 5: Digital Input 1 (shares physical input with Analog 1)
- Logical Input 6: Digital Input 3 (shares physical input with Analog 3)

## Troubleshooting

### Common Issues
1. Connection Issues
    - Verify the amplifier is powered on
    - Check network connectivity
    - Verify IP address and port settings

2. Control Issues
    - Ensure the amplifier is not in standby mode
    - Check that the selected input is properly connected
    - Verify volume settings are not at minimum

### Debug Logging

To enable debug logging, add the following to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.control4_amplifier: debug