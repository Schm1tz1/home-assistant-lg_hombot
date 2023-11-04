import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from .const import DOMAIN

class HombotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Hombot configuration flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """User config step."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_HOST],
                data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, description="IP Address"): str}
            )
        )

