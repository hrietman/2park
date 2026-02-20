"""API client for 2Park."""

import json
import logging
import re
from datetime import datetime

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://mijn.2park.nl"
API_PREFIX = "/gsmpark-app-www/json/"


class AuthenticationError(Exception):
    """Raised when authentication fails."""


class ConnectionError(Exception):
    """Raised when connection to 2Park fails."""


class TwoParkApiError(Exception):
    """Raised when the 2Park API returns a non-OK response."""


class TwoParkApi:
    """Client for the 2Park REST API."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize the API client."""
        self._session = session or aiohttp.ClientSession()
        self._owns_session = session is None

    def _url(self, endpoint: str) -> str:
        """Build a full URL for the given endpoint."""
        return f"{BASE_URL}{API_PREFIX}{endpoint}"

    async def authenticate(self, email: str, password: str) -> bool:
        """Authenticate with 2Park. Returns True on success."""
        try:
            resp = await self._session.post(
                self._url("check_credentials.json"),
                data={"email": email, "password": password, "locale": "nl_NL"},
            )
            result = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("Connection error during authentication: %s", err)
            raise ConnectionError(
                f"Cannot connect to 2Park: {err}"
            ) from err

        _LOGGER.debug("Auth response status: %s, body: %s", resp.status, result)

        major = result.get("status", {}).get("code", {}).get("major")
        if major != "OK":
            _LOGGER.warning("Authentication failed: %s", result.get("status"))
            raise AuthenticationError("Invalid credentials")

        return True

    async def get_categories(self) -> list[dict]:
        """Fetch categories and return a flat list of products."""
        try:
            resp = await self._session.post(
                self._url("get_categories.json"),
                data={"locale": "nl_NL"},
            )
            result = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ConnectionError(
                f"Cannot connect to 2Park: {err}"
            ) from err

        _LOGGER.debug("Categories response: %s", result)

        products = []
        for category in result.get("data", {}).get("categories", []):
            for product in category.get("cty_products", []):
                products.append(
                    {
                        "pdt_id": product["pdt_id"],
                        "pdt_name": product["pdt_name"],
                        "pdt_valid_from": product.get("pdt_valid_from"),
                        "pdt_valid_to": product.get("pdt_valid_to"),
                        "pdt_is_blocked": product.get("pdt_is_blocked"),
                        "pdt_options": product.get("pdt_options"),
                        "pdt_member_pool_max_active": product.get(
                            "pdt_member_pool_max_active"
                        ),
                        "pdt_location": _extract_location(product),
                    }
                )
        return products

    async def get_product_details(self, product_id: str) -> dict:
        """Fetch details for a specific product."""
        try:
            resp = await self._session.post(
                self._url("get_category_product_details.json"),
                data={"product_id": product_id, "locale": "nl_NL"},
            )
            result = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ConnectionError(
                f"Cannot connect to 2Park: {err}"
            ) from err

        return result.get("data", {})

    async def get_balance(self, product_id: str) -> dict:
        """Fetch the balance for a product."""
        try:
            resp = await self._session.post(
                self._url("get_balance.json"),
                data={"product_id": product_id, "locale": "nl_NL"},
            )
            result = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ConnectionError(
                f"Cannot connect to 2Park: {err}"
            ) from err

        return result.get("data", {}).get("balance", {})

    async def start_action(
        self,
        product_id: str,
        license_plate: str,
        time_end: str,
        location: str,
        time_start: str | None = None,
    ) -> dict:
        """Start a parking action. Returns the API response data."""
        if time_start is None:
            time_start = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

        action_data = {
            "action": {
                "atn_parameters": [
                    {"prr_label": "MBR_IDENT", "prr_value": license_plate},
                    {"prr_label": "TIMESTART", "prr_value": time_start},
                    {"prr_label": "TIMEEND", "prr_value": time_end},
                    {"prr_label": "LOCATION", "prr_value": location},
                ]
            }
        }

        try:
            resp = await self._session.post(
                self._url("start_action.json"),
                data={
                    "product_id": product_id,
                    "locale": "nl_NL",
                    "data": json.dumps(action_data),
                },
            )
            result = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ConnectionError(
                f"Cannot connect to 2Park: {err}"
            ) from err

        _LOGGER.debug("start_action response: %s", result)

        major = result.get("status", {}).get("code", {}).get("major")
        if major != "OK":
            message = result.get("status", {}).get("message", "Unknown error")
            raise TwoParkApiError(f"Failed to start parking: {message}")

        return result.get("data", {})

    async def stop_action(self, product_id: str, action_id: str) -> dict:
        """Stop a parking action."""
        try:
            resp = await self._session.post(
                self._url("stop_action.json"),
                data={
                    "action_id": action_id,
                    "product_id": product_id,
                    "locale": "nl_NL",
                },
            )
            result = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ConnectionError(
                f"Cannot connect to 2Park: {err}"
            ) from err

        _LOGGER.debug("stop_action response: %s", result)

        major = result.get("status", {}).get("code", {}).get("major")
        if major != "OK":
            message = result.get("status", {}).get("message", "Unknown error")
            raise TwoParkApiError(f"Failed to stop parking: {message}")

        return result.get("data", {})

    async def close(self) -> None:
        """Close the underlying session if we own it."""
        if self._owns_session:
            await self._session.close()


def _extract_location(product: dict) -> str | None:
    """Extract the LOCATION default value from a product's parameter groups."""
    for group in product.get("pdt_parameter_groups", []):
        for param in group.get("pgr_parameters", []):
            if param.get("prr_label") == "LOCATION":
                value = param.get("prr_value")
                if value:
                    return value
    # Fallback: derive from product_id (e.g. BDABZRG_1317$... -> BDA1317)
    pdt_id = product.get("pdt_id", "")
    match = re.match(r"^(BDA)\w+_(\d+)\$", pdt_id)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    return None
