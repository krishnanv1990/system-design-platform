# Stock Trading Platform Design (Robinhood-like)

## Problem Overview

Design a stock trading platform with <10ms order execution, 10M trades/day, and real-time price updates.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Market Data Feed                                       │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │    Exchange Feeds (NYSE, NASDAQ)  →  Market Data Service  →  Redis/Kafka  │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────┬─────────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Client Layer                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                          │
│  │  Mobile App  │  │   Web App    │  │  Trading API │                          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                          │
└─────────┼─────────────────┼─────────────────┼───────────────────────────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
          ┌─────────────────▼─────────────────┐
          │          API Gateway               │
          │   (Auth, Rate Limit, Routing)      │
          └─────────────────┬─────────────────┘
                            │
     ┌──────────────────────┼──────────────────────┐
     │                      │                      │
     ▼                      ▼                      ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Order     │     │  Portfolio  │     │   Account   │
│   Service   │     │  Service    │     │   Service   │
└──────┬──────┘     └─────────────┘     └─────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Order Management System                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Order     │  │   Risk      │  │  Matching   │  │  Execution  │            │
│  │   Router    │──│   Check     │──│   Engine    │──│   Handler   │            │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │
└───────────────────────────────────────────┬─────────────────────────────────────┘
                                            │
                                            ▼
                              ┌─────────────────────────┐
                              │   Exchange Connectivity  │
                              │   (FIX Protocol)         │
                              └─────────────────────────┘
```

### Core Components

#### 1. Order Management

```python
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
import uuid

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LIMIT = "stop_limit"

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

@dataclass
class Order:
    id: str
    user_id: str
    symbol: str
    order_type: OrderType
    side: OrderSide
    quantity: int
    price: Optional[Decimal]  # For limit orders
    stop_price: Optional[Decimal]  # For stop orders
    status: OrderStatus
    filled_quantity: int = 0
    average_price: Optional[Decimal] = None
    created_at: datetime = None
    updated_at: datetime = None

class OrderService:
    def __init__(self, risk_service, matching_engine, portfolio_service):
        self.risk = risk_service
        self.matching = matching_engine
        self.portfolio = portfolio_service

    async def place_order(self, order_request: dict) -> Order:
        """Place a new order with full validation."""
        order = Order(
            id=str(uuid.uuid4()),
            user_id=order_request["user_id"],
            symbol=order_request["symbol"],
            order_type=OrderType(order_request["order_type"]),
            side=OrderSide(order_request["side"]),
            quantity=order_request["quantity"],
            price=Decimal(order_request.get("price")) if order_request.get("price") else None,
            stop_price=Decimal(order_request.get("stop_price")) if order_request.get("stop_price") else None,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )

        # Risk checks
        risk_result = await self.risk.check_order(order)
        if not risk_result.approved:
            order.status = OrderStatus.REJECTED
            await self.save_order(order)
            raise OrderRejectedException(risk_result.reason)

        order.status = OrderStatus.VALIDATED

        # Submit to matching engine
        execution = await self.matching.submit_order(order)

        order.status = execution.status
        order.filled_quantity = execution.filled_quantity
        order.average_price = execution.average_price
        order.updated_at = datetime.utcnow()

        await self.save_order(order)

        # Update portfolio if filled
        if order.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
            await self.portfolio.update_position(order)

        return order

    async def cancel_order(self, order_id: str, user_id: str) -> Order:
        """Cancel an open order."""
        order = await self.get_order(order_id)

        if order.user_id != user_id:
            raise PermissionError("Not your order")

        if order.status not in [OrderStatus.PENDING, OrderStatus.VALIDATED, OrderStatus.SUBMITTED]:
            raise InvalidStateError("Order cannot be cancelled")

        # Send cancel to exchange
        await self.matching.cancel_order(order_id)

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.utcnow()
        await self.save_order(order)

        return order
```

#### 2. Risk Management

```python
class RiskService:
    """Pre-trade risk checks to prevent invalid orders."""

    async def check_order(self, order: Order) -> RiskResult:
        """Perform comprehensive risk checks."""
        checks = [
            self.check_account_status(order.user_id),
            self.check_buying_power(order),
            self.check_position_limits(order),
            self.check_order_size(order),
            self.check_market_hours(order.symbol),
            self.check_pattern_day_trader(order),
        ]

        results = await asyncio.gather(*checks)

        for result in results:
            if not result.passed:
                return RiskResult(approved=False, reason=result.reason)

        return RiskResult(approved=True)

    async def check_buying_power(self, order: Order) -> CheckResult:
        """Verify user has sufficient buying power."""
        if order.side == OrderSide.SELL:
            # Check if user has the shares to sell
            position = await self.portfolio.get_position(
                order.user_id, order.symbol
            )
            if position.quantity < order.quantity:
                return CheckResult(False, "Insufficient shares")
        else:
            # Check if user has cash to buy
            account = await self.accounts.get(order.user_id)
            required = self.calculate_required_funds(order)

            if account.buying_power < required:
                return CheckResult(False, "Insufficient buying power")

        return CheckResult(True)

    async def check_pattern_day_trader(self, order: Order) -> CheckResult:
        """Check PDT rules for margin accounts."""
        account = await self.accounts.get(order.user_id)

        if account.account_type != "margin":
            return CheckResult(True)

        if account.equity >= 25000:
            return CheckResult(True)

        # Count day trades in last 5 business days
        day_trades = await self.count_day_trades(order.user_id)

        if day_trades >= 3:
            return CheckResult(False, "PDT limit reached")

        return CheckResult(True)
```

#### 3. Real-Time Market Data

```python
class MarketDataService:
    """Real-time market data distribution."""

    def __init__(self, redis_client, kafka_producer):
        self.redis = redis_client
        self.kafka = kafka_producer
        self.subscribers: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def process_market_data(self, data: dict):
        """Process incoming market data from exchanges."""
        symbol = data["symbol"]
        quote = {
            "symbol": symbol,
            "bid": data["bid"],
            "ask": data["ask"],
            "last": data["last"],
            "volume": data["volume"],
            "timestamp": datetime.utcnow().isoformat()
        }

        # Update cache
        await self.redis.hset(f"quote:{symbol}", mapping=quote)

        # Publish to Kafka for processing
        await self.kafka.send("market-data", quote)

        # Push to WebSocket subscribers
        await self.broadcast(symbol, quote)

    async def get_quote(self, symbol: str) -> dict:
        """Get current quote for a symbol."""
        quote = await self.redis.hgetall(f"quote:{symbol}")
        return quote

    async def subscribe(self, websocket: WebSocket, symbols: List[str]):
        """Subscribe client to symbol updates."""
        for symbol in symbols:
            self.subscribers[symbol].add(websocket)

            # Send current quote immediately
            quote = await self.get_quote(symbol)
            if quote:
                await websocket.send(json.dumps({
                    "type": "quote",
                    "data": quote
                }))

    async def broadcast(self, symbol: str, data: dict):
        """Broadcast update to all subscribers."""
        subscribers = self.subscribers.get(symbol, set())
        dead = set()

        for ws in subscribers:
            try:
                await ws.send(json.dumps({
                    "type": "quote_update",
                    "data": data
                }))
            except:
                dead.add(ws)

        self.subscribers[symbol] -= dead
```

### Database Schema

```sql
-- Accounts
CREATE TABLE accounts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    account_type VARCHAR(20),  -- cash, margin
    cash_balance DECIMAL(20, 4),
    buying_power DECIMAL(20, 4),
    equity DECIMAL(20, 4),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Orders
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    symbol VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    price DECIMAL(20, 4),
    stop_price DECIMAL(20, 4),
    status VARCHAR(20) NOT NULL,
    filled_quantity INTEGER DEFAULT 0,
    average_price DECIMAL(20, 4),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_orders_user_status ON orders(user_id, status);
CREATE INDEX idx_orders_symbol ON orders(symbol);

-- Positions
CREATE TABLE positions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    symbol VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    average_cost DECIMAL(20, 4),
    current_value DECIMAL(20, 4),
    unrealized_pnl DECIMAL(20, 4),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, symbol)
);

-- Trades (executions)
CREATE TABLE trades (
    id UUID PRIMARY KEY,
    order_id UUID REFERENCES orders(id),
    symbol VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    price DECIMAL(20, 4) NOT NULL,
    side VARCHAR(10) NOT NULL,
    executed_at TIMESTAMP DEFAULT NOW()
);
```

---

## Realistic Testing

```python
class TestTradingPlatform:
    async def test_market_order_execution(self, client):
        """Test market order executes immediately."""
        response = await client.post("/api/v1/orders", json={
            "symbol": "AAPL",
            "order_type": "market",
            "side": "buy",
            "quantity": 10
        })

        assert response.status_code == 201
        order = response.json()
        assert order["status"] in ["filled", "submitted"]

    async def test_limit_order(self, client):
        """Test limit order placement."""
        response = await client.post("/api/v1/orders", json={
            "symbol": "AAPL",
            "order_type": "limit",
            "side": "buy",
            "quantity": 10,
            "price": "150.00"
        })

        assert response.status_code == 201
        assert response.json()["order_type"] == "limit"

    async def test_insufficient_funds_rejected(self, client):
        """Test order rejected when insufficient funds."""
        # Try to buy more than account can afford
        response = await client.post("/api/v1/orders", json={
            "symbol": "AAPL",
            "order_type": "market",
            "side": "buy",
            "quantity": 1000000
        })

        assert response.status_code == 400
        assert "Insufficient" in response.json()["error"]

    async def test_real_time_quotes(self, ws_client):
        """Test real-time quote streaming."""
        await ws_client.send(json.dumps({
            "action": "subscribe",
            "symbols": ["AAPL", "GOOGL"]
        }))

        quotes_received = []
        for _ in range(10):
            msg = await asyncio.wait_for(ws_client.recv(), timeout=5)
            quotes_received.append(json.loads(msg))

        assert len(quotes_received) >= 2
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Order Latency | < 10ms |
| Quote Latency | < 100ms |
| Availability | 99.999% |
| Order Fill Rate | > 99.9% |
