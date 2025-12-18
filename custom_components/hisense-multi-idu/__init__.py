import re
async def get_power_data(self):
    """Получает данные электросчетчика."""
    url = f"http://{self._host}/cgi/get_meter_pwr.shtml"
    try:
        _LOGGER.debug("Requesting power data from: %s", url)
        
        # Только POST запрос с правильным телом
        payload = {"ids": ["1", "2"], "ip": self._host}
        
        async with self._session.post(
            url,
            json=payload,
            timeout=10
        ) as resp:
            _LOGGER.debug("Response status: %s", resp.status)
            
            if resp.status != 200:
                _LOGGER.warning("Request failed with status: %s", resp.status)
                return None
            
            # Используем resp.read() и вручную декодируем
            raw_data = await resp.read()
            
            # Декодируем байты в строку (они уже в ASCII формате)
            text = raw_data.decode('ascii')
            
            # Если это ASCII коды (вида "123 34 115 ..."), декодируем их
            if re.match(r'^(\d+\s*)+\s*$', text.strip()):
                # Конвертируем "123 34 115" в текст
                chars = []
                for num_str in text.strip().split():
                    try:
                        chars.append(chr(int(num_str)))
                    except ValueError:
                        continue
                decoded_text = ''.join(chars)
                _LOGGER.debug("Decoded ASCII: %s", decoded_text)
                text = decoded_text
            
            # Теперь парсим JSON
            data = json.loads(text)
            
            if data.get("status") != "success":
                return None
            
            # Извлекаем значение мощности
            for meter in data.get("dats", []):
                if isinstance(meter, dict) and "pwr" in meter:
                    power = meter["pwr"]
                    if isinstance(power, (int, float)) and power >= 0:
                        return float(power)
            
            return None
                
    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout when accessing power meter")
        return None
    except json.JSONDecodeError as e:
        _LOGGER.error("JSON decode error: %s", e)
        return None
    except Exception as e:
        _LOGGER.error("Failed to get power data: %s", e)
        return None
