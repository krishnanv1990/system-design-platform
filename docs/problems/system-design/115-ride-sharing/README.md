# Ride Sharing Service Design (Uber-like)

## Problem Overview

Design a ride-sharing platform with 20M rides/day, <10s matching latency, and real-time tracking.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Real-time Location Layer                            │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │            Driver/Rider Apps → Location Updates (3-5 sec)                 │   │
│  └────────────────────────────────────┬─────────────────────────────────────┘   │
│                                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    Location Service (Redis Geo)                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │
┌────────────────────────────────────────▼────────────────────────────────────────┐
│                              Core Services                                       │
│                                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────┐   │
│  │  Matching  │  │  Pricing   │  │   Trip     │  │  Payment   │  │ Driver │   │
│  │  Service   │  │  Service   │  │  Service   │  │  Service   │  │ Service│   │
│  └─────┬──────┘  └────────────┘  └────────────┘  └────────────┘  └────────┘   │
│        │                                                                        │
│        ▼                                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                        Dispatch Engine                                    │  │
│  │   (Matches riders with optimal drivers using geospatial algorithms)      │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Location Service

```python
import redis.asyncio as redis
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Location:
    lat: float
    lng: float
    timestamp: datetime

@dataclass
class Driver:
    id: str
    location: Location
    status: str  # available, busy, offline
    vehicle_type: str
    rating: float

class LocationService:
    """Real-time driver location tracking."""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.LOCATION_TTL = 60  # Seconds

    async def update_driver_location(
        self,
        driver_id: str,
        lat: float,
        lng: float,
        status: str
    ):
        """Update driver's current location."""
        # Update geo position
        await self.redis.geoadd(
            "drivers:locations",
            lng, lat, driver_id
        )

        # Update driver status
        await self.redis.hset(f"driver:{driver_id}", mapping={
            "lat": lat,
            "lng": lng,
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        })

        # Set TTL for auto-removal
        await self.redis.expire(f"driver:{driver_id}", self.LOCATION_TTL)

    async def find_nearby_drivers(
        self,
        lat: float,
        lng: float,
        radius_km: float = 5,
        vehicle_type: str = None,
        limit: int = 10
    ) -> List[Driver]:
        """Find available drivers near a location."""
        # Geo query
        nearby = await self.redis.georadius(
            "drivers:locations",
            lng, lat,
            radius_km,
            unit="km",
            withdist=True,
            count=limit * 3  # Get more to filter
        )

        drivers = []
        for driver_id, distance in nearby:
            driver_data = await self.redis.hgetall(f"driver:{driver_id}")

            if not driver_data:
                continue
            if driver_data.get("status") != "available":
                continue
            if vehicle_type and driver_data.get("vehicle_type") != vehicle_type:
                continue

            drivers.append(Driver(
                id=driver_id,
                location=Location(
                    float(driver_data["lat"]),
                    float(driver_data["lng"]),
                    datetime.now()
                ),
                status=driver_data["status"],
                vehicle_type=driver_data.get("vehicle_type", "standard"),
                rating=float(driver_data.get("rating", 5.0))
            ))

            if len(drivers) >= limit:
                break

        return drivers
```

#### 2. Matching Service

```python
class MatchingService:
    """Matches riders with optimal drivers."""

    def __init__(self, location_service, pricing_service):
        self.location = location_service
        self.pricing = pricing_service

    async def request_ride(
        self,
        rider_id: str,
        pickup: Location,
        dropoff: Location,
        vehicle_type: str = "standard"
    ) -> RideRequest:
        """Create a new ride request and find matches."""
        # Calculate price
        price = await self.pricing.calculate(
            pickup, dropoff, vehicle_type
        )

        # Create ride request
        request = RideRequest(
            id=str(uuid.uuid4()),
            rider_id=rider_id,
            pickup=pickup,
            dropoff=dropoff,
            vehicle_type=vehicle_type,
            estimated_price=price,
            status="pending",
            created_at=datetime.utcnow()
        )

        await self.save_request(request)

        # Find and dispatch to drivers
        asyncio.create_task(self.find_driver(request))

        return request

    async def find_driver(self, request: RideRequest):
        """Find and dispatch to optimal driver."""
        MAX_ATTEMPTS = 3
        TIMEOUT = 30  # seconds per driver

        for attempt in range(MAX_ATTEMPTS):
            # Find nearby available drivers
            drivers = await self.location.find_nearby_drivers(
                request.pickup.lat,
                request.pickup.lng,
                radius_km=5 * (attempt + 1),  # Expand radius on retry
                vehicle_type=request.vehicle_type
            )

            if not drivers:
                continue

            # Score and rank drivers
            scored = await self.score_drivers(drivers, request)

            for driver in scored:
                # Dispatch to driver
                accepted = await self.dispatch_to_driver(
                    driver, request, timeout=TIMEOUT
                )

                if accepted:
                    request.driver_id = driver.id
                    request.status = "matched"
                    await self.save_request(request)
                    return

        # No driver found
        request.status = "no_drivers"
        await self.save_request(request)
        await self.notify_rider(request.rider_id, "no_drivers_available")

    async def score_drivers(
        self,
        drivers: List[Driver],
        request: RideRequest
    ) -> List[Driver]:
        """Score drivers by ETA, rating, and acceptance rate."""
        scored = []

        for driver in drivers:
            # Calculate ETA
            eta = await self.calculate_eta(
                driver.location,
                request.pickup
            )

            # Get acceptance rate
            stats = await self.get_driver_stats(driver.id)

            # Score (lower is better)
            score = (
                eta.minutes * 2 +
                (5 - driver.rating) * 10 +
                (1 - stats.acceptance_rate) * 20
            )

            scored.append((score, driver, eta))

        scored.sort(key=lambda x: x[0])
        return [(d, e) for _, d, e in scored]

    async def dispatch_to_driver(
        self,
        driver: Driver,
        request: RideRequest,
        timeout: int
    ) -> bool:
        """Send ride request to driver and wait for response."""
        # Send push notification
        await self.notify_driver(driver.id, {
            "type": "ride_request",
            "request_id": request.id,
            "pickup": request.pickup.__dict__,
            "dropoff": request.dropoff.__dict__,
            "price": request.estimated_price
        })

        # Wait for response
        try:
            response = await asyncio.wait_for(
                self.wait_for_response(request.id, driver.id),
                timeout=timeout
            )
            return response == "accepted"
        except asyncio.TimeoutError:
            return False
```

#### 3. Pricing Service

```python
class PricingService:
    """Dynamic pricing with surge support."""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def calculate(
        self,
        pickup: Location,
        dropoff: Location,
        vehicle_type: str
    ) -> PriceEstimate:
        """Calculate ride price with surge."""
        # Base price calculation
        distance_km = self.haversine_distance(pickup, dropoff)
        duration_min = await self.estimate_duration(pickup, dropoff)

        base_price = self.get_base_price(vehicle_type)
        per_km = self.get_per_km_rate(vehicle_type)
        per_min = self.get_per_min_rate(vehicle_type)

        base_fare = (
            base_price +
            distance_km * per_km +
            duration_min * per_min
        )

        # Get surge multiplier
        surge = await self.get_surge_multiplier(pickup)

        final_price = base_fare * surge

        return PriceEstimate(
            base_fare=base_fare,
            surge_multiplier=surge,
            final_price=final_price,
            currency="USD",
            distance_km=distance_km,
            duration_min=duration_min
        )

    async def get_surge_multiplier(self, location: Location) -> float:
        """Calculate surge based on supply/demand."""
        geohash = self.location_to_geohash(location, precision=5)

        # Get demand (ride requests in area)
        demand = await self.redis.get(f"demand:{geohash}") or 0

        # Get supply (available drivers in area)
        supply = await self.redis.get(f"supply:{geohash}") or 1

        ratio = int(demand) / max(int(supply), 1)

        # Surge tiers
        if ratio > 3:
            return 2.5
        elif ratio > 2:
            return 2.0
        elif ratio > 1.5:
            return 1.5
        elif ratio > 1.2:
            return 1.25
        else:
            return 1.0

    async def update_demand(self, location: Location):
        """Record demand signal."""
        geohash = self.location_to_geohash(location, precision=5)
        await self.redis.incr(f"demand:{geohash}")
        await self.redis.expire(f"demand:{geohash}", 300)  # 5 min window
```

### Testing

```python
class TestRideSharing:
    async def test_request_ride(self, client):
        """Test ride request flow."""
        response = await client.post("/api/v1/rides", json={
            "pickup": {"lat": 37.7749, "lng": -122.4194},
            "dropoff": {"lat": 37.7849, "lng": -122.4094},
            "vehicle_type": "standard"
        })

        assert response.status_code == 201
        ride = response.json()
        assert ride["status"] in ["pending", "matched"]
        assert ride["estimated_price"] > 0

    async def test_driver_matching(self, client, driver_client):
        """Test driver gets matched to ride."""
        # Driver goes online
        await driver_client.post("/api/v1/driver/status", json={
            "status": "available",
            "location": {"lat": 37.7750, "lng": -122.4195}
        })

        # Rider requests
        ride = await client.post("/api/v1/rides", json={
            "pickup": {"lat": 37.7749, "lng": -122.4194},
            "dropoff": {"lat": 37.7849, "lng": -122.4094}
        })

        # Driver should receive request
        notification = await driver_client.get_notification(timeout=30)
        assert notification["type"] == "ride_request"

    async def test_surge_pricing(self, client):
        """Test surge pricing triggers."""
        # Simulate high demand
        for _ in range(100):
            await client.post("/api/v1/rides", json={
                "pickup": {"lat": 37.7749, "lng": -122.4194},
                "dropoff": {"lat": 37.7849, "lng": -122.4094}
            })

        # Next request should have surge
        ride = await client.post("/api/v1/rides", json={
            "pickup": {"lat": 37.7749, "lng": -122.4194},
            "dropoff": {"lat": 37.7849, "lng": -122.4094}
        })

        assert ride.json()["surge_multiplier"] > 1.0
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Matching Latency | < 10 seconds |
| Location Update Freq | 3-5 seconds |
| ETA Accuracy | > 90% |
| Driver Utilization | > 70% |
