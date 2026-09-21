"""Structural log templates for the MESSAGING category (6 families, 60 templates).

Each family defines 10 templates: 6 TRAIN, 2 VALIDATION, 2 TEST.
Includes P4_LOW coverage, normalized metadata, strictly isolated single-incident narratives,
and split-aware variant pools.
"""

from typing import Callable
from src.data.models import DatasetSplit, ImpactScenario, Severity
from src.data.templates.base import LogTemplate
from src.schemas.enums import IncidentFamily


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
    obs = observed_failure_mechanism or FAMILY_OBSERVED_MAP.get(family, "")
    hyps = possible_hypotheses if possible_hypotheses is not None else FAMILY_HYPOTHESES_MAP.get(family, [])
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
        observed_failure_mechanism=obs,
        possible_hypotheses=hyps,
    )


FAMILY_OBSERVED_MAP = {
    IncidentFamily.MSG_CONSUMER_LAG_ACCUMULATION: (
        "Message consumer lag accumulating due to consumption rate falling behind arrival throughput"
    ),
    IncidentFamily.MSG_DEAD_LETTER_QUEUE_OVERFLOW: (
        "Dead-letter queue message volume approaching or exceeding storage capacity threshold"
    ),
    IncidentFamily.MSG_PARTITION_LEADER_OFFLINE: (
        "Topic partition leader offline or unavailable, halting partition read/write operations"
    ),
    IncidentFamily.MSG_POISON_PILL_FAILURE: (
        "Consumer message processing failure or crash triggered by unhandled exception on malformed payload"
    ),
    IncidentFamily.MSG_QUEUE_STORAGE_BACKPRESSURE: (
        "Message broker storage volume or memory capacity saturated, triggering publisher backpressure"
    ),
    IncidentFamily.MSG_DUPLICATE_DELIVERY_OR_IDEMPOTENCY: (
        "Duplicate message processing or redelivery detected due to uncommitted offset or rebalance"
    ),
}

FAMILY_HYPOTHESES_MAP = {
    IncidentFamily.MSG_CONSUMER_LAG_ACCUMULATION: [
        "slow downstream I/O",
        "under-provisioned workers",
        "database lock contention",
        "unindexed insert",
    ],
    IncidentFamily.MSG_DEAD_LETTER_QUEUE_OVERFLOW: [
        "persistent downstream outage",
        "poison-pill payload",
        "consumer deserialization bug",
        "schema mismatch",
    ],
    IncidentFamily.MSG_PARTITION_LEADER_OFFLINE: [
        "broker crash",
        "insufficient in-sync replicas",
        "KRaft quorum loss",
        "zookeeper session expiration",
    ],
    IncidentFamily.MSG_POISON_PILL_FAILURE: [
        "corrupt binary data",
        "schema registry missing id",
        "unhandled JSON parse error",
        "invalid UTF-8 sequence",
    ],
    IncidentFamily.MSG_QUEUE_STORAGE_BACKPRESSURE: [
        "disk full",
        "memory high watermark alarm",
        "slow consumer drain rate",
        "uncompacted log segments",
    ],
    IncidentFamily.MSG_DUPLICATE_DELIVERY_OR_IDEMPOTENCY: [
        "poll timeout expired",
        "consumer rebalance",
        "missing idempotency key",
        "lost acknowledgment",
    ],
}


# =========================================================================
# 1. MSG_CONSUMER_LAG_ACCUMULATION
# =========================================================================

FAM_LAG = IncidentFamily.MSG_CONSUMER_LAG_ACCUMULATION

SCEN_LAG = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Consumer lag exceeded 500,000 messages; order fulfillment delayed by >45 minutes",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Consumer lag spike on topic orders-stream: 120,000 unread messages in {service}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Minor consumer group lag during marketing push; consumer slowly catching up",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Transient consumer lag of 25 messages on low-priority telemetry topic; fully processed within 60s",
    ),
]

RC_LAG_TRAIN = {
    "RC_TRAIN_1": "Message consumer group processing rate fell behind publisher throughput, accumulating backlog in {service}.",
    "RC_TRAIN_2": "Consumer lag accumulation exceeding operational threshold across topic partitions on {ip}.",
    "RC_TRAIN_3": "Message queue subscriber processing capacity overwhelmed by incoming event arrival rate in {service}.",
}
ACT_LAG_TRAIN = {
    "ACT_TRAIN_1": "Scale up consumer pod replica count and increase consumer concurrency in {service}.",
    "ACT_TRAIN_2": "Profile slow consumer message handler logic, optimize downstream batch inserts, and inspect database latency.",
    "ACT_TRAIN_3": "Increase partition count on target message topic to enable greater parallel processing.",
}

RC_LAG_VAL = {
    "RC_VAL_1": "Message queue consumer backlog growth due to arrival rate exceeding subscriber processing capacity on {ip}.",
}
ACT_LAG_VAL = {
    "ACT_VAL_1": "Increase subscriber thread count and inspect database latency in consumer pipeline for {service}.",
}

RC_LAG_TEST = {
    "RC_TEST_1": "Consumer group lag accumulation exceeding operational threshold across topic partitions on {ip}.",
}
ACT_LAG_TEST = {
    "ACT_TEST_1": "Autoscale consumer group instances and evaluate partition assignment distribution for {service}.",
}

RC_LAG = {**RC_LAG_TRAIN, **RC_LAG_VAL, **RC_LAG_TEST}
ACT_LAG = {**ACT_LAG_TRAIN, **ACT_LAG_VAL, **ACT_LAG_TEST}

TEMPLATES_LAG = [
    _create_template("MSG_LAG_01", FAM_LAG, "Apache Kafka", "Java/Kafka", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] org.apache.kafka.clients.consumer.internals.ConsumerCoordinator: [Consumer clientId={service}-1, groupId=billing-workers] Consumer lag is high: partition orders-2 has lag of {num*5000} messages",
            f"[{ts}] [ERROR] [{service}] Estimated time to catch up: 2800s on broker {ip}:9092",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Consumer lag is high: partition",
            "has lag of",
            impact_line,
        ], SCEN_LAG, RC_LAG, ACT_LAG, "KAFKA_CONSUMER_LAG_HIGH"),
    _create_template("MSG_LAG_02", FAM_LAG, "RabbitMQ", "Erlang/RabbitMQ", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] rabbitmq-monitor: queue 'tasks-queue' message count {num*2000} exceeds alarm threshold 10000 on node {ip}",
            f"[{ts}] [ERROR] [{service}] Consumer throughput (50 msg/s) lower than publishing rate (450 msg/s)",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "queue 'tasks-queue' message count",
            "exceeds alarm threshold",
            "Consumer throughput (50 msg/s) lower than publishing rate",
            impact_line,
        ], SCEN_LAG, RC_LAG, ACT_LAG, "RABBITMQ_QUEUE_BACKLOG"),
    _create_template("MSG_LAG_03", FAM_LAG, "Celery", "Python/Celery", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] celery.worker.consumer: Queue 'celery' has {num*1500} unacknowledged tasks waiting for worker capacity",
            f"[{ts}] [WARN] [{service}] Celery worker pool active on {ip} saturated: 16/16 worker slots busy",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Queue 'celery' has",
            "unacknowledged tasks waiting for worker capacity",
            "Celery worker pool active on",
            impact_line,
        ], SCEN_LAG, RC_LAG, ACT_LAG, "CELERY_UNACKNOWLEDGED_BACKLOG"),
    _create_template("MSG_LAG_04", FAM_LAG, "AWS SQS", "AWS/SQS", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] aws-sqs: ApproximateNumberOfMessagesVisible metric reached {num*3000} on queue 'order-events' (host {ip})",
            f"[{ts}] [ERROR] [{service}] SQS consumer polling latency increased: drain rate 20 msg/sec vs publish rate 250 msg/sec",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ApproximateNumberOfMessagesVisible metric reached",
            "SQS consumer polling latency increased",
            impact_line,
        ], SCEN_LAG, RC_LAG, ACT_LAG, "SQS_VISIBLE_MESSAGES_BACKLOG"),
    _create_template("MSG_LAG_05", FAM_LAG, "Google Cloud Pub/Sub", "GCP/PubSub", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] google.cloud.pubsub: Subscription 'sub-orders-process' backlog age: oldest unacknowledged message is {num*120}s old on {ip}",
            f"[{ts}] [ERROR] [{service}] num_undelivered_messages spiked to {num*4000}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Subscription 'sub-orders-process' backlog age: oldest unacknowledged message",
            "num_undelivered_messages spiked to",
            impact_line,
        ], SCEN_LAG, RC_LAG, ACT_LAG, "PUBSUB_UNDELIVERED_BACKLOG"),
    _create_template("MSG_LAG_06", FAM_LAG, "Redis Streams", "Go/Redis", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] redis-streams: XINFO GROUPS orders: group 'billing-workers' lag count {num*2500} unread entries on {ip}:6379",
            f"[{ts}] [ERROR] [{service}] Pending Entries List (PEL) count exceeded 5000 records",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "group 'billing-workers' lag count",
            "unread entries on",
            "Pending Entries List (PEL) count exceeded",
            impact_line,
        ], SCEN_LAG, RC_LAG, ACT_LAG, "REDIS_STREAMS_PEL_LAG"),
    _create_template("MSG_LAG_07", FAM_LAG, "Apache Pulsar", "Java/Pulsar", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] pulsar-client: Subscription 'sub-events' has backlog of {num*5000} messages on topic persistent://public/default/events on {ip}",
            f"[{ts}] [ERROR] [{service}] Consumer rate (12 msg/s) trailing producer publish rate (300 msg/s)",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Subscription 'sub-events' has backlog of",
            "messages on topic persistent://public/default/events on",
            impact_line,
        ], SCEN_LAG, RC_LAG, ACT_LAG, "PULSAR_SUBSCRIPTION_BACKLOG"),
    _create_template("MSG_LAG_08", FAM_LAG, "NSQ", "Go/NSQ", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] nsqd[{ip}:4150]: [orders/processor] channel depth {num*3000} exceeds memory queue size, writing to disk",
            f"[{ts}] [ERROR] [{service}] Consumer channel latency degraded: deferred count spiking",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "channel depth",
            "exceeds memory queue size, writing to disk",
            impact_line,
        ], SCEN_LAG, RC_LAG, ACT_LAG, "NSQ_CHANNEL_DEPTH_WARNING"),
    _create_template("MSG_LAG_09", FAM_LAG, "Apache ActiveMQ", "Java/ActiveMQ", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] org.apache.activemq.broker.region.Queue: Queue 'OrderQueue' queueSize={num*6000} exceeds alarm limit on {ip}:61616",
            f"[{ts}] [WARN] [{service}] Consumer count 2 is insufficient for current message arrival rate",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Queue 'OrderQueue' queueSize=",
            "exceeds alarm limit on",
            impact_line,
        ], SCEN_LAG, RC_LAG, ACT_LAG, "ACTIVEMQ_QUEUE_SIZE_ALARM"),
    _create_template("MSG_LAG_10", FAM_LAG, "Azure Service Bus", "C#/.NET", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] azure-servicebus: Queue 'events' activeMessageCount reached {num*10000} on namespace {hex_id}",
            f"[{ts}] [FATAL] [{service}] Consumer receiver processing stalled on client {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Queue 'events' activeMessageCount reached",
            "Consumer receiver processing stalled on client",
            impact_line,
        ], SCEN_LAG, RC_LAG, ACT_LAG, "AZURE_SERVICEBUS_ACTIVE_COUNT"),
]


# =========================================================================
# 2. MSG_DEAD_LETTER_QUEUE_OVERFLOW
# =========================================================================

FAM_DLQ = IncidentFamily.MSG_DEAD_LETTER_QUEUE_OVERFLOW

SCEN_DLQ = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Dead letter queue 'orders-dlq' at 100% capacity (20,000/20,000); dropping failed events",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: DLQ message count reached 15,000 on {service}; consumer routing 40 msg/s to DLQ",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single malformed event routed to dead-letter queue; normal queue processing unaffected",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Isolated poison message moved to DLQ and archived; dead-letter queue storage usage <1%",
    ),
]

RC_DLQ_TRAIN = {
    "RC_TRAIN_1": "Dead-letter queue (DLQ) message volume approaching or exceeding capacity threshold in {service}.",
    "RC_TRAIN_2": "Dead-letter queue threshold breached due to high volume of rejected message deliveries on {ip}.",
    "RC_TRAIN_3": "Continuous routing of unprocessable messages to dead-letter queue exhausting storage limits for {service}.",
}
ACT_DLQ_TRAIN = {
    "ACT_TRAIN_1": "Inspect failed DLQ message payloads, patch consumer error handler, and redrive messages.",
    "ACT_TRAIN_2": "Purge invalid poisoned messages from DLQ or archive to offline storage to prevent overflow.",
    "ACT_TRAIN_3": "Deploy schema migration fix in consumer to correctly handle incoming message format.",
}

RC_DLQ_VAL = {
    "RC_VAL_1": "Dead-letter queue depth spike caused by recurrent processing exceptions on {ip}.",
}
ACT_DLQ_VAL = {
    "ACT_VAL_1": "Examine DLQ dead-letter reasons, increase DLQ maximum message threshold, and patch consumer parser in {service}.",
}

RC_DLQ_TEST = {
    "RC_TEST_1": "Dead-letter queue storage quota exhausted due to surge in unhandled consumer processing errors on {ip}.",
}
ACT_DLQ_TEST = {
    "ACT_TEST_1": "Archive DLQ messages to object storage, identify poison payload schema, and redrive valid messages for {service}.",
}

RC_DLQ = {**RC_DLQ_TRAIN, **RC_DLQ_VAL, **RC_DLQ_TEST}
ACT_DLQ = {**ACT_DLQ_TRAIN, **ACT_DLQ_VAL, **ACT_DLQ_TEST}

TEMPLATES_DLQ = [
    _create_template("MSG_DLQ_01", FAM_DLQ, "RabbitMQ DLQ", "Erlang/RabbitMQ", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] rabbitmq-monitor: DLQAlert: Dead letter queue 'order-events-dlq' reached 95% capacity ({num*100}/20000 messages) on {ip}",
            f"[{ts}] [WARN] [{service}] x-dead-letter-exchange routing high volume of unroutable messages",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "DLQAlert: Dead letter queue 'order-events-dlq' reached 95% capacity",
            "x-dead-letter-exchange routing high volume",
            impact_line,
        ], SCEN_DLQ, RC_DLQ, ACT_DLQ, "RABBITMQ_DLQ_CAPACITY_ALERT"),
    _create_template("MSG_DLQ_02", FAM_DLQ, "AWS SQS DLQ", "AWS/CloudWatch", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] cloudwatch: SQS_DLQ_HighMessageCount firing for queue 'billing-dead-letter' (count: {num*500})",
            f"[{ts}] [ERROR] [{service}] MaxReceiveCount of 3 exceeded for {num} messages; routed to DLQ on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "SQS_DLQ_HighMessageCount firing for queue 'billing-dead-letter'",
            "MaxReceiveCount of 3 exceeded for",
            impact_line,
        ], SCEN_DLQ, RC_DLQ, ACT_DLQ, "SQS_DLQ_HIGH_MESSAGE_COUNT"),
    _create_template("MSG_DLQ_03", FAM_DLQ, "Apache Kafka DLT", "Java/SpringKafka", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] DeadLetterPublishingRecoverer: Failed processing record offset={num}; sending to topic orders.DLT",
            f"[{ts}] [WARN] [{service}] Dead letter topic orders.DLT size reached {num*50}MB on broker {ip}:9092",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "DeadLetterPublishingRecoverer: Failed processing record",
            "sending to topic orders.DLT",
            impact_line,
        ], SCEN_DLQ, RC_DLQ, ACT_DLQ, "KAFKA_DEAD_LETTER_TOPIC_GROWTH"),
    _create_template("MSG_DLQ_04", FAM_DLQ, "Celery DLQ", "Python/Celery", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] celery.worker: MaxRetriesExceededError: Task charge_customer[{hex_id}] failed after 5 retries; moving to dead_letter_queue",
            f"[{ts}] [FATAL] [{service}] DLQ queue size reached {num*200} items on host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "MaxRetriesExceededError: Task charge_customer[",
            "moving to dead_letter_queue",
            impact_line,
        ], SCEN_DLQ, RC_DLQ, ACT_DLQ, "CELERY_MAX_RETRIES_EXCEEDED_DLQ"),
    _create_template("MSG_DLQ_05", FAM_DLQ, "Google Cloud Pub/Sub", "Python/PubSub", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] google.cloud.pubsub_v1: Dead-letter policy forwarded message {hex_id} to dead-letter topic 'projects/prod/topics/events-dlq'",
            f"[{ts}] [WARN] [{service}] DLQ topic forward rate exceeded 25 msgs/sec on subscriber {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Dead-letter policy forwarded message",
            "to dead-letter topic 'projects/prod/topics/events-dlq'",
            impact_line,
        ], SCEN_DLQ, RC_DLQ, ACT_DLQ, "PUBSUB_DEAD_LETTER_FORWARD_SPIKE"),
    _create_template("MSG_DLQ_06", FAM_DLQ, "Apache ActiveMQ", "Java/ActiveMQ", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] org.apache.activemq.broker.region.Queue: ActiveMQ.DLQ is full: memory usage 100% ({num*10}MB) on {ip}:61616",
            f"[{ts}] [FATAL] [{service}] Broker pausing message flow to dead-letter queue",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ActiveMQ.DLQ is full: memory usage 100%",
            "Broker pausing message flow to dead-letter queue",
            impact_line,
        ], SCEN_DLQ, RC_DLQ, ACT_DLQ, "ACTIVEMQ_DLQ_MEMORY_FULL"),
    _create_template("MSG_DLQ_07", FAM_DLQ, "Azure Service Bus", "C#/.NET", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] azure-servicebus: DeadLetterQueueFullException: The dead-letter subqueue '$DeadLetterQueue' for entity 'orders' is full on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "DeadLetterQueueFullException: The dead-letter subqueue '$DeadLetterQueue' for entity 'orders' is full",
            impact_line,
        ], SCEN_DLQ, RC_DLQ, ACT_DLQ, "AZURE_SB_DLQ_QUOTA_EXCEEDED"),
    _create_template("MSG_DLQ_08", FAM_DLQ, "RabbitMQ Spring AMQP", "Java/Spring", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] org.springframework.amqp.rabbit.retry.RepublishMessageRecoverer: Republishing failed message to exchange=error.exchange routingKey=orders.dlq",
            f"[{ts}] [ERROR] [{service}] DLQ depth reached critical threshold ({num*1000}) on host {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "RepublishMessageRecoverer: Republishing failed message to exchange=error.exchange",
            "routingKey=orders.dlq",
            impact_line,
        ], SCEN_DLQ, RC_DLQ, ACT_DLQ, "SPRING_AMQP_REPUBLISH_DLQ_SPIKE"),
    _create_template("MSG_DLQ_09", FAM_DLQ, "Apache Pulsar", "Java/Pulsar", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] pulsar-client: Message redelivery count exceeded maxRedeliverCount (5); dispatched to DLQ topic 'persistent://public/default/orders-DLQ'",
            f"[{ts}] [WARN] [{service}] DLQ storage quota threshold reached 98% on broker {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Message redelivery count exceeded maxRedeliverCount",
            "dispatched to DLQ topic 'persistent://public/default/orders-DLQ'",
            impact_line,
        ], SCEN_DLQ, RC_DLQ, ACT_DLQ, "PULSAR_DLQ_QUOTA_BREACH"),
    _create_template("MSG_DLQ_10", FAM_DLQ, "NSQ", "Go/NSQ", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] nsqd[{ip}]: [orders/failed_channel] message {hex_id} attempts 10 exceeded limit, routed to dead channel buffer",
            f"[{ts}] [FATAL] [{service}] Dead letter buffer reached capacity ({num*500} records)",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "attempts 10 exceeded limit, routed to dead channel buffer",
            "Dead letter buffer reached capacity",
            impact_line,
        ], SCEN_DLQ, RC_DLQ, ACT_DLQ, "NSQ_DEAD_CHANNEL_BUFFER_FULL"),
]


# =========================================================================
# 3. MSG_PARTITION_LEADER_OFFLINE
# =========================================================================

FAM_LDR = IncidentFamily.MSG_PARTITION_LEADER_OFFLINE

SCEN_LDR = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Leader election failed on topic orders-partition-0; all incoming order writes failing",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Partition leader offline for 3 partitions on broker {ip}:9092",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Temporary partition leader rebalance in progress; producers retrying writes",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Controlled leader election completed during scheduled rolling restart; no data loss",
    ),
]

RC_LDR_TRAIN = {
    "RC_TRAIN_1": "Topic partition leader unavailable or election in progress, blocking message writes in {service}.",
    "RC_TRAIN_2": "Partition leader offline or in-sync replicas insufficient on broker {ip}.",
    "RC_TRAIN_3": "Broker metadata or quorum failure preventing active partition leader assignment in {service}.",
}
ACT_LDR_TRAIN = {
    "ACT_TRAIN_1": "Investigate crashed broker node, verify network reachability, and restart broker service.",
    "ACT_TRAIN_2": "Verify replica sync state (ISR) and trigger preferred replica leader election.",
    "ACT_TRAIN_3": "Check metadata quorum health (KRaft/Zookeeper) and restore quorum connectivity.",
}

RC_LDR_VAL = {
    "RC_VAL_1": "Partition leader unavailable: broker offline and in-sync replicas insufficient for leader election on {ip}.",
}
ACT_LDR_VAL = {
    "ACT_VAL_1": "Recover failed broker instance, verify cluster controller status, and reconcile partition replica state for {service}.",
}

RC_LDR_TEST = {
    "RC_TEST_1": "Message topic partition leader offline due to broker unresponsiveness or cluster quorum loss on {ip}.",
}
ACT_LDR_TEST = {
    "ACT_TEST_1": "Restart offline broker node, verify KRaft/Zookeeper quorum connectivity, and rebalance partition leaders for {service}.",
}

RC_LDR = {**RC_LDR_TRAIN, **RC_LDR_VAL, **RC_LDR_TEST}
ACT_LDR = {**ACT_LDR_TRAIN, **ACT_LDR_VAL, **ACT_LDR_TEST}

TEMPLATES_LEADER = [
    _create_template("MSG_LDR_01", FAM_LDR, "Apache Kafka", "Java/Kafka", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] org.apache.kafka.common.errors.LeaderNotAvailableException: There is no leader for this topic-partition as leader election is in progress: [orders-0]",
            f"[{ts}] [ERROR] [{service}] Producer failed to send batch to broker {ip}:9092: NOT_ENOUGH_REPLICAS",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "LeaderNotAvailableException: There is no leader for this topic-partition",
            "NOT_ENOUGH_REPLICAS",
            impact_line,
        ], SCEN_LDR, RC_LDR, ACT_LDR, "KAFKA_LEADER_NOT_AVAILABLE"),
    _create_template("MSG_LDR_02", FAM_LDR, "Apache Kafka Broker", "Scala/Kafka", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] kafka.server: UnderReplicatedPartitions count spike: 12 partitions have no active leader on broker id={num}",
            f"[{ts}] [WARN] [{service}] ISR shrank to empty for topic payments-stream on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "UnderReplicatedPartitions count spike:",
            "partitions have no active leader on broker",
            "ISR shrank to empty",
            impact_line,
        ], SCEN_LDR, RC_LDR, ACT_LDR, "KAFKA_UNDER_REPLICATED_NO_LEADER"),
    _create_template("MSG_LDR_03", FAM_LDR, "RabbitMQ Quorum", "Erlang/RabbitMQ", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] rabbitmq[1891]: quorum queue 'orders_qq' has no active leader on node {ip}",
            f"[{ts}] [FATAL] [{service}] Raft consensus election timed out: 2 of 3 cluster nodes unresponsive",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "quorum queue 'orders_qq' has no active leader on node",
            "Raft consensus election timed out",
            impact_line,
        ], SCEN_LDR, RC_LDR, ACT_LDR, "RABBITMQ_QUORUM_NO_LEADER"),
    _create_template("MSG_LDR_04", FAM_LDR, "Python Kafka", "Python/kafka-python", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] kafka.errors.NotLeaderForPartitionError: Request sent to broker {ip} that is not the leader for [events-1]",
            f"[{ts}] [ERROR] [{service}] Metadata response: leader is -1 (leader offline)",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "NotLeaderForPartitionError: Request sent to broker",
            "leader is -1 (leader offline)",
            impact_line,
        ], SCEN_LDR, RC_LDR, ACT_LDR, "PYTHON_KAFKA_NOT_LEADER_FOR_PARTITION"),
    _create_template("MSG_LDR_05", FAM_LDR, "Apache Kafka KRaft", "Java/KRaft", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] org.apache.kafka.raft.RaftException: Lost connection to controller quorum leader on {ip}:9093",
            f"[{ts}] [ERROR] [{service}] Metadata log partition leader unavailable; cluster state updates frozen",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Lost connection to controller quorum leader on",
            "Metadata log partition leader unavailable",
            impact_line,
        ], SCEN_LDR, RC_LDR, ACT_LDR, "KRAFT_CONTROLLER_QUORUM_LOST"),
    _create_template("MSG_LDR_06", FAM_LDR, "Go Sarama", "Go/Sarama", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] sarama: kafka: error while producing message: kafka server: The leader is not available (waiting for leader election)",
            f"[{ts}] [WARN] [{service}] topic=audit partition={num} broker={ip}:9092",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "kafka server: The leader is not available (waiting for leader election)",
            impact_line,
        ], SCEN_LDR, RC_LDR, ACT_LDR, "SARAMA_LEADER_NOT_AVAILABLE"),
    _create_template("MSG_LDR_07", FAM_LDR, "Apache Pulsar", "Java/Pulsar", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] pulsar-broker[{ip}]: Failed to acquire ownership of namespace bundle 'public/default/0x00000000_0x80000000'",
            f"[{ts}] [FATAL] [{service}] Topic partitions unassigned; producer connections rejected",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Failed to acquire ownership of namespace bundle",
            "Topic partitions unassigned; producer connections rejected",
            impact_line,
        ], SCEN_LDR, RC_LDR, ACT_LDR, "PULSAR_BUNDLE_OWNERSHIP_LOST"),
    _create_template("MSG_LDR_08", FAM_LDR, "Apache Kafka Controller", "Java/Kafka", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [CRITICAL] [{service}] kafka.controller: OfflinePartitionsCount metric > 0: 4 topic partitions have no active broker leader",
            f"[{ts}] [ERROR] [{service}] Broker 101 on {ip} died unexpectedly; controller attempting failover election",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "OfflinePartitionsCount metric > 0:",
            "topic partitions have no active broker leader",
            impact_line,
        ], SCEN_LDR, RC_LDR, ACT_LDR, "KAFKA_OFFLINE_PARTITIONS_CONTROLLER"),
    _create_template("MSG_LDR_09", FAM_LDR, "Node librdkafka", "C/librdkafka", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] librdkafka: [thrd:main]: [thrd:producer]: orders [3]: Leader not available (5)",
            f"[{ts}] [FATAL] [{service}] Message delivery failed on broker {ip}:9092: ERR__LEADER_NOT_AVAILABLE",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Leader not available (5)",
            "ERR__LEADER_NOT_AVAILABLE",
            impact_line,
        ], SCEN_LDR, RC_LDR, ACT_LDR, "LIBRDKAFKA_LEADER_NOT_AVAILABLE"),
    _create_template("MSG_LDR_10", FAM_LDR, "Apache ZooKeeper", "Java/ZooKeeper", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] org.apache.zookeeper.KeeperException$SessionExpiredException: KeeperErrorCode = SessionExpired for /brokers/ids/1",
            f"[{ts}] [ERROR] [{service}] Kafka broker {ip} unregistered from Zookeeper; partitions marked leaderless",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "KeeperErrorCode = SessionExpired for /brokers/ids/",
            "unregistered from Zookeeper; partitions marked leaderless",
            impact_line,
        ], SCEN_LDR, RC_LDR, ACT_LDR, "ZOOKEEPER_SESSION_EXPIRED_LEADERLESS"),
]


# =========================================================================
# 4. MSG_POISON_PILL_FAILURE
# =========================================================================

FAM_PSN = IncidentFamily.MSG_POISON_PILL_FAILURE

SCEN_PSN = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Poison pill message crashing all consumer instances; partition processing completely frozen",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Repeated consumer crash on offset 94812 in topic checkout-stream on {service}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single poison pill message quarantined to error topic; consumer recovered",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Corrupt payload skipped by defensive deserializer filter; logged warning without consumer restart",
    ),
]

RC_PSN_TRAIN = {
    "RC_TRAIN_1": "Consumer message processing crash triggered by unhandled exception while deserializing payload in {service}.",
    "RC_TRAIN_2": "Malformed message payload causing consumer listener failure or process crash on {ip}.",
    "RC_TRAIN_3": "Consumer processing loop failure caused by unparseable message payload in {service}.",
}
ACT_PSN_TRAIN = {
    "ACT_TRAIN_1": "Identify and skip offending poison message offset; route bad payload to quarantine queue.",
    "ACT_TRAIN_2": "Add defensive parsing and schema validation around message deserializer in {service}.",
    "ACT_TRAIN_3": "Deploy hotfix catching unhandled parsing exceptions without consumer crash.",
}

RC_PSN_VAL = {
    "RC_VAL_1": "Unparseable malformed payload triggering unhandled exception in message listener on {ip}.",
}
ACT_PSN_VAL = {
    "ACT_VAL_1": "Implement defensive error boundary around deserializer and skip corrupt record offset in {service}.",
}

RC_PSN_TEST = {
    "RC_TEST_1": "Poison message decoding crash: invalid schema or corrupt byte sequence causing consumer termination on {ip}.",
}
ACT_PSN_TEST = {
    "ACT_TEST_1": "Quarantine poisoned message to dead-letter storage, update consumer deserializer schema, and resume consumption in {service}.",
}

RC_PSN = {**RC_PSN_TRAIN, **RC_PSN_VAL, **RC_PSN_TEST}
ACT_PSN = {**ACT_PSN_TRAIN, **ACT_PSN_VAL, **ACT_PSN_TEST}

TEMPLATES_POISON_PILL = [
    _create_template("MSG_PSN_01", FAM_PSN, "Apache Kafka", "Java/Jackson", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] org.apache.kafka.common.errors.SerializationException: Error deserializing key/value for partition orders-0 at offset {num*1000}",
            f"[{ts}] [FATAL] [{service}] Caused by: com.fasterxml.jackson.core.JsonParseException: Unexpected character (''') at line 1",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "SerializationException: Error deserializing key/value for partition",
            "at offset",
            impact_line,
        ], SCEN_PSN, RC_PSN, ACT_PSN, "KAFKA_JSON_PARSE_SERIALIZATION_EXCEPTION"),
    _create_template("MSG_PSN_02", FAM_PSN, "Celery", "Python/Celery", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] celery.worker.strategy: Received corrupted task message {hex_id}: UnpicklingError: invalid load key, '\\x00'",
            f"[{ts}] [ERROR] [{service}] Worker child process crashed immediately upon payload receipt on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Received corrupted task message",
            "UnpicklingError: invalid load key",
            "Worker child process crashed immediately upon payload receipt",
            impact_line,
        ], SCEN_PSN, RC_PSN, ACT_PSN, "CELERY_CORRUPTED_UNPICKLING_CRASH"),
    _create_template("MSG_PSN_03", FAM_PSN, "RabbitMQ Consumer", "Java/RabbitMQ", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] ConsumerException: Unhandled exception processing delivery tag {num}; message rejected with requeue=true",
            f"[{ts}] [WARN] [{service}] Infinite NACK re-delivery loop detected: message id {hex_id} processed 100 times without success on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Unhandled exception processing delivery tag",
            "Infinite NACK re-delivery loop detected:",
            "processed 100 times without success",
            impact_line,
        ], SCEN_PSN, RC_PSN, ACT_PSN, "RABBITMQ_NACK_LOOP_CRASH"),
    _create_template("MSG_PSN_04", FAM_PSN, "Go Sarama", "Go/Sarama", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] panic: runtime error: slice bounds out of range [:128] with capacity 12 while parsing payload offset {num*500}",
            f"[{ts}] [FATAL] [{service}] Consumer process terminated on {ip}: poisoned binary message header",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "panic: runtime error: slice bounds out of range",
            "while parsing payload offset",
            "poisoned binary message header",
            impact_line,
        ], SCEN_PSN, RC_PSN, ACT_PSN, "GO_SLICE_BOUNDS_POISON_HEADER"),
    _create_template("MSG_PSN_05", FAM_PSN, "KafkaJS", "Node.js/KafkaJS", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] KafkaJSProtocolError: Response Heartbeat(key: 12, version: 4) failed: message offset {hex_id} caused fatal unhandled JSON parse error",
            f"[{ts}] [ERROR] [{service}] Consumer group coordinator evicted crashing member {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "failed: message offset",
            "caused fatal unhandled JSON parse error",
            impact_line,
        ], SCEN_PSN, RC_PSN, ACT_PSN, "KAFKAJS_UNHANDLED_JSON_PARSE"),
    _create_template("MSG_PSN_06", FAM_PSN, "MassTransit", "C#/.NET", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] MassTransit.SerializationException: An error occurred while deserializing the message envelope",
            f"[{ts}] [ERROR] [{service}] Inner: System.FormatException: The string '{hex_id}' was not recognized as a valid DateTime on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "MassTransit.SerializationException: An error occurred while deserializing the message envelope",
            "was not recognized as a valid DateTime on",
            impact_line,
        ], SCEN_PSN, RC_PSN, ACT_PSN, "MASSTRANSIT_SERIALIZATION_FORMAT_ERROR"),
    _create_template("MSG_PSN_07", FAM_PSN, "AWS SQS Boto3", "Python/Boto3", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)",
            f"[{ts}] [ERROR] [{service}] SQS message {hex_id} contains raw binary garbage instead of JSON string on {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "json.decoder.JSONDecodeError: Expecting value: line 1 column 1",
            "contains raw binary garbage instead of JSON string",
            impact_line,
        ], SCEN_PSN, RC_PSN, ACT_PSN, "SQS_JSON_DECODE_BINARY_GARBAGE"),
    _create_template("MSG_PSN_08", FAM_PSN, "Spring Kafka", "Java/Spring", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] org.springframework.kafka.listener.ListenerExecutionFailedException: Listener failed; nested exception is java.lang.IllegalArgumentException: Invalid transaction code",
            f"[{ts}] [ERROR] [{service}] KafkaListenerContainer crashed; partition assignment revoked on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ListenerExecutionFailedException: Listener failed; nested exception is java.lang.IllegalArgumentException",
            "KafkaListenerContainer crashed; partition assignment revoked",
            impact_line,
        ], SCEN_PSN, RC_PSN, ACT_PSN, "SPRING_KAFKA_LISTENER_POISON_EXCEPTION"),
    _create_template("MSG_PSN_09", FAM_PSN, "Apache Avro", "Java/Avro", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] io.confluent.kafka.serializers.KafkaAvroDeserializer: Error deserializing Avro message for id {num}: schema id 9981 not found in registry",
            f"[{ts}] [FATAL] [{service}] Consumer blocked on unparseable message at offset {hex_id} on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Error deserializing Avro message for id",
            "schema id",
            "not found in registry",
            "Consumer blocked on unparseable message",
            impact_line,
        ], SCEN_PSN, RC_PSN, ACT_PSN, "AVRO_SCHEMA_REGISTRY_MISSING"),
    _create_template("MSG_PSN_10", FAM_PSN, "Ruby Shoryuken", "Ruby/Shoryuken", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] Shoryuken::Errors::WorkerError: Processor crashed while handling SQS message {hex_id}: ArgumentError: invalid UTF-8 byte sequence",
            f"[{ts}] [ERROR] [{service}] Worker worker-1 exited with failure status on host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Shoryuken::Errors::WorkerError: Processor crashed while handling SQS message",
            "ArgumentError: invalid UTF-8 byte sequence",
            impact_line,
        ], SCEN_PSN, RC_PSN, ACT_PSN, "SHORYUKEN_INVALID_UTF8_BYTE_SEQUENCE"),
]


# =========================================================================
# 5. MSG_QUEUE_STORAGE_BACKPRESSURE
# =========================================================================

FAM_BKP = IncidentFamily.MSG_QUEUE_STORAGE_BACKPRESSURE

SCEN_BKP = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Message broker out of storage; all publisher writes blocked across {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Broker memory/storage threshold exceeded on {ip}; incoming message publishing throttled",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Broker disk utilization at 85%; retention cleanup running to reclaim space",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Storage watermark warning cleared after automated topic compaction on {ip}; zero publishers blocked",
    ),
]

RC_BKP_TRAIN = {
    "RC_TRAIN_1": "Message broker storage volume or memory capacity saturated, triggering publisher backpressure in {service}.",
    "RC_TRAIN_2": "Broker storage watermark alarm triggered, throttling incoming producer connections on {ip}.",
    "RC_TRAIN_3": "Broker commit log storage exhaustion forcing message ingestion halt on {ip}.",
}
ACT_BKP_TRAIN = {
    "ACT_TRAIN_1": "Expand message broker volume storage and decrease log segment retention hours.",
    "ACT_TRAIN_2": "Clear unneeded message queues, enable topic compaction, and adjust broker high watermark memory threshold.",
    "ACT_TRAIN_3": "Enable topic log compaction and clean up expired segment files in broker storage.",
}

RC_BKP_VAL = {
    "RC_VAL_1": "Queue storage or message payload size limit breached, causing broker publisher flow control to pause writes on {ip}.",
}
ACT_BKP_VAL = {
    "ACT_VAL_1": "Increase broker disk quota, prune obsolete topic partitions, and adjust maximum request payload size in {service}.",
}

RC_BKP_TEST = {
    "RC_TEST_1": "Broker storage limit reached: volume disk utilization at capacity, halting incoming publisher append operations on {ip}.",
}
ACT_BKP_TEST = {
    "ACT_TEST_1": "Expand broker disk volume, shorten log retention policy, and verify storage alarms for {service}.",
}

RC_BKP = {**RC_BKP_TRAIN, **RC_BKP_VAL, **RC_BKP_TEST}
ACT_BKP = {**ACT_BKP_TRAIN, **ACT_BKP_VAL, **ACT_BKP_TEST}

TEMPLATES_BACKPRESSURE = [
    _create_template("MSG_BKP_01", FAM_BKP, "RabbitMQ", "Erlang/RabbitMQ", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] rabbitmq[1024]: vm_memory_high_watermark set. Memory alarm triggered! Total memory usage: {num*100}MB (limit: 4096MB) on node {ip}",
            f"[{ts}] [ERROR] [{service}] All publishers blocked. connection.blocked sent to client channels",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "vm_memory_high_watermark set. Memory alarm triggered!",
            "All publishers blocked. connection.blocked sent to client channels",
            impact_line,
        ], SCEN_BKP, RC_BKP, ACT_BKP, "RABBITMQ_VM_MEMORY_ALARM"),
    _create_template("MSG_BKP_02", FAM_BKP, "Apache Kafka Broker", "Java/Kafka", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] kafka.log.Log: KafkaStorageException: Log directory /var/lib/kafka/data is full: No space left on device",
            f"[{ts}] [ERROR] [{service}] Broker {ip}:9092 shutting down log append operations for all topics",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "KafkaStorageException: Log directory /var/lib/kafka/data is full: No space left on device",
            "shutting down log append operations for all topics",
            impact_line,
        ], SCEN_BKP, RC_BKP, ACT_BKP, "KAFKA_STORAGE_DISK_FULL"),
    _create_template("MSG_BKP_03", FAM_BKP, "RabbitMQ", "Erlang/RabbitMQ", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] rabbitmq: disk_free_limit alarm triggered: available free disk 48MB is below threshold 500MB on {ip}",
            f"[{ts}] [WARN] [{service}] Blocking 24 active AMQP connections from publishing messages",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "disk_free_limit alarm triggered: available free disk",
            "Blocking 24 active AMQP connections from publishing messages",
            impact_line,
        ], SCEN_BKP, RC_BKP, ACT_BKP, "RABBITMQ_DISK_FREE_LIMIT_ALARM"),
    _create_template("MSG_BKP_04", FAM_BKP, "Apache ActiveMQ", "Java/ActiveMQ", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] org.apache.activemq.broker.region.virtual.VirtualTopic: Store limit reached! 100% of 20GB disk storage used on {ip}",
            f"[{ts}] [FATAL] [{service}] Producer flow control activated: senders blocked waiting for consumer dequeue",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Store limit reached! 100% of 20GB disk storage used",
            "Producer flow control activated: senders blocked",
            impact_line,
        ], SCEN_BKP, RC_BKP, ACT_BKP, "ACTIVEMQ_STORE_LIMIT_REACHED"),
    _create_template("MSG_BKP_05", FAM_BKP, "Redis Streams", "C/Redis", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] redis-server: OOM command not allowed when used memory > 'maxmemory' (limit: {num*10}MB) on {ip}:6379",
            f"[{ts}] [WARN] [{service}] Redis Streams XADD command rejected: memory quota reached",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "OOM command not allowed when used memory > 'maxmemory'",
            "Redis Streams XADD command rejected",
            impact_line,
        ], SCEN_BKP, RC_BKP, ACT_BKP, "REDIS_MAXMEMORY_XADD_REJECTED"),
    _create_template("MSG_BKP_06", FAM_BKP, "Apache Pulsar", "Java/Pulsar", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] pulsar-broker[{ip}]: Backlog quota exceeded on namespace public/default: limit 50GB breached",
            f"[{ts}] [FATAL] [{service}] Backlog quota retention policy 'producer_exception' triggered: producers blocked from publishing",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Backlog quota exceeded on namespace",
            "producers blocked from publishing",
            impact_line,
        ], SCEN_BKP, RC_BKP, ACT_BKP, "PULSAR_BACKLOG_QUOTA_BREACH"),
    _create_template("MSG_BKP_07", FAM_BKP, "Apache Kafka Client", "Java/Kafka", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] org.apache.kafka.common.errors.RecordTooLargeException: The message is 15728640 bytes when serialized which is larger than the maximum request size you have configured with the max.request.size configuration (10485760 bytes)",
            f"[{ts}] [ERROR] [{service}] Producer buffer full on broker {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "RecordTooLargeException: The message is",
            "larger than the maximum request size",
            impact_line,
        ], SCEN_BKP, RC_BKP, ACT_BKP, "KAFKA_RECORD_TOO_LARGE_BACKPRESSURE"),
    _create_template("MSG_BKP_08", FAM_BKP, "NSQ", "Go/NSQ", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] nsqd[{ip}]: diskqueue(orders) write failed: disk quota full in /var/lib/nsq",
            f"[{ts}] [ERROR] [{service}] Publisher TCP connections paused to prevent data loss on channel {hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "diskqueue(orders) write failed: disk quota full",
            "Publisher TCP connections paused to prevent data loss",
            impact_line,
        ], SCEN_BKP, RC_BKP, ACT_BKP, "NSQ_DISKQUEUE_QUOTA_FULL"),
    _create_template("MSG_BKP_09", FAM_BKP, "NATS JetStream", "Go/NATS", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] nats-server[{ip}]: jetstream: stream 'ORDERS' storage limit reached: 50GB used of 50GB allocated",
            f"[{ts}] [FATAL] [{service}] JS error: 10077: stream storage limit reached: publishes rejected for {service}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "stream 'ORDERS' storage limit reached",
            "JS error: 10077: stream storage limit reached: publishes rejected",
            impact_line,
        ], SCEN_BKP, RC_BKP, ACT_BKP, "NATS_JETSTREAM_STORAGE_LIMIT"),
    _create_template("MSG_BKP_10", FAM_BKP, "AWS MSK", "AWS/CloudWatch", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] cloudwatch: KafkaDataVolumeUsedPercentage exceeds 95% on cluster msk-prod-{hex_id} node {ip}",
            f"[{ts}] [FATAL] [{service}] Kafka broker broker-{num} rejecting producer writes to avoid disk saturation",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "KafkaDataVolumeUsedPercentage exceeds 95%",
            "rejecting producer writes to avoid disk saturation",
            impact_line,
        ], SCEN_BKP, RC_BKP, ACT_BKP, "AWS_MSK_DATA_VOLUME_USED_ALERT"),
]


# =========================================================================
# 6. MSG_DUPLICATE_DELIVERY_OR_IDEMPOTENCY
# =========================================================================

FAM_IDM = IncidentFamily.MSG_DUPLICATE_DELIVERY_OR_IDEMPOTENCY

SCEN_IDM = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Duplicate credit card charges processed due to message redelivery loop in {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Duplicate delivery detected: 320 redelivered messages processed twice on {ip}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Idempotency filter caught and skipped duplicate message id; no business impact",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Duplicate event payload safely dropped by deduplication table filter; zero duplicate side-effects",
    ),
]

RC_IDM_TRAIN = {
    "RC_TRAIN_1": "Message re-delivery or consumer commit failure resulting in duplicate message processing in {service}.",
    "RC_TRAIN_2": "Consumer offset commit failure or rebalance triggering at-least-once message redelivery on {ip}.",
    "RC_TRAIN_3": "Duplicate event execution due to re-delivered message processing in consumer for {service}.",
}
ACT_IDM_TRAIN = {
    "ACT_TRAIN_1": "Increase max.poll.interval.ms, implement transactional idempotency key checking in {service}.",
    "ACT_TRAIN_2": "Enforce database unique constraint on message idempotency key and commit offsets asynchronously.",
    "ACT_TRAIN_3": "Audit consumer transaction boundary and enable Kafka idempotent producer (enable.idempotence=true).",
}

RC_IDM_VAL = {
    "RC_VAL_1": "Message acknowledgment timeout expired, causing broker redelivery of already processed batch on {ip}.",
}
ACT_IDM_VAL = {
    "ACT_VAL_1": "Tune message acknowledgment visibility window and enforce deduplication cache lookup in {service}.",
}

RC_IDM_TEST = {
    "RC_TEST_1": "At-least-once message redelivery leading to duplicate database records due to missing idempotency checks on {ip}.",
}
ACT_IDM_TEST = {
    "ACT_TEST_1": "Enable idempotent producer mode, persist processed message IDs in deduplication store, and commit offsets atomically for {service}.",
}

RC_IDM = {**RC_IDM_TRAIN, **RC_IDM_VAL, **RC_IDM_TEST}
ACT_IDM = {**ACT_IDM_TRAIN, **ACT_IDM_VAL, **ACT_IDM_TEST}

TEMPLATES_IDEMPOTENCY = [
    _create_template("MSG_IDM_01", FAM_IDM, "Apache Kafka Consumer", "Java/Kafka", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] org.apache.kafka.clients.consumer.CommitFailedException: Commit cannot be completed since the group has already rebalanced and assigned the partitions to another member",
            f"[{ts}] [WARN] [{service}] Message offset {num*500} will be re-processed by another consumer (potential duplicate delivery)",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "CommitFailedException: Commit cannot be completed since the group has already rebalanced",
            "will be re-processed by another consumer (potential duplicate delivery)",
            impact_line,
        ], SCEN_IDM, RC_IDM, ACT_IDM, "KAFKA_COMMIT_FAILED_REBALANCE"),
    _create_template("MSG_IDM_02", FAM_IDM, "FastAPI / PostgreSQL", "Python/SQLAlchemy", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] IntegrityError: duplicate key value violates unique constraint \"idx_orders_idempotency_key\"",
            f"[{ts}] [WARN] [{service}] Duplicate message delivery detected for transaction id {hex_id} from {ip}: message already processed",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "IntegrityError: duplicate key value violates unique constraint \"idx_orders_idempotency_key\"",
            "Duplicate message delivery detected for transaction id",
            impact_line,
        ], SCEN_IDM, RC_IDM, ACT_IDM, "SQL_UNIQUE_IDEMPOTENCY_VIOLATION"),
    _create_template("MSG_IDM_03", FAM_IDM, "Apache Kafka Consumer", "Java/Kafka", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] org.apache.kafka.clients.consumer.internals.ConsumerCoordinator: consumer poll timeout has expired. This means the time between subsequent calls to poll() was longer than the configured max.poll.interval.ms (300000ms)",
            f"[{ts}] [WARN] [{service}] Member {service}-{hex_id} left group; uncommitted messages will redeliver",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "was longer than the configured max.poll.interval.ms",
            "uncommitted messages will redeliver",
            impact_line,
        ], SCEN_IDM, RC_IDM, ACT_IDM, "KAFKA_MAX_POLL_INTERVAL_EXPIRED"),
    _create_template("MSG_IDM_04", FAM_IDM, "RabbitMQ Consumer", "Python/Pika", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] rabbitmq-consumer: Received message with redelivered=true (delivery_tag: {num}) from node {ip}",
            f"[{ts}] [ERROR] [{service}] IdempotencyCheck: Order '{hex_id}' already processed in database; duplicate processing averted",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Received message with redelivered=true",
            "already processed in database; duplicate processing averted",
            impact_line,
        ], SCEN_IDM, RC_IDM, ACT_IDM, "RABBITMQ_REDELIVERED_FLAG_DETECTED"),
    _create_template("MSG_IDM_05", FAM_IDM, "AWS SQS Consumer", "Python/Boto3", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] sqs-listener: Message visibility timeout (30s) expired before handler finished processing task id={hex_id}",
            f"[{ts}] [ERROR] [{service}] SQS re-delivered message to worker 2 on {ip}; concurrent duplicate execution started",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Message visibility timeout (30s) expired before handler finished processing",
            "concurrent duplicate execution started",
            impact_line,
        ], SCEN_IDM, RC_IDM, ACT_IDM, "SQS_VISIBILITY_TIMEOUT_DUPLICATE"),
    _create_template("MSG_IDM_06", FAM_IDM, "Go Sarama", "Go/Sarama", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] sarama: rebalance in progress: partition [orders-1] claimed by another worker",
            f"[{ts}] [WARN] [{service}] At-least-once delivery: message offset {num*200} dispatched twice on host {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "rebalance in progress: partition",
            "At-least-once delivery: message offset",
            "dispatched twice on host",
            impact_line,
        ], SCEN_IDM, RC_IDM, ACT_IDM, "SARAMA_REBALANCE_DUPLICATE_DELIVERY"),
    _create_template("MSG_IDM_07", FAM_IDM, "Apache Pulsar Consumer", "Java/Pulsar", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] pulsar-consumer[{ip}]: Ack timeout expired for message {hex_id}; triggering negative acknowledgment",
            f"[{ts}] [ERROR] [{service}] Message redelivery triggered for un-acked batch; checking idempotency table",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Ack timeout expired for message",
            "triggering negative acknowledgment",
            "Message redelivery triggered for un-acked batch",
            impact_line,
        ], SCEN_IDM, RC_IDM, ACT_IDM, "PULSAR_ACK_TIMEOUT_REDELIVERY"),
    _create_template("MSG_IDM_08", FAM_IDM, "Celery Redis", "Python/Celery", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num, prev_exec_ts="", **kwargs: [
            f"[{ts}] [WARN] [{service}] celery.app.trace: Task send_invoice[{hex_id}] was already executed at {prev_exec_ts or '2026-09-14T09:12:00Z'}",
            f"[{ts}] [ERROR] [{service}] Redis broker ack loss caused duplicate task delivery to worker on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "was already executed at",
            "Redis broker ack loss caused duplicate task delivery to worker",
            impact_line,
        ], SCEN_IDM, RC_IDM, ACT_IDM,
        signature_profile="CELERY_REDIS_ACK_LOSS_DUPLICATE",
        failure_mechanism="DUPLICATE_DELIVERY_ACK_LOSS",
        expected_tokens=["celery.app.trace: Task", "duplicate task delivery"],
        forbidden_tokens=["partition rebalance", "JetStream"]),
    _create_template("MSG_IDM_09", FAM_IDM, "Apache Kafka Producer", "Java/Kafka", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] ProducerConfig enable.idempotence=false: transient network disconnect on broker {ip}:9092 caused duplicate batch append",
            f"[{ts}] [FATAL] [{service}] Duplicate financial transactions created on partition ledger-0 at offset {num*1000}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ProducerConfig enable.idempotence=false: transient network disconnect",
            "caused duplicate batch append",
            "Duplicate financial transactions created",
            impact_line,
        ], SCEN_IDM, RC_IDM, ACT_IDM, "KAFKA_NON_IDEMPOTENT_RETRY_DUPLICATE"),
    _create_template("MSG_IDM_10", FAM_IDM, "Redis Streams", "Go/Redis", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] redis-streams: XACK failed due to connection reset to {ip}:6379; message {hex_id} remaining in PEL",
            f"[{ts}] [WARN] [{service}] Autoclaim worker re-read message; duplicate downstream webhook dispatched",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "XACK failed due to connection reset to",
            "remaining in PEL",
            "Autoclaim worker re-read message; duplicate downstream webhook dispatched",
            impact_line,
        ], SCEN_IDM, RC_IDM, ACT_IDM, "REDIS_STREAMS_XACK_LOST_DUPLICATE"),
]


MESSAGING_TEMPLATES: list[LogTemplate] = (
    TEMPLATES_LAG +
    TEMPLATES_DLQ +
    TEMPLATES_LEADER +
    TEMPLATES_POISON_PILL +
    TEMPLATES_BACKPRESSURE +
    TEMPLATES_IDEMPOTENCY
)

assert len(MESSAGING_TEMPLATES) == 60, f"Expected 60 templates in MESSAGING, got {len(MESSAGING_TEMPLATES)}"
