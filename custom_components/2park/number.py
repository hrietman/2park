"""Number platform for 2Park — refresh interval."""

from datetime import timedelta

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_REFRESH_INTERVAL, DOMAIN
from .coordinator import TwoParkCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 2Park number entities from a config entry."""
    coordinator: TwoParkCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([TwoParkRefreshIntervalNumber(coordinator, entry)])


class TwoParkRefreshIntervalNumber(NumberEntity):
    """Number entity to configure the polling interval."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:timer-cog-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 60
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "min"

    def __init__(
        self,
        coordinator: TwoParkCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the refresh interval number."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_refresh_interval"
        self._attr_name = "2Park refresh interval"
        self._attr_native_value = float(
            coordinator.update_interval.total_seconds() / 60
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "2Park",
            "manufacturer": "2Park",
            "entry_type": "service",
        }

    async def async_set_native_value(self, value: float) -> None:
        """Update the polling interval."""
        self._attr_native_value = value
        self._coordinator.update_interval = timedelta(minutes=int(value))
        self.async_write_ha_state()
