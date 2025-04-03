import glob
import platform
import time

from server.db.supabase_client import SupabaseClientManager
from server.sensors.ds18b20.models import TemperatureReading
from shared.logger_setup import get_logger

logger = get_logger(__name__)

# Initialize the Supabase client
supabase = SupabaseClientManager().get_client()


def _locate_ds18b20_device() -> str | None:
    # Locate the DS18B20 sensor device file
    base_dir = "/sys/bus/w1/devices/"
    try:
        device_folder = glob.glob(base_dir + "28*")[0]
        device_file = device_folder + "/w1_slave"
        return device_file
    except IndexError:
        logger.error("No DS18B20 device found")
        return None


def _read_temp_raw() -> list[str]:
    """Read raw data from the sensor's w1_slave file."""
    device_file = _locate_ds18b20_device()
    if device_file is None:
        raise Exception("Temperature sensor not found")
    with open(device_file, "r") as f:
        lines = f.readlines()
    return lines


def read_temp() -> tuple[float, float]:
    """Process raw data to extract temperature in Celsius and Fahrenheit."""

    lines = _read_temp_raw()
    while lines[0].strip()[-3:] != "YES":  # Wait for a valid reading
        time.sleep(0.2)
        lines = _read_temp_raw()
    equals_pos = lines[1].find("t=")
    if equals_pos != -1:
        temp_string = lines[1][equals_pos + 2 :]
        temp_c = float(temp_string) / 1000.0
        temp_f = temp_c * 9.0 / 5.0 + 32.0
        logger.info(f"Temperature: {temp_c:.2f}°C / {temp_f:.2f}°F")
        return round(temp_c, 2), round(temp_f, 2)
    else:
        logger.error("Invalid temperature data")
        raise Exception("Invalid temperature data")


def store_temperature(temp_c: float, temp_f: float) -> TemperatureReading | None:
    """Store the temperature data in Supabase and verify the insertion."""
    try:
        data = {"celsius": temp_c, "fahrenheit": temp_f}
        response = supabase.table("temperature_readings").insert(data).execute()
        if hasattr(response, "data") and len(response.data) > 0:
            inserted_data = response.data[0]
            validated_data = TemperatureReading(**inserted_data)
            if (
                abs(validated_data.celsius - temp_c) < 0.01
                and abs(validated_data.fahrenheit - temp_f) < 0.01
            ):
                logger.info(
                    f"Stored and verified temperature in Supabase: {validated_data.model_dump()}"
                )
                return validated_data
            else:
                logger.error(
                    f"Data verification failed. Expected ({temp_c}, {temp_f}), "
                    f"got ({validated_data.celsius}, {validated_data.fahrenheit})"
                )
                return None
        else:
            logger.error("Failed to insert temperature data: No data returned")
            return None
    except Exception as e:
        logger.error(f"Failed to store temperature in Supabase: {e}")
        return None
