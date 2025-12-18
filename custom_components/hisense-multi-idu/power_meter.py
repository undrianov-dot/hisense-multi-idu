"""Power meter data fetcher for Hisense Multi-IDU."""
import asyncio
import json
import logging
import aiohttp

_LOGGER = logging.getLogger(__name__)

async def fetch_power_data(host: str) -> float | None:
    """Fetch power data from Hisense device."""
    url = f"http://{host}/cgi/get_meter_pwr.shtml"
    
    try:
        # Создаем отдельную сессию для обхода проблем с MIME-type
        timeout = aiohttp.ClientTimeout(total=10)
        connector = aiohttp.TCPConnector(limit=1)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": "HomeAssistant"}
        ) as session:
            
            payload = {"ids": ["1", "2"], "ip": host}
            headers = {"Content-Type": "application/json"}
            
            async with session.post(
                url, 
                json=payload, 
                headers=headers
            ) as response:
                
                if response.status != 200:
                    _LOGGER.warning("Power meter returned status: %s", response.status)
                    return None
                
                # Читаем сырые байты
                raw_bytes = await response.read()
                
                # Преобразуем байты в строку (предполагаем ASCII)
                try:
                    raw_text = raw_bytes.decode('ascii')
                except UnicodeDecodeError:
                    # Попробуем UTF-8 на всякий случай
                    raw_text = raw_bytes.decode('utf-8', errors='ignore')
                
                _LOGGER.debug("Raw response: %s", raw_text)
                
                # Если ответ состоит из чисел, декодируем ASCII коды
                if raw_text.strip() and all(c.isdigit() or c.isspace() for c in raw_text.strip()):
                    try:
                        ascii_codes = [int(x) for x in raw_text.split()]
                        decoded_text = ''.join(chr(code) for code in ascii_codes)
                        _LOGGER.debug("Decoded ASCII: %s", decoded_text)
                        raw_text = decoded_text
                    except Exception as e:
                        _LOGGER.warning("Failed to decode ASCII: %s", e)
                
                # Парсим JSON
                try:
                    data = json.loads(raw_text)
                    
                    if data.get("status") != "success":
                        _LOGGER.warning("Power meter API error: %s", data.get("status"))
                        return None
                    
                    # Ищем данные счетчика
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
                    
                except json.JSONDecodeError as e:
                    _LOGGER.error("JSON decode error: %s. Text: %s", e, raw_text[:100])
                    return None
                    
    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout fetching power data")
        return None
    except Exception as e:
        _LOGGER.error("Error fetching power data: %s", e, exc_info=True)
        return None
