"""Structural log templates for the DATABASE category (6 families, 60 templates).

Each family defines 10 templates: 6 TRAIN, 2 VALIDATION, 2 TEST.
Includes P4_LOW coverage, normalized metadata, and split-aware variant pools.
"""

from typing import Callable
from src.data.models import DatasetSplit, ImpactScenario, Severity
from src.data.templates.base import LogTemplate
from src.schemas.enums import IncidentFamily


FAMILY_1 = IncidentFamily.DB_CONNECTION_POOL_STARVATION
FAMILY_2 = IncidentFamily.DB_DEADLOCK_OR_CONTENTION
FAMILY_3 = IncidentFamily.DB_REPLICATION_LAG
FAMILY_4 = IncidentFamily.DB_QUERY_TIMEOUT
FAMILY_5 = IncidentFamily.DB_STORAGE_EXHAUSTION
FAMILY_6 = IncidentFamily.DB_INDEX_OR_DATA_CORRUPTION

FAMILY_OBSERVED_MAP = {
    FAMILY_1: "Database connection pool capacity is exhausted, preventing the service from acquiring a connection within the timeout limit.",
    FAMILY_2: "Concurrent database transactions encountered mutual lock contention or deadlock, resulting in transaction abort or lock wait timeout.",
    FAMILY_3: "Database replica replication delay or replay lag exceeded acceptable operational threshold.",
    FAMILY_4: "Database query execution exceeded configured statement timeout limit before completing.",
    FAMILY_5: "Database filesystem storage volume reached 100% capacity (No space left on device), rejecting write operations.",
    FAMILY_6: "Database block or page corruption / checksum verification mismatch detected on disk.",
}

FAMILY_HYPOTHESES_MAP = {
    FAMILY_1: ["connection leak", "lingering connections", "query surge", "slow queries", "unreleased connections"],
    FAMILY_2: ["unindexed foreign key", "inconsistent lock ordering", "lock escalation", "unindexed table scan"],
    FAMILY_3: ["high write volume", "network latency", "slow storage I/O", "bulk write operations"],
    FAMILY_4: ["unindexed sequential scan", "missing index", "suboptimal execution plan", "expensive scan", "lock contention"],
    FAMILY_5: ["WAL accumulation", "tablespace growth", "temporary table spill", "audit log volume", "unpurged transaction logs"],
    FAMILY_6: ["hardware bit-rot", "crash recovery failure", "storage controller fault", "power loss"],
}


def _create_template(
    template_id: str,
    family: IncidentFamily,
    technology: str,
    runtime: str,
    split: DatasetSplit,
    log_gen: Callable[..., list[str]],
    evidence_gen: Callable[..., list[str]],
    impact_scenarios: list[ImpactScenario],
    root_cause_variants: dict[str, str],
    action_variants: dict[str, str],
    signature_profile: str = "",
    failure_mechanism: str = "",
    expected_tokens: list[str] = None,
    forbidden_tokens: list[str] = None,
    expected_status_code: int = None,
    observed_failure_mechanism: str = "",
    possible_hypotheses: list[str] = None,
) -> LogTemplate:
    sig = signature_profile or f"{template_id}_{technology.replace(' ', '_').replace('-', '_').upper()}"
    return LogTemplate(
        template_id=template_id,
        family=family,
        technology=technology,
        runtime=runtime,
        signature_profile=sig,
        assigned_split=split,
        log_generator=log_gen,
        evidence_generator=evidence_gen,
        impact_scenarios=impact_scenarios,
        root_cause_variants=root_cause_variants,
        action_variants=action_variants,
        failure_mechanism=failure_mechanism or sig,
        expected_tokens=expected_tokens or [],
        forbidden_tokens=forbidden_tokens or [],
        expected_status_code=expected_status_code,
        observed_failure_mechanism=observed_failure_mechanism or FAMILY_OBSERVED_MAP.get(family, ""),
        possible_hypotheses=possible_hypotheses or FAMILY_HYPOTHESES_MAP.get(family, []),
    )


# =========================================================================
# 1. DB_CONNECTION_POOL_STARVATION
# =========================================================================

SCENARIOS_1 = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: 100% of checkout transactions failing; all worker threads blocked on pool acquisition",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Connection pool utilization at 98%; request latency spike observed across {service}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Intermittent pool wait timeouts in background batch worker; auto-retrying request",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Transient pool connection wait of 250ms in read-only cache sync; auto-recovered with 0 customer errors",
    ),
]

RC_VARS_1_TRAIN = {
    "RC_TRAIN_1": "Database connection pool capacity exhausted, preventing {service} from acquiring a connection within the timeout limit.",
    "RC_TRAIN_2": "Connection pool reached maximum capacity on database host {ip}, causing connection acquisition timeouts.",
    "RC_TRAIN_3": "Database connection pool capacity exhausted, blocking new connection checkout requests in {service}.",
}
ACT_VARS_1_TRAIN = {
    "ACT_TRAIN_1": "Increase max connection pool limit; inspect active connection lifetime, slow queries, and thread concurrency in {service}.",
    "ACT_TRAIN_2": "Review connection-release behavior, terminate idle unreleased connections, and optimize slow query execution.",
    "ACT_TRAIN_3": "Tune pool timeout parameters, examine connection holding times, and inspect active worker processes in {service}.",
}

RC_VARS_1_VAL = {
    "RC_VAL_1": "Database client connection pool capacity exhausted on host {ip}, exceeding maximum wait timeout.",
}
ACT_VARS_1_VAL = {
    "ACT_VAL_1": "Scale database proxy connection pool, review checkout timeouts, and inspect connection reuse in {service}.",
}

RC_VARS_1_TEST = {
    "RC_TEST_1": "Client connection acquisition timeout due to fully exhausted connection pool on {ip}.",
}
ACT_VARS_1_TEST = {
    "ACT_TEST_1": "Verify application database connection release logic, inspect slow queries, and adjust pool ceiling for {service}.",
}

TEMPLATES_CONN_STARVATION = [
    _create_template(
        "DB_CONN_01", FAMILY_1, "PostgreSQL", "Java/Spring", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] com.zaxxer.hikari.pool.HikariPool: HikariPool-1 - Connection is not available, request timed out after {num*100}ms",
            f"[{ts}] [ERROR] [{service}] org.postgresql.util.PSQLException: Connection checkout failed for pool on host {ip}:5432",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Connection is not available, request timed out",
            "Connection checkout failed for pool",
            impact_line,
        ],
        SCENARIOS_1, RC_VARS_1_TRAIN, ACT_VARS_1_TRAIN,
        signature_profile="HIKARICP_POOL_TIMEOUT",
    ),
    _create_template(
        "DB_CONN_02", FAMILY_1, "PostgreSQL", "Python/FastAPI", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] sqlalchemy.exc.TimeoutError: QueuePool limit of size 20 overflow 10 reached, connection timed out, timeout 30.00",
            f"[{ts}] [WARNING] [{service}] Database pool exhausted on {ip}:5432 while acquiring connection for request {hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "QueuePool limit of size 20 overflow 10 reached",
            "Database pool exhausted",
            impact_line,
        ],
        SCENARIOS_1, RC_VARS_1_TRAIN, ACT_VARS_1_TRAIN,
        signature_profile="SQLALCHEMY_QUEUEPOOL_TIMEOUT",
    ),
    _create_template(
        "DB_CONN_03", FAMILY_1, "PgBouncer", "C", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] pgbouncer[8192]: FATAL: remaining connection slots are reserved for non-replication superuser connections",
            f"[{ts}] [ERROR] [{service}] pgbouncer[8192]: client connection pool max_client_conn limit reached for host {ip}",
            f"[{ts}] [ERROR] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "FATAL: remaining connection slots are reserved",
            "client connection pool max_client_conn limit reached",
            impact_line,
        ],
        SCENARIOS_1, RC_VARS_1_TRAIN, ACT_VARS_1_TRAIN,
        signature_profile="PGBOUNCER_POOL_EXHAUSTION",
    ),
    _create_template(
        "DB_CONN_04", FAMILY_1, "MySQL", "Java", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] com.mchange.v2.c3p0.impl.NewPooledConnection: A client timed out while waiting to acquire a resource from com.mchange.v2.c3p0.ComboPooledDataSource",
            f"[{ts}] [WARN] [{service}] Could not destroy null pooled connection on MySQL {ip}:3306",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "A client timed out while waiting to acquire a resource",
            "ComboPooledDataSource",
            impact_line,
        ],
        SCENARIOS_1, RC_VARS_1_TRAIN, ACT_VARS_1_TRAIN,
        signature_profile="C3P0_MYSQL_TIMEOUT",
    ),
    _create_template(
        "DB_CONN_05", FAMILY_1, "Redis", "Python", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] redis.exceptions.ConnectionError: Too many open connections (ConnectionPool limit exceeded: 500)",
            f"[{ts}] [ERROR] [{service}] Failed to acquire redis connection handle for cache key {hex_id} on {ip}:6379",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ConnectionPool limit exceeded: 500",
            "Failed to acquire redis connection handle",
            impact_line,
        ],
        SCENARIOS_1, RC_VARS_1_TRAIN, ACT_VARS_1_TRAIN,
        signature_profile="REDIS_POOL_LIMIT_EXCEEDED",
    ),
    _create_template(
        "DB_CONN_06", FAMILY_1, "MongoDB", "Node.js", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] MongoWaitQueueTimeoutError: Timed out while checking out a connection from connection pool: maxPoolSize=100 reached",
            f"[{ts}] [WARN] [{service}] MongoDB cluster node {ip}:27017 queue length {num} exceeded threshold",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "MongoWaitQueueTimeoutError: Timed out while checking out a connection",
            "maxPoolSize=100 reached",
            impact_line,
        ],
        SCENARIOS_1, RC_VARS_1_TRAIN, ACT_VARS_1_TRAIN,
        signature_profile="MONGODB_WAIT_QUEUE_TIMEOUT",
    ),
    _create_template(
        "DB_CONN_07", FAMILY_1, "Oracle", "Java", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] oracle.ucp.UniversalConnectionPoolException: All connections in Universal Connection Pool are in use",
            f"[{ts}] [ERROR] [{service}] ORA-00018: maximum number of sessions exceeded on Oracle instance {ip}:1521",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "All connections in Universal Connection Pool are in use",
            "ORA-00018: maximum number of sessions exceeded",
            impact_line,
        ],
        SCENARIOS_1, RC_VARS_1_VAL, ACT_VARS_1_VAL,
        signature_profile="ORACLE_UCP_POOL_SATURATION",
    ),
    _create_template(
        "DB_CONN_08", FAMILY_1, "PostgreSQL", "Go", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] pgx: acquiring connection: context deadline exceeded (pool stats: total=50 idle=0 acquired=50)",
            f"[{ts}] [ERROR] [{service}] connection pool depleted while executing query {hex_id} against {ip}:5432",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "pgx: acquiring connection: context deadline exceeded",
            "pool stats: total=50 idle=0 acquired=50",
            impact_line,
        ],
        SCENARIOS_1, RC_VARS_1_VAL, ACT_VARS_1_VAL,
        signature_profile="GO_PGX_POOL_DEPLETED",
    ),
    _create_template(
        "DB_CONN_09", FAMILY_1, "PostgreSQL", ".NET", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Npgsql.NpgsqlException: The connection pool has reached its maximum size and no connections are currently available",
            f"[{ts}] [WARN] [{service}] Npgsql connection checkout wait time: 15000ms exceeded on {ip}:5432",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "The connection pool has reached its maximum size and no connections are currently available",
            impact_line,
        ],
        SCENARIOS_1, RC_VARS_1_TEST, ACT_VARS_1_TEST,
        signature_profile="DOTNET_NPGSQL_POOL_EXHAUSTED",
    ),
    _create_template(
        "DB_CONN_10", FAMILY_1, "Ruby on Rails", "Ruby", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] ActiveRecord::ConnectionTimeoutError: could not obtain a connection from the pool within 5.000 seconds (size=15, occupied=15)",
            f"[{ts}] [ERROR] [{service}] ActionController::RoutingError while dispatching request {hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ActiveRecord::ConnectionTimeoutError: could not obtain a connection from the pool",
            impact_line,
        ],
        SCENARIOS_1, RC_VARS_1_TEST, ACT_VARS_1_TEST,
        signature_profile="RAILS_ACTIVERECORD_POOL_TIMEOUT",
    ),
]


# =========================================================================
# 2. DB_DEADLOCK_OR_CONTENTION
# =========================================================================

SCENARIOS_2 = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Cascading deadlocks causing 65% rollback rate on financial ledger transactions",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Repeated transaction deadlocks in {service} order placement pipeline",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single isolated deadlock abort in batch reconciliation job; retrying transaction",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Background cleanup task encountered row lock conflict; retried successfully after 50ms",
    ),
]

RC_VARS_2_TRAIN = {
    "RC_TRAIN_1": "Database transaction deadlock detected between concurrent transactions in {service}, causing automatic transaction rollback.",
    "RC_TRAIN_2": "Database lock wait timeout exceeded while waiting for conflicting row or table locks on {ip}.",
    "RC_TRAIN_3": "Concurrent lock contention between competing database transactions on {ip} causing transaction abort.",
}
ACT_VARS_2_TRAIN = {
    "ACT_TRAIN_1": "Enforce consistent lock acquisition ordering across transactions and optimize transaction duration.",
    "ACT_TRAIN_2": "Inspect conflicting queries, check for unindexed foreign keys causing lock escalation, and optimize transaction scope.",
    "ACT_TRAIN_3": "Implement exponential backoff on transaction retries and review transaction isolation level.",
}

RC_VARS_2_VAL = {
    "RC_VAL_1": "Database lock wait timeout exceeded while waiting for row lock held by concurrent transaction on {ip}.",
}
ACT_VARS_2_VAL = {
    "ACT_VAL_1": "Shorten write transaction locks, evaluate lock acquisition order, and adjust lock_wait_timeout on database host {ip}.",
}

RC_VARS_2_TEST = {
    "RC_TEST_1": "Concurrent serializable transaction conflicts triggering repeated transaction aborts on {ip}.",
}
ACT_VARS_2_TEST = {
    "ACT_TEST_1": "Review application concurrency control and implement client-side transaction retry logic.",
}

TEMPLATES_DEADLOCK = [
    _create_template(
        "DB_DEAD_01", FAMILY_2, "PostgreSQL", "C/Engine", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] postgres[1928]: ERROR: deadlock detected",
            f"[{ts}] [DETAIL] [{service}] Process 1928 waits for ShareLock on transaction 8891; blocked by process 1930 on {ip}",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ERROR: deadlock detected",
            "waits for ShareLock on transaction",
            impact_line,
        ],
        SCENARIOS_2, RC_VARS_2_TRAIN, ACT_VARS_2_TRAIN,
        signature_profile="POSTGRES_DEADLOCK_DETECTED",
    ),
    _create_template(
        "DB_DEAD_02", FAMILY_2, "MySQL", "C++/InnoDB", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] mysqld: Deadlock found when trying to get lock; try restarting transaction",
            f"[{ts}] [INFO] [{service}] InnoDB: *** (1) TRANSACTION: ACTIVE {num} sec starting index read on orders on {ip}:3306",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Deadlock found when trying to get lock; try restarting transaction",
            impact_line,
        ],
        SCENARIOS_2, RC_VARS_2_TRAIN, ACT_VARS_2_TRAIN,
        signature_profile="MYSQL_INNODB_DEADLOCK",
    ),
    _create_template(
        "DB_DEAD_03", FAMILY_2, "SQL Server", "T-SQL", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Microsoft.Data.SqlClient.SqlException: Transaction (Process ID {num}) was deadlocked on lock resources with another process and has been chosen as the deadlock victim",
            f"[{ts}] [ERROR] [{service}] Error 1205 executing batch query against SQL Server {ip}:1433",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Transaction (Process ID",
            "was deadlocked on lock resources with another process and has been chosen as the deadlock victim",
            impact_line,
        ],
        SCENARIOS_2, RC_VARS_2_TRAIN, ACT_VARS_2_TRAIN,
        signature_profile="MSSQL_DEADLOCK_VICTIM",
    ),
    _create_template(
        "DB_DEAD_04", FAMILY_2, "Oracle", "PL/SQL", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] ORA-00060: deadlock detected while waiting for resource on Oracle node {ip}",
            f"[{ts}] [WARN] [{service}] Rows in table ACCOUNT_BALANCES locked exclusively by session {hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ORA-00060: deadlock detected while waiting for resource",
            impact_line,
        ],
        SCENARIOS_2, RC_VARS_2_TRAIN, ACT_VARS_2_TRAIN,
        signature_profile="ORACLE_ORA_00060_DEADLOCK",
    ),
    _create_template(
        "DB_DEAD_05", FAMILY_2, "PostgreSQL", "Go", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] pq: canceling statement due to lock timeout: query failed on relation orders_queue on {ip}",
            f"[{ts}] [WARN] [{service}] Lock wait duration 10000ms exceeded lock_timeout setting",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "pq: canceling statement due to lock timeout",
            "Lock wait duration",
            impact_line,
        ],
        SCENARIOS_2, RC_VARS_2_TRAIN, ACT_VARS_2_TRAIN,
        signature_profile="POSTGRES_LOCK_TIMEOUT",
    ),
    _create_template(
        "DB_DEAD_06", FAMILY_2, "MongoDB", "WiredTiger", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] MongoError: WriteConflict: WriteConflict error: this operation conflicted with another operation. Please retry your operation or multi-document transaction",
            f"[{ts}] [WARN] [{service}] Collection users.profiles locked in exclusive write mode on {ip}:27017",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "WriteConflict error: this operation conflicted with another operation",
            impact_line,
        ],
        SCENARIOS_2, RC_VARS_2_TRAIN, ACT_VARS_2_TRAIN,
        signature_profile="MONGODB_WRITE_CONFLICT",
    ),
    _create_template(
        "DB_DEAD_07", FAMILY_2, "SQLite", "C", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] sqlite3.OperationalError: database is locked (busy_timeout={num}ms)",
            f"[{ts}] [WARN] [{service}] Multiple writer processes attempting concurrent WAL commits on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "sqlite3.OperationalError: database is locked",
            impact_line,
        ],
        SCENARIOS_2, RC_VARS_2_VAL, ACT_VARS_2_VAL,
        signature_profile="SQLITE_DATABASE_LOCKED",
    ),
    _create_template(
        "DB_DEAD_08", FAMILY_2, "MySQL", "Go", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Error 1205 (HY000): Lock wait timeout exceeded; try restarting transaction",
            f"[{ts}] [ERROR] [{service}] query failed on table customer_balances on {ip}:3306",
            f"[{ts}] [ERROR] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Error 1205 (HY000): Lock wait timeout exceeded",
            impact_line,
        ],
        SCENARIOS_2, RC_VARS_2_VAL, ACT_VARS_2_VAL,
        signature_profile="MYSQL_LOCK_WAIT_TIMEOUT",
    ),
    _create_template(
        "DB_DEAD_09", FAMILY_2, "CockroachDB", "Go", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] TransactionRetryWithProtoRefreshError: TransactionRetryError: retry txn (preempted by concurrent txn: priority {num})",
            f"[{ts}] [WARN] [{service}] CockroachDB serializable lock conflict detected on key span [{hex_id}]",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "TransactionRetryError: retry txn (preempted by concurrent txn",
            "serializable lock conflict detected",
            impact_line,
        ],
        SCENARIOS_2, RC_VARS_2_TEST, ACT_VARS_2_TEST,
        signature_profile="COCKROACHDB_TXN_RETRY",
    ),
    _create_template(
        "DB_DEAD_10", FAMILY_2, "Neo4j", "Java", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] org.neo4j.exceptions.TransientException: LockClient[{hex_id}]: Deadlock detected on Node {num}",
            f"[{ts}] [ERROR] [{service}] Graph transaction failed to acquire exclusive WRITE lock on relationship",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Deadlock detected on Node",
            "failed to acquire exclusive WRITE lock",
            impact_line,
        ],
        SCENARIOS_2, RC_VARS_2_TEST, ACT_VARS_2_TEST,
        signature_profile="NEO4J_GRAPH_DEADLOCK",
    ),
]


# =========================================================================
# 3. DB_REPLICATION_LAG
# =========================================================================

SCENARIOS_3 = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Read replica lag exceeds 600s; stale data causing data inconsistency across {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Replica lag reached 180s on reader node {ip}; read SLA violated",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Transient replication delay of 35s during scheduled batch ingest; catching up",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Minor replication delay of 3s on auxiliary reporting replica; within allowable SLA",
    ),
]

RC_VARS_3_TRAIN = {
    "RC_TRAIN_1": "Database read replica replication lag exceeded acceptable operational threshold for {service} on host {ip}.",
    "RC_TRAIN_2": "Replication delay between primary and read-replica database nodes on {ip} exceeding replication window.",
    "RC_TRAIN_3": "Database replica replication apply thread falling behind the primary write stream on {ip}.",
}
ACT_VARS_3_TRAIN = {
    "ACT_TRAIN_1": "Inspect primary write volume, evaluate replication thread progress, and throttle bulk operations if necessary on {ip}.",
    "ACT_TRAIN_2": "Monitor replication apply worker threads and investigate disk write latency on lagging replica.",
    "ACT_TRAIN_3": "Investigate network latency, disk I/O metrics on replica {ip}, and route read traffic away until synchronized.",
}

RC_VARS_3_VAL = {
    "RC_VAL_1": "Database replication slot backlog accumulating on secondary node {ip}.",
}
ACT_VARS_3_VAL = {
    "ACT_VAL_1": "Verify network throughput and replica replay performance between primary and standby {ip}.",
}

# Distinct technology-appropriate variants for Cassandra (DB_REPL_09) and ClickHouse (DB_REPL_10)
RC_VARS_3_CASSANDRA = {
    "RC_TEST_1": "Cassandra replica desynchronization and dropped hinted handoff mutations for endpoint {ip}.",
}
ACT_VARS_3_CASSANDRA = {
    "ACT_TEST_1": "Run nodetool repair on the lagging Cassandra keyspace and verify replica gossip status on {ip}.",
}

RC_VARS_3_CLICKHOUSE = {
    "RC_TEST_1": "ClickHouse ReplicatedMergeTree replication queue delay behind leader on host {ip}.",
}
ACT_VARS_3_CLICKHOUSE = {
    "ACT_TEST_1": "Inspect ClickHouse system.replication_queue on {ip} and verify keeper/ZooKeeper connectivity.",
}

TEMPLATES_REPL_LAG = [
    _create_template(
        "DB_REPL_01", FAMILY_3, "PostgreSQL", "C/Engine", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] postgres: standby replication lag is 452MB (replay_lag: {num*10}s) on host {ip}",
            f"[{ts}] [ERROR] [{service}] walreceiver: streaming replication connection closed: unexpected EOF",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "standby replication lag is",
            "streaming replication connection closed",
            impact_line,
        ],
        SCENARIOS_3, RC_VARS_3_TRAIN, ACT_VARS_3_TRAIN,
        signature_profile="POSTGRES_WAL_REPLAY_LAG",
    ),
    _create_template(
        "DB_REPL_02", FAMILY_3, "MySQL", "C++/InnoDB", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] mysqld: Seconds_Behind_Master: {num*15} on replica host {ip}:3306",
            f"[{ts}] [ERROR] [{service}] Slave_SQL_Running: Yes, but SQL thread queue length {num} exceeds threshold",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Seconds_Behind_Master:",
            "Slave_SQL_Running:",
            impact_line,
        ],
        SCENARIOS_3, RC_VARS_3_TRAIN, ACT_VARS_3_TRAIN,
        signature_profile="MYSQL_SECONDS_BEHIND_MASTER",
    ),
    _create_template(
        "DB_REPL_03", FAMILY_3, "MongoDB", "WiredTiger", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] mongod: replication secondary member {ip}:27017 is lagging behind primary by {num*20} seconds",
            f"[{ts}] [WARN] [{service}] oplog: reader fallback to slow query path; oplog buffer full",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "replication secondary member",
            "is lagging behind primary by",
            impact_line,
        ],
        SCENARIOS_3, RC_VARS_3_TRAIN, ACT_VARS_3_TRAIN,
        signature_profile="MONGODB_OPLOG_REPL_LAG",
    ),
    _create_template(
        "DB_REPL_04", FAMILY_3, "Redis", "C/Sentinel", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] redis-server: master_repl_offset: 98129412, secondary_repl_offset: 87129400 (lag: {num*1000} bytes)",
            f"[{ts}] [ERROR] [{service}] Replica {ip}:6379 lagging behind replication stream; SYNC required",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "master_repl_offset:",
            "lagging behind replication stream; SYNC required",
            impact_line,
        ],
        SCENARIOS_3, RC_VARS_3_TRAIN, ACT_VARS_3_TRAIN,
        signature_profile="REDIS_REPL_OFFSET_LAG",
    ),
    _create_template(
        "DB_REPL_05", FAMILY_3, "SQL Server", "AlwaysOn", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] AlwaysOn Availability Groups: Secondary replica on {ip} synchronization state is NOT SYNCHRONIZING",
            f"[{ts}] [WARN] [{service}] Estimated data loss (time): {num*5} seconds on availability database OrdersDB",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "AlwaysOn Availability Groups: Secondary replica on",
            "synchronization state is NOT SYNCHRONIZING",
            impact_line,
        ],
        SCENARIOS_3, RC_VARS_3_TRAIN, ACT_VARS_3_TRAIN,
        signature_profile="MSSQL_ALWAYSON_NOT_SYNCHRONIZING",
    ),
    _create_template(
        "DB_REPL_06", FAMILY_3, "CockroachDB", "Raft", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] cockroach: range {num} leaseholder on {ip}: replica on node 3 has fallen behind Raft log",
            f"[{ts}] [ERROR] [{service}] RaftSnapshotRequest initiated: replica requires full catch-up snapshot",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "has fallen behind Raft log",
            "RaftSnapshotRequest initiated: replica requires full catch-up snapshot",
            impact_line,
        ],
        SCENARIOS_3, RC_VARS_3_TRAIN, ACT_VARS_3_TRAIN,
        signature_profile="COCKROACHDB_RAFT_LAG",
    ),
    _create_template(
        "DB_REPL_07", FAMILY_3, "PostgreSQL", "C/Engine", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] postgres[2841]: WAL receiver process terminated: replication slot 'sub_01' is falling behind",
            f"[{ts}] [WARN] [{service}] Standby node {ip} is lagging by {num*4} WAL segments",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "WAL receiver process terminated: replication slot",
            "is falling behind",
            impact_line,
        ],
        SCENARIOS_3, RC_VARS_3_VAL, ACT_VARS_3_VAL,
        signature_profile="POSTGRES_REPL_SLOT_BACKLOG",
    ),
    _create_template(
        "DB_REPL_08", FAMILY_3, "MySQL", "C/Engine", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] mysqld: Slave worker thread retried transaction 10 times; replication lag increasing",
            f"[{ts}] [ERROR] [{service}] GTID set mismatch: replica missing transactions from master {ip}:3306",
            f"[{ts}] [ERROR] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Slave worker thread retried transaction",
            "replication lag increasing",
            impact_line,
        ],
        SCENARIOS_3, RC_VARS_3_VAL, ACT_VARS_3_VAL,
        signature_profile="MYSQL_GTID_REPL_DELAY",
    ),
    _create_template(
        "DB_REPL_09", FAMILY_3, "Cassandra", "Java", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] org.apache.cassandra.db.HintedHandoffManager: High rate of dropped hints for endpoint {ip}; node lagging",
            f"[{ts}] [WARN] [{service}] Read repair invoked on {num} mismatched keys due to replica desynchronization",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "High rate of dropped hints for endpoint",
            "replica desynchronization",
            impact_line,
        ],
        SCENARIOS_3, RC_VARS_3_CASSANDRA, ACT_VARS_3_CASSANDRA,
        signature_profile="CASSANDRA_HINTS_REPL_LAG",
    ),
    _create_template(
        "DB_REPL_10", FAMILY_3, "ClickHouse", "C++", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] DB::StorageReplicatedMergeTree: ReplicaDelay: Replica is lagging behind master by {num*30} seconds",
            f"[{ts}] [WARN] [{service}] Replicated queue on {ip}:9000 contains {num} unexecuted log parts",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ReplicaDelay: Replica is lagging behind master",
            impact_line,
        ],
        SCENARIOS_3, RC_VARS_3_CLICKHOUSE, ACT_VARS_3_CLICKHOUSE,
        signature_profile="CLICKHOUSE_MERGETREE_REPL_DELAY",
    ),
]


# =========================================================================
# 4. DB_QUERY_TIMEOUT
# =========================================================================

SCENARIOS_4 = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Core search queries timing out globally; 90% HTTP 504 errors on user storefront",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Database statement timeout on critical report generator on {ip}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single analytical aggregation query timed out after {num}s; non-blocking",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Background telemetry purge query reached 30s statement timeout; rescheduled for off-peak hours",
    ),
]

RC_VARS_4_TRAIN = {
    "RC_TRAIN_1": "Database query statement execution timed out after exceeding configured limit in {service} on host {ip}.",
    "RC_TRAIN_2": "Database query execution exceeded configured statement_timeout threshold on host {ip}.",
    "RC_TRAIN_3": "Query execution cancelled after exceeding maximum allowable runtime on {ip}.",
}
ACT_VARS_4_TRAIN = {
    "ACT_TRAIN_1": "Inspect query execution plan with EXPLAIN ANALYZE, check for unindexed sequential scans, and add covering indexes.",
    "ACT_TRAIN_2": "Kill stalled queries on database host {ip}, tune statement timeout thresholds, and inspect lock contention.",
    "ACT_TRAIN_3": "Rewrite long-running query to paginate results, evaluate suboptimal execution plans, and reduce table scan scope.",
}

RC_VARS_4_VAL = {
    "RC_VAL_1": "Database query cancelled due to statement timeout threshold exceeded on host {ip}.",
}
ACT_VARS_4_VAL = {
    "ACT_VAL_1": "Optimize slow database query plan, check for missing indexes, and evaluate query duration for {service}.",
}

RC_VARS_4_TEST = {
    "RC_TEST_1": "Database command execution timed out after exceeding maximum execution time limit on {ip}.",
}
ACT_VARS_4_TEST = {
    "ACT_TEST_1": "Add index covering predicate columns, inspect expensive table scans, and configure query pagination for {service}.",
}

# Distinct Cassandra-specific timeout variants avoiding relational unindexed scan explanations
RC_VARS_4_CASSANDRA = {
    "RC_TRAIN_1": "Cassandra read query timeout at consistency LOCAL_QUORUM: insufficient replica responses received before coordinator timeout on {ip}.",
    "RC_TRAIN_2": "Coordinator timed out waiting for required replica quorum responses on Cassandra node {ip}.",
    "RC_TRAIN_3": "Cassandra read request timeout due to coordinator-to-replica latency or node saturation on {ip}.",
}
ACT_VARS_4_CASSANDRA = {
    "ACT_TRAIN_1": "Inspect Cassandra replica node health, coordinator-to-replica latency, and verify consistency-level requirements on {ip}.",
    "ACT_TRAIN_2": "Check nodetool tpstats for dropped ReadStage tasks and inspect JVM GC pauses on node {ip}.",
    "ACT_TRAIN_3": "Verify network connectivity between coordinator and replicas; tune read_request_timeout_in_ms if appropriate.",
}

TEMPLATES_QUERY_TIMEOUT = [
    _create_template("DB_TOUT_01", FAMILY_4, "PostgreSQL", "C/Engine", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] postgres[4190]: ERROR: canceling statement due to statement timeout",
            f"[{ts}] [DETAIL] [{service}] Query duration: {num*1000}ms exceeded statement_timeout (30000ms) on {ip}:5432",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ERROR: canceling statement due to statement timeout",
            "exceeded statement_timeout",
            impact_line,
        ], SCENARIOS_4, RC_VARS_4_TRAIN, ACT_VARS_4_TRAIN, signature_profile="POSTGRES_STATEMENT_TIMEOUT"),
    _create_template("DB_TOUT_02", FAMILY_4, "MySQL", "C++/InnoDB", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] mysqld: Error 3024 (HY000): Query execution was interrupted, max_execution_time exceeded",
            f"[{ts}] [WARN] [{service}] Query on table inventory timed out after {num} seconds on {ip}:3306",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Error 3024 (HY000): Query execution was interrupted, max_execution_time exceeded",
            impact_line,
        ], SCENARIOS_4, RC_VARS_4_TRAIN, ACT_VARS_4_TRAIN, signature_profile="MYSQL_MAX_EXEC_TIME_EXCEEDED"),
    _create_template("DB_TOUT_03", FAMILY_4, "MongoDB", "WiredTiger", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] MongoError: operation exceeded time limit: MaxTimeMSExpired (maxTimeMS: 5000)",
            f"[{ts}] [WARN] [{service}] COLLSCAN on collection audit_logs scanning {num*10000} documents without index on {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "operation exceeded time limit: MaxTimeMSExpired",
            impact_line,
        ], SCENARIOS_4, RC_VARS_4_TRAIN, ACT_VARS_4_TRAIN, signature_profile="MONGODB_MAX_TIME_MS_EXPIRED"),
    _create_template("DB_TOUT_04", FAMILY_4, "Oracle", "Java", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] java.sql.SQLTimeoutException: ORA-01013: user requested cancel of current operation",
            f"[{ts}] [ERROR] [{service}] Statement query timeout ({num}s) triggered for SQL handle {hex_id} on {ip}:1521",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "java.sql.SQLTimeoutException: ORA-01013: user requested cancel of current operation",
            impact_line,
        ], SCENARIOS_4, RC_VARS_4_TRAIN, ACT_VARS_4_TRAIN, signature_profile="ORACLE_SQL_TIMEOUT_ORA_01013"),
    _create_template("DB_TOUT_05", FAMILY_4, "Cassandra", "CQL", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] com.datastax.oss.driver.api.core.servererrors.ReadTimeoutException: Cassandra timeout during read query at consistency LOCAL_QUORUM (2 responses were required but only 1 replica responded)",
            f"[{ts}] [WARN] [{service}] Coordinator node {ip} timed out waiting for replica response",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ReadTimeoutException: Cassandra timeout during read query at consistency",
            impact_line,
        ], SCENARIOS_4, RC_VARS_4_CASSANDRA, ACT_VARS_4_CASSANDRA,
        signature_profile="CASSANDRA_READ_TIMEOUT_QUORUM",
        failure_mechanism="CASSANDRA_REPLICA_TIMEOUT",
        expected_tokens=["ReadTimeoutException", "LOCAL_QUORUM"],
        forbidden_tokens=["unindexed", "EXPLAIN ANALYZE", "full-table"]),
    _create_template("DB_TOUT_06", FAMILY_4, "Elasticsearch", "REST", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] ElasticsearchStatusException: Elasticsearch exception [type=search_phase_execution_exception, reason=all shards failed]",
            f"[{ts}] [WARN] [{service}] Failed shard: [orders-2026][{num}] timeout while waiting for response from {ip}:9200",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "search_phase_execution_exception, reason=all shards failed",
            impact_line,
        ], SCENARIOS_4, RC_VARS_4_TRAIN, ACT_VARS_4_TRAIN, signature_profile="ES_SEARCH_PHASE_TIMEOUT"),
    _create_template("DB_TOUT_07", FAMILY_4, "ClickHouse", "HTTP", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Code: 159. DB::Exception: Timeout exceeded: elapsed {num} seconds, maximum: 30 seconds",
            f"[{ts}] [WARN] [{service}] Memory limit exceeded for query {hex_id} on ClickHouse cluster node {ip}:8123",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Timeout exceeded: elapsed",
            "maximum: 30 seconds",
            impact_line,
        ], SCENARIOS_4, RC_VARS_4_VAL, ACT_VARS_4_VAL, signature_profile="CLICKHOUSE_TIMEOUT_EXCEEDED"),
    _create_template("DB_TOUT_08", FAMILY_4, "Presto/Trino", "JVM", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] io.trino.spi.TrinoException: EXCEEDED_TIME_LIMIT: Query exceeded maximum execution time of {num}m on coordinator {ip}",
            f"[{ts}] [ERROR] [{service}] Stage 2 failed due to slow worker response",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "TrinoException: EXCEEDED_TIME_LIMIT: Query exceeded maximum execution time",
            impact_line,
        ], SCENARIOS_4, RC_VARS_4_VAL, ACT_VARS_4_VAL, signature_profile="TRINO_EXCEEDED_TIME_LIMIT"),
    _create_template("DB_TOUT_09", FAMILY_4, "CockroachDB", "Go", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] pq: statement execution timeout ({num*1000}ms): query canceled on CockroachDB node {ip}",
            f"[{ts}] [WARN] [{service}] DistSQL plan execution canceled: scan exceeded statement_timeout",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "statement execution timeout",
            "query canceled on CockroachDB node",
            impact_line,
        ], SCENARIOS_4, RC_VARS_4_TEST, ACT_VARS_4_TEST, signature_profile="COCKROACHDB_STATEMENT_TIMEOUT"),
    _create_template("DB_TOUT_10", FAMILY_4, "Redis", "C", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] redis.exceptions.TimeoutError: Timeout reading from socket on {ip}:6379 after {num}ms",
            f"[{ts}] [WARN] [{service}] Redis slowlog: SLOWLOG entry: KEYS * command blocked single-threaded event loop for {num}ms",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Timeout reading from socket on",
            "SLOWLOG entry: KEYS * command blocked",
            impact_line,
        ], SCENARIOS_4, RC_VARS_4_TEST, ACT_VARS_4_TEST, signature_profile="REDIS_SOCKET_SLOWLOG_TIMEOUT"),
]


# =========================================================================
# 5. DB_STORAGE_EXHAUSTION
# =========================================================================

SCENARIOS_5 = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Primary database volume 100% full; database crashed and remounted read-only",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Database disk space utilization at 96% on {ip}; writes will fail imminently",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Temp tablespace disk usage threshold exceeded 85%; temporary sort spill warning",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Isolated disk quota exceeded on temporary staging export partition on host {ip}; primary database storage unaffected",
    ),
]

RC_VARS_5_TRAIN = {
    "RC_TRAIN_1": "Database filesystem storage volume reached 100% capacity on {ip}, rejecting further write operations.",
    "RC_TRAIN_2": "Disk storage space exhausted on database host {ip}, preventing write operations.",
    "RC_TRAIN_3": "Filesystem partition reached maximum disk capacity, causing database writes to fail on {ip}.",
}
ACT_VARS_5_TRAIN = {
    "ACT_TRAIN_1": "Expand database persistent disk volume; inspect WAL accumulation, bloated tables, and temporary files on {ip}.",
    "ACT_TRAIN_2": "Purge obsolete WAL archives, clean up temporary table spills, and terminate runaway sorting queries.",
    "ACT_TRAIN_3": "Configure automated WAL retention policy, rotate database audit logs, and allocate additional disk space.",
}

RC_VARS_5_VAL = {
    "RC_VAL_1": "Database storage capacity exhausted on host {ip}, preventing database write transactions.",
}
ACT_VARS_5_VAL = {
    "ACT_VAL_1": "Allocate additional disk volume capacity; clean up stale temporary files and check transaction log purge status on {ip}.",
}

RC_VARS_5_TEST = {
    "RC_TEST_1": "Database disk partition exhausted preventing transaction commit and write operations on {ip}.",
}
ACT_VARS_5_TEST = {
    "ACT_TEST_1": "Increase storage volume size for database instance {ip} and verify automated archive purging.",
}

TEMPLATES_STORAGE_EXHAUSTION = [
    _create_template("DB_STOR_01", FAMILY_5, "PostgreSQL", "C/Engine", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [PANIC] [{service}] postgres[984]: PANIC: could not write to file \"pg_wal/xlogtemp.{hex_id}\": No space left on device",
            f"[{ts}] [FATAL] [{service}] database system is shut down in recovery mode on {ip}:5432",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "PANIC: could not write to file",
            "No space left on device",
            impact_line,
        ], SCENARIOS_5, RC_VARS_5_TRAIN, ACT_VARS_5_TRAIN, signature_profile="POSTGRES_PG_WAL_NO_SPACE"),
    _create_template("DB_STOR_02", FAMILY_5, "MySQL", "C++/InnoDB", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] mysqld: [ERROR] InnoDB: Write to file ./ibdata1 failed at offset {num*1000000}. No space left on device",
            f"[{ts}] [ERROR] [{service}] Disk is full writing './orders.ibd' (OS errno 28 - No space left on device) on {ip}:3306",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "InnoDB: Write to file ./ibdata1 failed",
            "No space left on device",
            impact_line,
        ], SCENARIOS_5, RC_VARS_5_TRAIN, ACT_VARS_5_TRAIN, signature_profile="MYSQL_IBDATA1_NO_SPACE"),
    _create_template("DB_STOR_03", FAMILY_5, "MongoDB", "WiredTiger", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] mongod: WiredTiger error (28) [17281928]: /data/db/journal/WiredTigerLog.{num}: write: No space left on device",
            f"[{ts}] [FATAL] [{service}] terminating mongod process due to storage failure on node {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "WiredTiger error (28)",
            "No space left on device",
            impact_line,
        ], SCENARIOS_5, RC_VARS_5_TRAIN, ACT_VARS_5_TRAIN, signature_profile="MONGODB_WIREDTIGER_STORAGE_FULL"),
    _create_template("DB_STOR_04", FAMILY_5, "Elasticsearch", "Java", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] org.elasticsearch.cluster.routing.allocation.DiskThresholdMonitor: flood stage disk watermark [95%] exceeded on [{hex_id}][{ip}:9200], all indices marked read-only",
            f"[{ts}] [ERROR] [{service}] ClusterBlockException: blocked by: [TOO_MANY_REQUESTS/12/disk usage exceeded flood-stage watermark]",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "flood stage disk watermark [95%] exceeded",
            "indices marked read-only",
            impact_line,
        ], SCENARIOS_5, RC_VARS_5_TRAIN, ACT_VARS_5_TRAIN, signature_profile="ES_FLOOD_STAGE_WATERMARK"),
    _create_template("DB_STOR_05", FAMILY_5, "PostgreSQL", "C/Tablespace", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] postgres: ERROR: could not extend file \"base/16384/{num}\": No space left on device",
            f"[{ts}] [HINT] [{service}] Check free disk space in tablespace mount /mnt/pg_data on host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ERROR: could not extend file",
            "No space left on device",
            impact_line,
        ], SCENARIOS_5, RC_VARS_5_TRAIN, ACT_VARS_5_TRAIN, signature_profile="POSTGRES_TABLESPACE_FULL"),
    _create_template("DB_STOR_06", FAMILY_5, "Redis", "C", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARNING] [{service}] redis-server: Short read or OOM writing RDB snapshot to dump.rdb: No space left on device",
            f"[{ts}] [ERROR] [{service}] MISCONF Errors writing to the AOF file on {ip}:6379: Disk full",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "writing RDB snapshot to dump.rdb: No space left on device",
            "MISCONF Errors writing to the AOF file",
            impact_line,
        ], SCENARIOS_5, RC_VARS_5_TRAIN, ACT_VARS_5_TRAIN, signature_profile="REDIS_RDB_DISK_FULL"),
    _create_template("DB_STOR_07", FAMILY_5, "Oracle", "C/ASM", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] ORA-01653: unable to extend table SALES.ORDERS by 128 in tablespace USERS on {ip}:1521",
            f"[{ts}] [ERROR] [{service}] ORA-01116: error in opening database file: diskgroup DATA full",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ORA-01653: unable to extend table",
            "in tablespace USERS",
            impact_line,
        ], SCENARIOS_5, RC_VARS_5_VAL, ACT_VARS_5_VAL, signature_profile="ORACLE_TABLESPACE_USERS_FULL"),
    _create_template("DB_STOR_08", FAMILY_5, "Cassandra", "Java", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] org.apache.cassandra.io.FSWriteError: java.io.IOException: No space left on device during compaction of data directory on {ip}",
            f"[{ts}] [ERROR] [{service}] Cassandra commitlog directory disk space utilization at 99.8%",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "FSWriteError: java.io.IOException: No space left on device during compaction",
            impact_line,
        ], SCENARIOS_5, RC_VARS_5_VAL, ACT_VARS_5_VAL, signature_profile="CASSANDRA_COMPACTION_DISK_FULL"),
    _create_template("DB_STOR_09", FAMILY_5, "ClickHouse", "C++", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Code: 243. DB::Exception: Cannot write to file /var/lib/clickhouse/data/default/metrics/data.bin: No space left on device",
            f"[{ts}] [ERROR] [{service}] Table metrics on node {ip}:9000 marked readonly due to disk full",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "DB::Exception: Cannot write to file",
            "No space left on device",
            impact_line,
        ], SCENARIOS_5, RC_VARS_5_TEST, ACT_VARS_5_TEST, signature_profile="CLICKHOUSE_DATA_BIN_DISK_FULL"),
    _create_template("DB_STOR_10", FAMILY_5, "SQLite", "C", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] sqlite3.OperationalError: disk I/O error: error writing WAL frame: No space left on device",
            f"[{ts}] [FATAL] [{service}] Database file /app/data/app_{hex_id}.db failed WAL checkpoint on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "sqlite3.OperationalError: disk I/O error",
            "No space left on device",
            impact_line,
        ], SCENARIOS_5, RC_VARS_5_TEST, ACT_VARS_5_TEST, signature_profile="SQLITE_WAL_DISK_IO_ERROR"),
]


# =========================================================================
# 6. DB_INDEX_OR_DATA_CORRUPTION
# =========================================================================

SCENARIOS_6 = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Primary database table corrupt; all read/write operations aborting on cluster",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Index corruption detected on payments table; query results returning invalid pages on {ip}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single corrupted index leaf node detected during maintenance REINDEX; rebuilding index",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Isolated checksum mismatch on non-critical secondary replica log segment; replica restarted and resynced",
    ),
]

RC_VARS_6_TRAIN = {
    "RC_TRAIN_1": "Physical database page corruption or torn block write detected on disk for {service}.",
    "RC_TRAIN_2": "B-Tree index leaf corruption causing query engine traversal abort on {ip}.",
    "RC_TRAIN_3": "Corrupted database page or block checksum mismatch detected during storage read on {ip}.",
}
ACT_VARS_6_TRAIN = {
    "ACT_TRAIN_1": "Execute REINDEX on corrupted relation and run pg_checksums / database consistency checks.",
    "ACT_TRAIN_2": "Failover to healthy standby node and restore corrupted table from backup.",
    "ACT_TRAIN_3": "Perform block-level integrity verification, inspect storage hardware for bit-rot, and rebuild corrupted index partitions.",
}

RC_VARS_6_VAL = {
    "RC_VAL_1": "Database index corruption causing query failure on host {ip}.",
}
ACT_VARS_6_VAL = {
    "ACT_VAL_1": "Rebuild corrupted index with REINDEX command and verify table integrity on {ip}.",
}

RC_VARS_6_TEST = {
    "RC_TEST_1": "Database storage block corruption detected on disk for host {ip}.",
}
ACT_VARS_6_TEST = {
    "ACT_TEST_1": "Restore corrupted database partition from verified backup and inspect hardware storage on {ip}.",
}

TEMPLATES_DATA_CORRUPTION = [
    _create_template("DB_CORR_01", FAMILY_6, "PostgreSQL", "C/Engine", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] postgres[5812]: ERROR: invalid page in block {num} of relation base/16384/26810",
            f"[{ts}] [FATAL] [{service}] block checksum mismatch: calculated {hex_id} expected deadbeef on {ip}:5432",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ERROR: invalid page in block",
            "block checksum mismatch",
            impact_line,
        ], SCENARIOS_6, RC_VARS_6_TRAIN, ACT_VARS_6_TRAIN, signature_profile="POSTGRES_PAGE_CHECKSUM_CORRUPT"),
    _create_template("DB_CORR_02", FAMILY_6, "MySQL", "C++/InnoDB", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] mysqld: [ERROR] InnoDB: Database page corruption on disk or a failed read of page [page id: space={num}, page number={num*2}]",
            f"[{ts}] [ERROR] [{service}] InnoDB: Page checksum mismatch in file './orders/payments.ibd' on {ip}:3306",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "InnoDB: Database page corruption on disk",
            "Page checksum mismatch in file",
            impact_line,
        ], SCENARIOS_6, RC_VARS_6_TRAIN, ACT_VARS_6_TRAIN, signature_profile="MYSQL_INNODB_PAGE_CORRUPT"),
    _create_template("DB_CORR_03", FAMILY_6, "MongoDB", "WiredTiger", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] mongod: WiredTiger error (-31802) [182910]: WT_ERROR: non-specific WiredTiger error: read checksum error on block {hex_id}",
            f"[{ts}] [ERROR] [{service}] Data file collection-4-{hex_id}.wt contains corrupted record on {ip}:27017",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "WT_ERROR: non-specific WiredTiger error: read checksum error",
            impact_line,
        ], SCENARIOS_6, RC_VARS_6_TRAIN, ACT_VARS_6_TRAIN, signature_profile="MONGODB_WIREDTIGER_READ_CORRUPT"),
    _create_template("DB_CORR_04", FAMILY_6, "PostgreSQL", "C/Index", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] postgres: ERROR: index \"idx_customer_email\" contains corrupted page {num}",
            f"[{ts}] [ERROR] [{service}] B-tree root page is not a root page in index idx_customer_email on {ip}",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "contains corrupted page",
            "B-tree root page is not a root page",
            impact_line,
        ], SCENARIOS_6, RC_VARS_6_TRAIN, ACT_VARS_6_TRAIN, signature_profile="POSTGRES_BTREE_INDEX_CORRUPT"),
    _create_template("DB_CORR_05", FAMILY_6, "SQLite", "C", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] sqlite3.DatabaseError: file is not a database or database disk image is malformed",
            f"[{ts}] [FATAL] [{service}] PRAGMA integrity_check failed on /data/prod_{hex_id}.sqlite: *** in database main *** Page {num} is never used",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "database disk image is malformed",
            "PRAGMA integrity_check failed",
            impact_line,
        ], SCENARIOS_6, RC_VARS_6_TRAIN, ACT_VARS_6_TRAIN, signature_profile="SQLITE_IMAGE_MALFORMED"),
    _create_template("DB_CORR_06", FAMILY_6, "Oracle", "C", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] ORA-01578: ORACLE data block corrupted (file # {num}, block # {num*10}) on {ip}:1521",
            f"[{ts}] [ERROR] [{service}] ORA-01110: data file {num}: '+DATA/orcl/datafile/users.259.{hex_id}'",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ORA-01578: ORACLE data block corrupted",
            impact_line,
        ], SCENARIOS_6, RC_VARS_6_TRAIN, ACT_VARS_6_TRAIN, signature_profile="ORACLE_BLOCK_CORRUPTED_ORA_01578"),
    _create_template("DB_CORR_07", FAMILY_6, "MySQL", "C++", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] mysqld: CHECK TABLE users.accounts returned: Corrupt index btree leaf node {hex_id}",
            f"[{ts}] [WARN] [{service}] Table is marked as crashed and should be repaired on {ip}:3306",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "CHECK TABLE users.accounts returned: Corrupt index btree leaf node",
            "Table is marked as crashed and should be repaired",
            impact_line,
        ], SCENARIOS_6, RC_VARS_6_VAL, ACT_VARS_6_VAL, signature_profile="MYSQL_CHECK_TABLE_CORRUPT"),
    _create_template("DB_CORR_08", FAMILY_6, "Redis", "C", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] redis-server: Bad checksum in RDB file! Expected {hex_id}, got ffffffff",
            f"[{ts}] [FATAL] [{service}] Corrupted RDB file loading aborted; server startup failed on {ip}:6379",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Bad checksum in RDB file!",
            "Corrupted RDB file loading aborted",
            impact_line,
        ], SCENARIOS_6, RC_VARS_6_VAL, ACT_VARS_6_VAL, signature_profile="REDIS_RDB_CHECKSUM_CORRUPT"),
    _create_template("DB_CORR_09", FAMILY_6, "Cassandra", "Java", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] org.apache.cassandra.io.sstable.CorruptSSTableException: Corrupted SSTable /var/lib/cassandra/data/keyspace1/orders-{hex_id}/nb-{num}-big-Data.db on {ip}",
            f"[{ts}] [FATAL] [{service}] Failed reading data block from SSTable: CRC32 checksum mismatch",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "CorruptSSTableException: Corrupted SSTable",
            "Failed reading data block from SSTable",
            impact_line,
        ], SCENARIOS_6, RC_VARS_6_TEST, ACT_VARS_6_TEST, signature_profile="CASSANDRA_SSTABLE_CRC_CORRUPT"),
    _create_template("DB_CORR_10", FAMILY_6, "Elasticsearch", "Java", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] org.apache.lucene.index.CorruptIndexException: codec header mismatch from /data/indices/shard/index/_2a.si on {ip}",
            f"[{ts}] [ERROR] [{service}] Shard failed to open: corrupted index files detected on cluster node",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "CorruptIndexException: codec header mismatch",
            "corrupted index files detected",
            impact_line,
        ], SCENARIOS_6, RC_VARS_6_TEST, ACT_VARS_6_TEST, signature_profile="LUCENE_CORRUPT_INDEX_HEADER"),
]


DATABASE_TEMPLATES: list[LogTemplate] = (
    TEMPLATES_CONN_STARVATION +
    TEMPLATES_DEADLOCK +
    TEMPLATES_REPL_LAG +
    TEMPLATES_QUERY_TIMEOUT +
    TEMPLATES_STORAGE_EXHAUSTION +
    TEMPLATES_DATA_CORRUPTION
)

assert len(DATABASE_TEMPLATES) == 60, f"Expected 60 templates in DATABASE, got {len(DATABASE_TEMPLATES)}"
