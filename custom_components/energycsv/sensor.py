import csv
import statistics
import os
from datetime import datetime, timedelta, timezone
import logging

from .const import DOMAIN, CONF_FOLDER_PATHS
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_FILENAME,
    UnitOfEnergy,
)
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.util import dt as dtutil

from homeassistant.components.sensor import ENTITY_ID_FORMAT

from homeassistant_historical_sensor import (
    HistoricalSensor,
    HistoricalState,
    PollUpdateMixin,
)


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,  # noqa DiscoveryInfoType | None
) -> None:
    """Set up the energy sensors."""
    _LOGGER.info(config_entry)
    _LOGGER.info(config_entry.data)

    # Fetch metering_points
    # metering_points = energiinfo_client.get_metering_points()
    # if not metering_points:
    #    _LOGGER.error("Failed to fetch metering points")
    #    return

    # metering_points = energiinfo_client.get_metering_points()
    # if not metering_points:
    #    _LOGGER.error("Failed to fetch metering points")
    #    return

    # Add the meter received
    entities = []
    entities.append(
        CsvHistorySensor(
            config_entry.title, config_entry.data[CONF_FILENAME], config_entry
        )
    )

    async_add_entities(entities)


class CsvHistorySensor(PollUpdateMixin, HistoricalSensor, SensorEntity):
    """Representation of an energy sensor."""

    #
    # Base clases:
    # - SensorEntity: This is a sensor, obvious
    # - HistoricalSensor: This sensor implements historical sensor methods
    # - PollUpdateMixin: Historical sensors disable poll, this mixing
    #                    reenables poll only for historical states and not for
    #                    present state
    #
    UPDATE_INTERVAL: timedelta = timedelta(hours=2)

    def __init__(
        self,
        meterid: str,
        filename: str,
        config_entry: ConfigEntry,
    ):
        """Initialize the CsvHistorySensor."""
        self._unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._filename = filename
        self._meterid = meterid
        self._config_entry = config_entry

        # A unique_id for this entity with in this domain. This means for example if you
        # have a sensor on this cover, you must ensure the value returned is unique,
        # which is done here by appending "_cover". For more information, see:
        # https://developers.home-assistant.io/docs/entity_registry_index/#unique-id-requirements
        # Note: This is NOT used to generate the user visible Entity ID used in automations.
        self._attr_unique_id = f"{self._meterid}_energy"

        # This is the name for this *entity*, the "name" attribute from "device_info"
        # is used as the device name for device screens in the UI. This name is used on
        # entity screens, and used to build the Entity ID that's used is automations etc.
        self._attr_has_entity_name = True
        self._attr_name = f"{self._meterid}"
        self._attr_entity_id = f"sensor.{DOMAIN}_{self._meterid}"

        self._attr_entity_registry_enabled_default = True
        self._attr_state = None

    # async def async_added_to_hass(self) -> None:
    #     """Run when this Entity has been added to HA."""
    #     # Importantly for a push integration, the module that will be getting updates
    #     # needs to notify HA of changes. The dummy device has a registercallback
    #     # method, so to this we add the 'self.async_write_ha_state' method, to be
    #     # called where ever there are changes.
    #     # The call back registration is done once this entity is registered with HA
    #     # (rather than in the __init__)
    #     _LOGGER.info(f"Added {self._attr_name}:{self._attr_unique_id}")
    #     self._energiinfo_client.register_callback(self.async_write_ha_state)

    # async def async_will_remove_from_hass(self) -> None:
    #     """Entity being removed from hass."""
    #     # The opposite of async_added_to_hass. Remove any registered call backs here.
    #     _LOGGER.info(f"Removed {self._attr_name}:{self._attr_unique_id}")
    #     self._roller.remove_callback(self.async_write_ha_state)

    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will refelect this.
    @property
    def available(self) -> bool:
        """Return True if api and hub is available."""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._attr_name} Energy Usage"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def statistic_id(self) -> str:
        return self.entity_id

    async def async_update_historical(self):
        # Fill `HistoricalSensor._attr_historical_states` with HistoricalState's
        # This functions is equivaled to the `Sensor.async_update` from
        # HomeAssistant core
        #
        # Important: You must provide datetime with tzinfo
        hist_states = []
        # Check if file exist
        if os.path.exists(self._filename):
            with open(self._filename, "r", encoding="utf-8-sig", newline="") as csvfile:
                reader = csv.DictReader(csvfile, delimiter=";")
                for row in reader:
                    # Access data from each row
                    anlid = row["Anlid"]
                    datum_str = row["Datum"]
                    value = float(row["Förbrukn"].replace(",", "."))
                    enhet = row["Enhet"]

                    # Convert datum_str to datetime with timezone information
                    # Here, you may need to replace 'Europe/Stockholm' with your actual timezone
                    datum = dtutil.as_local(
                        datetime.strptime(datum_str, "%Y-%m-%d %H:%M:%S")
                    )
                    # _LOGGER.debug(
                    #    "Time: %s Value: %s", datum, row["Förbrukn"].replace(",", ".")
                    # )
                    # Create a HistoricalState object and append it to hist_states
                    hist_states.append(HistoricalState(state=value, dt=datum))
            # Remove file once completed
            os.remove(self._filename)
        else:
            _LOGGER.info(
                f"File {self._filename} does not exist. Most likely already consumed"
            )
        self._attr_historical_states = hist_states

    async def async_calculate_statistic_data(
        self, hist_states: list[HistoricalState], *, latest: dict | None = None
    ) -> list[StatisticData]:
        #
        # Group historical states by hour
        # Calculate sum, mean, etc...
        #
        accumulated = latest["sum"] if latest else 0
        _LOGGER.info(f"Calculating statistics data")

        ret = []
        for hist in hist_states:
            mean = hist.state
            partial_sum = hist.state
            accumulated = accumulated + partial_sum

            ret.append(
                StatisticData(
                    start=hist.dt,
                    state=partial_sum,
                    mean=mean,
                    sum=accumulated,
                )
            )

        return ret

    def get_statistic_metadata(self) -> StatisticMetaData:
        #
        # Add sum and mean to base statistics metadata
        # Important: HistoricalSensor.get_statistic_metadata returns an
        # internal source by default.
        #
        meta = super().get_statistic_metadata()
        meta["has_sum"] = True
        # meta["has_mean"] = True
        return meta
