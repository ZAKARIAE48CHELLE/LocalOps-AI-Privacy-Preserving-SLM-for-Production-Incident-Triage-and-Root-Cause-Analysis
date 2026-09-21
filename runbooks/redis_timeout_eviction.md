# Runbook: Redis Timeout and Key Eviction

- **Incident Type**: DATABASE
- **Affected Services**: cache-service, session-service, rate-limiter, product-catalog
- **Severity Default**: P2_HIGH
- **Keywords**: RedisTimeoutException, OOM command not allowed when used memory, maxmemory-policy, volatile-lru, allkeys-lru, Redis command timed out

## Symptoms
- Applications log `StackExchange.Redis.RedisTimeoutException: Timeout performing GET`.
- Redis throws `OOM command not allowed when used memory > 'maxmemory'`.
- Hit ratios drop precipitously in cache metrics dashboards.
- Upstream databases experience secondary overload due to cache-stampede.

## Root Cause Diagnosis
1. Execute `redis-cli info memory` to inspect `used_memory`, `used_memory_rss`, and `mem_fragmentation_ratio`.
2. Check eviction metrics: `redis-cli info stats | grep evicted_keys`.
3. Identify top memory-consuming keys or missing TTLs using `redis-cli --bigkeys` or `redis-cli --hotkeys`.
4. Inspect slow log: `redis-cli slowlog get 10` to find non-O(1) operations (e.g. `KEYS *`, `SMEMBERS` on giant sets).

## Immediate Mitigation
1. Change eviction policy dynamically to evict expired or volatile keys:
   `CONFIG SET maxmemory-policy allkeys-lru`
2. Temporarily increase maxmemory ceiling if node RAM permits:
   `CONFIG SET maxmemory <increased_bytes>`
3. Terminate runaway blocking operations or flush volatile caches if safe.

## Long-Term Remediation
- Audit application caching code to enforce mandatory TTLs on all written keys.
- Replace unbounded `KEYS` or `HGETALL` operations with `SCAN` or paginated lookups.
- Scale Redis to cluster mode or shard read traffic across read-replicas.
