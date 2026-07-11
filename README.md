# Yev Steam Deposit Calculator & CS2 Arbitrage Tool

A calculator for CS2 investors and traders, built with Python (Streamlit). It computes the real profit of topping up your Steam balance through third-party marketplaces, finds the cheapest way to buy and the most profitable way to sell a skin, and ranks the rarities of a CS2 collection using float, cleanliness and trade-up economics.

## Modes

| # | Mode | What it answers |
|---|------|-----------------|
| 1 | **Balance top-up (profit)** | Buy a skin on a third-party site, sell it on the Steam Community Market — what do you actually net? |
| 2 | **Where to buy cheaper?** | Pay real money on a site, or spend a previously topped-up Steam balance? |
| 3 | **Withdrawal (cashout)** | Buy on Steam with balance, sell on a site, withdraw to card/crypto — what is the cashout ratio? |
| 4 | **Where to sell more profitably?** | Sell on a third-party site, or directly on the Steam Market? |
| 5 | **Best rarity to buy (collection)** | Which rarity of a collection is worth buying — and, in advanced mode, exactly which skin and quality? |

## Key Features

### Trading & arbitrage (modes 1–4)
- **Precise profit math** — third-party marketplace fees (percentage + fixed) and Steam Market taxes are modelled separately, not lumped together.
- **Steam integer-currency math** — native support for Steam's rounding logic in integer-only currencies (e.g. UAH/₴), which prevents "impossible price" results.
- **Exact seller revenue** — the buyer→seller price is resolved by searching the real fee ladder, not by naive division.
- **Advanced cross-rates** — multi-currency mode with independent conversions across the chain (card → site → Steam).
- **Fee presets** — built-in presets for popular marketplaces (CSFloat Crypto/Card, SkinSwap Card/Crypto), all editable.
- **Quantity support** — fee scaling and profit for bulk purchases.

### Collection analysis (mode 5)
- **Rarity ranking (F … A++)** — each rarity is graded from the price ratio between neighbouring rarities, with a reverse-scored penalty for the top rarity and positional adjustments.
- **Simple mode** — one price per rarity, plus a "beautiful / liquid" bonus.
- **Advanced float mode:**
  - **Float caps** — non-standard caps are normalised to the contract weight `w = (float − cap_min) / (cap_max − cap_min)`.
  - **Cleanliness premium** — how much you overpay, per unit of cleanliness, inside a single skin.
  - **Trade-up economics (10 → 1)** — contracts are computed on your *actual* records: 10 copies of one filler, with the output averaged over **all** skins of the next rarity, each priced at the float the contract actually produces (1 skin = 1 outcome).
  - **Two filler strategies** — *by cheapest* (the classic cheapest-filler craft) or *by best price/quality* (every record is tried, the best-return filler wins).
  - **"What to buy" table** — every candidate filler with its float, price, input cost, average output and return, sorted by the selected strategy.
  - **Steam (TP) prices** — optionally enter a Steam price next to each item; prices are converted to your real currency (via cross-rates and the top-up bonus) and the **cheaper** of market vs Steam is used, with the source labelled.
  - **Collection templates** — ready-made collections (currently **Cobblestone** and **Overpass 2024**) fill in every skin, cap, quality and float in one click; you only update the prices.

### General
- **Three languages** — English, Russian, Ukrainian.
- **Multiple currencies** — `$ € ₴ ₽ £`, with integer-currency handling where Steam requires it.
- **No tracking, no accounts, no network calls** — everything is computed locally from the numbers you type.

> **Return vs profit:** in mode 5 the trade-up figure is shown as a **full return** — `output ÷ input`. `100%` means you broke even, `105%` means +5% profit, below `100%` is a loss.

## Quick Start

```bash
git clone https://github.com/Mr4Cemper/Yev-Steam-Deposit-Calculator.git
cd Yev-Steam-Deposit-Calculator
pip install -r requirements.txt
streamlit run app.py
```

Requirements: **Python 3.9+** and `streamlit>=1.30.0` (the only dependency — everything else is the standard library).

## Legal Disclaimer

**Not affiliated with Valve Corp.** This application is an independent analytical tool created for educational and utility purposes. It is NOT affiliated with, endorsed, sponsored, or specifically approved by Valve Corporation. "Counter-Strike", "CS2", "Steam", and their respective logos are trademarks and/or registered trademarks of Valve Corporation. All financial calculations are estimates; use at your own risk. Nothing here is financial advice.

Prices shipped inside the collection templates are **starting values only** — update them to the current market before relying on any result.

Any trademarks contained in the source code, binaries, and/or in the documentation, are the sole property of their respective owners.

## License

This project is licensed under the GNU Affero General Public License v3.0 or later.

Copyright (c) 2026 Bohdan Yevtushenko (Mr4Cemper)

You are free to use, modify, and redistribute this project under the terms of the AGPLv3.

If you run a modified version of this application over a network, you must provide the corresponding source code to users interacting with it.

The full license text is available in the `LICENSE` file.
