# Grocery Price Optimizer 🛒

Daily pipeline: scrape PL grocery prices → pick cheapest store per item →
Telegram notification grouped by store.

## Coverage reality
| Store | Data | Source |
|---|---|---|
| Frisco | full catalog | JSON search API |
| Auchan | full catalog | Playwright + XHR intercept |
| Carrefour | full catalog | Playwright + XHR intercept |
| Lidl | promos only | leaflet feed (calibrate) |
| Biedronka | promos only | leaflet feed (calibrate) |

No match from Lidl/Biedronka = no data, not "unavailable".

## Setup
1. `pip install -r requirements.txt && playwright install chromium`
2. Telegram: @BotFather → `/newbot` → token. Message the bot once, then
   `https://api.telegram.org/bot<TOKEN>/getUpdates` → `chat.id`.
3. Push to GitHub, add repo Secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
4. Test manually: Actions → *Daily grocery price check* → Run workflow.

## Calibration (one-time, ~30 min)
- **Frisco**: verify `SEARCH_URL` response shape in DevTools; adjust field paths.
- **Auchan/Carrefour**: run `hypermarkets.search(..., headless=False)` locally,
  watch Network tab, pin the real `xhr_marker` URL patterns.
- **Lidl/Biedronka**: implement `fetch_*_promos()` against the leaflet JSON
  feeds (or Blix as aggregator fallback).
- Once matches look right, pin `product_id` per store in the YAML instead of
  free-text queries — deterministic beats fuzzy.

## Tuning
- Add items in `config/shopping_list.yaml` (one block per product).
- Unit prices (zł/kg, zł/l) drive comparisons; pack price is the fallback.
- The message shows savings vs. the cheapest single store covering everything.

## Notes
- GitHub Actions cron is free; runs may drift ±15 min.
- Scrape gently: daily frequency, few queries, standard UA. Respect ToS.
