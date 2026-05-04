# DrinkX CRM Prototype

🌐 **Live:** https://globalsasha.github.io/drinkx-crm-prototype/

Кликабельный прототип Smart AI CRM для DrinkX (Phase 0 deliverable).
131 реальный клиент из drinkx-client-map с настоящим AI Brief, ЛПР, sales triggers.

## Файлы

- **`prototype.html`** — сам прототип (открой в браузере: `open prototype.html`)
- **`data.js`** — данные 131 клиента, сгенерировано из `drinkx-client-map-v0.5`
- **`build_data.py`** — парсер. Запусти когда `drinkx-client-map` обновится:
  ```bash
  python3 build_data.py
  ```
- **`docs/`** — design spec и PRD-additions

## Что в прототипе

- **131 реальная компания** из 6 сегментов: ритейл, non-food, кофейни, QSR, АЗС, дистрибьюторы оборудования
- Настоящие данные AI Brief: company overview, network scale, geography, foodservice signals, decision makers, sales triggers, recommended entry route, source links, research gaps
- Реальные ЛПР (где есть LinkedIn-обогащение)
- Сгенерированные deal_amount, fit_score, stages — на основе реальных сигналов

## Распределение

- 14 Tier 1 (приоритет A) · 93 Tier 2 · 24 Tier 3
- Стадии: 41 новых · 30 квалификация · 26 КП · 19 переговоров · 10 согласование · 3 won · 2 lost
- Менеджеры: Кирилл (53) · Иван (46) · Алексей (32)
- ₽1.28B в воронке, 45 rotting

## Demo-states (слева внизу)

- **Роль:** Менеджер (Кирилл) ↔ Руководитель (Алёна)
- **Today:** реально / всё сделано / пусто
- **Pipeline:** реально / пусто
- **Onb:** 4 шага онбординга
- **Голова (для роли руководителя):** → Команда / Knowledge / Настройки / WebForm

## Sharing

Чтобы поделиться прототипом одним файлом — нужно встроить `data.js` в `prototype.html`:

```bash
# Inline data.js into prototype.html (todo)
```

Пока — папка целиком (HTML + data.js).

## Регенерация данных

```bash
# 1. Положи обновлённую папку drinkx-client-map в Downloads
# 2. Запусти:
python3 build_data.py
# 3. Открой prototype.html — увидишь свежие данные
```
