"""DataUpdateCoordinator for 2Park."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, ConnectionError, TwoParkApi
from .const import CONF_EMAIL, CONF_PASSWORD, CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TwoParkCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Coordinator that polls balance and product details for all products."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: TwoParkApi,
        products: list[dict],
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        interval_minutes = entry.options.get(
            CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=interval_minutes),
            config_entry=entry,
        )
        self.api = api
        self.products = products

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch balance and product details for each product."""
        data: dict[str, dict] = {}

        for product in self.products:
            pdt_id = product["pdt_id"]
            try:
                balance_resp = await self.api.get_balance(pdt_id)
                details = await self.api.get_product_details(pdt_id)
            except AuthenticationError:
                # Session expired — try to re-authenticate once
                try:
                    await self.api.authenticate(
                        self.config_entry.data[CONF_EMAIL],
                        self.config_entry.data[CONF_PASSWORD],
                    )
                    balance_resp = await self.api.get_balance(pdt_id)
                    details = await self.api.get_product_details(pdt_id)
                except AuthenticationError as auth_err:
                    raise ConfigEntryAuthFailed from auth_err
                except ConnectionError as conn_err:
                    raise UpdateFailed(
                        f"Error communicating with 2Park: {conn_err}"
                    ) from conn_err
            except ConnectionError as err:
                raise UpdateFailed(
                    f"Error communicating with 2Park: {err}"
                ) from err

            pdt_options = product.get("pdt_options", "")

            if "FLPN" in pdt_options:
                # Resident permits: FLPN members from pdt_identifications
                members = _extract_flpn_members(details)
            else:
                # Visitor schemes: LPN members from pdt_members
                members = [
                    m for m in details.get("pdt_members", [])
                    if m.get("mbr_type") == "LPN"
                ]

            data[pdt_id] = {
                "balance": _extract_balance(balance_resp),
                "currency_code": _extract_param(balance_resp, "CURRENCY_CODE"),
                "currency_desc": _extract_param(balance_resp, "CURRENCY_DESC"),
                "pdt_name": product["pdt_name"],
                "pdt_options": pdt_options,
                "pdt_location": product.get("pdt_location"),
                "members": [
                    {
                        "mbr_id": m["mbr_id"],
                        "mbr_identifier": m["mbr_identifier"],
                        "mbr_type": m.get("mbr_type"),
                        "mbr_active": m.get("mbr_active"),
                        "nickname": _extract_member_nickname(m),
                        "actions": m.get("mbr_actions", []),
                    }
                    for m in members
                ],
            }

        return data


def _extract_balance(balance: dict) -> float | None:
    """Extract the AMOUNT value from a balance response as a float."""
    for param in balance.get("ble_parameters", []):
        if param.get("prr_label") == "AMOUNT":
            try:
                return float(param["prr_value"])
            except (ValueError, KeyError):
                return None
    return None


def _extract_param(balance: dict, label: str) -> str | None:
    """Extract a parameter value from a balance response by label."""
    for param in balance.get("ble_parameters", []):
        if param.get("prr_label") == label:
            return param.get("prr_value")
    return None


def _extract_flpn_members(details: dict) -> list[dict]:
    """Extract FLPN members from pdt_identifications."""
    seen: set[str] = set()
    members: list[dict] = []
    for identification in details.get("pdt_identifications", []):
        for m in identification.get("idn_members", []):
            if m.get("mbr_type") == "FLPN" and m["mbr_id"] not in seen:
                seen.add(m["mbr_id"])
                members.append(m)
    return members


def _extract_member_nickname(member: dict) -> str | None:
    """Extract the NICKNAME from a member's parameters."""
    for param in member.get("mbr_parameters", []):
        if param.get("prr_label") == "NICKNAME":
            return param.get("prr_value")
    return None
