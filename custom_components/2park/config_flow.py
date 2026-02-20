"""Config flow for 2Park integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .api import AuthenticationError, ConnectionError, TwoParkApi
from .const import CONF_EMAIL, CONF_PASSWORD, CONF_PRODUCTS, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class TwoParkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for 2Park."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api = TwoParkApi()
            try:
                await api.authenticate(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
                products = await api.get_categories()
            except AuthenticationError:
                _LOGGER.warning("Authentication failed for %s", user_input[CONF_EMAIL])
                errors["base"] = "invalid_auth"
            except ConnectionError:
                _LOGGER.error("Cannot connect to 2Park API")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during 2Park login")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_PRODUCTS: products,
                    },
                )
            finally:
                await api.close()

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )
