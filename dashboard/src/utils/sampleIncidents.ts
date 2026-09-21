/**
 * Synthetic Sample Incidents for Operator Quick-Testing
 * Fully synthetic logs representing various incident categories.
 */

export interface SampleIncident {
  id: string;
  name: string;
  category: string;
  rawLog: string;
}

export const SAMPLE_INCIDENTS: SampleIncident[] = [
  {
    id: 'db_pool_exhaustion',
    name: 'Postgres Connection Pool Starvation',
    category: 'DATABASE',
    rawLog: `2026-09-18T10:14:02.112Z [order-service] [ERROR] [HikariCP-WorkerPool] Failed to acquire connection from pool "OrderDBPool" after 30000ms. Active connections: 50/50, Idle: 0, Waiting threads: 142.
2026-09-18T10:14:02.115Z [order-service] [ERROR] org.postgresql.util.PSQLException: Connection to 10.0.4.12:5432 refused: database connection pool exhausted.
2026-09-18T10:14:02.118Z [order-service] [WARN] [CircuitBreaker] State transitioned to OPEN for target "order-db-read-write".`,
  },
  {
    id: 'k8s_oom_killed',
    name: 'Kubernetes Pod OOMKilled Container Exit',
    category: 'INFRASTRUCTURE',
    rawLog: `2026-09-18T10:18:22.401Z [k8s-node-worker-04] [WARNING] kernel: [149204.120] Memory cgroup out of memory: Killed process 24901 (inventory-api) total-vm:4194304kB, anon-rss:2097152kB, file-rss:12288kB, shmem-rss:0kB
2026-09-18T10:18:23.011Z [kubelet] [ERROR] Container inventory-api-worker in Pod inventory-service-7f89d-v9x2l terminated with exit code 137 (OOMKilled).
2026-09-18T10:18:24.100Z [kubelet] [INFO] Back-off restarting failed container inventory-api-worker in pod inventory-service-7f89d-v9x2l.`,
  },
  {
    id: 'app_thread_exhaustion',
    name: 'Java JVM Thread Pool Exhaustion',
    category: 'APPLICATION',
    rawLog: `2026-09-18T10:25:31.902Z [payment-gateway] [ERROR] org.apache.tomcat.util.threads.ThreadPoolExecutor: Thread pool "http-nio-8080-exec" is exhausted (max: 200, current: 200, queue: 1000).
2026-09-18T10:25:32.140Z [payment-gateway] [ERROR] Request processing rejected: java.util.concurrent.RejectedExecutionException: Task rejected from Tomcat worker pool.
2026-09-18T10:25:33.001Z [payment-gateway] [WARN] Inbound payment checkout requests timing out after 15000ms latency.`,
  },
  {
    id: 'sec_auth_token_expired',
    name: 'OAuth2 JWKS Signature Verification Failure',
    category: 'SECURITY',
    rawLog: `2026-09-18T10:30:11.876Z [api-gateway] [WARN] [AuthFilter] JWT validation failed: Token expired at 2026-09-18T10:29:59Z, skew allowance: 0s. Subject: srv_batch_sync_prod.
2026-09-18T10:30:12.012Z [api-gateway] [ERROR] [SecurityManager] Signature verification failed against key ID "rsa-2024-primary" from IDP endpoint https://idp.internal/jwks.json: HTTP 403 Forbidden.
2026-09-18T10:30:12.015Z [api-gateway] [WARN] Rejecting request 401 Unauthorized for client 192.168.4.12.`,
  },
  {
    id: 'net_dns_resolution_failure',
    name: 'CoreDNS Service Resolution Timeout',
    category: 'NETWORK',
    rawLog: `2026-09-18T10:35:44.201Z [auth-service] [ERROR] dial tcp: lookup redis-cluster-cache.cache.svc.cluster.local on 10.96.0.10:53: read udp 10.244.2.14:48102->10.96.0.10:53: i/o timeout.
2026-09-18T10:35:45.302Z [auth-service] [ERROR] Failed to establish redis session connection: DNS lookup timeout after 2 retries.
2026-09-18T10:35:46.002Z [auth-service] [CRITICAL] Session validation downgraded to fallback offline mode.`,
  },
  {
    id: 'msg_kafka_lag',
    name: 'Kafka Consumer Lag Accumulation & Rebalance',
    category: 'MESSAGING',
    rawLog: `2026-09-18T10:41:19.452Z [billing-consumer] [WARN] [org.apache.kafka.clients.consumer.internals.ConsumerCoordinator] Consumer poll() timeout expired! Commit failed: CommitFailedException: The coordinator is not aware of this member.
2026-09-18T10:41:20.102Z [billing-consumer] [ERROR] Member consumer-billing-1-49fa revoked partition billing.events-2 due to heartbeat failure. Consumer lag on topic "billing.events" reached 48,290 messages.
2026-09-18T10:41:21.005Z [billing-consumer] [INFO] Group rebalance triggered for consumer group "billing-processor-group".`,
  },
];
