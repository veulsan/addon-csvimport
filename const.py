"""Constants for the energycsvimport integration."""
import logging
from homeassistant.const import Platform

DOMAIN = "energycsv"
PLATFORMS = [Platform.SENSOR]
LOGGER = logging.getLogger(__package__)

CONF_FOLDER_PATHS = "folder"
