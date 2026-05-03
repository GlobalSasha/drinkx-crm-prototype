# PRD Smart AI CRM — Additions v1.4

**Базовый документ:** PRD v1.3 (передан в чате)
**Дата:** 2026-05-03
**Источник:** Исследование 17 open-source CRM проектов (см. `docs/superpowers/specs/2026-05-03-smart-ai-crm-phase0-ia-ux-design.md` секция References)
**Статус:** Draft — изменения и дополнения к v1.3 для следующей ревизии PRD

---

## A. Новые фичи для добавления в PRD

Сгруппированы по приоритету для DrinkX MVP.

### A1. MVP — добавить сразу в Phase 1

| Фича | Откуда | Зачем нам | Сложность |
|---|---|---|---|
| **Multi-pipeline на data-уровне** + поле `pipeline_id` на сделке | EspoCRM, lsfusion | DrinkX точно нужны разные воронки: ритейл / HoReCa / АЗС / сервис. Нельзя хардкодить enum. | S |
| **Quote / КП как first-class сущность** | Krayin Quote package | B2B продажа кофе-станций = всегда КП с конфигурацией (модели, кол-во, опции, доставка). Без этого менеджеры будут вести в Word. | M |
| **Email/SMS/TG templates как ресурс** (CRUD + переменные `{{lead.name}}`) | EspoCRM, IONDV `commtpl/` | Типовые ответы и follow-ups; AI генерирует черновик из шаблона как baseline | S |
| **WebForm / lead-capture forms** — публичные посадочные формы с UTM-захватом | Krayin WebForm | Захват с лендингов и партнёрских страниц. Сейчас в PRD только Email/Telegram inbox | M |
| **Document/Visit-card parser** (загрузить PDF/фото визитки → AI создаёт лид) | Krayin AI MagicAIService | Менеджер фоткает визитку с выставки → карточка готова. Высокий wow, низкая сложность | M |

### A2. Phase 2 — после MVP

| Фича | Откуда | Зачем |
|---|---|---|
| **AI Sales Coach chat** в sidebar карточки | ai-crm-streamlit | Контекст текущей карточки + DrinkX knowledge-base. «Как ответить на возражение про Nespresso?» |
| **Stalled deal detector + next-action recommender** | ai-crm-agents | Объяснимый rotting: «3 follow-up без ответа, попробуй другого ЛПР» |
| **Public signal monitoring** (cron HH.ru на pipeline-компании) | Vyapaar pattern | Авто growth_signal в карточке: «Магнит открыл 3 вакансии «оператор кофейного оборудования»» |
| **NL search over pipeline** через whitelisted views | Odoo AI, EspoCRM Copilot | «Покажи горячие лиды HoReCa СПб без активности 7 дней» → safe query |
| **Sales Knowledge Base** (`knowledge/drinkx/*.md` — playbooks, объекции, success stories) | ai-crm-streamlit | Подмешивается в Research Agent + Sales Coach. Резко повышает качество AI-ответов |

### A3. Future / v1.5+

| Фича | Откуда |
|---|---|
| **MCP-server поверх FastAPI** — экспонировать карточки/пайплайн для внешних AI (Claude Desktop, Cursor) | Relaticle, EspoCRM MCP — это тренд 2025-2026 |
| **Marketplace расширений** | EspoCRM community |
| **Vector DB для контекста** (эмбеддинги предыдущих успешных deals → retrieval похожих кейсов в промпт Research Agent) | ai-crm-agents |

---

## B. Архитектурные изменения

### B1. Изменения в существующих секциях PRD v1.3

#### B1.1. Backend modular structure (PRD §6 «Technical Stack»)

**Было:** «Backend: Python 3.12 + FastAPI». Без указаний по разбиению.
**Стало:** Package-per-domain (как Krayin):

```
backend/
  app/
    leads/         # CRUD, поиск, фильтры
    pipeline/      # воронки, стадии, переходы
    inbox/         # email + telegram, матчинг → лид
    enrichment/    # Research Agent, источники, кэш
    automation/    # workflow rules, триггеры
    assignment/    # workload distribution algorithm
    activity/      # unified activity stream
    quote/         # КП
    template/      # email/sms/tg шаблоны
    auth/          # OAuth, JWT, roles, workspaces
    common/        # shared models, utils
```

Каждый пакет: `models.py`, `schemas.py`, `repositories.py`, `services.py`, `tasks.py` (Celery), `routers.py`, `events.py`. **Не** layered (`models/`, `services/`, `controllers/`).

#### B1.2. Data model (PRD §7) — новые сущности

```sql
-- Pipelines на data-уровне
pipelines: id, workspace_id, name, type (sales|partner|service), is_default, created_at
stages: id, pipeline_id, name, position, color, rot_days, is_won, is_lost  -- уже было

-- Кастомные атрибуты (EAV из Krayin)
custom_attributes: id, workspace_id, entity_type (lead|contact),
                   key, label, type (text|number|select|date|multiselect),
                   options_json, required, position
custom_attribute_values: id, entity_id, attribute_id, value_text, value_number, value_date

-- Quote / КП
quotes: id, lead_id, workspace_id, number, status (draft|sent|accepted|rejected),
        subtotal, discount, total, valid_until, sent_at, created_at
quote_lines: id, quote_id, product_name, quantity, unit_price, discount, total
            -- может ссылаться на products каталог в будущем

-- Templates коммуникаций
templates: id, workspace_id, channel (email|tg|sms),
           name, subject, body, variables_json, is_archived

-- Materialized AI runs (вместо только Celery task'ов)
enrichment_runs: id, lead_id, status (pending|running|done|failed),
                 sources_json,         -- какие источники и их статусы
                 input_json,            -- что подали на вход
                 output_json,           -- результат
                 cost_tokens,           -- сколько токенов
                 cost_usd,              -- сколько денег
                 duration_ms,
                 model,                 -- какой LLM использовали
                 attempt,               -- попытка №
                 created_at, completed_at, error

-- Unified activity stream (EspoCRM Stream pattern)
activities: id, workspace_id, entity_type (lead|quote|contact|user),
            entity_id, actor_id, type, payload_json, created_at
            -- type: created | updated | stage_changed | message_sent
            --       enrichment_completed | quote_sent | meeting_held | call_made

-- WebForms
web_forms: id, workspace_id, name, slug, fields_json, target_pipeline_id,
           target_stage_id, redirect_url, is_active, submissions_count
form_submissions: id, web_form_id, lead_id, raw_payload, utm_json, ip, created_at
```

#### B1.3. AI Architecture (PRD §5) — добавить

**B1.3.1. Output schema c fallback-дефолтами (Krayin pattern):**

Все Pydantic-модели для LLM-ответов используют `Optional` + дефолты, чтобы никогда не падать при отсутствии полей в ответе.

```python
class ResearchOutput(BaseModel):
    company_profile: str = "Информация недоступна"
    scale_signals: str = ""
    growth_signals: list[str] = Field(default_factory=list)
    risk_signals: list[str] = Field(default_factory=list)
    decision_maker_hints: str = ""
    drinkx_fit_score: int = Field(ge=0, le=10, default=5)
    next_steps: list[NextStep] = Field(default_factory=list)
    urgency: Literal["low", "medium", "high"] = "low"
    sources_used: list[str] = Field(default_factory=list)
```

**B1.3.2. Quality pre-filter перед Research Agent (cost control):**

Перед запуском полного Research Agent — дешёвая проверка «стоит ли тратить токены»:
- regex/правила: компания не в стоп-листе, не дубль существующего лида, не банкрот по ИНН (СБИС API)
- mini-LLM call (~50 токенов): «по входным данным — это релевантный B2B-лид для DrinkX? yes/no/maybe»

Только при `yes/maybe` → запуск Research Agent. Срезает 40-60% впустую потраченных токенов на мусорные лиды.

**B1.3.3. Knowledge Base (`knowledge/drinkx/*.md`) для grounding:**

Папка с playbooks подмешивается в системный промпт Research Agent и Sales Coach:
- `playbook_horeca.md` — как продавать в кофейни
- `playbook_retail.md` — как продавать в продуктовый ритейл
- `playbook_azs.md` — как продавать в АЗС
- `objections.md` — типовые возражения и ответы
- `success_stories.md` — кейсы (Дикси pilot и т.п.)
- `competitors.md` — Drive Café, LukCafe, Зерно — что говорить
- `product_specs.md` — модели станций, характеристики, цены

Загружается при старте сервиса в Redis. Менеджер может редактировать через админку.

**B1.3.4. business-profile config (`config/drinkx_profile.yaml`):**

Единый источник правды о DrinkX, подмешивается в КАЖДЫЙ AI-промпт:

```yaml
company:
  name: DrinkX
  product: умные кофе-станции для B2B (офис, HoReCa, ритейл, АЗС)
  unique_value:
    - автоматизация без бариста
    - стабильное качество
    - снижение себестоимости чашки
icp:
  ideal_segments: [horeca_chains, retail_grocery, qsr, gas_stations]
  ideal_size: 10+ точек
  ideal_pain: [нехватка бариста, текучка, нестабильное качество]
voice_tone: профессиональный, без воды, с цифрами
language: ru
```

**B1.3.5. Model tier switching (cost control):**

| Use case | Default model | Fallback |
|---|---|---|
| Bulk Research Agent enrichment | DeepSeek V3 | OpenAI GPT-4o-mini |
| High-fit карточки (drinkx_fit_score ≥ 8) — re-enrichment | OpenAI GPT-4o | Gemini 1.5 Pro |
| Sales Coach chat (контекст + быстрый ответ) | DeepSeek V3 | — |
| Daily Plan generation (1 раз/день/менеджер) | DeepSeek V3 | OpenAI GPT-4o-mini |
| Visit-card OCR + parsing | OpenAI GPT-4o (vision) | Gemini 1.5 Pro |

#### B1.4. Background jobs (PRD §6) — расширить

**Materialized job records pattern (EspoCRM):**

Все long-running задачи (enrichment, daily plan, mass email, import) хранятся как сущности в БД, а не только как Celery tasks:

```
enrichment_runs ── status, attempts, cost, output, error
daily_plan_jobs ── status, generated_for_date, output_plan_json
import_jobs    ── status, source, total, processed, failed_rows_json
```

Это даёт:
- Аудит: кто, когда, сколько потратил
- Retry: можно перезапустить failed jobs из админки
- Биллинг: суммируем `cost_usd` за период
- Debugging: видим input/output каждого AI-запуска

#### B1.5. WorkloadCalculator + AssignmentEngine — отдельный модуль

В PRD v1.3 было упомянуто как алгоритм. **Делаем отдельный пакет `app/assignment/`** с pluggable стратегиями:

```python
class AssignmentStrategy(Protocol):
    def assign(self, lead: Lead, candidates: list[User]) -> User: ...

class RoundRobinStrategy: ...
class WorkloadBasedStrategy: ...   # current_load * weight
class ExpertiseBasedStrategy: ...  # на основе sales history
class HybridStrategy: ...          # комбинация (текущий PRD §4.4)
```

**Это наша оригинальная фича** — ни в одной из 17 исследованных систем нет встроенного workload distribution. Конкурентное преимущество, оформляется как изолированный модуль для будущего open-source (или отдельного продукта).

---

## C. Anti-patterns — явный запрет

Добавить в новую секцию PRD «Что мы НЕ делаем»:

1. **Не делать sync REST для длинных AI-задач.** Минимум 30 секунд → POST создаёт `enrichment_run`, возвращает ID; SSE/WebSocket стрим прогресса; Celery воркер пишет результат.
2. **Не давать LLM прямой SQL access без whitelisting.** Даже read-only к raw таблицам = риск SQL injection через prompt + утечка PII в логи провайдера. Только через узкие, заранее определённые view/функции.
3. **Не делать multi-agent ради multi-agent.** Один оркестратор + явные Celery шаги. Multi-agent только когда есть РЕАЛЬНАЯ независимость задач.
4. **Не делать AI auto-actions без human-in-the-loop.** Для B2B критично: AI ПРЕДЛАГАЕТ, менеджер аппрувит. Никаких автоматических исходящих сообщений без явного согласия менеджера.
5. **Не делать metadata-driven «всё через DSL».** Соблазнительно, но даёт нечитаемый код и теряет типизацию. Metadata только для полей/форм/навигации, бизнес-логика — обычный Python.
6. **Не делать монолитный `cron/` со скриптами.** Все периодические задачи — Celery beat с явным реестром в `app/scheduled/jobs.py` + observability на каждую.

---

## E. Import / Export + Bulk Update (новый блок, 2026-05-03)

### E1. Назначение

Менеджер DrinkX часто получает список новых лидов или обновлений извне:
- Research от внешнего AI / аналитика (Perplexity, Claude, ChatGPT)
- Выгрузка из старой CRM (Bitrix24, AmoCRM)
- Markdown-папки в стиле `drinkx-client-map`
- CSV/Excel от партнёров

Нужен сценарий: **«дать задание → получить результат → загрузить → AI применит изменения после превью»**.

### E2. Поддерживаемые форматы

| Формат | Назначение | Auto-detect |
|---|---|---|
| **DrinkX Update YAML v1.0** | Native: bulk-update с полями ai_data, contacts, tags, next_steps | ✅ |
| **CSV** | Простой импорт компаний + контактов | ✅ |
| **JSON** | Программный импорт от внешних агентов | ✅ |
| **Excel (.xlsx)** | Выгрузки от партнёров / тендерные списки | ✅ |
| **ZIP с Markdown** | Совместимость с drinkx-client-map (Obsidian-стиль) | ✅ |
| **Bitrix24 REST dump** | Импорт сделок + контактов | спецшаблон |
| **AmoCRM JSON dump** | То же | спецшаблон |

### E3. DrinkX Update Format v1.0 — спецификация

```yaml
format: drinkx-crm-update
version: 1.0
generated_at: 2026-05-03T15:00:00Z
generator: <имя AI или researcher>

updates:
  - action: update | create | skip
    match_by: inn | company_name | id | email
    company:
      name: ...
      inn: ...
    fields:
      ai_data:
        company_profile: "..."        # перезаписать
        growth_signals:
          add: [...]                  # дополнить
          remove: [...]
        fit_score: 9                  # перезаписать
      contacts:
        add: [...]
        update_by_email:
          "x@y.ru": {...}
      tags:
        add: [...]
        remove: [...]
      next_steps:
        replace: [...]                # полная замена
      stage: "Переговоры"
      assigned_to: "elena@drinkx.ru"
```

### E4. Bulk Update Workflow (UI)

3 шага в Import-модалке:

1. **Скачать снэпшот** — `leads_snapshot.yaml` со всеми текущими лидами + AI Brief. Отдаёшь внешнему AI как контекст, чтобы он не создавал дубли.
2. **Скопировать промпт** — готовый промпт со схемой ответа в буфер. Внешний AI получает его + снэпшот → выдаёт совместимый YAML/JSON.
3. **Загрузить ответ** — drag-drop файл → preview diff → Apply.

### E5. Preview / Diff UI

После загрузки файла менеджер видит:
- Сводку: ✨ создать (12) · 🔄 обновить (28) · ⏸ skip дубль (5) · ⚠️ конфликт (2)
- Таблицу с каждой строкой: badge действия · название · по чему мэтчили · ▾ раскрытие diff
- Конфликты подсвечены красным — требуют ручного решения (например fit_score у нас = 7, в импорте = 5)

### E6. Бэкенд

Новый пакет `app/import_export/`:
- `parsers/` — yaml.py, csv.py, xlsx.py, bitrix.py, amocrm.py, markdown_zip.py
- `differ.py` — сравнение текущей базы с импортом, генерация diff
- `applier.py` — применение diff после approval (транзакционно)
- `prompt_templates.py` — генерация промпт-задания для внешнего AI
- `snapshot.py` — экспорт текущей базы в `drinkx-update-format` (для bulk-update workflow)

Сущность `import_jobs` в БД (см. B1.4 — Materialized job records):
```sql
import_jobs: id, workspace_id, source (file|bulk_update|api),
             format, status (uploaded|previewed|applied|failed),
             total, created, updated, skipped, conflicts,
             diff_json, applied_changes_json,
             initiated_by, applied_by, created_at, applied_at
```

### E7. Export

Простой modal со scope (current pipeline / all / filtered / won) + format (YAML/JSON/CSV/Excel/Markdown ZIP) + поля (basic / AI Brief / messages / activities / quotes).

Опция «**включить промпт-задание для AI**» (добавит INSTRUCTIONS.md в zip) — для bulk-update workflow.

---

## F. Knowledge Base UI (admin, новый блок)

### F1. Назначение

Управление контентом, который AI использует как контекст. Отдельный экран для admin/head:
- **Playbooks** (6) — стратегии продажи по сегментам (HoReCa, ритейл, QSR, АЗС, офис, франшиза)
- **Success stories** (12) — кейсы для подмешивания в Sales Coach и КП
- **Объекции** (8) — типовые возражения с ответами
- **Конкуренты** (5) — Drive Café, LukCafe, Зерно — слабости/сильные/угол
- **Продукт** (4) — модели станций, характеристики, цены
- **Профиль DrinkX** (`profile.yaml`, `icp.yaml`, `tone.yaml`)

### F2. UI-структура

3 колонки:
- **Категории** (6 + профиль)
- **Список файлов** в выбранной категории — название, описание, статистика использования AI, дата изменения
- **Редактор** справа: title, теги для матчинга (сегмент / тип / стадия), markdown-контент, действия (Тест на лиде / История / Сохранить / Архив)

Внизу редактора — **«Использование AI за 7 дней»**: список случаев когда этот файл подмешивался в промпт (какая карточка, какой агент, какая секция файла использовалась).

### F3. Теги для матчинга

Каждый файл имеет теги: `сегмент: HoReCa`, `тип: кофейная сеть`, `размер: 5+ точек`, `стадия: Квалификация`. AI выбирает релевантные файлы по этим тегам когда формирует промпт для конкретной карточки.

### F4. Бэкенд

Пакет `app/knowledge/`:
- `models.py` — `KnowledgeFile(category, name, content_md, tags_json, usage_count, last_used_at, ...)`
- `services.py` — селектор файлов по тегам карточки, инжектор в промпт
- `usage_tracking.py` — лог каждого использования (какая карточка, какой агент, какие секции упомянуты)
- `routers.py` — CRUD + поиск + статистика

### F5. Версионирование и история

Каждое сохранение → новая версия в `knowledge_versions`. Можно откатить, посмотреть diff между версиями, увидеть кто что менял.

---

## G. Drag-drop UX для Kanban (новый блок)

### G1. Поведение

- Любая карточка в Kanban draggable
- При hover на колонку — подсветка drop-зоны + AI-подсказка (зависит от типа перехода)
- Типы переходов: **forward** (нормально) / **skip** (пропуск стадий — нужно подтверждение) / **back** (откат — нужна причина) / **won** (закрытие — нужны детали)
- Top-banner показывает текущее действие: «Перетаскиваешь Stars Coffee → Согласование. 🤖 Прогрессирование — AI запишет в активности»

### G2. Stage-change confirmation modal (для won/lost)

При drop на «Закрыто (won)»:
- Финальная сумма (предзаполнено из текущей)
- Дата подписания
- **Что сработало** — chips для AI Knowledge Base (Кейс Дикси / ROI-расчёт / Brand-customization / Партнёрская скидка / Demo с CTO)
- Заметка для команды
- AI promise: «AI добавит этот кейс в knowledge base success_stories/ — будет использовать в подсказках по похожим лидам»

При drop на «Закрыто (lost)»:
- Причина (dropdown: цена / конкурент / сроки / не нужно сейчас / нет бюджета / другое)
- Свободный комментарий
- AI promise: «использую для калибровки fit_score у похожих лидов»

### G3. Бэкенд

Stage-change события идут через `app/automation/stage_change.py`:
- `pre_change_hook(lead, from_stage, to_stage)` — валидация, могут блокировать
- `apply_change(lead, to_stage, reason, metadata)` — обновление + activity record
- `post_change_hook(lead, ...)` — триггеры (e.g., при won → добавить в knowledge base через AI synthesizer)

---

## H. Onboarding flow (новый блок, 4 шага)

### H1. Шаги
1. **Welcome / Google OAuth** — большая кнопка `Войти через Google` + invite-link (для приглашённых) + privacy-нота. После OAuth → step 2.
2. **Профиль** — имя/email из Google · 3 роли (Junior / Middle-Senior / Head) · спецификация чипами (HoReCa / Ритейл / QSR / АЗС / Офис / Партнёры) · **визуальный schedule grid** Пн-Вс × 9-18 (work / lunch / off) · timezone · max active leads.
3. **Каналы** — Email Gmail (auto-connect через OAuth) · Telegram Business (отдельный flow с webhook + Premium-аккаунт) · WhatsApp / VK на Phase 2.
4. **Готово** — статистика «1 канал · 6.5ч · 20 макс лидов» + 4 CTA (Создать вручную / Фото визитки / Импорт CSV / Bitrix24-AmoCRM) → переход в `today-empty`.

### H2. Bypass
В шапке каждого шага кнопка `Подключу позже →`. Минимум — обязательно step 2 (профиль). Каналы и финальные CTA можно skip.

### H3. Бэкенд
`app/auth/onboarding.py`:
- `OnboardingState` (sub-entity на `User`) — текущий шаг + что заполнено
- хук `post_signup` создаёт `User` в pending состоянии, направляет на step 2
- завершение step 4 → `User.onboarding_completed = true`

---

## I. Admin Settings (новый блок)

Отдельный экран с боковой навигацией:

| Раздел | Содержимое |
|---|---|
| **📊 Воронки и стадии** | CRUD воронок · конструктор стадий (drag-drop, цвет, rot_days, probability) |
| **👥 Команда** | список менеджеров с ролями · invite-ссылка с TTL · реферальный токен · стратегия AI-распределения |
| **💬 Каналы** | подключённые email/Telegram/SMTP с per-channel статистикой (входящих/исходящих, % матчинга, unmatched) |
| **🤖 AI-провайдеры** | список моделей с ролью (primary/fallback) · cost summary (бюджет / расход / cache hit) · лимиты |
| **🔧 Кастом-поля (EAV)** | список + типы + условия применения (по сегменту/стадии) |
| **🔔 Уведомления** | см. секцию K |
| **🔗 Интеграции / webhooks** | Bitrix24, Slack, Notion, 1C, Zapier, собственный API |
| **🔐 Роли и права** | базовые (Manager/Head/Admin) + кастомные с гранулярными правами |
| **📜 Audit log** | все события за период с фильтрами |
| **💳 Тариф / 📈 Использование** | биллинг + графики использования AI |

---

## J. WebForm builder (новый блок)

### J1. UI структура (3 колонки + tabs)

**Tabs:** 🎨 Дизайн · 📥 Маршрутизация · 🎯 UTM · 📊 Стили · 🔗 Embed · 📈 Аналитика

**3-column layout:**
- **Палитра полей** (слева) — 16 типов: Имя, Email, Телефон, Telegram, Компания, ИНН, Сегмент, Город, Кол-во точек, Сообщение, Файл, Дата, Чекбокс, UTM-метки, Источник, Cookie ID
- **Live-preview формы** (центр) — drag-drop полей, click → выбор для редактирования
- **Field config panel** (справа) — title, placeholder, обязательное, валидация, **mapping на лид** (`form.email → contact.email`), AI после-сабмита (auto-обогащение, quality pre-filter, дедуп, auto-assign), статистика 30 дней, embed-код

### J2. AI после сабмита
1. Quality pre-filter (отсеять spam) → reject early
2. Дедупликация по email/ИНН → merge или новый
3. Research Agent enrichment → AI Brief
4. Auto-assign по сегменту через `app/assignment/`

### J3. Бэкенд
`app/forms/`:
- `models.py` — `WebForm`, `FormField`, `FormSubmission`
- `routers.py` — публичный `POST /f/{slug}` + админский CRUD
- `processors.py` — pre-filter → dedup → enrichment → assign → notify

---

## K. Notifications (новый блок)

### K1. UI
- **Bell icon** в правом верхнем углу с badge unread count
- **Drawer** справа: фильтры (Все / 🔥 Срочные / 🤖 AI / 💬 Сообщения / ⏸ Системные), группировка по времени (Сейчас / Сегодня / Вчера / Ранее)
- Каждый уведомление: иконка по типу (urgent/alert/success/info/ai), заголовок + desc + время, action-кнопки (Открыть карточку / Ответить / etc), unread-индикатор
- Mark all read · переход в Settings → Notifications

### K2. Каналы доставки

| Канал | Назначение |
|---|---|
| **In-app** | bell + drawer (всегда вкл) |
| **Email** | для дайджестов и важных событий, off-by-default для шумных |
| **Push (web/desktop)** | для срочных событий, тихие часы |
| **Telegram bot** | срочные / новые сообщения / push-fallback |
| **SMS** | только критичное (билинг limit) |

### K3. Матрица событий

10 типовых событий (срочный сигнал, новое сообщение, AI Brief готов, дневной план, rotting, новая заявка с WebForm, won-сделка, bulk import, биллинг-лимит, нагрузка команды) × 5 каналов. Дефолты разумные, кастом per-user.

### K4. AI-сглаживание (важно)
Похожие события в коротком окне (2-5 мин) сворачиваются в одно: «5 карточек обогащено», «3 сообщения от Эрнесто» — чтобы не утопить в шуме.

### K5. Тихие часы
22:00 — 08:00 по умолчанию: push/Telegram отключены, in-app копятся в bell.

### K6. Email digest
- Утренний brief (8:00) — задачи + сигналы дня
- Weekly report (пятница 18:00) — конверсия, движение по воронке, AI-cost

### K7. Бэкенд
`app/notifications/`:
- `models.py` — `Notification`, `NotificationPreference`, `Digest`
- `dispatcher.py` — выбор канала по preferences + приоритет + тихие часы
- `aggregator.py` — sliding-window сворачивание похожих событий
- `channels/` — `inapp.py`, `email.py`, `push.py`, `telegram.py`, `sms.py`

---

## D. Что осталось решить

- **MCP-server** — на каком этапе планировать (Phase 2 или отложить)?
- **Multi-tenancy** — workspace модель уже есть, но нужно решить про data isolation (row-level security в Postgres? отдельные схемы?)
- **Vector DB** — нужен ли он на v1.0 или отложить?
- **Quote/КП** — насколько сложный конфигуратор: line items с фиксированными моделями станций или свободный?
- **WebForms** — публичный API или embed-скрипт?

---

## References

Полный анализ 17 проектов с пер-проектной оценкой релевантности — в чате (раунд исследования 2026-05-03). Ключевые референсы по приоритету:

| Проект | Что забрали | Файлы для глубокого reverse-engineering |
|---|---|---|
| Krayin CRM | Модульность, EAV, Quote, AI Lead Gen, structured output | `packages/Webkul/Lead/`, `packages/Webkul/Attribute/`, `MagicAIService` |
| EspoCRM | Metadata-driven, Stream API, EmailQueueItem, ScheduledJob | `application/Espo/Core/`, `application/Espo/Modules/Crm/` |
| atomic-crm | DataProvider абстракция, FE-нарезка по фичам | `src/components/atomic-crm/`, `src/providers/` |
| business-leads-ai-automation | business-profile config, dual-template output, quality scoring | основной pipeline + `business-profile.json` |
| ai-crm-agents | Stack-twin (FastAPI+Celery+Redis), multi-agent split | README архитектурный (кода мало) |
