# Runbook: NATS JetStream Storage Limit and Stream Starvation

- **Incident Type**: MESSAGING
- **Affected Services**: event-router, telemetry-collector, async-dispatcher
- **Severity Default**: P2_HIGH
- **Keywords**: nats: maximum bytes exceeded, storage limit reached, JetStream stream limit, NATS JetStream publish timeout

## Symptoms
- Producers fail to publish messages with `nats: maximum bytes exceeded` or `nats: insufficient storage`.
- NATS server logs warn that stream file storage has reached 100% of configured `max_bytes`.
- Asynchronous message delivery drops or blocks across critical workflows.

## Root Cause Diagnosis
1. Inspect JetStream account and stream utilization:
   `nats stream info <stream_name>`
2. Check storage retention policy (`LimitsPolicy`, `InterestPolicy`, `WorkQueuePolicy`).
3. Verify if consumer delivery acknowledgment is stalling, causing messages to remain un-purged.
4. Check volume disk space on NATS JetStream storage mount: `df -h /data/nats`.

## Immediate Mitigation
1. Purge obsolete message historical ranges if permissible:
   `nats stream purge <stream_name> --force`
2. Dynamically expand the stream storage limit:
   `nats stream edit <stream_name> --max-bytes=<expanded_size>`
3. Restart or unblock stalled consumers to allow work-queue streams to drain.

## Long-Term Remediation
- Set appropriate message TTLs (`max_age`) on transient event streams.
- Configure JetStream file storage volumes with automated resize alarms.
- Deploy cluster monitoring on NATS storage watermark metrics (`jetstream_stream_bytes`).
