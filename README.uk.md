# HA Auditor для Home Assistant

[![English](https://img.shields.io/badge/lang-English-blue)](README.md)
[![Українська](https://img.shields.io/badge/lang-Українська-yellow)](README.uk.md)
[![Validate](https://github.com/rodion981/ha-auditor/actions/workflows/validate.yml/badge.svg)](https://github.com/rodion981/ha-auditor/actions/workflows/validate.yml)
[![Ліцензія: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

HA Auditor це кастомна YAML-інтеграція Home Assistant. Вона перевіряє GitHub
Releases встановлених через HACS інтеграцій і показує зміни, на які варто
звернути увагу перед оновленням.

Інтеграція відповідає на три практичні питання:

1. Для яких HACS-інтеграцій зараз доступні оновлення?
2. У яких нових релізах можуть бути критичні зміни, важливі виправлення або
   нові функції?
3. Аудит завершився повністю чи частину репозиторіїв не вдалося перевірити?

## Що робить інтеграція

- Знаходить активні сутності `update.*`, створені HACS.
- Під час першого запуску мовчки формує базову точку, щоб не показувати всі
  старі релізи як нові.
- Використовує GitHub Releases та ETag, зменшуючи кількість API-запитів.
- Окремо показує доступні в HACS оновлення й нові знайдені релізи.
- Класифікує release notes як критичні, важливі, функціональні або незначні за
  детермінованими ключовими словами та показує причину класифікації.
- Зберігає контрольні точки релізів і чергу щотижневого дайджесту в сховищі
  Home Assistant.
- Позначає неповний аудит як `partial`, а не видає його за успішний.
- За бажанням надсилає термінові сповіщення та щотижневий дайджест.

Інтеграція не встановлює оновлення, не змінює конфігурацію Home Assistant і не
виводить GitHub-токен в атрибути сенсора.

## Важливе обмеження

Класифікація за ключовими словами є підказкою, а не аудитом безпеки чи доказом
несумісності. Перед встановленням критичного або важливого релізу завжди
відкривайте повні release notes.

Репозиторії, які публікують лише теги або коміти без GitHub Releases, поки що
не можуть створювати сповіщення про зміни релізу.

## Встановлення

### Через HACS як кастомний репозиторій

1. Відкрийте HACS у Home Assistant.
2. Додайте `https://github.com/rodion981/ha-auditor` як кастомний репозиторій
   категорії **Integration**.
3. Встановіть **HA Auditor**.
4. Перезапустіть Home Assistant.
5. Додайте YAML-конфігурацію нижче та перезапустіть Home Assistant ще раз.

### Вручну

Скопіюйте каталог:

```text
custom_components/custom_components_auditor
```

за таким самим шляхом у каталозі конфігурації Home Assistant, після чого
перезапустіть Home Assistant.

## Налаштування

Щоб повний аудит міг перевірити всі репозиторії за один запуск, додайте
GitHub-токен лише для читання до `secrets.yaml`:

```yaml
custom_components_auditor_github_token: YOUR_GITHUB_TOKEN
```

Підключіть секрет у `configuration.yaml`:

```yaml
custom_components_auditor:
  github_token: !secret custom_components_auditor_github_token
  notify_service: notify.mobile_app_your_phone
  daily_hour: 9
  weekly_weekday: 6
  max_requests_per_run: 45
```

`notify_service` необов'язковий. Не вказуйте його, щоб вимкнути push-сповіщення.
Без GitHub-токена інтеграція перевіряє не більше
`max_requests_per_run` репозиторіїв і продовжує з наступного репозиторію під час
наступного запуску.

Ніколи не додавайте `secrets.yaml` або справжній токен до Git.

## Запуск аудиту

Інтеграція реєструє таку дію Home Assistant:

```yaml
action: custom_components_auditor.run_audit
data:
  mode: full
  notify: false
```

Режими:

- `daily`: перевірити наступну налаштовану порцію репозиторіїв;
- `full`: перевірити всі репозиторії з авторизацією, без неї одну порцію;
- `digest`: перевірити репозиторії та надіслати накопичений тижневий дайджест.

Плановий аудит запускається на 15-й хвилині `daily_hour`. У день
`weekly_weekday` запускається режим дайджесту. Використовуються номери днів
Python: понеділок `0`, неділя `6`.

## Як читати результат

Інтеграція створює `sensor.custom_components_auditor`.

- `status`: `idle`, `running`, `partial` або `error`;
- `last_attempt`: час початку останньої спроби аудиту;
- `last_successful_audit`: час останнього повністю успішного аудиту;
- `total_components`: усі знайдені HACS-інтеграції;
- `targeted_this_run`: репозиторії, вибрані для поточного запуску;
- `checked_this_run`: репозиторії, які вдалося перевірити;
- `updates_available` і `available_updates`: оновлення, які зараз пропонує HACS;
- `critical`, `important`, `new_features` і `minor`: нові релізи за категоріями;
- `last_run_changes`: нові релізи, знайдені під час останнього запуску;
- `pending_digest_changes`: релізи, що чекають тижневого дайджесту;
- `error_details`: помилки, згруповані за типом;
- `github_rate_remaining`: залишок квоти GitHub API, якщо він доступний.

Статус `partial` означає, що хоча б один вибраний репозиторій не перевірено.
Результат неповний, а причина міститься в `error_details`.

Приклад стандартної картки дашборда доступний у
[`examples/dashboard.yaml`](examples/dashboard.yaml).

## Розробка і перевірка

```bash
python -m pip install -r requirements_test.txt
python -m compileall -q custom_components
ruff check custom_components tests
pytest
```

Юніт-тести перевіряють класифікацію релізів, заперечення фраз про несумісні
зміни, очищення описів, дедуплікацію, метадані репозиторію та базовий пошук
секретів. Runtime-перевірка Home Assistant і встановлення через HACS у чистій
системі залишаються окремими релізними бар'єрами.

## Безпека

Надавайте GitHub-токену лише необхідні права. Не публікуйте в Issues токени,
конфігурацію Home Assistant, вміст `.storage` або payload сповіщень. Докладніше
в [`SECURITY.md`](SECURITY.md).

## Ліцензія

[MIT](LICENSE)
