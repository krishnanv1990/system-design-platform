# Location-Based Service Design (Google Maps-like)

## Problem Overview

Design a mapping and navigation service with 1B MAU, real-time traffic, and route calculation in <2 seconds.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Client Apps                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                          │
│  │  Mobile App  │  │  Web App     │  │  Car System  │                          │
│  │  (iOS/And)   │  │              │  │  (CarPlay)   │                          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                          │
└─────────┼─────────────────┼─────────────────┼───────────────────────────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
          ┌─────────────────▼─────────────────┐
          │          CDN / Edge Cache          │
          │   (Map tiles, popular routes)      │
          └─────────────────┬─────────────────┘
                            │
          ┌─────────────────▼─────────────────┐
          │           API Gateway              │
          └─────────────────┬─────────────────┘
                            │
     ┌──────────────────────┼──────────────────────┐
     │                      │                      │
     ▼                      ▼                      ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Map Tile   │     │  Routing    │     │  Search/    │
│  Service    │     │  Service    │     │  Geocoding  │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Traffic   │
                    │   Service   │
                    └─────────────┘
```

### Core Components

#### 1. Geospatial Indexing

```python
from dataclasses import dataclass
from typing import List, Tuple
import geohash

@dataclass
class GeoPoint:
    lat: float
    lng: float

@dataclass
class Place:
    id: str
    name: str
    location: GeoPoint
    category: str
    address: str

class GeoIndex:
    """Geospatial indexing using geohash for efficient queries."""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def add_place(self, place: Place):
        """Add a place to the geo index."""
        # Store in Redis geo set
        await self.redis.geoadd(
            "places",
            place.location.lng,
            place.location.lat,
            place.id
        )

        # Store details
        await self.redis.hset(
            f"place:{place.id}",
            mapping={
                "name": place.name,
                "lat": place.location.lat,
                "lng": place.location.lng,
                "category": place.category,
                "address": place.address
            }
        )

    async def search_nearby(
        self,
        center: GeoPoint,
        radius_km: float,
        category: str = None,
        limit: int = 20
    ) -> List[Place]:
        """Search for places near a location."""
        # Query Redis geo
        results = await self.redis.georadius(
            "places",
            center.lng,
            center.lat,
            radius_km,
            unit="km",
            withdist=True,
            count=limit * 2  # Get more to filter by category
        )

        places = []
        for place_id, distance in results:
            place_data = await self.redis.hgetall(f"place:{place_id}")

            if category and place_data.get("category") != category:
                continue

            places.append({
                **place_data,
                "distance_km": distance
            })

            if len(places) >= limit:
                break

        return places

    async def geocode(self, address: str) -> GeoPoint:
        """Convert address to coordinates."""
        # Check cache first
        cache_key = f"geocode:{hashlib.md5(address.encode()).hexdigest()}"
        cached = await self.redis.get(cache_key)
        if cached:
            lat, lng = cached.split(",")
            return GeoPoint(float(lat), float(lng))

        # Query geocoding service
        result = await self.geocoding_api.geocode(address)

        # Cache result
        await self.redis.setex(
            cache_key,
            86400 * 30,  # 30 days
            f"{result.lat},{result.lng}"
        )

        return result
```

#### 2. Routing Engine

```python
import heapq
from typing import Dict, List, Tuple

class RoutingEngine:
    """
    A* routing algorithm with traffic-aware edge weights.
    """

    def __init__(self, road_graph, traffic_service):
        self.graph = road_graph
        self.traffic = traffic_service

    async def find_route(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        avoid: List[str] = None
    ) -> Route:
        """Find optimal route using A* algorithm."""
        # Find nearest nodes to origin and destination
        origin_node = await self.graph.find_nearest_node(origin)
        dest_node = await self.graph.find_nearest_node(destination)

        # A* search
        open_set = [(0, origin_node)]
        came_from = {}
        g_score = {origin_node: 0}
        f_score = {origin_node: self.heuristic(origin_node, dest_node)}

        while open_set:
            current = heapq.heappop(open_set)[1]

            if current == dest_node:
                return await self.reconstruct_path(came_from, current)

            for neighbor, edge in await self.graph.get_neighbors(current):
                # Get traffic-adjusted edge weight
                weight = await self.get_edge_weight(edge, avoid)

                tentative_g = g_score[current] + weight

                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self.heuristic(neighbor, dest_node)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        raise NoRouteFoundError()

    async def get_edge_weight(self, edge, avoid: List[str]) -> float:
        """Get edge weight adjusted for current traffic."""
        base_time = edge.length / edge.speed_limit

        # Check if road type should be avoided
        if avoid and edge.road_type in avoid:
            return float('inf')

        # Get current traffic
        traffic_factor = await self.traffic.get_factor(edge.id)

        return base_time * traffic_factor

    def heuristic(self, node_a, node_b) -> float:
        """Haversine distance heuristic."""
        return haversine_distance(
            node_a.lat, node_a.lng,
            node_b.lat, node_b.lng
        ) / 100  # Assume max speed 100 km/h

    async def reconstruct_path(self, came_from: dict, current) -> Route:
        """Reconstruct the path from A* result."""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()

        # Build turn-by-turn directions
        directions = await self.build_directions(path)

        return Route(
            nodes=path,
            directions=directions,
            distance_km=self.calculate_distance(path),
            duration_minutes=self.calculate_duration(path)
        )
```

#### 3. Traffic Service

```python
class TrafficService:
    """Real-time traffic data management."""

    def __init__(self, redis_client, kafka_consumer):
        self.redis = redis_client
        self.kafka = kafka_consumer

    async def get_factor(self, edge_id: str) -> float:
        """Get traffic factor for an edge (1.0 = normal, >1 = slower)."""
        traffic = await self.redis.get(f"traffic:{edge_id}")
        if traffic:
            return float(traffic)
        return 1.0

    async def update_traffic(self, edge_id: str, speed_ratio: float):
        """Update traffic for an edge."""
        # speed_ratio = actual_speed / speed_limit
        # Convert to factor (lower speed = higher factor)
        factor = 1.0 / max(speed_ratio, 0.1)

        await self.redis.setex(
            f"traffic:{edge_id}",
            300,  # 5 minute TTL
            str(factor)
        )

    async def process_location_updates(self):
        """Process location updates from users to compute traffic."""
        async for message in self.kafka.consume("user-locations"):
            user_id = message["user_id"]
            location = message["location"]
            speed = message["speed"]
            timestamp = message["timestamp"]

            # Map location to road edge
            edge = await self.graph.find_edge(location)
            if edge:
                # Update traffic sample
                await self.add_traffic_sample(edge.id, speed)

    async def add_traffic_sample(self, edge_id: str, speed: float):
        """Add a speed sample for traffic calculation."""
        key = f"traffic_samples:{edge_id}"
        now = time.time()

        # Add sample
        await self.redis.zadd(key, {f"{speed}:{now}": now})

        # Remove old samples (> 5 minutes)
        await self.redis.zremrangebyscore(key, 0, now - 300)

        # Calculate average speed
        samples = await self.redis.zrange(key, 0, -1)
        if samples:
            speeds = [float(s.split(":")[0]) for s in samples]
            avg_speed = sum(speeds) / len(speeds)

            edge = await self.graph.get_edge(edge_id)
            speed_ratio = avg_speed / edge.speed_limit
            await self.update_traffic(edge_id, speed_ratio)
```

#### 4. Map Tile Service

```python
class MapTileService:
    """Vector and raster map tile serving."""

    async def get_tile(
        self,
        z: int,  # Zoom level
        x: int,  # Tile X
        y: int   # Tile Y
    ) -> bytes:
        """Get a map tile."""
        cache_key = f"tile:{z}/{x}/{y}"

        # Check cache
        cached = await self.redis.get(cache_key)
        if cached:
            return cached

        # Generate or fetch tile
        tile = await self.generate_tile(z, x, y)

        # Cache with appropriate TTL based on zoom
        ttl = 86400 if z < 10 else 3600  # Longer cache for lower zoom
        await self.redis.setex(cache_key, ttl, tile)

        return tile
```

### Testing

```python
class TestLocationService:
    async def test_geocoding(self, client):
        """Test address to coordinates."""
        response = await client.get("/api/v1/geocode", params={
            "address": "1600 Amphitheatre Parkway, Mountain View, CA"
        })

        assert response.status_code == 200
        result = response.json()
        assert abs(result["lat"] - 37.422) < 0.01
        assert abs(result["lng"] - -122.084) < 0.01

    async def test_routing(self, client):
        """Test route calculation."""
        response = await client.get("/api/v1/directions", params={
            "origin": "37.7749,-122.4194",
            "destination": "37.3382,-121.8863"
        })

        assert response.status_code == 200
        route = response.json()
        assert route["distance_km"] > 0
        assert len(route["directions"]) > 0

    async def test_nearby_search(self, client):
        """Test nearby places search."""
        response = await client.get("/api/v1/places/nearby", params={
            "lat": 37.7749,
            "lng": -122.4194,
            "radius": 1,
            "category": "restaurant"
        })

        assert response.status_code == 200
        assert len(response.json()["places"]) > 0
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Route Calculation | < 2 seconds |
| Tile Load Time | < 200ms |
| Traffic Update Lag | < 1 minute |
| Geocoding Latency | < 100ms |
