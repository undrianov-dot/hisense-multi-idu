"""Power meter data fetcher for Hisense Multi-IDU."""
import asyncio
import json
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)


async def fetch_power_data(session: aiohttp.ClientSession, host: str) -> float | None:
    """Fetch power data from Hisense device using shared Home Assistant session."""
    url = f"http://{host}/cgi/get_meter_pwr.shtml"

    try:
        payload = {"ids": ["1", "2"], "ip": host}
        headers = {"Content-Type": "application/json", "User-Agent": "HomeAssistant"}

        async with session.post(
            url,
            json=payload,
            headers=headers,
            timeout=10,
        ) as response:
            if response.status != 200:
                _LOGGER.warning("Power meter returned status: %s", response.status)
                return None

            raw_bytes = await response.read()

            try:
                raw_text = raw_bytes.decode("ascii")
            except UnicodeDecodeError:
                raw_text = raw_bytes.decode("utf-8", errors="ignore")

            _LOGGER.debug("Raw response: %s", raw_text)

            if raw_text.strip() and all(c.isdigit() or c.isspace() for c in raw_text.strip()):
                try:
                    ascii_codes = [int(x) for x in raw_text.split()]
                    decoded_text = "".join(chr(code) for code in ascii_codes)
                    _LOGGER.debug("Decoded ASCII: %s", decoded_text)
                    raw_text = decoded_text
                except Exception as err:
                    _LOGGER.warning("Failed to decode ASCII: %s", err)

            try:
                data = json.loads(raw_text)

                if data.get("status") != "success":
                    _LOGGER.warning("Power meter API error: %s", data.get("status"))
                    return None

                for meter in data.get("dats", []):
                    if isinstance(meter, dict) and "pwr" in meter:
                        power_value = meter["pwr"]
                        try:
                            power = float(power_value)
                            if power >= 0:
                                _LOGGER.info("Found power value: %s W", power)
                                return power
                        except (ValueError, TypeError):
                            continue

                _LOGGER.warning("No valid power value found in response")
                return None

            except json.JSONDecodeError as err:
                _LOGGER.error("JSON decode error: %s. Text: %s", err, raw_text[:100])
                return None

    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout fetching power data")
        return None
    except Exception as err:
        _LOGGER.error("Error fetching power data: %s", err, exc_info=True)
        return None
