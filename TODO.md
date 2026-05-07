# TODO — оставшиеся блокеры до запуска

## BLOCKED — нужны действия от пользователя

- [ ] **Yandex.Metrika ID**
  Получить счётчик на metrika.yandex.ru (новый счётчик → ввести `getdoday.ru`).
  После получения цифрового ID (например `12345678`):
  1. На сервере: `cd /var/www/getdoday/data/www/getdoday.ru/app && nano .env`,
     заменить `YA_METRIKA_ID=` на `YA_METRIKA_ID=12345678`.
  2. Перезапустить uvicorn (`lsof -ti:8011 | xargs kill -9 && python3 /var/www/getdoday/data/start_uvicorn.py`).
  3. В Метрике добавить цели: `signup` (тип: JS-событие), `login`, `first_task`.

- [ ] **Реальные iPhone-скриншоты**
  Для landing-блока со скриншотами нужны 3-4 скриншота с реального iPhone:
  /app/today, /app/projects/<любой>, /app/calendar, /app/graph.
  Сейчас в landing.html стоят SVG-плейсхолдеры в фиолетовых тонах — заменить
  на реальные скриншоты, когда у пользователя будет под рукой айфон.

- [ ] **Подключить ЮKassa**
  /pricing уже готова. Кнопки «Оформить» сейчас задизейблены. Когда у пользователя
  откроется юр-лицо/ИП, подключить ЮKassa (платёжный модуль уже частично готов
  в app/billing/, нужно только дописать webhook + редирект).
