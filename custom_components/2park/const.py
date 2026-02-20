"""Constants for the 2Park integration."""

from homeassistant.const import Platform

DOMAIN = "2park"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_PRODUCTS = "products"
CONF_REFRESH_INTERVAL = "refresh_interval"

DEFAULT_REFRESH_INTERVAL = 5  # minutes

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT, Platform.BUTTON, Platform.NUMBER]
