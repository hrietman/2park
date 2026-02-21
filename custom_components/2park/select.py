"""Select platform for 2Park — license plate picker."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TwoParkCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 2Park select entities from a config entry."""
    coordinator: TwoParkCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[SelectEntity] = []

    for pdt_id, product_data in coordinator.data.items():
        pdt_options = product_data.get("pdt_options", "")
        # Only create select for visitor products (no FLPN)
        if "FLPN" in pdt_options:
            continue
        entities.append(TwoParkLicensePlateSelect(coordinator, entry, pdt_id))

    async_add_entities(entities)


class TwoParkLicensePlateSelect(
    CoordinatorEntity[TwoParkCoordinator], SelectEntity
):
    """Select entity for picking a visitor license plate."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:car"

    def __init__(
        self,
        coordinator: TwoParkCoordinator,
        entry: ConfigEntry,
        pdt_id: str,
    ) -> None:
        """Initialize the license plate select."""
        super().__init__(coordinator)
        self._pdt_id = pdt_id
        pdt_name = coordinator.data[pdt_id]["pdt_name"]

        self._attr_unique_id = f"{entry.entry_id}_{pdt_id}_license_plate"
        self._attr_name = f"{pdt_name} license plate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "2Park",
            "manufacturer": "2Park",
            "entry_type": "service",
        }
        self._attr_current_option = None

    @property
    def options(self) -> list[str]:
        """Return available license plates from coordinator data."""
        if not self.coordinator.data or self._pdt_id not in self.coordinator.data:
            return []
        members = self.coordinator.data[self._pdt_id].get("members", [])
        return [_format_plate_option(m) for m in members]

    async def async_select_option(self, option: str) -> None:
        """Store the selected license plate locally."""
        self._attr_current_option = option
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Reset selection if the plate was removed."""
        if self._attr_current_option and self._attr_current_option not in self.options:
            self._attr_current_option = None
        super()._handle_coordinator_update()


def _format_plate_option(member: dict) -> str:
    """Format a member as 'PLATE (nickname)' or just 'PLATE'."""
    plate = member["mbr_identifier"]
    nickname = member.get("nickname")
    if nickname:
        return f"{plate} ({nickname})"
    return plate


def extract_plate(option: str) -> str:
    """Extract the license plate from a display option like 'HRL96K (Mats)'."""
    return option.split(" (")[0]
