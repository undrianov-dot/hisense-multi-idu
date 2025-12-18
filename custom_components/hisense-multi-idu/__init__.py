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
            
            # ВАЖНО: читаем сырые байты, а не используем resp.text() или resp.json()
            raw_bytes = await resp.read()
            _LOGGER.debug("Raw response bytes (first 100): %s", raw_bytes[:100])
            
            # Конвертируем байты в строку (ASCII)
            try:
                text = raw_bytes.decode('ascii')
            except UnicodeDecodeError:
                _LOGGER.error("Failed to decode response as ASCII")
                return None
            
            _LOGGER.debug("Decoded text: %s", text)
            
            # Декодируем ASCII коды, если текст состоит из чисел
            if text and all(c.isdigit() or c.isspace() for c in text.strip()):
                try:
                    # Разделяем по пробелам и конвертируем в числа
                    ascii_codes = [int(x) for x in text.split()]
                    decoded_text = ''.join(chr(code) for code in ascii_codes)
                    _LOGGER.debug("Decoded ASCII to text: %s", decoded_text)
                    text = decoded_text
                except Exception as decode_error:
                    _LOGGER.warning("Failed to decode ASCII: %s", decode_error)
                    return None
            
            # Пробуем распарсить JSON
            try:
                data = json.loads(text)
                _LOGGER.debug("Parsed JSON data: %s", data)
                
                # Проверяем статус
                if data.get("status") != "success":
                    _LOGGER.warning("API returned error status: %s", data.get("status"))
                    return None
                
                # Ищем данные счетчика
                if "dats" in data and isinstance(data["dats"], list) and len(data["dats"]) > 0:
                    # Ищем счетчик с положительным значением мощности
                    for meter in data["dats"]:
                        if isinstance(meter, dict) and "pwr" in meter:
                            pwr_value = meter["pwr"]
                            
                            # Преобразуем в число
                            try:
                                power = float(pwr_value)
                                
                                # Игнорируем отрицательные значения (обычно это ошибка)
                                if power >= 0:
                                    _LOGGER.info(
                                        "Power meter %s: %s W (sampled at: %s)", 
                                        meter.get("id", "unknown"), 
                                        power, 
                                        meter.get("sampledt", "unknown")
                                    )
                                    return power
                                else:
                                    _LOGGER.debug("Skipping negative power value: %s", power)
                            except (ValueError, TypeError):
                                _LOGGER.warning("Invalid power value: %s", pwr_value)
                    
                    _LOGGER.warning("No valid positive power value found in: %s", data["dats"])
                    return None
                else:
                    _LOGGER.warning("No 'dats' array in response: %s", data)
                    return None
                    
            except json.JSONDecodeError as json_error:
                _LOGGER.error("Failed to parse JSON: %s. Text was: %s", json_error, text[:100])
                return None
                
    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout when accessing power meter endpoint")
        return None
    except Exception as e:
        _LOGGER.error("Failed to get power data: %s", e, exc_info=True)
        return None
