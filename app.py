"""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║                        YEV STEAM DEPOSIT CALCULATOR                        ║
║                                                                            ║
║ Copyright (c) 2026 Bohdan Yevtushenko (Mr4Cemper)                          ║
║ License: AGPL 3.0 — see the LICENSE file for the full text.                ║
║                                                                            ║
║ ────────────────────────────────────────────────────────────────────────── ║
║                                                                            ║
║ DISCLAIMER: This application is an independent educational and analytical  ║
║ tool. It is NOT affiliated with, endorsed, sponsored, or specifically      ║
║ approved by Valve Corporation. Counter-Strike, CS2, Steam, and their       ║
║ respective logos are trademarks and/or registered trademarks of Valve      ║
║ Corporation.                                                               ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝

Yev Steam Deposit Calculator
============================

Version: 1.7

Streamlit-приложение для оценки экономики торговли скинами CS2. Оно сравнивает
стоимость покупки предмета на стороннем сайте за реальные деньги с операциями
по тому же предмету на Торговой площадке Steam.

Режимы работы:
    Режим 1 — прибыль от покупки скина на стороннем сайте и его последующей
        продажи на Торговой площадке Steam.
    Режим 2 — сравнение: что выгоднее, купить предмет напрямую на сайте за
        реальные деньги или на Steam за заранее пополненный баланс.

Структура модуля:
    * Расчётные функции (calculate_*, get_valid_steam_price) не зависят от
      Streamlit и не имеют побочных эффектов; их можно тестировать и
      переиспользовать отдельно от интерфейса.
    * Локализация (en / ru / uk) реализована через словарь переводов и функцию
      доступа _(); английский текст служит ключом перевода.
    * calculate_mode_1 и calculate_mode_2 строят интерфейс соответствующих
      режимов, main() настраивает страницу и является точкой входа.

Запуск:
    streamlit run app.py
"""

import streamlit as st

# ===========================================================================
# КОНФИГУРАЦИЯ И КОНСТАНТЫ
# ===========================================================================

# Предустановленные профили комиссий популярных торговых площадок.
# Ключи словаря используются как стабильные идентификаторы и не переводятся;
# исключение — "Manual input", который локализуется через format_func.
# Поля профиля:
#   percent_fee   — процент комиссии пополнения;
#   fixed_fee_usd — фиксированная комиссия; задаётся всегда в долларах США и
#                   при необходимости конвертируется в валюту расчёта;
#   enabled       — учитывать ли комиссию по умолчанию при выборе профиля.
DEPOSIT_FEE_TEMPLATES = {
    "Manual input":      {"percent_fee": 0.00, "fixed_fee_usd": 0.00, "enabled": False},
    "CSFloat (Crypto)":  {"percent_fee": 1.00, "fixed_fee_usd": 0.00, "enabled": True},
    "CSFloat (Card)":    {"percent_fee": 2.80, "fixed_fee_usd": 0.30, "enabled": True},
    "SkinSwap (Card)":   {"percent_fee": 3.52, "fixed_fee_usd": 0.32, "enabled": True},
    "SkinSwap (Crypto)": {"percent_fee": 1.01, "fixed_fee_usd": 0.01, "enabled": True},
}

# Комиссия Steam при продаже по умолчанию: 10% CS2 + 5% Steam = 15%.
DEFAULT_STEAM_FEE_PERCENT = 15.0

# Для целочисленных валют комиссия Steam рассчитывается фиксированным
# разбиением 10% (CS2) + 5% (Steam); общее поле "комиссия %" в интерфейсе
# на такие валюты не влияет.
STEAM_CS2_FEE_PERCENT = 10.0
STEAM_STEAM_FEE_PERCENT = 5.0

# Валюты для отображения результатов (символы).
CURRENCIES = ["$", "€", "₴", "₽", "£"]
DEFAULT_CURRENCY = "$"

# Грубые стартовые курсы "сколько валюты за 1 USD" (РЕДАКТИРУЕМЫЕ значения по
# умолчанию для поля конвертации фиксы; курсы меняются — это лишь подсказка).
USD_RATE_DEFAULTS = {"€": 0.92, "₴": 41.0, "₽": 90.0, "£": 0.79}

# Валюты, у которых на Торговой площадке Steam НЕТ дробной части: цены и
# комиссии выражаются только в целых единицах. Указаны и символы, и буквенные
# коды (гривна, иена, вона, чилийское песо, индонезийская рупия).
INTEGER_CURRENCIES = ["₴", "¥", "₩", "CLP", "IDR"]

# Текстовые псевдонимы тех же валют для распознавания по коду в свободном вводе
# (продвинутый режим). Множество нормализовано к нижнему регистру.
_INTEGER_CURRENCY_ALIASES = {
    "₴", "uah", "грн", "uah.", "¥", "jpy", "yen", "иена",
    "₩", "krw", "won", "вона", "clp", "idr", "rp",
}

# Коды/символы, означающие доллар США.
USD_CODES = {"usd", "$", "usd.", "us$"}

# Языки: отображаемое имя -> код.
LANG_OPTIONS = {"English": "en", "Русский": "ru", "Українська": "uk"}
DEFAULT_LANG_NAME = "English"   # язык интерфейса по умолчанию


# ===========================================================================
# ЛОКАЛИЗАЦИЯ (i18n)
# ===========================================================================
# Английские строки используются как ключи (паттерн gettext). Для en функция
# возвращает сам ключ; исключение — спец-ключи (например, MODE1_FORMULAS),
# для которых английский текст хранится в TRANSLATIONS["en"].

_CURRENT_LANG = "en"


def set_language(code):
    """Задаёт активный язык интерфейса ('en' | 'ru' | 'uk')."""
    global _CURRENT_LANG
    _CURRENT_LANG = code if code in ("en", "ru", "uk") else "en"


def _(key):
    """Возвращает перевод строки key для активного языка.

    Сначала ищем ключ в словаре активного языка (для en там лежат только
    спец-ключи вроде формул). Если не нашли — возвращаем сам ключ, который
    для английского и является готовой строкой (безопасный fallback).
    """
    return TRANSLATIONS.get(_CURRENT_LANG, {}).get(key, key)


# Словарь переводов. Плейсхолдеры в фигурных скобках ({a}, {amount}, ...)
# СОХРАНЯЮТСЯ во всех языках — подстановка значений делается через .format().
TRANSLATIONS = {
    # Для английского храним только строки, чьё значение отличается от ключа.
    "en": {
        "MODE1_FORMULAS":
            "- **Real spent** = (site price × qty) × (1 + fee% / 100) + fixed USD fee (converted)\n"
            "- **Steam received** = seller subtotal × qty. The subtotal is derived from the buyer "
            "price using Steam's exact fee model: each fee is floored (truncated) with a 1-unit "
            "minimum, computed in the currency's smallest unit — whole units for integer currencies, "
            "cents otherwise.\n"
            "- **Net profit** = Steam received − Real spent\n"
            "- **Profit %** = Net profit / Real spent × 100\n\n"
            "In advanced mode each side is first computed in its own currency, then converted to the "
            "spent (base) currency via your rates.",
        "MODE2_FORMULAS":
            "- **Real price (site)** = (site price × qty) × (1 + fee% / 100) + fixed USD fee (converted)\n"
            "- **Real price (Steam)** = (Steam price × qty) / (1 + top-up profit% / 100)\n"
            "- **Savings** = |site real price − Steam real price| (in the base currency when advanced).",
        "MODE3_FORMULAS":
            "- **Steam balance spent** = Steam purchase price × qty\n"
            "- **Real Steam cost** = Steam balance spent / (1 + top-up profit% / 100)  *(only when top-up profit is set)*\n"
            "- **Gross site revenue** = site sell price × qty\n"
            "- **After sales fee** = gross revenue × (1 − sales fee% / 100)\n"
            "- **Real money received** = after sales fee × (1 − withdrawal fee% / 100) − fixed USD fee (converted)\n"
            "- **Cashout ratio** = real money received / Real Steam cost × 100  *(or / Steam balance spent when no top-up profit)*\n"
            "- **Net profit / loss** = real money received − Real Steam cost\n\n"
            "In advanced mode the site side and the Steam side are each computed in their own currency, "
            "then converted to the base (card) currency via your rates.",
        "Real Steam cost (with top-up)": "Real Steam cost (with top-up)",
        "Effective cashout ratio": "Effective cashout ratio",
        "Top-up profit factored in. Ratio > 100% means you profit even after cashing out.":
            "Top-up profit factored in. Ratio > 100% means you profit even after cashing out.",
        # --- Режим 4 ---
        "Where to sell more profitably?": "Where to sell more profitably?",
        "We compare selling a skin on a third-party site (then topping up Steam at a profit) "
        "versus selling it directly on the Steam Market.":
            "We compare selling a skin on a third-party site (then topping up Steam at a profit) "
            "versus selling it directly on the Steam Market.",
        "Sell on third-party site → top up Steam": "Sell on third-party site → top up Steam",
        "Sell on Steam Market directly": "Sell on Steam Market directly",
        "Steam sell price (buyer pays)": "Steam sell price (buyer pays)",
        "Steam Market fee (%)": "Steam Market fee (%)",
        "Steam balance via site (with top-up)": "Steam balance via site (with top-up)",
        "Steam balance via Steam Market": "Steam balance via Steam Market",
        "Real money from site: {amount}": "Real money from site: {amount}",
        "Selling via site and topping up Steam is more profitable. "
        "Extra Steam balance: {amount}.":
            "Selling via site and topping up Steam is more profitable. "
            "Extra Steam balance: {amount}.",
        "Selling on Steam Market is more profitable. "
        "Extra Steam balance: {amount}.":
            "Selling on Steam Market is more profitable. "
            "Extra Steam balance: {amount}.",
        "Both options yield the same Steam balance.":
            "Both options yield the same Steam balance.",
        "MODE4_FORMULAS":
            "**Side A — Sell on site, top up Steam:**\n"
            "- Gross revenue = site sell price × qty\n"
            "- After sales fee = gross × (1 − sales fee% / 100)\n"
            "- Real money = after sales fee × (1 − withdrawal fee% / 100) − fixed fee\n"
            "- **Steam balance (A)** = real money × (1 + top-up profit% / 100)\n\n"
            "**Side B — Sell on Steam Market directly:**\n"
            "- **Steam balance (B)** = seller's cut from Steam Market × qty\n"
            "  *(Steam takes ~15% for CS2: 10% publisher + 5% platform; "
            "  for integer currencies the exact Valve rounding model is used)*\n\n"
            "**Comparison:** whichever side gives more Steam balance is recommended.",
        # --- Режим 5 ---
        "Best rarity to buy (collection)": "Best rarity to buy (collection)",
        "We rank which rarity in a collection is the best buy, based on the price ratio "
        "between adjacent rarities (10 lower-rarity items trade up into 1 higher-rarity item).":
            "We rank which rarity in a collection is the best buy, based on the price ratio "
            "between adjacent rarities (10 lower-rarity items trade up into 1 higher-rarity item).",
        "Enter prices in ONE currency. Use one float tier (or the tier that best fits your goal): "
        "for most filler the result is nearly the same regardless of quality; it only matters for "
        "low-float crafts (0.01+). Leave a rarity at 0 to exclude it from the collection.":
            "Enter prices in ONE currency. Use one float tier (or the tier that best fits your goal): "
            "for most filler the result is nearly the same regardless of quality; it only matters for "
            "low-float crafts (0.01+). Leave a rarity at 0 to exclude it from the collection.",
        "Rarity prices": "Rarity prices",
        "Price (0 = not in collection)": "Price (0 = not in collection)",
        "Rarity": "Rarity",
        "Price": "Price",
        "Ratio": "Ratio",
        "Rank": "Rank",
        "Comment": "Comment",
        "Enter at least two rarity prices to compare.": "Enter at least two rarity prices to compare.",
        "Best buy: {rarity} (rank {rank})": "Best buy: {rarity} (rank {rank})",
        "Ranking (higher = better buy)": "Ranking (higher = better buy)",
        "{n}× this rarity = one rarity above": "{n}× this rarity = one rarity above",
        "this rarity = {n}× the rarity below": "this rarity = {n}× the rarity below",
        "rarity_consumer": "Consumer Grade (grey)",
        "rarity_industrial": "Industrial Grade (light blue)",
        "rarity_milspec": "Mil-Spec (blue)",
        "rarity_restricted": "Restricted (purple)",
        "rarity_classified": "Classified (pink)",
        "rarity_covert": "Covert (red)",
        "rk_over": "overpriced — bad buy",
        "rk_over_slight": "slightly overpriced",
        "rk_normal": "normal average ratio",
        "rk_good": "a bit better than average",
        "rk_under": "underpriced — good buy",
        "rk_under_susp": "underpriced, suspicious — check liquidity",
        "rk_exp": "expensive vs lower tier",
        "rk_exp_slight": "a bit expensive",
        "rk_cheap": "cheap vs lower tier — good buy",
        "rk_cheap_susp": "very cheap, suspicious — check liquidity",
        "Enter the price you consider fair for each rarity. Tick the box if you "
        "find that rarity's skins beautiful or especially liquid.":
            "Enter the price you consider fair for each rarity. Tick the box if you "
            "find that rarity's skins beautiful or especially liquid.",
        "Beautiful / liquid?": "Beautiful / liquid?",
        "rk_top_note": "(Top rarity: it can't be crafted up and its supply only grows, "
                       "so its rank carries a penalty.)",
        "MODE5_FORMULAS":
            "For each rarity except the highest, ratio = **price(rarity above) / price(this rarity)** "
            "— how many of this rarity, by price, equal one item of the rarity above. A trade-up turns "
            "10 of one rarity into 1 of the next, so a **bigger ratio** means this rarity is cheap "
            "relative to what it becomes → a better buy:\n\n"
            "- ≤ 2 → **E** (this tier overpriced)\n"
            "- 2–4 → **D**\n"
            "- 4–5.5 → **C** (normal)\n"
            "- 5.5–6.5 → **B**\n"
            "- 6.5–8 → **A** (this tier underpriced)\n"
            "- 8–10 → **A+**\n"
            "- > 10 → **A++** (unusual — 10 of these craft 1 above; check the higher tier's liquidity)\n\n"
            "The **highest** rarity is scored in reverse (nothing is above it): its ratio vs the tier "
            "below is flipped, then a penalty is applied (−2 if it lands on A or above, −1 for B/C/D/E) "
            "because the top rarity can't be crafted upward and its supply only grows.\n\n"
            "**Beauty / liquidity:** ticking a rarity adds +0.5 to its ratio and to the tier one below, "
            "+0.25 to the tier two below (nothing three below); it never affects a rarity above the "
            "ticked one. For the top rarity the bonus instead improves its reversed score.\n\n"
            "Empty/0 prices are skipped, so collections missing some rarities are handled. "
            "This is a heuristic on the prices you enter, not financial advice.",
    },
    "ru": {
        # --- сайдбар / общее ---
        "Settings": "Настройки",
        "Language": "Язык",
        "Display currency": "Валюта отображения",
        "Advanced currency mode (cross-rates)": "Продвинутый режим валют (кросс-курсы)",
        "When enabled, all modes let you set separate currencies for your card, the site, and Steam.":
            "Если включено, во всех режимах можно задать отдельные валюты для карты, сайта и Steam.",
        "CS2 Skin Investing Toolkit": "Инструментарий инвестора CS2",
        "© 2026 Yev Capital. Not affiliated with Valve Corp. Steam and CS2 are trademarks of Valve Corporation.":
            "© 2026 Yev Capital. Не связано с Valve Corp. Steam и CS2 являются торговыми марками Valve Corporation.",
        "This is an analytical tool, not financial advice. All investments carry risks.":
            "Это аналитический инструмент, а не финансовая рекомендация. Все инвестиции сопряжены с рисками.",
        "All prices are entered manually. This is a calculator, not financial advice.":
            "Все цены вводятся вручную. Это калькулятор, а не финансовая рекомендация.",
        "Steam balance top-up profit calculator and skin purchase analyzer":
            "Калькулятор выгоды пополнения баланса Steam и анализа покупок скинов",
        # --- вкладки ---
        "Balance top-up (profit)": "Пополнение баланса (профит)",
        "Where to buy cheaper?": "Где купить выгоднее?",
        # --- кнопка / общие поля ---
        "Calculate": "Рассчитать",
        "Press Calculate to see the results.": "Нажмите «Рассчитать», чтобы увидеть результат.",
        "Quantity": "Количество предметов",
        # --- блок комиссии ---
        "Fee template": "Шаблон комиссии сайта",
        "Presets for popular sites. Manual input is also available.":
            "Шаблоны популярных сайтов. Также доступен ручной ввод.",
        "Account for top-up fee": "Учитывать комиссию пополнения",
        "Top-up fee (%)": "Комиссия пополнения (%)",
        "Fixed fee (USD)": "Фиксированная комиссия (USD)",
        "Manual input": "Ручной ввод",
        "USD fixed fee converted via your existing cross-rate.":
            "Фиксированная комиссия USD конвертирована по вашему кросс-курсу.",
        # --- Режим 1 ---
        "Steam balance top-up calculator": "Калькулятор пополнения баланса Steam",
        "We calculate the final profit from buying a skin on a third-party site and selling it on the Steam Market.":
            "Считаем итоговый плюс при покупке скина на стороннем сайте и его продаже на Торговой площадке Steam.",
        "Purchase (third-party site)": "Покупка (сторонний сайт)",
        "Skin price on third-party site": "Стоимость скина на стороннем сайте",
        "Sale (Steam Market)": "Продажа (ТП Steam)",
        "Steam sale price": "Цена продажи на ТП Steam",
        "Steam sale fee (%)": "Комиссия Steam при продаже (%)",
        "Default 15% = 10% CS2 fee + 5% Steam fee.":
            "По умолчанию 15% = 10% комиссия CS2 + 5% комиссия Steam.",
        "Currency without cents (integers only)": "Валюта без копеек (целые числа)",
        "Forces integer Steam pricing. Auto-enabled for ₴ / UAH.":
            "Включает целочисленные цены Steam. Для ₴ / UAH включается автоматически.",
        "For integer currencies the 10% + 5% model with nearest rounding is used; the % field above is ignored.":
            "Для целочисленных валют используется модель 10% + 5% с округлением до ближайшего; поле % выше не учитывается.",
        "Cross-currency settings": "Настройки кросс-курсов",
        "Spent currency (e.g. UAH)": "Валюта затрат (например, UAH)",
        "Site currency (e.g. USD)": "Валюта сайта (например, USD)",
        "Steam currency (e.g. EUR)": "Валюта Steam (например, EUR)",
        "Rate: how many {a} in 1 {b}": "Курс: сколько {a} в 1 {b}",
        "Both rates are in the spent currency per 1 unit (a common base).":
            "Оба курса заданы в валюте затрат за 1 единицу (приведение к единому знаменателю).",
        "Site cost": "Затраты на сайте",
        "Steam proceeds": "Получено в Steam",
        "Steam cost": "Стоимость в Steam",
        "Results": "Результаты",
        "Real spent": "Реальные затраты",
        "Steam received": "Получено на Steam",
        "Net profit": "Чистый плюс",
        "Buyer pays {buyer} · you receive {seller} (per item)":
            "Покупатель платит {buyer} · вы получаете {seller} (за 1 шт.)",
        "Steam fees are floored to whole units with a 1-unit minimum, following Steam's exact fee model.":
            "Комиссии Steam округляются вниз до целых единиц с минимумом в одну единицу — по точной модели Steam.",
        "Price {x} is impossible in Steam for integer currencies. Rounded to the nearest possible: {y}.":
            "Цена {x} невозможна в Steam для целочисленных валют. Округлено до ближайшей возможной: {y}.",
        "Enter a skin price to see the calculation.": "Введите стоимость скина, чтобы увидеть расчёт.",
        "Top-up in profit: +{amount} ({percent}).": "Пополнение в плюс: +{amount} ({percent}).",
        "Top-up at a loss: {amount} ({percent}).": "Пополнение в минус: {amount} ({percent}).",
        "Break-even result.": "Нулевой результат — выходите в ноль.",
        "Calculation formulas": "Формулы расчёта",
        "MODE1_FORMULAS":
            "- **Реальные затраты** = (цена на сайте × кол-во) × (1 + %комиссии / 100) + фикса USD (конвертированная)\n"
            "- **Получено на Steam** = промежуточный итог продавца × кол-во. Итог выводится из цены "
            "покупателя по точной модели Steam: каждая комиссия округляется вниз (отбрасывание дробной "
            "части) с минимумом в одну единицу и считается в наименьшей единице валюты — целые единицы "
            "для целочисленных валют, копейки/центы для остальных.\n"
            "- **Чистый плюс** = Получено на Steam − Реальные затраты\n"
            "- **Процент плюса** = Чистый плюс / Реальные затраты × 100\n\n"
            "В продвинутом режиме каждая сторона сначала считается в своей валюте, и только потом "
            "приводится к валюте затрат (базовой) по вашим курсам.",
        # --- Режим 2 ---
        "We compare buying a skin directly on a third-party site with real money versus buying it on the Steam Market with a balance topped up 'in profit'.":
            "Сравниваем покупку скина напрямую на стороннем сайте за реальные деньги "
            "против покупки на ТП Steam за баланс, пополненный «в плюс».",
        "Buy on Steam Market": "Покупка на ТП Steam",
        "Current Steam Market price": "Текущая стоимость скина на ТП Steam",
        "Steam top-up profit (%)": "Процент плюса пополнения Steam (%)",
        "How profitably you topped up Steam earlier. Example: spent 10 real, got 15 on balance → 50% profit.":
            "Насколько выгодно вы ранее пополнили Steam. Например: потратили 10 реальных, "
            "получили 15 на баланс → плюс 50%.",
        "Buy on third-party site": "Покупка на стороннем сайте",
        "Results comparison": "Результаты сравнения",
        "Real price (third-party site)": "Реальная цена (сторонний сайт)",
        "Real price (Steam, with profit)": "Реальная цена (Steam, с учётом плюса)",
        "Enter data to see the comparison.": "Введите данные, чтобы увидеть сравнение.",
        "Cheaper to buy on Steam. Savings: {amount}.": "Выгоднее купить в Steam. Экономия: {amount}.",
        "Cheaper to buy on the third-party site. Savings: {amount}.":
            "Выгоднее купить на стороннем сайте. Экономия: {amount}.",
        "Both options cost the same in real money.": "Оба варианта равнозначны по реальной стоимости.",
        "MODE2_FORMULAS":
            "- **Реальная цена (сайт)** = (цена на сайте × кол-во) × (1 + %комиссии / 100) + фикса USD (конвертированная)\n"
            "- **Реальная цена (Steam)** = (цена на ТП × кол-во) / (1 + %плюса / 100)\n"
            "- **Экономия** = модуль разницы между двумя реальными ценами (в базовой валюте при кросс-курсах).",
        # --- Режим 3 ---
        "Withdrawal (Cashout)": "Вывод средств (Cashout)",
        "Steam balance cashout calculator": "Калькулятор вывода баланса Steam",
        "We calculate how much real money you receive by buying a skin on the Steam Market, "
        "selling it on a third-party site, and withdrawing the proceeds.":
            "Считаем, сколько реальных денег вы получите, купив скин на Торговой площадке Steam, "
            "продав его на стороннем сайте и выведя выручку.",
        "Purchase (Steam Market)": "Покупка (ТП Steam)",
        "Steam purchase price": "Цена покупки в Steam",
        "Withdrawal (third-party site)": "Вывод (сторонний сайт)",
        "Site sell price": "Цена продажи на сайте",
        "Sales fee (%)": "Комиссия сайта за продажу (%)",
        "Withdrawal fee (%)": "Комиссия за вывод (%)",
        "Withdrawal fixed fee (USD)": "Фиксированная комиссия за вывод (USD)",
        "Total Steam spent": "Потрачено Steam баланса",
        "Real money received": "Получено реальных денег",
        "Cashout ratio": "Коэффициент вывода",
        "Net profit / loss": "Чистая прибыль / убыток",
        "Gross site revenue": "Грязная выручка на сайте",
        "After sales fee": "После комиссии за продажу",
        "Enter prices to see the cashout calculation.":
            "Введите цены, чтобы увидеть расчёт вывода.",
        "The higher the cashout ratio, the more of your Steam balance reaches your card.":
            "Чем выше коэффициент вывода, тем большая часть баланса Steam доходит до карты.",
        "MODE3_FORMULAS":
            "- **Потрачено баланса Steam** = цена покупки в Steam × кол-во\n"
            "- **Реальные затраты Steam** = потрачено баланса Steam / (1 + % плюса пополнения / 100)  *(только если задан % плюса)*\n"
            "- **Грязная выручка на сайте** = цена продажи на сайте × кол-во\n"
            "- **После комиссии за продажу** = грязная выручка × (1 − %комиссии продажи / 100)\n"
            "- **Получено реальных денег** = после комиссии за продажу × (1 − %комиссии вывода / 100) − фикса USD (конвертированная)\n"
            "- **Коэффициент вывода** = получено реальных денег / Реальные затраты Steam × 100  *(или / баланс Steam, если плюс не задан)*\n"
            "- **Чистая прибыль / убыток** = получено реальных денег − Реальные затраты Steam\n\n"
            "В продвинутом режиме сторона сайта и сторона Steam считаются каждая в своей валюте, "
            "а затем приводятся к базовой валюте (карты) по вашим курсам.",
        "Real Steam cost (with top-up)": "Реальные затраты Steam (с плюсом)",
        "Effective cashout ratio": "Эффективный коэффициент вывода",
        "Top-up profit factored in. Ratio > 100% means you profit even after cashing out.":
            "Учтён плюс пополнения. Коэффициент > 100% означает, что вы в плюсе даже после вывода.",
        # --- Режим 4 ---
        "Where to sell more profitably?": "Где продать выгоднее?",
        "We compare selling a skin on a third-party site (then topping up Steam at a profit) "
        "versus selling it directly on the Steam Market.":
            "Сравниваем продажу скина на стороннем сайте (с последующим пополнением Steam в плюс) "
            "и продажу напрямую через Steam Market.",
        "Sell on third-party site → top up Steam": "Продать на стороннем сайте → пополнить Steam",
        "Sell on Steam Market directly": "Продать на Steam Market напрямую",
        "Steam sell price (buyer pays)": "Цена на Steam Market (платит покупатель)",
        "Steam Market fee (%)": "Комиссия Steam Market (%)",
        "Steam balance via site (with top-up)": "Баланс Steam через сайт (с пополнением)",
        "Steam balance via Steam Market": "Баланс Steam через Steam Market",
        "Real money from site: {amount}": "Реальных денег с сайта: {amount}",
        "Selling via site and topping up Steam is more profitable. "
        "Extra Steam balance: {amount}.":
            "Выгоднее продать через сайт и пополнить Steam. "
            "Дополнительный баланс: {amount}.",
        "Selling on Steam Market is more profitable. "
        "Extra Steam balance: {amount}.":
            "Выгоднее продать на Steam Market напрямую. "
            "Дополнительный баланс: {amount}.",
        "Both options yield the same Steam balance.":
            "Оба варианта дают одинаковый Steam-баланс.",
        "MODE4_FORMULAS":
            "**Вариант А — Продать на сайте, пополнить Steam:**\n"
            "- Грязная выручка = цена продажи на сайте × кол-во\n"
            "- После комиссии продажи = грязная выручка × (1 − %комиссии продажи / 100)\n"
            "- Реальные деньги = после комиссии × (1 − %комиссии вывода / 100) − фикса\n"
            "- **Баланс Steam (А)** = реальные деньги × (1 + %плюса пополнения / 100)\n\n"
            "**Вариант Б — Продать на Steam Market напрямую:**\n"
            "- **Баланс Steam (Б)** = выручка продавца с учётом комиссии Steam × кол-во\n"
            "  *(Steam удерживает ~15% для CS2: 10% издательская + 5% площадка; "
            "  для целочисленных валют применяется точная модель округления Valve)*\n\n"
            "**Сравнение:** рекомендуется вариант, дающий больший Steam-баланс.",
        # --- Режим 5 ---
        "Best rarity to buy (collection)": "Лучшее качество для покупки (коллекция)",
        "We rank which rarity in a collection is the best buy, based on the price ratio "
        "between adjacent rarities (10 lower-rarity items trade up into 1 higher-rarity item).":
            "Оцениваем, какое качество в коллекции выгоднее покупать, по соотношению цен соседних "
            "качеств (10 предметов нижнего качества через контракт обмена дают 1 предмет выше).",
        "Enter prices in ONE currency. Use one float tier (or the tier that best fits your goal): "
        "for most filler the result is nearly the same regardless of quality; it only matters for "
        "low-float crafts (0.01+). Leave a rarity at 0 to exclude it from the collection.":
            "Вводи цены в ОДНОЙ валюте. Используй одно качество флоата (или наиболее подходящее под "
            "твою цель): для большинства филлеров результат почти одинаков вне зависимости от качества; "
            "это важно только для крафтов низких флотов (0,01 и выше). Оставь 0, чтобы исключить "
            "качество из коллекции.",
        "Rarity prices": "Цены по качествам",
        "Price (0 = not in collection)": "Цена (0 = нет в коллекции)",
        "Rarity": "Качество",
        "Price": "Цена",
        "Ratio": "Соотношение",
        "Rank": "Ранг",
        "Comment": "Комментарий",
        "Enter at least two rarity prices to compare.":
            "Введи цены минимум для двух качеств для сравнения.",
        "Best buy: {rarity} (rank {rank})": "Выгоднее всего покупать: {rarity} (ранг {rank})",
        "Ranking (higher = better buy)": "Рейтинг (выше — выгоднее покупать)",
        "{n}× this rarity = one rarity above": "{n}× этого качества = одно качество выше",
        "this rarity = {n}× the rarity below": "это качество = {n}× качества ниже",
        "rarity_consumer": "Ширпотреб (серое)",
        "rarity_industrial": "Промышленное (голубое)",
        "rarity_milspec": "Армейское (синее)",
        "rarity_restricted": "Запрещённое (фиолетовое)",
        "rarity_classified": "Засекреченное (розовое)",
        "rarity_covert": "Тайное (красное)",
        "rk_over": "переоценено — невыгодно покупать",
        "rk_over_slight": "слегка переоценено",
        "rk_normal": "нормальное среднее соотношение",
        "rk_good": "чуть лучше среднего",
        "rk_under": "недооценено — выгодно покупать",
        "rk_under_susp": "недооценено, подозрительно — проверь ликвидность",
        "rk_exp": "дорогое относительно качества ниже",
        "rk_exp_slight": "дороговато",
        "rk_cheap": "дёшево относительно качества ниже — выгодно",
        "rk_cheap_susp": "очень дёшево, подозрительно — проверь ликвидность",
        "Enter the price you consider fair for each rarity. Tick the box if you "
        "find that rarity's skins beautiful or especially liquid.":
            "Укажи цену, которую считаешь справедливой для каждого качества. Отметь галочку, "
            "если скины этого качества красивые или особенно ликвидные.",
        "Beautiful / liquid?": "Красивое / ликвидное?",
        "rk_top_note": "(Высшее качество: его нельзя скрафтить выше, а предложение только "
                       "растёт, поэтому к рангу применён штраф.)",
        "MODE5_FORMULAS":
            "Для каждого качества, кроме высшего, соотношение = **цена качества выше / цена этого "
            "качества** — сколько штук этого качества по цене равны одному предмету качества выше. "
            "Контракт превращает 10 предметов одного качества в 1 предмет следующего, поэтому "
            "**большее соотношение** означает, что качество дёшево относительно того, чем становится "
            "→ выгоднее покупать:\n\n"
            "- ≤ 2 → **E** (это качество переоценено)\n"
            "- 2–4 → **D**\n"
            "- 4–5.5 → **C** (норма)\n"
            "- 5.5–6.5 → **B**\n"
            "- 6.5–8 → **A** (это качество недооценено)\n"
            "- 8–10 → **A+**\n"
            "- > 10 → **A++** (необычно — 10 этих крафтят 1 выше; проверь ликвидность верхнего)\n\n"
            "**Высшее** качество считается наоборот (выше него ничего нет): его соотношение к качеству "
            "ниже реверсируется, затем применяется штраф (−2, если попадает на A и выше, −1 для B/C/D/E), "
            "потому что высшее качество нельзя скрафтить дальше, а его предложение только растёт.\n\n"
            "**Красота / ликвидность:** галочка добавляет +0.5 к соотношению этого качества и качества "
            "на 1 ниже, +0.25 к качеству на 2 ниже (на 3 ниже — ничего); на качество выше отмеченного "
            "бонус не влияет. Для высшего качества бонус, наоборот, улучшает его реверс-оценку.\n\n"
            "Пустые цены/0 пропускаются, поэтому коллекции без некоторых качеств учитываются. "
            "Это эвристика по введённым ценам, а не финансовая рекомендация.",
    },
    "uk": {
        # --- сайдбар / загальне ---
        "Settings": "Налаштування",
        "Language": "Мова",
        "Display currency": "Валюта відображення",
        "Advanced currency mode (cross-rates)": "Розширений режим валют (крос-курси)",
        "When enabled, all modes let you set separate currencies for your card, the site, and Steam.":
            "Якщо увімкнено, в усіх режимах можна задати окремі валюти для картки, сайту та Steam.",
        "CS2 Skin Investing Toolkit": "Інструментарій інвестора CS2",
        "© 2026 Yev Capital. Not affiliated with Valve Corp. Steam and CS2 are trademarks of Valve Corporation.":
            "© 2026 Yev Capital. Не пов'язано з Valve Corp. Steam та CS2 є торговими марками Valve Corporation.",
        "This is an analytical tool, not financial advice. All investments carry risks.":
            "Це аналітичний інструмент, а не фінансова порада. Усі інвестиції пов'язані з ризиками.",
        "All prices are entered manually. This is a calculator, not financial advice.":
            "Усі ціни вводяться вручну. Це калькулятор, а не фінансова порада.",
        "Steam balance top-up profit calculator and skin purchase analyzer":
            "Калькулятор вигоди поповнення балансу Steam та аналізу покупок скінів",
        # --- вкладки ---
        "Balance top-up (profit)": "Поповнення балансу (профіт)",
        "Where to buy cheaper?": "Де купити вигідніше?",
        # --- кнопка / загальні поля ---
        "Calculate": "Розрахувати",
        "Press Calculate to see the results.": "Натисніть «Розрахувати», щоб побачити результат.",
        "Quantity": "Кількість предметів",
        # --- блок комісії ---
        "Fee template": "Шаблон комісії сайту",
        "Presets for popular sites. Manual input is also available.":
            "Шаблони популярних сайтів. Також доступне ручне введення.",
        "Account for top-up fee": "Враховувати комісію поповнення",
        "Top-up fee (%)": "Комісія поповнення (%)",
        "Fixed fee (USD)": "Фіксована комісія (USD)",
        "Manual input": "Ручне введення",
        "USD fixed fee converted via your existing cross-rate.":
            "Фіксована комісія USD конвертована за вашим крос-курсом.",
        # --- Режим 1 ---
        "Steam balance top-up calculator": "Калькулятор поповнення балансу Steam",
        "We calculate the final profit from buying a skin on a third-party site and selling it on the Steam Market.":
            "Рахуємо підсумковий плюс при купівлі скіна на сторонньому сайті та його продажу на Торговому майданчику Steam.",
        "Purchase (third-party site)": "Купівля (сторонній сайт)",
        "Skin price on third-party site": "Вартість скіна на сторонньому сайті",
        "Sale (Steam Market)": "Продаж (ТМ Steam)",
        "Steam sale price": "Ціна продажу на ТМ Steam",
        "Steam sale fee (%)": "Комісія Steam при продажу (%)",
        "Default 15% = 10% CS2 fee + 5% Steam fee.":
            "За замовчуванням 15% = 10% комісія CS2 + 5% комісія Steam.",
        "Currency without cents (integers only)": "Валюта без копійок (цілі числа)",
        "Forces integer Steam pricing. Auto-enabled for ₴ / UAH.":
            "Вмикає цілочисельні ціни Steam. Для ₴ / UAH вмикається автоматично.",
        "For integer currencies the 10% + 5% model with nearest rounding is used; the % field above is ignored.":
            "Для цілочисельних валют використовується модель 10% + 5% із заокругленням до найближчого; поле % вище не враховується.",
        "Cross-currency settings": "Налаштування крос-курсів",
        "Spent currency (e.g. UAH)": "Валюта витрат (наприклад, UAH)",
        "Site currency (e.g. USD)": "Валюта сайту (наприклад, USD)",
        "Steam currency (e.g. EUR)": "Валюта Steam (наприклад, EUR)",
        "Rate: how many {a} in 1 {b}": "Курс: скільки {a} в 1 {b}",
        "Both rates are in the spent currency per 1 unit (a common base).":
            "Обидва курси задані у валюті витрат за 1 одиницю (приведення до спільного знаменника).",
        "Site cost": "Витрати на сайті",
        "Steam proceeds": "Отримано в Steam",
        "Steam cost": "Вартість у Steam",
        "Results": "Результати",
        "Real spent": "Реальні витрати",
        "Steam received": "Отримано на Steam",
        "Net profit": "Чистий плюс",
        "Buyer pays {buyer} · you receive {seller} (per item)":
            "Покупець платить {buyer} · ви отримуєте {seller} (за 1 шт.)",
        "Steam fees are floored to whole units with a 1-unit minimum, following Steam's exact fee model.":
            "Комісії Steam округлюються вниз до цілих одиниць з мінімумом в одну одиницю — за точною моделлю Steam.",
        "Price {x} is impossible in Steam for integer currencies. Rounded to the nearest possible: {y}.":
            "Ціна {x} неможлива в Steam для цілочисельних валют. Заокруглено до найближчої можливої: {y}.",
        "Enter a skin price to see the calculation.": "Введіть вартість скіна, щоб побачити розрахунок.",
        "Top-up in profit: +{amount} ({percent}).": "Поповнення в плюс: +{amount} ({percent}).",
        "Top-up at a loss: {amount} ({percent}).": "Поповнення в мінус: {amount} ({percent}).",
        "Break-even result.": "Нульовий результат — виходите в нуль.",
        "Calculation formulas": "Формули розрахунку",
        "MODE1_FORMULAS":
            "- **Реальні витрати** = (ціна на сайті × к-сть) × (1 + %комісії / 100) + фікса USD (конвертована)\n"
            "- **Отримано на Steam** = проміжний підсумок продавця × к-сть. Підсумок виводиться з ціни "
            "покупця за точною моделлю Steam: кожна комісія округлюється вниз (відкидання дробової "
            "частини) з мінімумом в одну одиницю і рахується в найменшій одиниці валюти — цілі одиниці "
            "для цілочисельних валют, копійки/центи для інших.\n"
            "- **Чистий плюс** = Отримано на Steam − Реальні витрати\n"
            "- **Відсоток плюса** = Чистий плюс / Реальні витрати × 100\n\n"
            "У розширеному режимі кожна сторона спочатку рахується у своїй валюті, і лише потім "
            "приводиться до валюти витрат (базової) за вашими курсами.",
        # --- Режим 2 ---
        "We compare buying a skin directly on a third-party site with real money versus buying it on the Steam Market with a balance topped up 'in profit'.":
            "Порівнюємо купівлю скіна напряму на сторонньому сайті за реальні гроші "
            "проти купівлі на ТМ Steam за баланс, поповнений «у плюс».",
        "Buy on Steam Market": "Купівля на ТМ Steam",
        "Current Steam Market price": "Поточна вартість скіна на ТМ Steam",
        "Steam top-up profit (%)": "Відсоток плюса поповнення Steam (%)",
        "How profitably you topped up Steam earlier. Example: spent 10 real, got 15 on balance → 50% profit.":
            "Наскільки вигідно ви раніше поповнили Steam. Наприклад: витратили 10 реальних, "
            "отримали 15 на баланс → плюс 50%.",
        "Buy on third-party site": "Купівля на сторонньому сайті",
        "Results comparison": "Результати порівняння",
        "Real price (third-party site)": "Реальна ціна (сторонній сайт)",
        "Real price (Steam, with profit)": "Реальна ціна (Steam, з урахуванням плюса)",
        "Enter data to see the comparison.": "Введіть дані, щоб побачити порівняння.",
        "Cheaper to buy on Steam. Savings: {amount}.": "Вигідніше купити в Steam. Економія: {amount}.",
        "Cheaper to buy on the third-party site. Savings: {amount}.":
            "Вигідніше купити на сторонньому сайті. Економія: {amount}.",
        "Both options cost the same in real money.": "Обидва варіанти рівнозначні за реальною вартістю.",
        "MODE2_FORMULAS":
            "- **Реальна ціна (сайт)** = (ціна на сайті × к-сть) × (1 + %комісії / 100) + фікса USD (конвертована)\n"
            "- **Реальна ціна (Steam)** = (ціна на ТМ × к-сть) / (1 + %плюса / 100)\n"
            "- **Економія** = модуль різниці між двома реальними цінами (у базовій валюті за крос-курсів).",
        # --- Режим 3 ---
        "Withdrawal (Cashout)": "Виведення коштів (Cashout)",
        "Steam balance cashout calculator": "Калькулятор виведення балансу Steam",
        "We calculate how much real money you receive by buying a skin on the Steam Market, "
        "selling it on a third-party site, and withdrawing the proceeds.":
            "Рахуємо, скільки реальних грошей ви отримаєте, купивши скін на Торговому майданчику Steam, "
            "продавши його на сторонньому сайті та вивівши виручку.",
        "Purchase (Steam Market)": "Купівля (ТМ Steam)",
        "Steam purchase price": "Ціна купівлі в Steam",
        "Withdrawal (third-party site)": "Виведення (сторонній сайт)",
        "Site sell price": "Ціна продажу на сайті",
        "Sales fee (%)": "Комісія сайту за продаж (%)",
        "Withdrawal fee (%)": "Комісія за виведення (%)",
        "Withdrawal fixed fee (USD)": "Фіксована комісія за виведення (USD)",
        "Total Steam spent": "Витрачено Steam балансу",
        "Real money received": "Отримано реальних грошей",
        "Cashout ratio": "Коефіцієнт виведення",
        "Net profit / loss": "Чистий прибуток / збиток",
        "Gross site revenue": "Брудна виручка на сайті",
        "After sales fee": "Після комісії за продаж",
        "Enter prices to see the cashout calculation.":
            "Введіть ціни, щоб побачити розрахунок виведення.",
        "The higher the cashout ratio, the more of your Steam balance reaches your card.":
            "Що вищий коефіцієнт виведення, то більша частина балансу Steam доходить до картки.",
        "MODE3_FORMULAS":
            "- **Витрачено балансу Steam** = ціна купівлі в Steam × к-сть\n"
            "- **Реальні витрати Steam** = витрачено балансу Steam / (1 + % плюса поповнення / 100)  *(лише якщо задано % плюса)*\n"
            "- **Брудна виручка на сайті** = ціна продажу на сайті × к-сть\n"
            "- **Після комісії за продаж** = брудна виручка × (1 − %комісії продажу / 100)\n"
            "- **Отримано реальних грошей** = після комісії за продаж × (1 − %комісії виведення / 100) − фікса USD (конвертована)\n"
            "- **Коефіцієнт виведення** = отримано реальних грошей / Реальні витрати Steam × 100  *(або / баланс Steam, якщо плюс не задано)*\n"
            "- **Чистий прибуток / збиток** = отримано реальних грошей − Реальні витрати Steam\n\n"
            "У розширеному режимі сторона сайту та сторона Steam рахуються кожна у своїй валюті, "
            "а потім приводяться до базової валюти (картки) за вашими курсами.",
        "Real Steam cost (with top-up)": "Реальні витрати Steam (з плюсом)",
        "Effective cashout ratio": "Ефективний коефіцієнт виведення",
        "Top-up profit factored in. Ratio > 100% means you profit even after cashing out.":
            "Враховано плюс поповнення. Коефіцієнт > 100% означає, що ви в плюсі навіть після виведення.",
        # --- Режим 4 ---
        "Where to sell more profitably?": "Де продати вигідніше?",
        "We compare selling a skin on a third-party site (then topping up Steam at a profit) "
        "versus selling it directly on the Steam Market.":
            "Порівнюємо продаж скіна на сторонньому сайті (з подальшим поповненням Steam у плюс) "
            "та продаж напряму через Steam Market.",
        "Sell on third-party site → top up Steam": "Продати на сторонньому сайті → поповнити Steam",
        "Sell on Steam Market directly": "Продати на Steam Market напряму",
        "Steam sell price (buyer pays)": "Ціна на Steam Market (платить покупець)",
        "Steam Market fee (%)": "Комісія Steam Market (%)",
        "Steam balance via site (with top-up)": "Баланс Steam через сайт (з поповненням)",
        "Steam balance via Steam Market": "Баланс Steam через Steam Market",
        "Real money from site: {amount}": "Реальних грошей з сайту: {amount}",
        "Selling via site and topping up Steam is more profitable. "
        "Extra Steam balance: {amount}.":
            "Вигідніше продати через сайт і поповнити Steam. "
            "Додатковий баланс: {amount}.",
        "Selling on Steam Market is more profitable. "
        "Extra Steam balance: {amount}.":
            "Вигідніше продати на Steam Market напряму. "
            "Додатковий баланс: {amount}.",
        "Both options yield the same Steam balance.":
            "Обидва варіанти дають однаковий Steam-баланс.",
        "MODE4_FORMULAS":
            "**Варіант А — Продати на сайті, поповнити Steam:**\n"
            "- Брудна виручка = ціна продажу на сайті × к-сть\n"
            "- Після комісії продажу = брудна виручка × (1 − %комісії продажу / 100)\n"
            "- Реальні гроші = після комісії × (1 − %комісії виведення / 100) − фікса\n"
            "- **Баланс Steam (А)** = реальні гроші × (1 + %плюса поповнення / 100)\n\n"
            "**Варіант Б — Продати на Steam Market напряму:**\n"
            "- **Баланс Steam (Б)** = виручка продавця з урахуванням комісії Steam × к-сть\n"
            "  *(Steam утримує ~15% для CS2: 10% видавнича + 5% майданчик; "
            "  для цілочисельних валют застосовується точна модель округлення Valve)*\n\n"
            "**Порівняння:** рекомендується варіант, що дає більший Steam-баланс.",
        # --- Режим 5 ---
        "Best rarity to buy (collection)": "Найкраща якість для купівлі (колекція)",
        "We rank which rarity in a collection is the best buy, based on the price ratio "
        "between adjacent rarities (10 lower-rarity items trade up into 1 higher-rarity item).":
            "Оцінюємо, яку якість у колекції вигідніше купувати, за співвідношенням цін сусідніх "
            "якостей (10 предметів нижчої якості через контракт обміну дають 1 предмет вище).",
        "Enter prices in ONE currency. Use one float tier (or the tier that best fits your goal): "
        "for most filler the result is nearly the same regardless of quality; it only matters for "
        "low-float crafts (0.01+). Leave a rarity at 0 to exclude it from the collection.":
            "Вводь ціни в ОДНІЙ валюті. Використовуй одну якість флоату (або найбільш відповідну до "
            "твоєї мети): для більшості філерів результат майже однаковий незалежно від якості; "
            "це важливо лише для крафтів низьких флоатів (0,01 і вище). Залиш 0, щоб виключити "
            "якість із колекції.",
        "Rarity prices": "Ціни за якостями",
        "Price (0 = not in collection)": "Ціна (0 = немає в колекції)",
        "Rarity": "Якість",
        "Price": "Ціна",
        "Ratio": "Співвідношення",
        "Rank": "Ранг",
        "Comment": "Коментар",
        "Enter at least two rarity prices to compare.":
            "Введи ціни мінімум для двох якостей для порівняння.",
        "Best buy: {rarity} (rank {rank})": "Найвигідніше купувати: {rarity} (ранг {rank})",
        "Ranking (higher = better buy)": "Рейтинг (вище — вигідніше купувати)",
        "{n}× this rarity = one rarity above": "{n}× цієї якості = одна якість вище",
        "this rarity = {n}× the rarity below": "ця якість = {n}× якості нижче",
        "rarity_consumer": "Ширвжиток (сіре)",
        "rarity_industrial": "Промислове (блакитне)",
        "rarity_milspec": "Армійське (синє)",
        "rarity_restricted": "Заборонене (фіолетове)",
        "rarity_classified": "Засекречене (рожеве)",
        "rarity_covert": "Таємне (червоне)",
        "rk_over": "переоцінено — невигідно купувати",
        "rk_over_slight": "трохи переоцінено",
        "rk_normal": "нормальне середнє співвідношення",
        "rk_good": "трохи краще за середнє",
        "rk_under": "недооцінено — вигідно купувати",
        "rk_under_susp": "недооцінено, підозріло — перевір ліквідність",
        "rk_exp": "дороге відносно якості нижче",
        "rk_exp_slight": "дорогувато",
        "rk_cheap": "дешево відносно якості нижче — вигідно",
        "rk_cheap_susp": "дуже дешево, підозріло — перевір ліквідність",
        "Enter the price you consider fair for each rarity. Tick the box if you "
        "find that rarity's skins beautiful or especially liquid.":
            "Вкажи ціну, яку вважаєш справедливою для кожної якості. Постав галочку, "
            "якщо скіни цієї якості гарні або особливо ліквідні.",
        "Beautiful / liquid?": "Гарне / ліквідне?",
        "rk_top_note": "(Найвища якість: її не можна скрафтити вище, а пропозиція лише "
                       "зростає, тому до рангу застосовано штраф.)",
        "MODE5_FORMULAS":
            "Для кожної якості, крім найвищої, співвідношення = **ціна якості вище / ціна цієї "
            "якості** — скільки штук цієї якості за ціною дорівнюють одному предмету якості вище. "
            "Контракт перетворює 10 предметів однієї якості на 1 предмет наступної, тому "
            "**більше співвідношення** означає, що якість дешева відносно того, чим стає "
            "→ вигідніше купувати:\n\n"
            "- ≤ 2 → **E** (ця якість переоцінена)\n"
            "- 2–4 → **D**\n"
            "- 4–5.5 → **C** (норма)\n"
            "- 5.5–6.5 → **B**\n"
            "- 6.5–8 → **A** (ця якість недооцінена)\n"
            "- 8–10 → **A+**\n"
            "- > 10 → **A++** (незвично — 10 цих крафтять 1 вище; перевір ліквідність верхньої)\n\n"
            "**Найвища** якість рахується навпаки (вище неї нічого немає): її співвідношення до якості "
            "нижче реверсується, потім застосовується штраф (−2, якщо потрапляє на A і вище, −1 для "
            "B/C/D/E), бо найвищу якість не можна скрафтити далі, а її пропозиція лише зростає.\n\n"
            "**Краса / ліквідність:** галочка додає +0.5 до співвідношення цієї якості та якості на 1 "
            "нижче, +0.25 до якості на 2 нижче (на 3 нижче — нічого); на якість вище позначеної бонус "
            "не впливає. Для найвищої якості бонус навпаки покращує її реверс-оцінку.\n\n"
            "Порожні ціни/0 пропускаються, тож колекції без деяких якостей враховуються. "
            "Це евристика за введеними цінами, а не фінансова порада.",
    },
}


# ===========================================================================
# МАТЕМАТИЧЕСКИЕ ФУНКЦИИ (чистые, без Streamlit — удобно тестировать)
# ===========================================================================

def calculate_real_spent(site_price, fee_percent=0.0, fixed_fee=0.0, quantity=1):
    """Реальные затраты на покупку предмета(ов) на стороннем сайте.

    Процентная комиссия начисляется на всю сумму заказа (цена × количество),
    фиксированная комиссия добавляется один раз за транзакцию:

        real_spent = (site_price * quantity) * (1 + fee_percent / 100) + fixed_fee

    Аргумент fixed_fee должен быть уже приведён к валюте расчёта; конвертация
    фиксированной комиссии из долларов выполняется в resolve_fixed_fee_in_target.

    Все числовые аргументы приводятся к неотрицательным значениям.
    """
    site_price = max(0.0, float(site_price))
    fee_percent = max(0.0, float(fee_percent))
    fixed_fee = max(0.0, float(fixed_fee))
    quantity = max(1, int(quantity))
    base = site_price * quantity
    return base * (1.0 + fee_percent / 100.0) + fixed_fee


def _split_total_fee(total_fee_percent):
    """Делит общий процент комиссии Steam на издательскую и площадочную части.

    Steam удерживает две отдельные комиссии: издательскую (для CS2 — 10%) и
    комиссию площадки (5%), в сумме 15%. Поле «комиссия %» в интерфейсе задаёт
    суммарный процент; здесь он распределяется пропорционально структуре 10:5,
    поэтому значение по умолчанию 15% даёт ровно (10.0, 5.0).

    Возвращает (cs2_fee_pct, steam_fee_pct).
    """
    total = max(0.0, float(total_fee_percent))
    default_total = STEAM_CS2_FEE_PERCENT + STEAM_STEAM_FEE_PERCENT
    if default_total <= 0:
        return 0.0, 0.0
    cs2 = total * (STEAM_CS2_FEE_PERCENT / default_total)
    steam = total * (STEAM_STEAM_FEE_PERCENT / default_total)
    return cs2, steam


def calculate_exact_steam_revenue(steam_buyer_price, is_integer_currency,
                                  cs2_fee_pct=STEAM_CS2_FEE_PERCENT,
                                  steam_fee_pct=STEAM_STEAM_FEE_PERCENT):
    """Точная модель комиссий Steam: из цены покупателя — выручка продавца.

    Для ЦЕЛОЧИСЛЕННЫХ валют (грн, ¥, ₩, CLP, IDR) модель выверена по реальным
    данным Торговой площадки Steam. Комиссия считается от суммы продавца, каждая
    часть округляется к БЛИЖАЙШЕМУ (round half up) с минимумом в одну единицу:

        fee_cs    = max(1, round(seller * cs2_fee_pct   / 100))
        fee_steam = max(1, round(seller * steam_fee_pct / 100))
        buyer     = seller + fee_cs + fee_steam

    Сумма продавца для запрошенной цены — это МАКСИМАЛЬНЫЙ seller, при котором
    итоговая цена покупателя не превышает запрошенную. Если ровно такая цена
    недостижима (на площадке лот можно выставить только за достижимую цену),
    берётся ближайшая меньшая достижимая.

    Единица расчёта зависит от валюты:
        * целочисленные валюты — целые единицы;
        * остальные (USD, EUR, RUB, …) — центы/копейки (цена × 100, затем / 100).

    Возвращает кортеж в ИСХОДНОМ масштабе валюты:
        (seller_revenue, valid_buyer_price, fee_cs, fee_steam).
    Для цены меньше одной минимальной единицы — нули.

    Деление на ноль исключено: масштаб равен 1 или 100, а делитель оценки
    защищён проверкой суммарного процента.
    """
    price = max(0.0, float(steam_buyer_price))
    scale = 1 if is_integer_currency else 100
    # Перевод цены покупателя в целые единицы/центы (округление ввода к ближайшему).
    desired = int(price * scale + 0.5)
    if desired < 1:
        return 0.0, 0.0, 0.0, 0.0

    cs2_fee_pct = max(0.0, float(cs2_fee_pct))
    steam_fee_pct = max(0.0, float(steam_fee_pct))

    def _fees(seller_units):
        """Комиссии Steam в наименьшей единице валюты.

        Для ЦЕЛОЧИСЛЕННЫХ валют (грн, ¥, ₩ и т.п.) комиссия считается от суммы
        продавца с округлением каждой части к БЛИЖАЙШЕМУ (round half up) и
        минимумом в одну единицу — это поведение Valve, выверенное по реальным
        данным Торговой площадки. Для дробных валют (центы) сохраняется прежний
        расчёт через отбрасывание дробной части (floor) в наименьшей единице.
        """
        if is_integer_currency:
            fc = max(1, int(seller_units * cs2_fee_pct / 100.0 + 0.5))
            fs = max(1, int(seller_units * steam_fee_pct / 100.0 + 0.5))
        else:
            fc = max(1, int(seller_units * cs2_fee_pct / 100.0 + 1e-9))
            fs = max(1, int(seller_units * steam_fee_pct / 100.0 + 1e-9))
        return fc, fs

    total_pct = cs2_fee_pct + steam_fee_pct
    growth = 1.0 + total_pct / 100.0
    estimate = int(desired / growth + 0.5) if growth > 0 else desired

    # Сумма продавца = МАКСИМАЛЬНЫЙ seller, при котором цена покупателя
    # (seller + комиссии) не превышает запрошенную цену. Если ровно эта цена
    # недостижима, берётся ближайшая меньшая достижимая (как на самой площадке:
    # выставить лот можно только за достижимую цену).
    best_seller = 0
    best_buyer = 0
    best_fc = 0
    best_fs = 0
    for seller in range(max(1, estimate - 8), estimate + 9):
        fc, fs = _fees(seller)
        buyer = seller + fc + fs
        if buyer <= desired and seller > best_seller:
            best_seller, best_buyer, best_fc, best_fs = seller, buyer, fc, fs

    if best_seller == 0:
        return 0.0, 0.0, 0.0, 0.0
    return (best_seller / scale, best_buyer / scale,
            best_fc / scale, best_fs / scale)


def calculate_steam_received(steam_price, steam_fee_percent=DEFAULT_STEAM_FEE_PERCENT):
    """Выручка продавца на Steam для валют с дробной частью (в центах/копейках).

    Тонкая обёртка над calculate_exact_steam_revenue: суммарный процент делится
    на издательскую и площадочную части, расчёт ведётся в центах по точной
    модели Steam (floor с минимумом в одну единицу), что устойчивее простого
    деления цены на коэффициент.

    Пример: при комиссии 15% цена покупателя 3299.00 даёт продавцу 2868.70
    (удержано 286.87 + 143.43).
    """
    cs2_fee_pct, steam_fee_pct = _split_total_fee(steam_fee_percent)
    seller_revenue, _, _, _ = calculate_exact_steam_revenue(
        steam_price, is_integer_currency=False,
        cs2_fee_pct=cs2_fee_pct, steam_fee_pct=steam_fee_pct)
    return seller_revenue


def calculate_profit(real_spent, steam_received):
    """Чистый плюс и процент плюса.

    Возвращает (profit_amount, profit_percent).
        profit_amount  = steam_received - real_spent
        profit_percent = (profit_amount / real_spent) * 100

    Защита от деления на ноль: при нулевых затратах процент = 0.
    """
    profit_amount = float(steam_received) - float(real_spent)
    profit_percent = (profit_amount / real_spent) * 100.0 if real_spent > 0 else 0.0
    return profit_amount, profit_percent


def calculate_profit_cross_currency(site_real_cost, steam_received,
                                    rate_site_to_spent, rate_steam_to_spent):
    """Профит в продвинутом мультивалютном режиме.

    Приводит затраты на сайте и выручку Steam к ВАЛЮТЕ ЗАТРАТ (базовая валюта),
    после чего считает плюс уже в ней.

        rate_site_to_spent  — сколько единиц валюты затрат в 1 единице валюты сайта;
        rate_steam_to_spent — сколько единиц валюты затрат в 1 единице валюты Steam.

    Возвращает (real_spent_base, steam_received_base, profit_amount, profit_percent).
    """
    real_spent_base = max(0.0, float(site_real_cost)) * max(0.0, float(rate_site_to_spent))
    steam_received_base = max(0.0, float(steam_received)) * max(0.0, float(rate_steam_to_spent))
    profit_amount, profit_percent = calculate_profit(real_spent_base, steam_received_base)
    return real_spent_base, steam_received_base, profit_amount, profit_percent


def calculate_steam_real_cost(steam_price, deposit_profit_percent):
    """Реальная стоимость покупки скина(ов) в Steam с учётом плюса пополнения (Режим 2).

        real_cost = steam_price / (1 + deposit_profit_percent / 100)

    Пример: при плюсе 50% скин за 15 на ТП стоит 15 / 1.5 = 10 реальных денег.
    (steam_price может быть уже умножена на количество — функция этого не знает.)

    Защита: при делителе <= 0 возвращается исходная цена (безопасный fallback).
    """
    steam_price = max(0.0, float(steam_price))
    divisor = 1.0 + (float(deposit_profit_percent) / 100.0)
    # Защита от деления на ноль: при -100% (и ниже) делитель <= 0 — возвращаем 0.
    if divisor <= 0:
        return 0.0
    return steam_price / divisor


def compare_purchase_options(site_real_cost, steam_real_cost):
    """Сравнение реальных затрат двух вариантов покупки (Режим 2).

    Возвращает словарь: recommendation ('steam'|'site'|'equal'),
    savings (абсолютная экономия) и обе исходные цены.
    """
    difference = abs(float(site_real_cost) - float(steam_real_cost))
    if steam_real_cost < site_real_cost:
        recommendation = "steam"
    elif site_real_cost < steam_real_cost:
        recommendation = "site"
    else:
        recommendation = "equal"
    return {
        "recommendation": recommendation,
        "savings": difference,
        "site_real_cost": site_real_cost,
        "steam_real_cost": steam_real_cost,
    }


def calculate_cashout(steam_price, site_sell_price, quantity=1,
                      sales_fee_percent=0.0, withdrawal_fee_percent=0.0,
                      withdrawal_fixed_fee=0.0):
    """Вывод баланса Steam в реальные деньги через продажу предмета на сайте.

    Модель денежного потока (все суммы — в одной валюте; конвертация, если
    нужна, выполняется вызывающим кодом до и после этой функции):

        steam_spent       = steam_price * quantity            # списано с баланса Steam
        gross_revenue     = site_sell_price * quantity        # цена выставления на сайте
        after_sales_fee   = gross_revenue * (1 - sales_fee% / 100)
        real_received     = after_sales_fee * (1 - withdrawal_fee% / 100)
                            - withdrawal_fixed_fee             # минус фикса за вывод

    Аргумент withdrawal_fixed_fee должен быть уже приведён к валюте сайта.
    Отрицательная чистая выручка обнуляется (вывести меньше нуля нельзя).

    Возвращает словарь:
        steam_spent    — затраты баланса Steam;
        gross_revenue  — выручка до комиссий;
        after_sales    — выручка после комиссии за продажу;
        real_received  — сумма к получению на карту/крипту;
        net_profit     — real_received - steam_spent (обычно отрицательна);
        ratio_percent  — (real_received / steam_spent) * 100; 0 при нулевых затратах.

    Все числовые аргументы приводятся к неотрицательным значениям; проценты
    выше 100 дают нулевую (а не отрицательную) выручку на соответствующем шаге.
    """
    steam_price = max(0.0, float(steam_price))
    site_sell_price = max(0.0, float(site_sell_price))
    quantity = max(1, int(quantity))
    sales_fee_percent = max(0.0, float(sales_fee_percent))
    withdrawal_fee_percent = max(0.0, float(withdrawal_fee_percent))
    withdrawal_fixed_fee = max(0.0, float(withdrawal_fixed_fee))

    steam_spent = steam_price * quantity
    gross_revenue = site_sell_price * quantity
    after_sales = gross_revenue * max(0.0, 1.0 - sales_fee_percent / 100.0)
    real_received = after_sales * max(0.0, 1.0 - withdrawal_fee_percent / 100.0)
    real_received = max(0.0, real_received - withdrawal_fixed_fee)

    net_profit = real_received - steam_spent
    ratio_percent = (real_received / steam_spent) * 100.0 if steam_spent > 0 else 0.0

    return {
        "steam_spent": steam_spent,
        "gross_revenue": gross_revenue,
        "after_sales": after_sales,
        "real_received": real_received,
        "net_profit": net_profit,
        "ratio_percent": ratio_percent,
    }


def get_valid_steam_price(desired_buyer_price,
                          cs2_fee_pct=STEAM_CS2_FEE_PERCENT,
                          steam_fee_pct=STEAM_STEAM_FEE_PERCENT):
    """Ближайшая достижимая цена покупателя для целочисленных валют (например, ₴).

    Тонкая обёртка над calculate_exact_steam_revenue для валют без дробной части.
    Возвращает кортеж (buyer_pays, seller_receive) целыми числами; для цены
    меньше одной единицы — (0, 0).
    """
    _, buyer, _, _ = calculate_exact_steam_revenue(
        desired_buyer_price, is_integer_currency=True,
        cs2_fee_pct=cs2_fee_pct, steam_fee_pct=steam_fee_pct)
    seller, _, _, _ = calculate_exact_steam_revenue(
        desired_buyer_price, is_integer_currency=True,
        cs2_fee_pct=cs2_fee_pct, steam_fee_pct=steam_fee_pct)
    return int(round(buyer)), int(round(seller))


def is_integer_currency(code):
    """True, если валюта считается без дробной части (см. INTEGER_CURRENCIES)."""
    if code is None:
        return False
    token = str(code).strip().lower()
    known = {c.lower() for c in INTEGER_CURRENCIES} | _INTEGER_CURRENCY_ALIASES
    return token in known


def is_usd_currency(code):
    """True, если валюта (символ/код) означает доллар США."""
    if code is None:
        return False
    return str(code).strip().lower() in USD_CODES


# ===========================================================================
# ВСПОМОГАТЕЛЬНЫЕ UI-ФУНКЦИИ
# ===========================================================================

def format_currency(value, currency=DEFAULT_CURRENCY, decimals=2):
    """Форматирует число как денежную сумму: '1 234.56 $' или '16 ₴' (decimals=0)."""
    return f"{value:,.{decimals}f} {currency}"


def default_usd_rate(currency_symbol):
    """Грубое значение по умолчанию «сколько валюты за 1 USD» (редактируемое)."""
    return USD_RATE_DEFAULTS.get(currency_symbol, 1.0)


def render_fee_template_controls(key_prefix):
    """Селектор профиля комиссии и флажок учёта комиссии.

    Размещается вне st.form, чтобы смена профиля немедленно перерисовывала
    зависимые поля ввода. Возвращает (template_name, enable_fees).
    """
    template_name = st.selectbox(
        _("Fee template"),
        options=list(DEPOSIT_FEE_TEMPLATES.keys()),
        format_func=_,  # переводит только "Manual input"; бренды — как есть
        key=f"{key_prefix}_template",
        help=_("Presets for popular sites. Manual input is also available."),
    )
    template = DEPOSIT_FEE_TEMPLATES[template_name]
    enable_fees = st.checkbox(
        _("Account for top-up fee"),
        value=template.get("enabled", False),
        key=f"{key_prefix}_enable",
    )
    return template_name, enable_fees


def render_fee_value_inputs(key_prefix, template_name, enable_fees):
    """Поля процентной и фиксированной (USD) комиссии внутри st.form.

    Ключи виджетов содержат имя профиля (template_name): при смене профиля
    Streamlit создаёт новые виджеты и сразу подставляет их значения по
    умолчанию. Без этого приёма значения обновлялись бы только при повторном
    взаимодействии с виджетом.

    Возвращает (fee_percent, fixed_fee_usd).
    """
    template = DEPOSIT_FEE_TEMPLATES[template_name]
    if not enable_fees:
        return 0.0, 0.0

    col_a, col_b = st.columns(2)
    with col_a:
        fee_percent = st.number_input(
            _("Top-up fee (%)"),
            min_value=0.0, value=float(template.get("percent_fee", 0.0)), step=0.5,
            key=f"{key_prefix}_percent_{template_name}",   # ключ зависит от профиля
        )
    with col_b:
        fixed_fee_usd = st.number_input(
            _("Fixed fee (USD)"),
            min_value=0.0, value=float(template.get("fixed_fee_usd", 0.0)), step=0.05,
            key=f"{key_prefix}_fixed_{template_name}",      # ключ зависит от профиля
        )
    return fee_percent, fixed_fee_usd


def resolve_fixed_fee_in_target(key_prefix, fixed_fee_usd, enable_fees, advanced,
                                display_ccy, spent_ccy, site_ccy, rate_site_to_spent):
    """Приводит фиксированную комиссию из долларов к валюте расчёта затрат.

    Рендерится внутри st.form. Целевая валюта зависит от режима:
        * обычный режим      — валюта отображения (display_ccy);
        * мультивалютный     — валюта сайта (site_ccy), которая позже
                               домножается на кросс-курс.

    Определение курса доллара:
        * если целевая валюта уже доллар — конвертация не требуется;
        * в мультивалютном режиме при затратах в долларах курс доллара к валюте
          сайта вычисляется из введённого кросс-курса (1 / rate_site_to_spent);
        * иначе отображается отдельное поле для ввода курса.

    Возвращает фиксированную комиссию в целевой валюте (неотрицательное число).
    """
    if not enable_fees or fixed_fee_usd <= 0:
        return 0.0

    # --- Простой режим: цель = валюта отображения ---
    if not advanced:
        if is_usd_currency(display_ccy):
            return float(fixed_fee_usd)
        usd_to_disp = st.number_input(
            _("Rate: how many {a} in 1 {b}").format(a=display_ccy, b="USD"),
            min_value=0.0, value=default_usd_rate(display_ccy), step=0.5,
            key=f"{key_prefix}_usd_rate",
        )
        return float(fixed_fee_usd) * usd_to_disp

    # --- Продвинутый режим: цель = валюта сайта ---
    if is_usd_currency(site_ccy):
        return float(fixed_fee_usd)

    # Если затраты в USD — выводим курс USD→сайт из существующего кросс-курса.
    if is_usd_currency(spent_ccy) and rate_site_to_spent and rate_site_to_spent > 0:
        usd_to_site = 1.0 / float(rate_site_to_spent)  # 1 USD = 1 / (курс сайта к валюте затрат)
        st.caption(_("USD fixed fee converted via your existing cross-rate."))
        return float(fixed_fee_usd) * usd_to_site

    # Иначе — явное поле курса USD → валюта сайта.
    usd_to_site = st.number_input(
        _("Rate: how many {a} in 1 {b}").format(a=site_ccy or "?", b="USD"),
        min_value=0.0, value=1.0, step=0.5,
        key=f"{key_prefix}_usd_rate",
    )
    return float(fixed_fee_usd) * usd_to_site


def render_cross_currency_selectors(key_prefix):
    """Рендерит ВНЕ формы три текстовых поля валют (карта/сайт/Steam).

    Вне формы — чтобы зависимое поле «курс USD → валюта сайта» появлялось
    динамически. Возвращает (spent_ccy, site_ccy, steam_ccy).
    """
    st.markdown("#### 🌍 " + _("Cross-currency settings"))
    c1, c2, c3 = st.columns(3)
    with c1:
        spent_ccy = st.text_input(_("Spent currency (e.g. UAH)"), value="UAH", key=f"{key_prefix}_spent_ccy")
    with c2:
        site_ccy = st.text_input(_("Site currency (e.g. USD)"), value="USD", key=f"{key_prefix}_site_ccy")
    with c3:
        steam_ccy = st.text_input(_("Steam currency (e.g. EUR)"), value="EUR", key=f"{key_prefix}_steam_ccy")
    return spent_ccy, site_ccy, steam_ccy


def render_cross_currency_rates(key_prefix, spent_ccy, site_ccy, steam_ccy):
    """Рендерит ВНУТРИ формы два курса к валюте затрат.

    Возвращает (rate_site_to_spent, rate_steam_to_spent).
    """
    spent_lbl = spent_ccy or "?"
    r1, r2 = st.columns(2)
    with r1:
        rate_site_to_spent = st.number_input(
            _("Rate: how many {a} in 1 {b}").format(a=spent_lbl, b=site_ccy or "?"),
            min_value=0.0, value=41.0, step=0.5, key=f"{key_prefix}_rate_site",
        )
    with r2:
        rate_steam_to_spent = st.number_input(
            _("Rate: how many {a} in 1 {b}").format(a=spent_lbl, b=steam_ccy or "?"),
            min_value=0.0, value=45.0, step=0.5, key=f"{key_prefix}_rate_steam",
        )
    st.caption(_("Both rates are in the spent currency per 1 unit (a common base)."))
    return rate_site_to_spent, rate_steam_to_spent


# ===========================================================================
# РЕЖИМ 1: КАЛЬКУЛЯТОР ПОПОЛНЕНИЯ БАЛАНСА STEAM
# ===========================================================================

def calculate_mode_1(currency, advanced):
    """Интерфейс Режима 1. currency — валюта отображения; advanced — режим кросс-курсов."""
    st.subheader("💰 " + _("Steam balance top-up calculator"))
    st.write(_("We calculate the final profit from buying a skin on a third-party site "
               "and selling it on the Steam Market."))

    # --- ВНЕ формы: шаблон комиссии + (опц.) валюты кросс-курсов ---
    template_name, enable_fees = render_fee_template_controls("m1")
    spent_ccy = site_ccy = steam_ccy = None
    if advanced:
        spent_ccy, site_ccy, steam_ccy = render_cross_currency_selectors("m1")

    # Значения по умолчанию (на случай отключённых блоков).
    fee_percent, fixed_fee_usd = 0.0, 0.0
    rate_site_to_spent, rate_steam_to_spent = 1.0, 1.0

    # Поля и кнопка внутри st.form: пересчёт выполняется только по нажатию.
    with st.form("m1_form"):
        col_buy, col_sell = st.columns(2)

        with col_buy:
            st.markdown("#### 🛒 " + _("Purchase (third-party site)"))
            site_price = st.number_input(
                _("Skin price on third-party site"),
                min_value=0.0, value=10.0, step=0.5, key="m1_site_price",
            )
            quantity = st.number_input(
                _("Quantity"), min_value=1, value=1, step=1, key="m1_qty",
            )
            fee_percent, fixed_fee_usd = render_fee_value_inputs("m1", template_name, enable_fees)

        with col_sell:
            st.markdown("#### 🏪 " + _("Sale (Steam Market)"))
            steam_price = st.number_input(
                _("Steam sale price"),
                min_value=0.0, value=15.0, step=0.5, key="m1_steam_price",
            )
            steam_fee = st.number_input(
                _("Steam sale fee (%)"),
                min_value=0.0, max_value=100.0, value=DEFAULT_STEAM_FEE_PERCENT, step=0.5,
                key="m1_steam_fee", help=_("Default 15% = 10% CS2 fee + 5% Steam fee."),
            )
            manual_integer = st.checkbox(
                _("Currency without cents (integers only)"),
                value=False, key="m1_manual_integer",
                help=_("Forces integer Steam pricing. Auto-enabled for ₴ / UAH."),
            )

        if advanced:
            st.divider()
            rate_site_to_spent, rate_steam_to_spent = render_cross_currency_rates(
                "m1", spent_ccy, site_ccy, steam_ccy)

        # Конвертация фиксы из USD в целевую валюту (поле появляется при нужде).
        fixed_in_target = resolve_fixed_fee_in_target(
            "m1", fixed_fee_usd, enable_fees, advanced,
            currency, spent_ccy, site_ccy, rate_site_to_spent)

        submitted = st.form_submit_button("🧮 " + _("Calculate"),
                                          type="primary", use_container_width=True)

    # --- Результаты (только после нажатия) ---
    if not submitted:
        st.info(_("Press Calculate to see the results."))
        return

    # Валютный контекст вывода.
    if advanced:
        steam_side_ccy = steam_ccy
        output_ccy = spent_ccy or DEFAULT_CURRENCY
    else:
        steam_side_ccy = currency
        output_ccy = currency

    quantity = max(1, int(quantity))

    # Целочисленный режим — по валюте стороны Steam или ручной галочке.
    integer_mode = manual_integer or is_integer_currency(steam_side_ccy)

    # Выручка продавца за 1 предмет считается по точной модели Steam (floor с
    # минимумом в одну единицу) в наименьшей единице валюты. Суммарный процент
    # комиссии распределяется на издательскую и площадочную части (10:5).
    cs2_fee_pct, steam_fee_pct = _split_total_fee(steam_fee)
    seller_unit, valid_buyer, fee_cs_unit, fee_steam_unit = calculate_exact_steam_revenue(
        steam_price, integer_mode, cs2_fee_pct, steam_fee_pct)
    steam_received_unit = float(seller_unit)
    integer_detail = (valid_buyer, seller_unit)

    # Предупреждение нужно только для целочисленных валют: там не каждая цена
    # листинга достижима и могла быть приведена к ближайшей возможной.
    integer_warning = None
    if integer_mode and abs(valid_buyer - round(float(steam_price))) >= 1:
        integer_warning = (int(round(steam_price)), int(round(valid_buyer)))

    # Выручка за всё количество (в валюте стороны Steam); конвертация — далее.
    steam_received_total = steam_received_unit * quantity

    # Реальные затраты на сайте (фикса уже в целевой валюте) за всё количество.
    site_real_cost = calculate_real_spent(site_price, fee_percent, fixed_in_target, quantity)

    # Приведение к базовой валюте и итоговый плюс.
    if advanced:
        real_spent_base, steam_received_base, profit_amount, profit_percent = \
            calculate_profit_cross_currency(
                site_real_cost, steam_received_total, rate_site_to_spent, rate_steam_to_spent)
    else:
        real_spent_base = site_real_cost
        steam_received_base = steam_received_total
        profit_amount, profit_percent = calculate_profit(real_spent_base, steam_received_base)

    # --- Вывод результатов ---
    st.divider()
    st.markdown("### 📊 " + _("Results"))

    if integer_warning is not None:
        x, y = integer_warning
        st.warning(_("Price {x} is impossible in Steam for integer currencies. "
                     "Rounded to the nearest possible: {y}.").format(x=x, y=y))

    # В целочисленном одновалютном режиме «Получено» — целое (без копеек).
    received_decimals = 0 if (integer_mode and not advanced) else 2

    m_spent, m_received, m_profit = st.columns(3)
    m_spent.metric(_("Real spent"), format_currency(real_spent_base, output_ccy))
    m_received.metric(_("Steam received"),
                      format_currency(steam_received_base, output_ccy, received_decimals))
    m_profit.metric(
        _("Net profit"),
        format_currency(profit_amount, output_ccy),
        delta=f"{profit_percent:+.2f}%",   # зелёный для плюса, красный для минуса
    )

    # Пояснение для целочисленного режима (за 1 предмет).
    if integer_mode and integer_detail is not None:
        buyer_pays, seller_receive = integer_detail
        st.caption(_("Buyer pays {buyer} · you receive {seller} (per item)").format(
            buyer=format_currency(buyer_pays, steam_side_ccy, 0),
            seller=format_currency(seller_receive, steam_side_ccy, 0)))
        st.caption(_("Steam fees are floored to whole units with a 1-unit minimum, "
                     "following Steam's exact fee model."))

    # В продвинутом режиме — промежуточные суммы в исходных валютах.
    if advanced:
        st.caption(
            f"{_('Site cost')}: {format_currency(site_real_cost, site_ccy or '?')} · "
            f"{_('Steam proceeds')}: "
            f"{format_currency(steam_received_total, steam_side_ccy or '?', received_decimals)}")

    # --- Итоговый вердикт ---
    if real_spent_base <= 0:
        st.info(_("Enter a skin price to see the calculation."))
    elif profit_amount > 0:
        st.success(_("Top-up in profit: +{amount} ({percent}).").format(
            amount=format_currency(profit_amount, output_ccy), percent=f"{profit_percent:+.2f}%"))
    elif profit_amount < 0:
        st.error(_("Top-up at a loss: {amount} ({percent}).").format(
            amount=format_currency(profit_amount, output_ccy), percent=f"{profit_percent:+.2f}%"))
    else:
        st.warning(_("Break-even result."))

    with st.expander("ℹ️ " + _("Calculation formulas")):
        st.markdown(_("MODE1_FORMULAS"))


# ===========================================================================
# РЕЖИМ 2: АНАЛИЗАТОР ВЫГОДНОЙ ПОКУПКИ ("ГДЕ КУПИТЬ ВЫГОДНЕЕ?")
# ===========================================================================

def calculate_mode_2(currency, advanced):
    """Интерфейс Режима 2. currency — валюта отображения; advanced — режим кросс-курсов."""
    st.subheader("🔍 " + _("Where to buy cheaper?"))
    st.write(_("We compare buying a skin directly on a third-party site with real money "
               "versus buying it on the Steam Market with a balance topped up 'in profit'."))

    # --- ВНЕ формы: шаблон комиссии + (опц.) валюты кросс-курсов ---
    template_name, enable_fees = render_fee_template_controls("m2")
    spent_ccy = site_ccy = steam_ccy = None
    if advanced:
        spent_ccy, site_ccy, steam_ccy = render_cross_currency_selectors("m2")

    fee_percent, fixed_fee_usd = 0.0, 0.0
    rate_site_to_spent, rate_steam_to_spent = 1.0, 1.0

    # --- Форма ---
    with st.form("m2_form"):
        col_steam, col_site = st.columns(2)

        with col_steam:
            st.markdown("#### 🏪 " + _("Buy on Steam Market"))
            steam_price = st.number_input(
                _("Current Steam Market price"),
                min_value=0.0, value=15.0, step=0.5, key="m2_steam_price",
            )
            deposit_profit = st.number_input(
                _("Steam top-up profit (%)"),
                min_value=-99.9, value=50.0, step=1.0, key="m2_deposit_profit",
                help=_("How profitably you topped up Steam earlier. "
                       "Example: spent 10 real, got 15 on balance → 50% profit."),
            )

        with col_site:
            st.markdown("#### 🛒 " + _("Buy on third-party site"))
            site_price = st.number_input(
                _("Skin price on third-party site"),
                min_value=0.0, value=12.0, step=0.5, key="m2_site_price",
            )
            quantity = st.number_input(
                _("Quantity"), min_value=1, value=1, step=1, key="m2_qty",
            )
            fee_percent, fixed_fee_usd = render_fee_value_inputs("m2", template_name, enable_fees)

        if advanced:
            st.divider()
            rate_site_to_spent, rate_steam_to_spent = render_cross_currency_rates(
                "m2", spent_ccy, site_ccy, steam_ccy)

        fixed_in_target = resolve_fixed_fee_in_target(
            "m2", fixed_fee_usd, enable_fees, advanced,
            currency, spent_ccy, site_ccy, rate_site_to_spent)

        submitted = st.form_submit_button("🧮 " + _("Calculate"),
                                          type="primary", use_container_width=True)

    # --- Результаты ---
    if not submitted:
        st.info(_("Press Calculate to see the results."))
        return

    if advanced:
        steam_side_ccy = steam_ccy
        output_ccy = spent_ccy or DEFAULT_CURRENCY
    else:
        steam_side_ccy = currency
        output_ccy = currency

    quantity = max(1, int(quantity))

    # Затраты на сайте (фикса уже в целевой валюте) за всё количество.
    site_real_cost = calculate_real_spent(site_price, fee_percent, fixed_in_target, quantity)

    # Сторона Steam: цена сначала приводится к целому для целочисленных валют,
    # затем применяется выгода пополнения и только потом — конвертация.
    integer_mode = is_integer_currency(steam_side_ccy)
    unit_price = float(int(round(steam_price))) if integer_mode else float(steam_price)
    steam_nominal = unit_price * quantity
    steam_real_cost = calculate_steam_real_cost(steam_nominal, deposit_profit)

    # Приведение к базовой валюте.
    if advanced:
        site_real_base = max(0.0, site_real_cost) * max(0.0, rate_site_to_spent)
        steam_real_base = max(0.0, steam_real_cost) * max(0.0, rate_steam_to_spent)
    else:
        site_real_base = site_real_cost
        steam_real_base = steam_real_cost

    result = compare_purchase_options(site_real_base, steam_real_base)

    # --- Вывод ---
    st.divider()
    st.markdown("### 📊 " + _("Results comparison"))

    m_site, m_steam = st.columns(2)
    m_site.metric(_("Real price (third-party site)"), format_currency(site_real_base, output_ccy))
    m_steam.metric(_("Real price (Steam, with profit)"), format_currency(steam_real_base, output_ccy))

    if advanced:
        st.caption(
            f"{_('Site cost')}: {format_currency(site_real_cost, site_ccy or '?')} · "
            f"{_('Steam cost')}: {format_currency(steam_real_cost, steam_side_ccy or '?')}")

    if site_real_base <= 0 and steam_real_base <= 0:
        st.info(_("Enter data to see the comparison."))
    elif result["recommendation"] == "steam":
        st.success(_("Cheaper to buy on Steam. Savings: {amount}.").format(
            amount=format_currency(result["savings"], output_ccy)))
    elif result["recommendation"] == "site":
        st.success(_("Cheaper to buy on the third-party site. Savings: {amount}.").format(
            amount=format_currency(result["savings"], output_ccy)))
    else:
        st.warning(_("Both options cost the same in real money."))

    with st.expander("ℹ️ " + _("Calculation formulas")):
        st.markdown(_("MODE2_FORMULAS"))


def calculate_sell_via_site_topup(site_sell_price, quantity, sales_fee_percent,
                                   withdrawal_fee_percent, withdrawal_fixed_fee,
                                   deposit_profit_percent):
    """Steam-баланс от продажи на сайте с последующим пополнением Steam (Режим 4).

    Шаги:
        gross_revenue = site_sell_price × quantity
        after_sales   = gross × (1 − sales_fee_percent / 100)
        real_money    = after_sales × (1 − withdrawal_fee_percent / 100) − withdrawal_fixed_fee
        steam_balance = real_money × (1 + deposit_profit_percent / 100)

    При deposit_profit_percent = 0 steam_balance равен real_money (пополнение 1:1).

    Возвращает dict с ключами:
        «gross»         — выручка до комиссий,
        «real_money»    — реальные деньги после всех удержаний,
        «steam_balance» — итоговый Steam-баланс.
    """
    site_sell_price = max(0.0, float(site_sell_price))
    quantity = max(1, int(quantity))
    sales_fee_percent = min(100.0, max(0.0, float(sales_fee_percent)))
    withdrawal_fee_percent = min(100.0, max(0.0, float(withdrawal_fee_percent)))
    withdrawal_fixed_fee = max(0.0, float(withdrawal_fixed_fee))

    gross = site_sell_price * quantity
    after_sales = gross * (1.0 - sales_fee_percent / 100.0)
    after_withdrawal = after_sales * (1.0 - withdrawal_fee_percent / 100.0)
    real_money = max(0.0, after_withdrawal - withdrawal_fixed_fee)

    divisor = 1.0 + float(deposit_profit_percent) / 100.0
    steam_balance = real_money * max(0.0, divisor)
    return {"gross": gross, "real_money": real_money, "steam_balance": steam_balance}


def calculate_steam_market_sell(steam_sell_price, quantity, total_steam_fee_percent,
                                 currency_code):
    """Steam-баланс от продажи на Steam Market напрямую (Режим 4).

    Для целочисленных валют (UAH, JPY, …) применяется точная модель Valve:
    round(10%)+round(5%) от суммы продавца с минимумом в одну единицу. Цена
    buyer-side проходит через get_valid_steam_price, чтобы учесть недостижимые
    цены так же, как реальная торговая площадка.

    Для дробных валют используется расчёт в центах (floor-модель).

    Возвращает dict: «seller_per_unit» — продавцу за единицу, «steam_balance» — итого.
    """
    steam_sell_price = max(0.0, float(steam_sell_price))
    quantity = max(1, int(quantity))
    total_steam_fee_percent = max(0.0, float(total_steam_fee_percent))
    cs2_fee_pct, steam_fee_pct = _split_total_fee(total_steam_fee_percent)
    int_ccy = is_integer_currency(currency_code)
    if int_ccy:
        unit_price = float(int(round(steam_sell_price)))
        seller_per_unit = calculate_exact_steam_revenue(
            unit_price, is_integer_currency=True,
            cs2_fee_pct=cs2_fee_pct, steam_fee_pct=steam_fee_pct)[0]
    else:
        seller_per_unit = calculate_steam_received(steam_sell_price, total_steam_fee_percent)
    return {"seller_per_unit": seller_per_unit, "steam_balance": seller_per_unit * quantity}


# ===========================================================================
# РЕЖИМ 5: ЛУЧШЕЕ КАЧЕСТВО ДЛЯ ПОКУПКИ В КОЛЛЕКЦИИ
# ===========================================================================

# Качества CS2 по возрастанию редкости: (ключ перевода, цвет редкости).
RARITY_DEFS = [
    ("rarity_consumer",   "#b0c3d9"),
    ("rarity_industrial", "#5e98d9"),
    ("rarity_milspec",    "#4b69ff"),
    ("rarity_restricted", "#8847ff"),
    ("rarity_classified", "#d32ce6"),
    ("rarity_covert",     "#eb4b4b"),
]

# Цвета рангов для подсветки (выше ранг — выгоднее покупка).
RANK_COLORS = {
    "A++": "#1a9850", "A+": "#52b04f", "A": "#86cb66",
    "B": "#b8b8b8", "C": "#9e9e9e",
    "D": "#f08a4b", "E": "#e2563b",
}


_RARITY_RANKS = ["E", "D", "C", "B", "A", "A+", "A++"]  # индекс 0..6


def _ratio_rank_index(ratio):
    """Индекс ранга 0..6 (E..A++) по соотношению цен соседних качеств.

    ratio — «во сколько раз дороже». Чем больше предметов нижнего качества по цене
    эквивалентны одному верхнему, тем дешевле нижнее относительно того, во что оно
    превращается контрактом 10->1, тем выгоднее покупка. Пороги заданы пользователем:
        ≤2 → E, 2–4 → D, 4–5.5 → C, 5.5–6.5 → B, 6.5–8 → A, 8–10 → A+, >10 → A++.
    Возвращает None при отсутствующем соотношении.
    """
    if ratio is None:
        return None
    if ratio <= 2.0:
        return 0
    if ratio <= 4.0:
        return 1
    if ratio <= 5.5:
        return 2
    if ratio <= 6.5:
        return 3
    if ratio <= 8.0:
        return 4
    if ratio <= 10.0:
        return 5
    return 6


# Категория комментария по (ранг, роль). role: "lower" — обычное качество,
# сравниваемое с тем, что выше; "highest" — высшее качество (наоборот).
_RANK_COMMENT_KEYS = {
    "lower":   {"E": "rk_over", "D": "rk_over_slight", "C": "rk_normal",
                "B": "rk_good", "A": "rk_under", "A+": "rk_under", "A++": "rk_under_susp"},
    "highest": {"E": "rk_exp", "D": "rk_exp_slight", "C": "rk_normal",
                "B": "rk_good", "A": "rk_cheap", "A+": "rk_cheap", "A++": "rk_cheap_susp"},
}

# Порядок рангов для выбора лучшего (по убыванию привлекательности покупки).
_RANK_ORDER = {"A++": 6, "A+": 5, "A": 4, "B": 3, "C": 2, "D": 1, "E": 0}


def analyze_collection_rarities(tiers):
    """Считает соотношения и инвестиционные ранги для заполненных качеств коллекции.

    tiers — список словарей {«key», «name», «color», «price», «beautiful»} ТОЛЬКО
    для качеств с ценой > 0, по возрастанию редкости (нижнее первым). Возвращает
    тот же список, обогащённый ключами «ratio» (базовое соотношение), «rank»,
    «rank_index», «role» («lower»/«highest»).

    Логика рангов:
        * НЕ высшее качество: ratio = цена_выше / цена_этого (сколько штук этого по
          цене = одно качество выше). Ранг — по _ratio_rank_index. Чем больше ratio,
          тем выгоднее покупка нижнего качества.
        * ВЫСШЕЕ качество (выше ничего нет): ранг считается «наоборот». ratio =
          цена_высшего / цена_ниже; индекс реверсируется (6 - idx, т.е. E<->A++).
          Затем штраф за инфляцию саплая (высшее нельзя скрафтить дальше, его
          предложение только растёт): для итогового A и выше −2, для B/C/D/E −1.
          Штраф берётся от БАЗОВОГО ratio (структурно), чтобы бонус красоты его
          не гасил.
        * Бонус «красоты/ликвидности»: если у качества включён флаг, к его ratio и к
          ratio качества на 1 ниже прибавляется +0.5, на 2 ниже +0.25 (на 3 ниже —
          ничего). На качество ВЫШЕ отмеченного бонус не влияет. Для высшего
          качества бонус, наоборот, СНИЖАЕТ его ratio (улучшает реверс-ранг).
    """
    n = len(tiers)

    # Накопление бонуса красоты по списку активных качеств (снизу вверх).
    bonus = [0.0] * n
    for i, t in enumerate(tiers):
        if t.get("beautiful"):
            bonus[i] += 0.5
            if i - 1 >= 0:
                bonus[i - 1] += 0.5
            if i - 2 >= 0:
                bonus[i - 2] += 0.25

    results = []
    for i, t in enumerate(tiers):
        price = t["price"]
        if i < n - 1:  # не высшее: сравниваем с тем, что выше
            higher = tiers[i + 1]["price"]
            base_ratio = (higher / price) if price > 0 else None
            role = "lower"
            idx = _ratio_rank_index(base_ratio + bonus[i]) if base_ratio is not None else None
        else:  # высшее: наоборот + штраф за инфляцию саплая
            role = "highest"
            lower = tiers[i - 1]["price"] if n >= 2 else 0.0
            if n >= 2 and lower > 0:
                base_ratio = price / lower
                reversed_base = 6 - _ratio_rank_index(base_ratio)
                penalty = 2 if reversed_base >= 4 else 1
                eff = max(0.0, base_ratio - bonus[i])      # красота снижает M -> лучше
                reversed_eff = 6 - _ratio_rank_index(eff)
                idx = max(0, min(6, reversed_eff - penalty))
            else:
                base_ratio = None
                idx = None
        rank = _RARITY_RANKS[idx] if idx is not None else None
        results.append({**t, "ratio": base_ratio, "rank": rank, "rank_index": idx, "role": role})
    return results


def calculate_mode_5(currency):
    """Интерфейс Режима 5. Только одна валюта (кросс-курсы не применяются).

    Пользователь вводит цены качеств коллекции; приложение ранжирует, какое
    качество выгоднее покупать, по соотношению цен соседних качеств.
    """
    st.subheader("🎚️ " + _("Best rarity to buy (collection)"))
    st.write(_(
        "We rank which rarity in a collection is the best buy, based on the price ratio "
        "between adjacent rarities (10 lower-rarity items trade up into 1 higher-rarity item)."
    ))
    st.info(_(
        "Enter prices in ONE currency. Use one float tier (or the tier that best fits your goal): "
        "for most filler the result is nearly the same regardless of quality; it only matters for "
        "low-float crafts (0.01+). Leave a rarity at 0 to exclude it from the collection."
    ))

    with st.form("m5_form"):
        st.markdown("#### 🎨 " + _("Rarity prices"))
        st.caption(_(
            "Enter the price you consider fair for each rarity. Tick the box if you "
            "find that rarity's skins beautiful or especially liquid."
        ))
        h_name, h_price, h_beauty = st.columns([2, 1, 1])
        h_name.markdown("**" + _("Rarity") + "**")
        h_price.markdown("**" + _("Price") + "**")
        h_beauty.markdown("**" + _("Beautiful / liquid?") + "**")
        prices = {}
        beauty = {}
        for key, color in RARITY_DEFS:
            label = (f"<span style='color:{color};font-weight:600;'>● </span>" + _(key))
            c_name, c_price, c_beauty = st.columns([2, 1, 1])
            with c_name:
                st.markdown("<div style='padding-top:0.5rem;'>" + label + "</div>",
                            unsafe_allow_html=True)
            with c_price:
                prices[key] = st.number_input(
                    _(key), min_value=0.0, value=0.0, step=0.1,
                    key=f"m5_price_{key}", label_visibility="collapsed",
                )
            with c_beauty:
                beauty[key] = st.checkbox(
                    _("Beautiful / liquid?"), value=False,
                    key=f"m5_beauty_{key}", label_visibility="collapsed",
                )
        submitted = st.form_submit_button("🧮 " + _("Calculate"),
                                          type="primary", use_container_width=True)

    if not submitted:
        st.info(_("Press Calculate to see the results."))
        return

    # Берём только заполненные качества (цена > 0), сохраняя порядок редкости.
    tiers = []
    for key, color in RARITY_DEFS:
        price = prices.get(key, 0.0)
        if price and price > 0:
            tiers.append({"key": key, "name": _(key), "color": color,
                          "price": float(price), "beautiful": bool(beauty.get(key))})

    if len(tiers) < 2:
        st.warning(_("Enter at least two rarity prices to compare."))
        return

    results = analyze_collection_rarities(tiers)

    # --- Таблица результатов ---
    st.divider()
    st.markdown("### 📊 " + _("Ranking (higher = better buy)"))

    header = (
        "<tr>"
        f"<th style='text-align:left;padding:6px 10px;'>{_('Rarity')}</th>"
        f"<th style='text-align:right;padding:6px 10px;'>{_('Price')}</th>"
        f"<th style='text-align:center;padding:6px 10px;'>{_('Ratio')}</th>"
        f"<th style='text-align:center;padding:6px 10px;'>{_('Rank')}</th>"
        f"<th style='text-align:left;padding:6px 10px;'>{_('Comment')}</th>"
        "</tr>"
    )
    rows = []
    for r in results:
        rank = r["rank"]
        rank_color = RANK_COLORS.get(rank, "#9e9e9e")
        # После реверса ранг высшего качества означает то же, что у нижних: высокий
        # ранг — выгодная покупка. Поэтому комментарий берём из единой шкалы, а для
        # высшего качества добавляем пометку про штраф за инфляцию саплая.
        comment_key = _RANK_COMMENT_KEYS["lower"].get(rank, "rk_normal") if rank else "rk_normal"
        comment = _(comment_key) if rank else "—"
        if rank and r["role"] == "highest":
            comment += " " + _("rk_top_note")
        if r["beautiful"]:
            comment += " ✨"
        if r["ratio"] is None:
            ratio_str = "—"
        elif r["role"] == "highest":
            ratio_str = _("this rarity = {n}× the rarity below").format(n=f"{r['ratio']:.2f}")
        else:
            ratio_str = _("{n}× this rarity = one rarity above").format(n=f"{r['ratio']:.2f}")
        rank_badge = (
            f"<span style='background:{rank_color};color:white;padding:2px 8px;"
            f"border-radius:6px;font-weight:700;'>{rank or '—'}</span>"
        )
        name_cell = f"<span style='color:{r['color']};font-weight:600;'>● </span>{r['name']}"
        rows.append(
            "<tr style='border-top:1px solid #3a3a3a;'>"
            f"<td style='text-align:left;padding:6px 10px;'>{name_cell}</td>"
            f"<td style='text-align:right;padding:6px 10px;'>{format_currency(r['price'], currency)}</td>"
            f"<td style='text-align:center;padding:6px 10px;font-size:0.85em;'>{ratio_str}</td>"
            f"<td style='text-align:center;padding:6px 10px;'>{rank_badge}</td>"
            f"<td style='text-align:left;padding:6px 10px;font-size:0.9em;'>{comment}</td>"
            "</tr>"
        )
    table_html = (
        "<table style='width:100%;border-collapse:collapse;'>"
        + "<thead>" + header + "</thead><tbody>" + "".join(rows) + "</tbody></table>"
    )
    st.markdown(table_html, unsafe_allow_html=True)

    # --- Лучшая покупка: наивысший ранг среди качеств с оценкой ---
    ranked = [r for r in results if r["rank"] is not None]
    if ranked:
        best = max(ranked, key=lambda r: _RANK_ORDER.get(r["rank"], -1))
        st.success(_("Best buy: {rarity} (rank {rank})").format(
            rarity=best["name"], rank=best["rank"]))

    with st.expander("ℹ️ " + _("Calculation formulas")):
        st.markdown(_("MODE5_FORMULAS"))


# ===========================================================================
# РЕЖИМ 4: АНАЛИЗАТОР ВЫГОДНОЙ ПРОДАЖИ ("ГДЕ ПРОДАТЬ ВЫГОДНЕЕ?")
# ===========================================================================

def calculate_mode_4(currency, advanced):
    """Интерфейс Режима 4. currency — валюта отображения; advanced — режим кросс-курсов.

    Сравниваем два пути продажи скина:
        Вариант А — продать на стороннем сайте, вывести деньги и пополнить Steam в плюс;
        Вариант Б — продать напрямую на Steam Market (Steam удерживает ~15%).

    Оба варианта дают Steam-баланс как итог, поэтому сравнение прямое.
    """
    st.subheader("📊 " + _("Where to sell more profitably?"))
    st.write(_(
        "We compare selling a skin on a third-party site (then topping up Steam at a profit) "
        "versus selling it directly on the Steam Market."
    ))

    # --- Вне формы: (опц.) валюты кросс-курсов ---
    spent_ccy = site_ccy = steam_ccy = None
    if advanced:
        spent_ccy, site_ccy, steam_ccy = render_cross_currency_selectors("m4")

    rate_site_to_spent, rate_steam_to_spent = 1.0, 1.0

    # --- Форма ---
    with st.form("m4_form"):
        col_site, col_steam = st.columns(2)

        with col_site:
            st.markdown("#### 🛒 " + _("Sell on third-party site → top up Steam"))
            site_sell_price = st.number_input(
                _("Site sell price"),
                min_value=0.0, value=12.0, step=0.5, key="m4_site_sell",
            )
            quantity = st.number_input(
                _("Quantity"), min_value=1, value=1, step=1, key="m4_qty",
            )
            sales_fee = st.number_input(
                _("Sales fee (%)"),
                min_value=0.0, max_value=100.0, value=2.0, step=0.5, key="m4_sales_fee",
            )
            withdrawal_fee = st.number_input(
                _("Withdrawal fee (%)"),
                min_value=0.0, max_value=100.0, value=0.0, step=0.5, key="m4_wd_fee",
            )
            withdrawal_fixed_usd = st.number_input(
                _("Withdrawal fixed fee (USD)"),
                min_value=0.0, value=0.0, step=0.5, key="m4_wd_fixed",
            )
            deposit_profit = st.number_input(
                _("Steam top-up profit (%)"),
                min_value=-99.9, value=50.0, step=1.0, key="m4_deposit_profit",
                help=_(
                    "How profitably you topped up Steam earlier. "
                    "Example: spent 10 real, got 15 on balance → 50% profit."
                ),
            )

        with col_steam:
            st.markdown("#### 🏪 " + _("Sell on Steam Market directly"))
            steam_sell_price = st.number_input(
                _("Steam sell price (buyer pays)"),
                min_value=0.0, value=15.0, step=0.5, key="m4_steam_sell",
                help=_("The price shown to buyers on the Steam Market."),
            )
            steam_fee_total = st.number_input(
                _("Steam Market fee (%)"),
                min_value=0.0, max_value=100.0, value=15.0, step=0.5, key="m4_steam_fee",
                help="Steam CS2: 10% (publisher) + 5% (platform) = 15%.",
            )

        if advanced:
            st.divider()
            rate_site_to_spent, rate_steam_to_spent = render_cross_currency_rates(
                "m4", spent_ccy, site_ccy, steam_ccy)

        # Фиксированная комиссия вывода задаётся в USD → приводится к валюте сайта.
        fixed_in_site = resolve_fixed_fee_in_target(
            "m4", withdrawal_fixed_usd, True, advanced,
            currency, spent_ccy, site_ccy, rate_site_to_spent)

        submitted = st.form_submit_button("🧮 " + _("Calculate"),
                                          type="primary", use_container_width=True)

    if not submitted:
        st.info(_("Press Calculate to see the results."))
        return

    # --- Контекст валют ---
    if advanced:
        output_ccy = spent_ccy or DEFAULT_CURRENCY
        steam_side_ccy = steam_ccy or DEFAULT_CURRENCY
    else:
        output_ccy = currency
        steam_side_ccy = currency

    quantity = max(1, int(quantity))

    # --- Вариант А: продать на сайте → реальные деньги → пополнить Steam ---
    result_site = calculate_sell_via_site_topup(
        site_sell_price=site_sell_price,
        quantity=quantity,
        sales_fee_percent=sales_fee,
        withdrawal_fee_percent=withdrawal_fee,
        withdrawal_fixed_fee=fixed_in_site,
        deposit_profit_percent=deposit_profit,
    )

    # --- Вариант Б: продать напрямую на Steam Market ---
    result_steam = calculate_steam_market_sell(
        steam_sell_price=steam_sell_price,
        quantity=quantity,
        total_steam_fee_percent=steam_fee_total,
        currency_code=steam_side_ccy,
    )

    # --- Приведение к базовой валюте для сравнения ---
    if advanced:
        # Вариант А: реальные деньги (сайт) → базовая валюта → мысленное пополнение Steam
        # Вариант Б: Steam-баланс → базовая валюта (по курсу Steam→base)
        real_money_base_a = result_site["real_money"] * max(0.0, rate_site_to_spent)
        divisor_a = max(0.0, 1.0 + deposit_profit / 100.0)
        steam_balance_a = real_money_base_a * divisor_a
        steam_balance_b = result_steam["steam_balance"] * max(0.0, rate_steam_to_spent)
    else:
        steam_balance_a = result_site["steam_balance"]
        steam_balance_b = result_steam["steam_balance"]

    # --- Вывод результатов ---
    st.divider()
    st.markdown("### 📊 " + _("Results comparison"))

    m_site, m_steam = st.columns(2)
    m_site.metric(
        _("Steam balance via site (with top-up)"),
        format_currency(steam_balance_a, output_ccy),
    )
    # Подсказка: сколько реальных денег пришло с сайта (до пополнения)
    real_money_display = (result_site["real_money"] * max(0.0, rate_site_to_spent)
                          if advanced else result_site["real_money"])
    m_site.caption(
        _("Real money from site: {amount}").format(
            amount=format_currency(real_money_display, output_ccy))
    )

    m_steam.metric(
        _("Steam balance via Steam Market"),
        format_currency(steam_balance_b, output_ccy),
    )
    # В продвинутом режиме — показываем исходные значения до конвертации.
    if advanced:
        st.caption(
            f"{_('Site')} → real: {format_currency(result_site['real_money'], site_ccy or '?')} · "
            f"{_('Steam Market')} → balance: "
            f"{format_currency(result_steam['steam_balance'], steam_side_ccy or '?')}"
        )

    # --- Вердикт ---
    diff = steam_balance_a - steam_balance_b
    both_zero = steam_balance_a <= 0 and steam_balance_b <= 0

    if both_zero:
        st.info(_("Enter data to see the comparison."))
    elif diff > 1e-4:
        st.success(_(
            "Selling via site and topping up Steam is more profitable. "
            "Extra Steam balance: {amount}."
        ).format(amount=format_currency(diff, output_ccy)))
    elif diff < -1e-4:
        st.success(_(
            "Selling on Steam Market is more profitable. "
            "Extra Steam balance: {amount}."
        ).format(amount=format_currency(-diff, output_ccy)))
    else:
        st.warning(_("Both options yield the same Steam balance."))

    with st.expander("ℹ️ " + _("Calculation formulas")):
        st.markdown(_("MODE4_FORMULAS"))


def calculate_mode_3(currency, advanced):
    """Интерфейс Режима 3. currency — валюта отображения; advanced — режим кросс-курсов.

    Сценарий: покупка предмета на Торговой площадке Steam за баланс, продажа на
    стороннем сайте и вывод выручки на карту/крипту. Цель — оценить, какая доля
    баланса Steam доходит до реальных денег (коэффициент вывода).
    """
    st.subheader("💳 " + _("Steam balance cashout calculator"))
    st.write(_("We calculate how much real money you receive by buying a skin on the Steam Market, "
               "selling it on a third-party site, and withdrawing the proceeds."))

    # Управляющие элементы вне формы: валюты кросс-курсов (если включён режим).
    spent_ccy = site_ccy = steam_ccy = None
    if advanced:
        spent_ccy, site_ccy, steam_ccy = render_cross_currency_selectors("m3")

    # Значения по умолчанию на случай отключённых блоков.
    rate_site_to_spent, rate_steam_to_spent = 1.0, 1.0

    # Поля и кнопка внутри st.form: пересчёт выполняется только по нажатию.
    with st.form("m3_form"):
        col_buy, col_sell = st.columns(2)

        with col_buy:
            st.markdown("#### 🏪 " + _("Purchase (Steam Market)"))
            steam_price = st.number_input(
                _("Steam purchase price"),
                min_value=0.0, value=15.0, step=0.5, key="m3_steam_price",
            )
            quantity = st.number_input(
                _("Quantity"), min_value=1, value=1, step=1, key="m3_qty",
            )
            deposit_profit = st.number_input(
                _("Steam top-up profit (%)"),
                min_value=-99.9, value=0.0, step=1.0, key="m3_deposit_profit",
                help=_(
                    "How profitably you topped up Steam earlier. "
                    "Example: spent 10 real, got 15 on balance → 50% profit."
                ),
            )

        with col_sell:
            st.markdown("#### 💳 " + _("Withdrawal (third-party site)"))
            site_sell_price = st.number_input(
                _("Site sell price"),
                min_value=0.0, value=12.0, step=0.5, key="m3_site_sell",
            )
            sales_fee = st.number_input(
                _("Sales fee (%)"),
                min_value=0.0, max_value=100.0, value=2.0, step=0.5, key="m3_sales_fee",
            )
            withdrawal_fee = st.number_input(
                _("Withdrawal fee (%)"),
                min_value=0.0, max_value=100.0, value=0.0, step=0.5, key="m3_wd_fee",
            )
            withdrawal_fixed_usd = st.number_input(
                _("Withdrawal fixed fee (USD)"),
                min_value=0.0, value=0.0, step=0.5, key="m3_wd_fixed",
            )

        if advanced:
            st.divider()
            rate_site_to_spent, rate_steam_to_spent = render_cross_currency_rates(
                "m3", spent_ccy, site_ccy, steam_ccy)

        # Фиксированная комиссия вывода задаётся в USD и приводится к валюте сайта
        # (комиссии сайта удерживаются именно в валюте сайта). enable_fees=True,
        # так как поле фиксы в этом режиме присутствует всегда.
        fixed_in_site = resolve_fixed_fee_in_target(
            "m3", withdrawal_fixed_usd, True, advanced,
            currency, spent_ccy, site_ccy, rate_site_to_spent)

        submitted = st.form_submit_button("🧮 " + _("Calculate"),
                                          type="primary", use_container_width=True)

    # Результаты выводятся только после нажатия кнопки.
    if not submitted:
        st.info(_("Press Calculate to see the results."))
        return

    # Валютный контекст вывода: база (карта) — итоговая валюта результата.
    if advanced:
        output_ccy = spent_ccy or DEFAULT_CURRENCY
    else:
        output_ccy = currency

    quantity = max(1, int(quantity))

    # Расчёт в валюте сайта: затраты Steam и стороны сайта изначально в разных
    # валютах, поэтому Steam-затраты считаем отдельно, а денежный поток сайта —
    # через чистую функцию, приведя обе стороны к базовой валюте далее.
    cashout = calculate_cashout(
        steam_price=steam_price, site_sell_price=site_sell_price, quantity=quantity,
        sales_fee_percent=sales_fee, withdrawal_fee_percent=withdrawal_fee,
        withdrawal_fixed_fee=fixed_in_site,
    )

    # Приведение к базовой валюте (карты).
    if advanced:
        steam_spent_base = max(0.0, cashout["steam_spent"]) * max(0.0, rate_steam_to_spent)
        real_received_base = max(0.0, cashout["real_received"]) * max(0.0, rate_site_to_spent)
    else:
        steam_spent_base = cashout["steam_spent"]
        real_received_base = cashout["real_received"]

    net_profit_base = real_received_base - steam_spent_base
    ratio_base = (real_received_base / steam_spent_base * 100.0) if steam_spent_base > 0 else 0.0

    # --- Вывод результатов ---
    st.divider()
    st.markdown("### 📊 " + _("Results"))

    # Если задан % плюса пополнения — пересчитываем реальные затраты на Steam-баланс.
    # deposit_profit=0 => real_steam_cost = steam_spent (поведение идентично прежнему).
    use_deposit = deposit_profit != 0.0
    if use_deposit:
        real_steam_cost_base = calculate_steam_real_cost(steam_spent_base, deposit_profit)
        display_ratio = (real_received_base / real_steam_cost_base * 100.0
                         ) if real_steam_cost_base > 0 else 0.0
        net_result_base = real_received_base - real_steam_cost_base
    else:
        real_steam_cost_base = steam_spent_base
        display_ratio = ratio_base
        net_result_base = net_profit_base

    base_ratio_delta = display_ratio - 100.0

    m_spent, m_received, m_ratio = st.columns(3)

    if use_deposit:
        # Колонка «потрачено»: баланс Steam сверху, реальная стоимость — подписью.
        m_spent.metric(
            _("Total Steam spent"),
            format_currency(steam_spent_base, output_ccy),
        )
        m_spent.caption(
            f"↳ {_('Real Steam cost (with top-up)')}: "
            f"**{format_currency(real_steam_cost_base, output_ccy)}**"
        )
        m_ratio.metric(
            _("Effective cashout ratio"),
            f"{display_ratio:.1f}%",
            help=_("Top-up profit factored in. Ratio > 100% means you profit even after cashing out."),
        )
    else:
        m_spent.metric(_("Total Steam spent"), format_currency(steam_spent_base, output_ccy))
        m_ratio.metric(_("Cashout ratio"), f"{display_ratio:.1f}%")

    m_received.metric(_("Real money received"), format_currency(real_received_base, output_ccy))

    # Чистый результат: знак процента используется как delta (красный для минуса).
    st.metric(
        _("Net profit / loss"),
        format_currency(net_result_base, output_ccy),
        delta=f"{base_ratio_delta:+.1f}%",
    )

    # В продвинутом режиме — промежуточные суммы в исходных валютах.
    if advanced:
        st.caption(
            f"{_('Gross site revenue')}: "
            f"{format_currency(cashout['gross_revenue'], site_ccy or '?')} · "
            f"{_('After sales fee')}: "
            f"{format_currency(cashout['after_sales'], site_ccy or '?')}")

    # Итоговый вердикт по чистому результату.
    if steam_spent_base <= 0:
        st.info(_("Enter prices to see the cashout calculation."))
    elif net_result_base > 0:
        st.success(_("Top-up in profit: +{amount} ({percent}).").format(
            amount=format_currency(net_result_base, output_ccy),
            percent=f"{base_ratio_delta:+.1f}%"))
    elif net_result_base < 0:
        st.error(_("Top-up at a loss: {amount} ({percent}).").format(
            amount=format_currency(net_result_base, output_ccy),
            percent=f"{base_ratio_delta:+.1f}%"))
    else:
        st.warning(_("Break-even result."))

    st.caption(_("The higher the cashout ratio, the more of your Steam balance reaches your card."))

    with st.expander("ℹ️ " + _("Calculation formulas")):
        st.markdown(_("MODE3_FORMULAS"))


# ===========================================================================
# ТОЧКА ВХОДА
# ===========================================================================

def main():
    """Точка входа: настройка страницы, выбор языка, сайдбар и вкладки режимов."""
    st.set_page_config(
        page_title="Yev Steam Deposit Calculator",
        page_icon="🎯",
        layout="wide",
    )

    # Язык восстанавливается до отрисовки, чтобы подписи были корректны при
    # повторных запусках скрипта (значение хранится в session_state).
    st.session_state.setdefault("lang_name", DEFAULT_LANG_NAME)
    set_language(LANG_OPTIONS[st.session_state["lang_name"]])

    # --- Сайдбар: общие настройки ---
    with st.sidebar:
        st.title("⚙️ " + _("Settings"))

        # Выбор языка. После выбора синхронизируем активный язык.
        lang_name = st.selectbox(_("Language"), list(LANG_OPTIONS.keys()), key="lang_name")
        set_language(LANG_OPTIONS[lang_name])

        currency = st.selectbox(
            _("Display currency"), CURRENCIES, index=CURRENCIES.index(DEFAULT_CURRENCY),
        )

        # Переключатель продвинутого валютного режима (по умолчанию выключен).
        advanced = st.checkbox(
            _("Advanced currency mode (cross-rates)"), value=False,
            help=_("When enabled, all modes let you set separate currencies "
                   "for your card, the site, and Steam."),
        )

        st.divider()
        st.caption(_("CS2 Skin Investing Toolkit"))
        st.caption(_("All prices are entered manually. This is a calculator, not financial advice."))
        st.caption("⚠️ " + _("This is an analytical tool, not financial advice. All investments carry risks."))

    # --- Заголовок ---
    st.title("🎯 Yev Steam Deposit Calculator")
    st.caption(_("Steam balance top-up profit calculator and skin purchase analyzer"))

    # --- Вкладки режимов ---
    tab_mode_1, tab_mode_2, tab_mode_3, tab_mode_4, tab_mode_5 = st.tabs([
        "💰 " + _("Balance top-up (profit)"),
        "🔍 " + _("Where to buy cheaper?"),
        "💳 " + _("Withdrawal (Cashout)"),
        "📈 " + _("Where to sell more profitably?"),
        "🎚️ " + _("Best rarity to buy (collection)"),
    ])
    with tab_mode_1:
        calculate_mode_1(currency, advanced)
    with tab_mode_2:
        calculate_mode_2(currency, advanced)
    with tab_mode_3:
        calculate_mode_3(currency, advanced)
    with tab_mode_4:
        calculate_mode_4(currency, advanced)
    with tab_mode_5:
        calculate_mode_5(currency)

    # --- Юридический футер (i18n): копирайт и товарные знаки Valve ---
    st.divider()
    st.markdown(
        "<div style='text-align: center; color: gray; font-size: 0.8em;'>"
        + _("© 2026 Yev Capital. Not affiliated with Valve Corp. "
            "Steam and CS2 are trademarks of Valve Corporation.")
        + "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()