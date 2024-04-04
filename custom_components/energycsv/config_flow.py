"""Config flow for energycsvimport integration."""
from __future__ import annotations

import glob
import logging
from typing import Any
import os
import csv


import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_FILENAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_FOLDER_PATHS

_LOGGER = logging.getLogger(__name__)

# Data schemas
STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_FOLDER_PATHS): str})
STEP_CHOOSEFILE_SCHEMA = vol.Schema({vol.Required(CONF_FILENAME): str})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    # Validate that folder Exists and contain CSV files
    # Normalize the path
    folder_path = os.path.abspath(data[CONF_FOLDER_PATHS])
    # Add a trailing slash if it's missing
    if not folder_path.endswith("/"):
        folder_path += "/"

    # Check if the folder exists
    if not os.path.exists(folder_path):
        _LOGGER.error(f"Folder '%s' does not exist.", folder_path)
        raise FileExistsError

    # Check if the folder contains any CSV files
    csv_files = glob.glob(os.path.join(folder_path, "*.csv"))
    if not csv_files:
        _LOGGER.error(f"Folder '%s' does not contain any CSV files.", folder_path)
        raise FileNotFoundError

    return True


class CsvImportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for energycsvimport."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1
    # MINOR_VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        _LOGGER.info("__init__")

    def get_files_list(self, folder_path, filter_term, sort, recursive):
        """Return the list of files, applying filter."""
        # Normalize the path
        folder_path += "/"
        folder_path = os.path.abspath(folder_path)
        if not folder_path.endswith("/"):
            folder_path += "/"

        query = folder_path + filter_term
        _LOGGER.info("get_files_list: %s", query)
        """files_list = glob.glob(query)"""
        if sort == "name":
            files_list = sorted(glob.glob(query, recursive=recursive))
        elif sort == "size":
            files_list = sorted(
                glob.glob(query, recursive=recursive), key=os.path.getsize
            )
        else:
            files_list = sorted(
                glob.glob(query, recursive=recursive), key=os.path.getmtime
            )
        return files_list

    def get_meterid(self, filename):
        """Return the first entry of file"""
        try:
            with open(filename, "r", encoding="utf-8-sig", newline="") as csvfile:
                reader = csv.DictReader(csvfile, delimiter=";")
                # Skip the header row
                row = next(reader)
                if row:
                    anlid = row["Anlid"]
                    return anlid
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
        return {}  # Return an empty dictionary if no row is found

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        _LOGGER.info("async_step_user")
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                _LOGGER.info("Will validate input")
                info = await validate_input(self.hass, user_input)
                if info:
                    self.folder_path = user_input[CONF_FOLDER_PATHS]
            except FileExistsError:
                errors[
                    "base"
                ] = f"Folder '{user_input[CONF_FOLDER_PATHS]}' does not exist"
            except FileNotFoundError:
                errors[
                    "base"
                ] = f"No CSV files found in '{user_input[CONF_FOLDER_PATHS]}'"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "Unknown error occured. See log"
            else:
                # Return the form of the next step.
                return await self.async_step_choosefile()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_choosefile(self, user_input: Dict[str, Any] = None):
        errors: dict[str, str] = {}
        if user_input is None:
            # If user_input is None, show the form to choose a file
            file_list = self.get_files_list(self.folder_path, "*.csv", "name", False)
            _LOGGER.debug("Files found in '%s': %s", self.folder_path, file_list)
            if not file_list:
                return self.async_abort(reason="no_files_found")

            return self.async_show_form(
                step_id="choosefile",
                data_schema=vol.Schema(
                    {
                        vol.Required("filename", description="Select a file"): vol.In(
                            file_list
                        )
                    }
                ),
                errors=errors,
            )
        else:
            # User has selected a file, finish the flow
            filepath = user_input["filename"]
            meter_id = self.get_meterid(filepath)

            if not meter_id:
                _LOGGER.error(f"No meter id found in csv file '{filepath}'")
                errors["base"] = f"No meter id found in csv file '{filepath}'"
                return self.async_show_form(
                    step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
                )
            else:
                # Use correct key to access selected filename
                _LOGGER.info("Create entry for %s", meter_id)
                # Now you can create an entry using the selected file path
                # For example:
                return self.async_create_entry(
                    title=meter_id,
                    data={
                        CONF_FILENAME: filepath,
                        # Add other data as needed
                    },
                )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
