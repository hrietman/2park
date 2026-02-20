"""Button platform for 2Park — force refresh."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TwoParkCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 2Park button entities from a config entry."""
    coordinator: TwoParkCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([TwoParkRefreshButton(coordinator, entry)])


class TwoParkRefreshButton(ButtonEntity):
    """Button to force a data refresh from 2Park."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: TwoParkCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the refresh button."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_name = "2Park refresh"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "2Park",
            "manufacturer": "2Park",
            "entry_type": "service",
        }

    async def async_press(self) -> None:
        """Handle the button press — trigger a coordinator refresh."""
        await self._coordinator.async_request_refresh()
