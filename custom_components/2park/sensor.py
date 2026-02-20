"""Sensor platform for 2Park."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
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
    """Set up 2Park sensors from a config entry."""
    coordinator: TwoParkCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[SensorEntity] = []

    for pdt_id, product_data in coordinator.data.items():
        # Balance sensor per product
        entities.append(TwoParkBalanceSensor(coordinator, entry, pdt_id))

        # Active parking count sensor per product
        entities.append(TwoParkActiveParkingSensor(coordinator, entry, pdt_id))

        # Per-member sensor for each favorite
        for member in product_data.get("members", []):
            entities.append(
                TwoParkMemberSensor(coordinator, entry, pdt_id, member)
            )

    async_add_entities(entities)

    # Listen for coordinator updates to add new member sensors dynamically
    known_members: dict[str, set[str]] = {
        pdt_id: {m["mbr_id"] for m in pd.get("members", [])}
        for pdt_id, pd in coordinator.data.items()
    }

    @callback
    def _async_check_new_members() -> None:
        """Check for new members and add sensors for them."""
        new_entities: list[SensorEntity] = []

        for pdt_id, product_data in coordinator.data.items():
            if pdt_id not in known_members:
                known_members[pdt_id] = set()

            for member in product_data.get("members", []):
                mbr_id = member["mbr_id"]
                if mbr_id not in known_members[pdt_id]:
                    known_members[pdt_id].add(mbr_id)
                    new_entities.append(
                        TwoParkMemberSensor(coordinator, entry, pdt_id, member)
                    )

        if new_entities:
            async_add_entities(new_entities)

    coordinator.async_add_listener(_async_check_new_members)


class TwoParkBalanceSensor(CoordinatorEntity[TwoParkCoordinator], SensorEntity):
    """Sensor showing the balance for a 2Park product."""

    _attr_state_class = SensorStateClass.TOTAL
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TwoParkCoordinator,
        entry: ConfigEntry,
        pdt_id: str,
    ) -> None:
        """Initialize the balance sensor."""
        super().__init__(coordinator)
        self._pdt_id = pdt_id
        product_data = coordinator.data[pdt_id]
        pdt_name = product_data["pdt_name"]
        currency_code = product_data.get("currency_code")

        if currency_code == "TIMES":
            self._attr_device_class = None
            self._attr_native_unit_of_measurement = "times"
            self._attr_icon = "mdi:counter"
        else:
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_native_unit_of_measurement = "EUR"

        self._attr_unique_id = f"{entry.entry_id}_{pdt_id}_balance"
        self._attr_name = f"{pdt_name} balance"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "2Park",
            "manufacturer": "2Park",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> float | None:
        """Return the current balance."""
        if self.coordinator.data and self._pdt_id in self.coordinator.data:
            return self.coordinator.data[self._pdt_id]["balance"]
        return None


class TwoParkActiveParkingSensor(CoordinatorEntity[TwoParkCoordinator], SensorEntity):
    """Sensor showing the number of active parking sessions for a product."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:car-multiple"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: TwoParkCoordinator,
        entry: ConfigEntry,
        pdt_id: str,
    ) -> None:
        """Initialize the active parking sensor."""
        super().__init__(coordinator)
        self._pdt_id = pdt_id
        pdt_name = coordinator.data[pdt_id]["pdt_name"]

        self._attr_unique_id = f"{entry.entry_id}_{pdt_id}_active_parking"
        self._attr_name = f"{pdt_name} active parking"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "2Park",
            "manufacturer": "2Park",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> int:
        """Return the number of currently active members."""
        if self.coordinator.data and self._pdt_id in self.coordinator.data:
            members = self.coordinator.data[self._pdt_id].get("members", [])
            return sum(1 for m in members if m.get("mbr_active") == "YES")
        return 0

    @property
    def extra_state_attributes(self) -> dict:
        """Return the full member list as attributes."""
        if not self.coordinator.data or self._pdt_id not in self.coordinator.data:
            return {}
        members = self.coordinator.data[self._pdt_id].get("members", [])
        return {
            "members": [
                {
                    "license_plate": m["mbr_identifier"],
                    "nickname": m.get("nickname"),
                    "active": m.get("mbr_active") == "YES",
                    **_extract_action_attrs(m),
                }
                for m in members
            ],
        }


class TwoParkMemberSensor(CoordinatorEntity[TwoParkCoordinator], SensorEntity):
    """Sensor tracking parking status of a single favorite license plate."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TwoParkCoordinator,
        entry: ConfigEntry,
        pdt_id: str,
        member: dict,
    ) -> None:
        """Initialize the member sensor."""
        super().__init__(coordinator)
        self._pdt_id = pdt_id
        self._mbr_id = member["mbr_id"]
        plate = member["mbr_identifier"]
        pdt_name = coordinator.data[pdt_id]["pdt_name"]

        self._attr_unique_id = f"{entry.entry_id}_{pdt_id}_{plate}_member"
        self._attr_name = f"{pdt_name} {plate}"
        self._attr_icon = "mdi:car"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "2Park",
            "manufacturer": "2Park",
            "entry_type": "service",
        }

    def _get_member(self) -> dict | None:
        """Find this member in coordinator data."""
        if not self.coordinator.data or self._pdt_id not in self.coordinator.data:
            return None
        for m in self.coordinator.data[self._pdt_id].get("members", []):
            if m["mbr_id"] == self._mbr_id:
                return m
        return None

    @property
    def native_value(self) -> str:
        """Return parked/not_parked."""
        member = self._get_member()
        if member and member.get("mbr_active") == "YES":
            return "parked"
        return "not_parked"

    @property
    def extra_state_attributes(self) -> dict:
        """Return plate, nickname, and active action details."""
        member = self._get_member()
        if not member:
            return {}
        attrs = {
            "license_plate": member["mbr_identifier"],
            "nickname": member.get("nickname"),
        }
        attrs.update(_extract_action_attrs(member))
        return attrs


def _extract_action_attrs(member: dict) -> dict:
    """Extract parking action attributes from a member's active actions."""
    actions = member.get("actions", [])
    if not actions:
        return {}
    action = actions[0]
    attrs: dict = {}
    for param in action.get("atn_parameters", []):
        label = param.get("prr_label")
        value = param.get("prr_value")
        if label == "TIMESTART":
            attrs["parking_start"] = value
        elif label == "TIMEEND":
            attrs["parking_end"] = value
        elif label == "AMOUNT":
            attrs["estimated_cost"] = value
    if "atn_id" in action:
        attrs["action_id"] = action["atn_id"]
    return attrs
