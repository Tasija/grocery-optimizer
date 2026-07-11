# Grocery Price Optimizer 🛒

Daily pipeline: scrape PL grocery prices → pick cheapest store per item →
Telegram notification grouped by store.

## Coverage reality
| Store | Data | Source |
|---|---|---|
| Frisco | full catalog | JSON search API (httpx) |
| Auchan | full catalog | SSR `__INITIAL_STATE__` JSON (httpx) |
| Carrefour | full catalog | Playwright + SSR `__NEXT_DATA__` JSON |
| Lidl | promos only | Schwarz leaflet JSON feed (non-food only, see below) |
| Biedronka | promos only | none found — returns no data |

No match from Lidl/Biedronka = no data, not "unavailable".

## Setup
1. `pip install -r requirements.txt && playwright install chromium`
2. Telegram: @BotFather → `/newbot` → token. Message the bot once, then
   `https://api.telegram.org/bot<TOKEN>/getUpdates` → `chat.id`.
3. Push to GitHub, add repo Secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
4. Test manually: Actions → *Daily grocery price check* → Run workflow.

## Calibration (done 2026-07-11)
Endpoints pinned against the live sites:

- **Frisco**: `GET https://www.frisco.pl/app/commerce/api/v1/offer/products/query`
  works with plain httpx. Products at `products[].product`; price at
  `price.price`; promo signal is `priceBeforeDiscount` inside `price` (the
  `promotions` list stays empty even on discounts). Unit price comes from
  `grammage` + `unitOfMeasure` (`Kilogram`/`Litre`); for `Piece` items
  grammage is 1.0 even on multipacks, so quantity is parsed from the name.
- **Auchan**: `GET https://zakupy.auchan.pl/search?q=...` — the AWS WAF
  passes plain httpx document GETs, and results are server-rendered into
  `window.__INITIAL_STATE__` (ordered ids at
  `data.search.catalogue.data.productGroups[0].products`, entities at
  `data.products.productEntities`). The product XHR
  (`/api/webproductpagews/v6/product-pages/search`) only fires on
  client-side navigation, so SSR parsing is the stable path. Promo =
  `price.original != price.current`; unit price at `price.unit`.
- **Carrefour**: `https://www.carrefour.pl/szukaj?q=...` returns 403 to
  plain httpx, so headless Chromium (pl-PL locale, realistic UA) loads it —
  no consent interaction needed since results ship server-rendered in
  `__NEXT_DATA__` at `props.initialState.products.data.content`. Price at
  `actualSku.amount.actualGrossPrice`, promo flag `actualSku.promotion`,
  unit price parsed from `actualSku.grammageWithUnitString` ("4,25 zł/1 l").
- **Lidl**: leaflets run on the Schwarz platform —
  `GET https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier=<slug>&region_id=0`
  (slugs scraped from `lidl.pl/c/nasze-gazetki/s10008614`). Caveat: the
  feed's structured `products` only cover lidl.pl online-shop (non-food)
  items; grocery promo pages are flat images, so grocery matches are rare.
  Food promos exist only in the authenticated Lidl Plus app API.
- **Biedronka**: no parseable feed. `biedronka.pl/pl/gazetki` is a JS shell
  whose leaflets are pure page images; the only site XHRs are user/store
  data. Structured offers live only in the authenticated Moja Biedronka
  app API. `fetch_biedronka_promos()` returns `[]` on purpose.
- Once matches look right, pin `product_id` per store in the YAML instead of
  free-text queries — deterministic beats fuzzy.

## Tuning
- Add items in `config/shopping_list.yaml` (one block per product).
- Unit prices (zł/kg, zł/l) drive comparisons; pack price is the fallback.
- The message shows savings vs. the cheapest single store covering everything.

## Notes
- GitHub Actions cron is free; runs may drift ±15 min.
- Scrape gently: daily frequency, few queries, standard UA. Respect ToS.
