# Runbook: Apache Kafka Consumer Group Lag and Partition Starvation

- **Incident Type**: MESSAGING
- **Affected Services**: stream-processor, telemetry-ingest, notification-service, event-hub
- **Severity Default**: P2_HIGH
- **Keywords**: CommitFailedException, consumer poll timeout, max.poll.interval.ms exceeded, consumer group rebalance, consumer lag spike

## Symptoms
- Consumer lag metrics (`kafka_consumergroup_lag`) climb continuously on primary topics.
- Consumer instances log `org.apache.kafka.clients.consumer.CommitFailedException: Offset commit cannot be completed since the group has already rebalanced`.
- Message processing latency increases; real-time event updates stall downstream.

## Root Cause Diagnosis
1. Check consumer group offset and lag per partition:
   `kafka-consumer-groups.sh --bootstrap-server <broker>:9092 --describe --group <group_id>`
2. Inspect application logs for slow synchronous calls inside the message processing loop causing `max.poll.interval.ms` expiration.
3. Check for unbalanced partition assignments where one slow consumer starves others.
4. Verify broker I/O saturation or disk latency using broker metrics.

## Immediate Mitigation
1. Increase `max.poll.interval.ms` or decrease `max.poll.records` to ensure poll loops complete before rebalance timeouts.
2. Scale up consumer replica count to match partition count:
   `kubectl scale deployment/<consumer_app> --replicas=<num_partitions>`
3. If an individual poison-pill message is blocking the group, seek the offset forward past the problematic message to restore throughput.

## Long-Term Remediation
- Offload heavy IO operations from the message consumption thread to an asynchronous worker thread pool.
- Implement a Dead Letter Queue (DLQ) pattern for non-transient message parsing errors.
- Ensure topic partition counts align with expected peak consumer horizontal scale.
