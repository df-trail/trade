# IBKR Integration Notes

IBKR is now the target future broker for zTrade.

## Candidate API Paths

### TWS / IB Gateway API

- Best fit for local personal automation.
- Requires Trader Workstation or IB Gateway running locally.
- Common paper trading port is `7497`; live TWS commonly uses `7496`.
- zTrade should start with a paper account, contract lookup, order preview, and paper-only order placement.

### IBKR Web / Client Portal API

- REST-style API path with local Client Portal Gateway or newer Web API/OAuth flows depending on account/API availability.
- Useful for account, portfolio, market data, and order workflows, but authentication/session behavior needs to be tested carefully before relying on it for automation.

## zTrade Implementation Plan

1. Keep `PaperBroker` as the default execution path.
2. Build `IbkrBroker` in stages:
   - connection/session health check
   - account lookup
   - contract lookup for stocks and single-leg options
   - quote/market-data entitlement check
   - paper order preview
   - paper order placement
   - order status/fill reconciliation
3. Keep live trading disabled until the full paper workflow is stable.
4. Make `IBKR_LIVE_TRADING_ENABLED=false` the default and require explicit opt-in plus UI confirmation before any live order path exists.

## Environment Variables

```env
IBKR_ACCOUNT_ID=
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1
IBKR_USE_TWS_API=true
IBKR_CLIENT_PORTAL_BASE_URL=https://localhost:5000/v1/api
IBKR_LIVE_TRADING_ENABLED=false
```

## References

- IBKR API documentation home: https://www.interactivebrokers.com/campus/api/
- IBKR TWS API documentation: https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/
- IBKR Web API documentation: https://www.interactivebrokers.com/campus/ibkr-api-page/webapi-doc/
