# 🏠 Hisense Multi-IDU для Home Assistant

Локальная интеграция Home Assistant для мульти-сплит систем Hisense (Multi-IDU) через web API контроллера.

![Version](https://img.shields.io/badge/version-1.0.1-blue)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2023.12%2B-green)
![Python](https://img.shields.io/badge/Python-3.10%2B-orange)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Что умеет интеграция сейчас

### Климатические сущности (`climate`)
Для каждого найденного внутреннего блока (IDU) создаётся отдельная климатическая сущность.

Поддерживается:
- включение/выключение;
- режимы: `cool`, `heat`, `dry`, `fan_only`;
- установка целевой температуры (16–30 °C, шаг 1 °C);
- скорость вентилятора: `auto`, `low`, `medium`, `high`;
- управление вертикальной жалюзи (`swing_mode`): `auto` + фиксированные углы `angle_1..angle_8`;
- отображение текущей комнатной температуры.

Дополнительно реализовано:
- сохранение последних настроек (режим/температура/вентилятор/жалюзи) при выключении;
- применение сохранённых настроек при следующем включении;
- optimistic update после команд, чтобы интерфейс не «отпрыгивал»;
- отложенный debounce-опрос после команд для синхронизации состояния.

### Сенсоры энергии (`sensor`)
Интеграция создаёт 3 сенсора по данным встроенного электросчётчика:

1. **Hisense raw meter** — сырое значение счётчика (Wh).
2. **Hisense электросчётчик** — накопленная энергия в kWh (`total_increasing`, подходит для Energy Dashboard).
3. **Текущая мощность** — расчётная текущая мощность в kW на основе дельты энергии между опросами.

### Архитектура и работа
- Полностью локальная работа по HTTP в LAN.
- Автообнаружение внутренних блоков через `get_miscdata.shtml` (`topo`).
- Чтение состояния IDU через `get_idu_data.shtml`.
- Управление IDU через `set_idu.shtml`.
- Чтение счётчика через `get_meter_pwr.shtml`.
- Отдельные координаторы обновления:
  - climate: каждые 10 сек;
  - sensors: каждые 30 сек.
- Кэш топологии устройства на 5 минут.
- Интеграция оформлена как `config_flow` + `local_polling`.

---

## Установка

### Вариант 1: через HACS (рекомендуется)
1. Добавьте репозиторий:
   `https://github.com/undrianov-dot/hisense-multi-idu`
2. Установите интеграцию **Hisense Multi-IDU**.
3. Перезапустите Home Assistant.

### Вариант 2: вручную
```bash
cd /config/custom_components
git clone https://github.com/undrianov-dot/hisense-multi-idu hisense_multi_idu
```

---

## Настройка

1. Откройте **Настройки → Устройства и службы → Добавить интеграцию**.
2. Выберите **Hisense Multi-IDU**.
3. Укажите IP-адрес контроллера (например, `10.99.3.100`).

После добавления интеграция автоматически поднимет:
- hub-устройство;
- climate-сущности для найденных IDU;
- сенсоры счётчика энергии/мощности.

---

## Пример автоматизации

```yaml
automation:
  - alias: "Включить кондиционер при высокой температуре"
    trigger:
      - platform: numeric_state
        entity_id: sensor.temperature_living_room
        above: 26
    action:
      - service: climate.turn_on
        target:
          entity_id: climate.living_room
      - service: climate.set_hvac_mode
        target:
          entity_id: climate.living_room
        data:
          hvac_mode: cool
      - service: climate.set_temperature
        target:
          entity_id: climate.living_room
        data:
          temperature: 24
```

---

## Отладка

Включите debug-логи:

```yaml
logger:
  default: info
  logs:
    custom_components.hisense_multi_idu: debug
```

Проверка доступности контроллера:

```bash
curl http://<IP>/cgi/get_miscdata.shtml
```

---

## Ограничения

- Только локальная сеть (без облака).
- Один IP-контроллер на один config entry.
- Поддерживается только шкала Celsius.
- Горизонтальные жалюзи не управляются (в команду отправляется фиксированное значение).
- Опциональное поле `hub_name` в форме сейчас не влияет на именование устройства.

---

## Совместимость

| Компонент | Версия |
|---|---|
| Home Assistant | 2023.12+ |
| Python | 3.10+ |
| Integration version | 1.0.1 |

---

## Лицензия

MIT
