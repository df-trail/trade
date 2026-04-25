# IBKR Integration Notes

IBKR is now the target broker for zTrade.

## Account Linking Checklist

Use the TWS or IB Gateway API path first. Do not put your IBKR username or password into zTrade; log in through TWS or IB Gateway and let zTrade connect to the local API socket.

1. Install and open Trader Workstation or IB Gateway.
2. Log in to the IBKR paper trading account first.
3. In TWS, open Global Configuration, then API, then Settings.
4. Enable `Enable ActiveX and Socket Clients`.
5. For the first pricing test, keep API `Read-Only` enabled. It blocks API orders but still lets us validate connectivity and market data.
6. When we are ready for paper order testing, disable `Read-Only` in the paper session only.
7. Use matching socket ports:
   - TWS paper: `7497`
   - TWS live: `7496`
   - IB Gateway paper: `4002`
   - IB Gateway live: `4001`
8. Keep host as `127.0.0.1` when zTrade and TWS/Gateway are on the same machine.
9. Use a unique `IBKR_CLIENT_ID` if another API tool is also connected.
10. Keep `IBKR_LIVE_TRADING_ENABLED=false`.

For market data, complete the Market Data API acknowledgement in Client Portal and confirm subscriptions/permissions for the instruments you want. U.S. stock and options data generally requires appropriate Level 1 subscriptions; OPRA is the common U.S. options data subscription, and options Greeks require underlying and derivative market data permissions.

zTrade does not need your login credentials. The `.env` file should only hold connection settings such as account id, host, port, client id, and the live-trading kill switch.

Current zTrade status: the app still defaults to `PaperBroker`. The next IBKR implementation step is a connection-health panel and read-only pricing provider, followed by paper order preview and paper order placement.

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
