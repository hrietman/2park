"""The 2Park integration."""

import logging
from datetime import datetime

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import entity_registry as er

from .api import TwoParkApi, TwoParkApiError
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN, PLATFORMS
from .coordinator import TwoParkCoordinator
from .select import extract_plate

_LOGGER = logging.getLogger(__name__)

SERVICE_START_PARKING = "start_parking"
SERVICE_STOP_PARKING = "stop_parking"

START_PARKING_SCHEMA = vol.Schema(
    {
        vol.Required("product_id"): cv.string,
        vol.Optional("license_plate"): cv.string,
        vol.Required("time_end"): cv.string,
    }
)

STOP_PARKING_SCHEMA = vol.Schema(
    {
        vol.Required("product_id"): cv.string,
        vol.Required("license_plate"): cv.string,
    }
)


def _normalize_time_end(time_end: str) -> str:
    """Normalize time_end: accept HH:MM shorthand or full datetime."""
    time_end = time_end.strip()
    # If it looks like HH:MM, expand to full datetime today
    if len(time_end) <= 5 and ":" in time_end:
        today = datetime.now().strftime("%d-%m-%Y")
        return f"{today} {time_end}:59"
    return time_end


def _find_select_entity_plate(hass: HomeAssistant, product_id: str) -> str | None:
    """Find the currently selected plate from the select entity for a product."""
    states = hass.states
    for state in states.async_all("select"):
        if (
            state.entity_id.startswith("select.2park_")
            and state.entity_id.endswith("_license_plate")
            and state.state not in (None, "", "unknown")
        ):
            # Check if this select entity belongs to the right product
            # by looking up its unique_id via the entity registry
            registry = er.async_get(hass)
            entry = registry.async_get(state.entity_id)
            if entry and product_id in (entry.unique_id or ""):
                return state.state
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up 2Park from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api = TwoParkApi()
    try:
        await api.authenticate(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    except Exception:
        await api.close()
        _LOGGER.error("Failed to authenticate with 2Park")
        return False

    # Fetch products from the API
    try:
        products = await api.get_categories()
    except Exception:
        await api.close()
        _LOGGER.error("Failed to fetch 2Park categories")
        return False

    _LOGGER.debug("Discovered %d products", len(products))

    # Create coordinator and do initial refresh
    coordinator = TwoParkCoordinator(hass, api, products, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "products": products,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (once per domain, not per entry)
    if not hass.services.has_service(DOMAIN, SERVICE_START_PARKING):
        _register_services(hass)

    return True


def _get_entry_data(hass: HomeAssistant, product_id: str) -> tuple[TwoParkApi, TwoParkCoordinator, dict]:
    """Find the config entry data that owns the given product_id."""
    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        coordinator: TwoParkCoordinator = data["coordinator"]
        if product_id in coordinator.data:
            return data["api"], coordinator, coordinator.data[product_id]
    raise HomeAssistantError(f"Product {product_id} not found")


def _register_services(hass: HomeAssistant) -> None:
    """Register 2Park services."""

    async def handle_start_parking(call: ServiceCall) -> None:
        """Handle the start_parking service call."""
        product_id = call.data["product_id"]
        license_plate = call.data.get("license_plate")
        time_end = _normalize_time_end(call.data["time_end"])

        api, coordinator, product_data = _get_entry_data(hass, product_id)

        # Fall back to select entity if no plate provided
        if not license_plate:
            selected = _find_select_entity_plate(hass, product_id)
            if selected:
                license_plate = extract_plate(selected)
        if not license_plate:
            raise HomeAssistantError(
                "No license plate provided and no plate selected in the select entity"
            )

        location = product_data.get("pdt_location")
        if not location:
            raise HomeAssistantError(
                f"No location found for product {product_id}"
            )

        try:
            await api.start_action(
                product_id=product_id,
                license_plate=license_plate,
                time_end=time_end,
                location=location,
            )
        except TwoParkApiError as err:
            raise HomeAssistantError(str(err)) from err

        await coordinator.async_request_refresh()

    async def handle_stop_parking(call: ServiceCall) -> None:
        """Handle the stop_parking service call."""
        product_id = call.data["product_id"]
        license_plate = call.data["license_plate"].upper()

        api, coordinator, product_data = _get_entry_data(hass, product_id)

        # Find the action_id for the active member matching the plate
        action_id = None
        for member in product_data.get("members", []):
            if (
                member["mbr_identifier"].upper() == license_plate
                and member.get("mbr_active") == "YES"
            ):
                for action in member.get("actions", []):
                    if "atn_id" in action:
                        action_id = action["atn_id"]
                        break
                break

        if not action_id:
            raise HomeAssistantError(
                f"No active parking session found for {license_plate}"
            )

        try:
            await api.stop_action(product_id=product_id, action_id=action_id)
        except TwoParkApiError as err:
            raise HomeAssistantError(str(err)) from err

        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN, SERVICE_START_PARKING, handle_start_parking, schema=START_PARKING_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_PARKING, handle_stop_parking, schema=STOP_PARKING_SCHEMA
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data and "api" in data:
            await data["api"].close()

        # Remove services if no more entries
        if not hass.data.get(DOMAIN):
            hass.services.async_remove(DOMAIN, SERVICE_START_PARKING)
            hass.services.async_remove(DOMAIN, SERVICE_STOP_PARKING)

    return unload_ok
