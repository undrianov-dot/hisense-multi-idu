# Hisense Multi-IDU Climate for Home Assistant

Custom integration for Hisense Multi-IDU air conditioning systems.

## Features
- Control 16 indoor units (2 systems x 8 addresses)
- Temperature control (16-30°C)
- HVAC modes: Cool, Dry, Fan Only, Heat, Off
- Fan speeds: High, Medium, Low
- Real-time status updates

## Installation

### Via HACS
1. Add this repository as a custom repository in HACS
2. Search for "Hisense Multi-IDU Climate"
3. Install the integration
4. Restart Home Assistant

### Manual Installation
1. Copy the `hisense_multi_idu` folder to `custom_components/` in your Home Assistant config directory
2. Restart Home Assistant

## Configuration

Add to your `configuration.yaml`:

```yaml
hisense_multi_idu:
  host: "10.99.3.100"
  scan_interval: 10