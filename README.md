# 2Park - Home Assistant Integration

Custom Home Assistant integration for [2Park](https://mijn.2park.nl), the municipal parking permit management system used by the city of Breda, Netherlands.

## Features

- **Balance tracking** — monitor your visitor parking credit (EUR) as a sensor
- **Parking status** — see which license plates are currently parked and how many active sessions you have
- **Start/stop parking** — register and end visitor parking sessions directly from Home Assistant
- **License plate picker** — select from your saved favorites to quickly start parking
- **Per-member sensors** — individual sensors for each favorite license plate showing parked/not parked status with parking times and estimated cost
- **Configurable polling** — adjust the refresh interval or trigger a manual refresh

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS
2. Search for "2Park" and install
3. Restart Home Assistant
4. Go to **Settings > Devices & Services > Add Integration > 2Park**
5. Enter your mijn.2park.nl email and password

### Manual

1. Copy the `custom_components/2park` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Add the integration via **Settings > Devices & Services**

## Entities

| Entity | Type | Description |
|--------|------|-------------|
| Balance | Sensor | Current visitor parking credit in EUR |
| Active parking | Sensor | Number of currently active parking sessions |
| Member (per plate) | Sensor | Parking status per favorite license plate |
| License plate | Select | Pick a license plate from your favorites |
| Refresh | Button | Force a data refresh from 2Park |
| Refresh interval | Number | Polling interval in minutes (1–60) |

## Services

### `2park.start_parking`

Start a visitor parking session.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `product_id` | Yes | Your 2Park visitor product ID |
| `license_plate` | No | License plate to park (falls back to select entity) |
| `time_end` | Yes | End time — accepts `HH:MM` (today) or `dd-MM-yyyy HH:mm:ss` |

### `2park.stop_parking`

Stop an active visitor parking session.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `product_id` | Yes | Your 2Park visitor product ID |
| `license_plate` | Yes | License plate of the session to stop |

## Disclaimer

**This integration is in beta and provided as-is. Use at your own risk.**

This is an unofficial, community-built integration. It is not affiliated with, endorsed by, or supported by 2Park or the municipality of Breda. The integration relies on a reverse-engineered API that may change without notice, potentially causing the integration to break. The authors are not responsible for any issues, incorrect parking registrations, unexpected charges, or other problems arising from the use of this integration.
