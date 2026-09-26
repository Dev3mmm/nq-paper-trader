# NQ Paper Trader

Rule-based **opening-range breakout** paper trader for Nasdaq-100 futures (NQ / MNQ), with a live dashboard.

**Dashboard:** https://dev3mmm.github.io/nq-paper-trader/  (pick a deposit + risk % to see the profit on your account size)

## Rules (frozen 2026-09-25)
1. Mark the high/low of the first 15 minutes (09:30-09:45 New York).
2. First candle close above the range = BUY, below = SELL.
3. Trade only if the breakout is strong (filters below), otherwise NO TRADE.
4. Stop / target / flat at 15:45 (cost 1 point per trade).

| Version | Chart | Filters | Stop | Target |
|---|---|---|---|---|
| 1-min | 1m | entry by 10:30, close >=10% of range past level, range >=0.35 x 14-day avg range | range midpoint | 1R |
| 5-min | 5m | candle body >=70%, close >=10% past level, range >=0.35 x avg range | opposite side of range | 1.5R |

Backtest (Jan 2023 - Sep 2026, Dukascopy Nasdaq-100 index CFD): 1-min 102 trades / 61% win / PF 1.74; 5-min 132 trades / 52% win / PF 1.56.
Forward paper test started 2026-09-25 and is counted separately on the dashboard.

## Files
- `paper_trader.py` - daily updater (downloads new data, rebuilds the dashboard)
- `strategies.py` - the two strategies
- `dashboard.py` + `dashboard_template.html` - dashboard generator
- `.github/workflows/update.yml` - runs daily in the cloud (GitHub Actions) and republishes the dashboard

> Simulated results, not financial advice. Backtests do not guarantee future results.
