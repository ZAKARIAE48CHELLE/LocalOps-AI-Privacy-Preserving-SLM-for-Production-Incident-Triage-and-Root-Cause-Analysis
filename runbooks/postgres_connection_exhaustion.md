# Runbook: PostgreSQL Connection Pool Exhaustion

- **Incident Type**: DATABASE
- **Affected Services**: event-processor, user-service, order-service, api-gateway
- **Severity Default**: P1_CRITICAL
- **Keywords**: Npgsql, NpgsqlException, connection pool has reached its maximum size, FATAL: remaining connection slots are reserved, max_connections, HikariPool

## Symptoms
- Applications reporting `Npgsql.NpgsqlException: The connection pool has reached its maximum size`.
- PostgreSQL rejecting new connections with `FATAL: remaining connection slots are reserved for non-replication superuser connections`.
- Spikes in HTTP 500/504 errors on downstream APIs.
- Service latency climbs sharply as threads block waiting for available connections.

## Root Cause Diagnosis
1. Run `SELECT count(*), state FROM pg_stat_activity GROUP BY state;` to check idle vs active client connections.
2. Identify long-running transactions:
   ```sql
   SELECT pid, now() - xact_start AS duration, query 
   FROM pg_stat_activity 
   WHERE state <> 'idle' 
   ORDER BY duration DESC LIMIT 10;
   ```
3. Check application connection pool leaks (unclosed sessions, missing `using` / try-with-resources blocks).
4. Verify if a microservice scaled out its replica count without proportional PgBouncer connection pooling.

## Immediate Mitigation
1. Terminate hanging idle-in-transaction connections:
   ```sql
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'idle in transaction' 
     AND now() - state_change > interval '5 minutes';
   ```
2. Rate-limit or restart offending application pods consuming excessive connections.
3. If PgBouncer is deployed, reload pool configurations or temporarily route non-critical traffic away from the primary instance.

## Long-Term Remediation
- Deploy PgBouncer in transaction pooling mode between microservices and PostgreSQL.
- Configure `idle_in_transaction_session_timeout = '60s'` in postgresql.conf.
- Cap application pool sizes per replica (e.g. `maximumPoolSize = 10` in HikariCP) rather than relying on large defaults.
- Implement circuit breaking on database queries in service data access layers.
