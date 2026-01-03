# Distributed Web Crawler Design

## Problem Overview

Design a web crawler that can crawl 1 billion pages per month with politeness, deduplication, and fault tolerance.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution Architecture

### High-Level Design

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                              Crawler Orchestration                                 │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                         URL Frontier Manager                                │  │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │  │
│  │   │  Priority   │  │  Politeness │  │  Domain     │  │  Back       │      │  │
│  │   │  Queue      │  │  Queue      │  │  Scheduler  │  │  Queue      │      │  │
│  │   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘      │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────┬──────────────────────────────────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        │                                │                                │
        ▼                                ▼                                ▼
┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
│  Crawler Node 1  │        │  Crawler Node 2  │        │  Crawler Node N  │
│  ┌────────────┐  │        │  ┌────────────┐  │        │  ┌────────────┐  │
│  │  Fetcher   │  │        │  │  Fetcher   │  │        │  │  Fetcher   │  │
│  │  (HTTP)    │  │        │  │  (HTTP)    │  │        │  │  (HTTP)    │  │
│  ├────────────┤  │        │  ├────────────┤  │        │  ├────────────┤  │
│  │  Parser    │  │        │  │  Parser    │  │        │  │  Parser    │  │
│  │  (HTML)    │  │        │  │  (HTML)    │  │        │  │  (HTML)    │  │
│  ├────────────┤  │        │  ├────────────┤  │        │  ├────────────┤  │
│  │  Extractor │  │        │  │  Extractor │  │        │  │  Extractor │  │
│  │  (Links)   │  │        │  │  (Links)   │  │        │  │  (Links)   │  │
│  └────────────┘  │        │  └────────────┘  │        │  └────────────┘  │
└────────┬─────────┘        └────────┬─────────┘        └────────┬─────────┘
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │                            │                            │
        ▼                            ▼                            ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Dedup Filter   │    │   Content Store  │    │   Link Store     │
│   (Bloom/Redis)  │    │   (Cloud Storage)│    │   (URL Frontier) │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

### Core Components

#### 1. URL Frontier

```python
from dataclasses import dataclass
from typing import List, Optional
import heapq
from collections import defaultdict

@dataclass
class CrawlRequest:
    url: str
    priority: int
    depth: int
    parent_url: Optional[str]
    discovered_at: datetime

class URLFrontier:
    """
    Manages URLs to be crawled with politeness and priority.
    Uses per-domain queues to respect crawl-delay.
    """

    def __init__(self, redis_client):
        self.redis = redis_client
        self.domain_queues: Dict[str, List] = defaultdict(list)
        self.domain_last_access: Dict[str, float] = {}

    async def add_urls(self, urls: List[CrawlRequest]):
        """Add URLs to frontier with deduplication."""
        for request in urls:
            # Check if already crawled or queued
            if await self.is_duplicate(request.url):
                continue

            domain = self.extract_domain(request.url)

            # Add to domain-specific queue with priority
            await self.redis.zadd(
                f"frontier:{domain}",
                {request.url: request.priority}
            )

            # Mark as queued
            await self.redis.sadd("queued_urls", request.url)

    async def get_next_urls(self, batch_size: int = 100) -> List[str]:
        """
        Get next batch of URLs respecting politeness.
        Returns URLs from domains that are ready for crawling.
        """
        urls = []
        now = time.time()

        # Get domains with queued URLs
        domains = await self.get_active_domains()

        for domain in domains:
            if len(urls) >= batch_size:
                break

            # Check politeness delay
            last_access = self.domain_last_access.get(domain, 0)
            crawl_delay = await self.get_crawl_delay(domain)

            if now - last_access < crawl_delay:
                continue

            # Get URLs from this domain
            domain_urls = await self.redis.zrevrange(
                f"frontier:{domain}",
                0, 9  # Get 10 per domain
            )

            for url in domain_urls:
                urls.append(url)
                # Remove from queue
                await self.redis.zrem(f"frontier:{domain}", url)

            self.domain_last_access[domain] = now

        return urls[:batch_size]

    async def get_crawl_delay(self, domain: str) -> float:
        """Get crawl delay from robots.txt cache."""
        delay = await self.redis.get(f"crawl_delay:{domain}")
        return float(delay) if delay else 1.0  # Default 1 second

    async def is_duplicate(self, url: str) -> bool:
        """Check if URL has been crawled or queued."""
        # Check bloom filter first (fast)
        if await self.bloom_filter.contains(url):
            # Verify in set (bloom filter has false positives)
            return await self.redis.sismember("crawled_urls", url)
        return False


class PolitenessManager:
    """Manages robots.txt and crawl delays per domain."""

    async def check_allowed(self, url: str, user_agent: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        domain = extract_domain(url)
        robots = await self.get_robots_txt(domain)

        if robots is None:
            return True  # Allow if no robots.txt

        return robots.can_fetch(user_agent, url)

    async def get_robots_txt(self, domain: str) -> Optional[RobotFileParser]:
        """Fetch and cache robots.txt."""
        cache_key = f"robots:{domain}"
        cached = await self.redis.get(cache_key)

        if cached:
            return self.parse_robots(cached)

        try:
            response = await self.http.get(
                f"https://{domain}/robots.txt",
                timeout=10
            )
            if response.status_code == 200:
                await self.redis.setex(cache_key, 86400, response.text)
                return self.parse_robots(response.text)
        except:
            pass

        return None
```

#### 2. Crawler Workers

```python
import aiohttp
from bs4 import BeautifulSoup
import hashlib

class Crawler:
    """
    Web crawler with async fetching and parsing.
    """

    def __init__(self, frontier, content_store, dedup_filter):
        self.frontier = frontier
        self.content_store = content_store
        self.dedup = dedup_filter
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": USER_AGENT}
        )

    async def crawl_batch(self, urls: List[str]):
        """Crawl a batch of URLs concurrently."""
        tasks = [self.crawl_url(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                await self.handle_error(url, result)
            else:
                await self.process_result(url, result)

    async def crawl_url(self, url: str) -> dict:
        """Fetch and parse a single URL."""
        # Check robots.txt
        if not await self.politeness.check_allowed(url, USER_AGENT):
            return {"status": "blocked", "url": url}

        try:
            async with self.session.get(url) as response:
                content = await response.text()
                content_hash = hashlib.sha256(content.encode()).hexdigest()

                # Content deduplication
                if await self.dedup.contains_content(content_hash):
                    return {"status": "duplicate_content", "url": url}

                return {
                    "status": "success",
                    "url": url,
                    "status_code": response.status,
                    "content": content,
                    "content_hash": content_hash,
                    "headers": dict(response.headers),
                    "fetched_at": datetime.utcnow()
                }

        except asyncio.TimeoutError:
            return {"status": "timeout", "url": url}
        except Exception as e:
            return {"status": "error", "url": url, "error": str(e)}

    async def process_result(self, url: str, result: dict):
        """Process crawl result: store content and extract links."""
        if result["status"] != "success":
            return

        # Store content
        await self.content_store.store(
            url=url,
            content=result["content"],
            content_hash=result["content_hash"],
            metadata={
                "status_code": result["status_code"],
                "fetched_at": result["fetched_at"].isoformat()
            }
        )

        # Mark as crawled
        await self.dedup.mark_crawled(url)
        await self.dedup.mark_content(result["content_hash"])

        # Extract and queue new links
        links = await self.extract_links(url, result["content"])
        await self.frontier.add_urls([
            CrawlRequest(
                url=link,
                priority=self.calculate_priority(link),
                depth=result.get("depth", 0) + 1,
                parent_url=url,
                discovered_at=datetime.utcnow()
            )
            for link in links
        ])

    async def extract_links(self, base_url: str, content: str) -> List[str]:
        """Extract and normalize links from HTML."""
        soup = BeautifulSoup(content, 'lxml')
        links = []

        for anchor in soup.find_all('a', href=True):
            href = anchor['href']
            absolute_url = urljoin(base_url, href)

            # Filter and normalize
            if self.is_valid_url(absolute_url):
                links.append(self.normalize_url(absolute_url))

        return list(set(links))  # Deduplicate
```

#### 3. Deduplication

```python
from pybloom_live import ScalableBloomFilter

class DeduplicationFilter:
    """
    Multi-level deduplication for URLs and content.
    Uses Bloom filters for speed with Redis backing for accuracy.
    """

    def __init__(self, redis_client):
        self.redis = redis_client
        self.url_bloom = ScalableBloomFilter(
            initial_capacity=10_000_000,
            error_rate=0.001
        )
        self.content_bloom = ScalableBloomFilter(
            initial_capacity=10_000_000,
            error_rate=0.001
        )

    async def contains_url(self, url: str) -> bool:
        """Check if URL has been seen."""
        normalized = self.normalize_url(url)
        url_hash = hashlib.md5(normalized.encode()).hexdigest()

        # Fast bloom filter check
        if url_hash not in self.url_bloom:
            return False

        # Verify in Redis (bloom filter may have false positives)
        return await self.redis.sismember("crawled_urls", url_hash)

    async def mark_crawled(self, url: str):
        """Mark URL as crawled."""
        normalized = self.normalize_url(url)
        url_hash = hashlib.md5(normalized.encode()).hexdigest()

        self.url_bloom.add(url_hash)
        await self.redis.sadd("crawled_urls", url_hash)

    async def contains_content(self, content_hash: str) -> bool:
        """Check if content has been seen (near-duplicate detection)."""
        if content_hash not in self.content_bloom:
            return False
        return await self.redis.sismember("crawled_content", content_hash)

    async def mark_content(self, content_hash: str):
        """Mark content hash as seen."""
        self.content_bloom.add(content_hash)
        await self.redis.sadd("crawled_content", content_hash)

    def normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        parsed = urlparse(url)
        # Remove fragments, sort query params, lowercase
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip('/'),
            parsed.params,
            urlencode(sorted(parse_qs(parsed.query).items())),
            ''  # No fragment
        ))
        return normalized
```

### Testing

```python
class TestWebCrawler:
    async def test_crawl_single_page(self, crawler):
        """Test crawling a single page."""
        # Setup mock server
        async with aioresponses() as m:
            m.get("https://example.com", body="<html><body>Test</body></html>")

            result = await crawler.crawl_url("https://example.com")

            assert result["status"] == "success"
            assert "Test" in result["content"]

    async def test_respects_robots_txt(self, crawler):
        """Test robots.txt compliance."""
        async with aioresponses() as m:
            m.get("https://example.com/robots.txt", body="User-agent: *\nDisallow: /private/")
            m.get("https://example.com/private/secret", body="Secret")

            result = await crawler.crawl_url("https://example.com/private/secret")
            assert result["status"] == "blocked"

    async def test_url_deduplication(self, frontier):
        """Test URL deduplication."""
        url = "https://example.com/page"

        await frontier.add_urls([CrawlRequest(url=url, priority=1, depth=0)])
        await frontier.add_urls([CrawlRequest(url=url, priority=1, depth=0)])

        # Should only have one copy
        queued = await frontier.get_queue_size()
        assert queued == 1

    async def test_politeness_delay(self, frontier, crawler):
        """Test crawl delay between requests to same domain."""
        urls = [
            "https://example.com/page1",
            "https://example.com/page2"
        ]

        start = time.time()
        for url in urls:
            await crawler.crawl_url(url)
        duration = time.time() - start

        # Should have waited at least 1 second between requests
        assert duration >= 1.0
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Crawl Rate | > 1000 pages/sec |
| Politeness | 100% robots.txt compliance |
| Dedup Accuracy | > 99.9% |
| Fault Recovery | < 5 minute |
