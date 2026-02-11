# Interactive Brokers Setup Guide

This guide covers setting up Interactive Brokers integration for the Trading Analyst system.

## Prerequisites

1. **Interactive Brokers Account**
   - Paper trading account (recommended for testing)
   - Or live trading account with funded balance

2. **TWS or IB Gateway Installed**
   - Download from: https://www.interactivebrokers.com/en/trading/tws-updateable-latest.php
   - IB Gateway is lighter-weight but TWS has a GUI for monitoring

## TWS/Gateway Configuration

### Step 1: Enable API Connections

1. Open TWS or IB Gateway
2. Go to **File** → **Global Configuration** (TWS) or **Configure** → **Settings** (Gateway)
3. Navigate to **API** → **Settings**
4. Configure:
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Allow connections from localhost only (recommended)
   - Socket port: **7497** (paper) or **7496** (live)
   - ❌ Read-Only API (must be unchecked to place orders)
   - Master API client ID: Leave as default or set to 0

### Step 2: Verify Port Settings

| Mode | TWS Port | Gateway Port |
|------|----------|--------------|
| Paper Trading | 7497 | 4001 |
| Live Trading | 7496 | 4002 |

### Step 3: Test Connection

```bash
# Quick connection test
cd backend
python -c "
from app.brokers.ib import IBBroker
import asyncio

async def test():
    broker = IBBroker()
    await broker.connect()
    print('Connected successfully!')
    await broker.disconnect()

asyncio.run(test())
"
```

## Environment Configuration

Add to your `.env` file:

```bash
BROKER_TYPE=ib
IB_HOST=127.0.0.1
IB_PORT=4001          # Paper: 4001, Live: 4002
IB_CLIENT_ID=1
IB_ACCOUNT=DUH123456  # Your IB account ID (DU* for paper, U* for live)
```

## Troubleshooting

### Connection Refused

**Error**: `Failed to connect to IB: Connection refused`

**Solutions**:
1. Ensure TWS/Gateway is running
2. Verify API is enabled in TWS settings
3. Check port number matches TWS configuration
4. Ensure "Allow connections from localhost" is enabled

### Client ID in Use

**Error**: `Client ID already in use`

**Solutions**:
1. Increment `IB_CLIENT_ID` in `.env`
2. Close other applications using the same client ID
3. Restart TWS/Gateway

**Note**: IB limits API connections to 8 per user. If you see connection failures, ensure other API clients (other terminals, scripts, third-party tools) are disconnected.

### Order Rejected

**Error**: `Order rejected by broker`

**Common causes**:
- Market is closed (US market: 9:30 AM - 4:00 PM ET)
- Insufficient funds in account
- Invalid symbol
- Order quantity below minimum

### API Connection Drops

**Symptoms**: Orders stop processing, "connection lost" messages

**Solutions**:
1. Check TWS/Gateway hasn't logged out (auto-logoff after inactivity)
2. Increase memory allocation for TWS (4GB+ recommended)
3. Check network connectivity
4. The IBBroker will attempt automatic reconnection

## Paper Trading vs Live Trading

### Paper Trading (Recommended for Testing)

- Uses simulated funds
- Orders fill at market prices
- No real money at risk
- Port: 7497 (TWS) or 4001 (Gateway)
- Account ID format: `DUH######` (Demo User Holder)

### Live Trading

- Uses real funds
- Real order execution
- **USE WITH CAUTION**
- Port: 7496 (TWS) or 4002 (Gateway)
- Account ID format: `U#######` (real account)

## Order Flow

When you execute a setup, we use IB's bracket order mechanism with `parentId` linking:

1. **Bracket Submission**: Entry (market) and stop orders submitted together atomically
2. **Entry Fills**: System waits for entry to fill (up to 60s)
3. **Stop Activates**: Stop order automatically activates after entry fills (IB manages this)
4. **Confirmation**: Order ID returned in format `IB-{entry}:{stop}`

**Key benefit**: No unprotected position window - stop is already queued before entry fills.

You can monitor orders in TWS:
- Orders appear in the "Orders" panel
- Fills appear in "Trades" panel
- Positions appear in "Portfolio" panel

## Data Subscriptions

Note: The API uses "off-platform" data which may require separate subscriptions.
For paper trading, delayed data is usually sufficient.

## Support

- IB API Documentation: https://interactivebrokers.github.io/tws-api/
- IB Customer Service: Contact through Client Portal

## Testing the Integration

### Prerequisites
- IB Gateway running with API enabled on port 4001 (paper) or 4002 (live)
- Docker services running (`./scripts/dc.sh up -d`)

### Quick Connection Test
```bash
./scripts/dc.sh exec -e IB_HOST=host.docker.internal -e IB_PORT=4001 backend-dev python -c "
from ib_async import IB
import asyncio
async def test():
    ib = IB()
    await ib.connectAsync('host.docker.internal', 4001, clientId=99, timeout=10)
    print(f'Connected! Accounts: {ib.managedAccounts()}')
    ib.disconnect()
asyncio.run(test())
"
```

### Integration Tests

Tests are in `backend/tests/integration/` and skipped by default (require live IB Gateway).

**Data Provider** (`test_ib_data_provider_integration.py`):
- `test_fetch_15min_data_for_aapl` - Fetches intraday data
- `test_get_symbol_info` - Retrieves symbol information and validates it exists

**Broker** (`test_ib_broker_integration.py`):
- `test_connection` - Verifies connection
- `test_place_and_query_order` - Places paper trade (1 share AAPL)
- `test_cancel_stop_order` - Places and cancels order

**Running Tests** (temporarily remove `@pytest.mark.skip` from test class):
```bash
# Data provider
./scripts/dc.sh exec -e IB_HOST=host.docker.internal -e IB_PORT=4001 -e IB_DATA_CLIENT_ID=10 \
  backend-dev pytest tests/integration/test_ib_data_provider_integration.py -v -s --no-cov

# Broker (places real paper trades!)
./scripts/dc.sh exec -e IB_HOST=host.docker.internal -e IB_PORT=4001 -e IB_CLIENT_ID=1 \
  backend-dev pytest tests/integration/test_ib_broker_integration.py -v -s --no-cov
```

**Important**: Restore `@pytest.mark.skip` after testing to prevent CI failures.
