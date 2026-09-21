"""Structural log templates for the NETWORK category (6 families, 60 templates).

Each family defines 10 templates: 6 TRAIN, 2 VALIDATION, 2 TEST.
Includes P4_LOW coverage, normalized metadata, strictly isolated TLS failure signatures,
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
    IncidentFamily.NET_DNS_RESOLUTION_FAILURE: (
        "Domain name resolution failure preventing target host lookup and connection establishment"
    ),
    IncidentFamily.NET_CONNECTION_REFUSED: (
        "TCP connection refused by destination host or port on target socket"
    ),
    IncidentFamily.NET_SOCKET_TIMEOUT: (
        "Network socket or connection read timeout awaiting response bytes from downstream host"
    ),
    IncidentFamily.NET_TLS_HANDSHAKE_FAILURE: (
        "TLS/SSL handshake negotiation failure during secure connection establishment"
    ),
    IncidentFamily.NET_INGRESS_GATEWAY_TIMEOUT: (
        "Ingress proxy or gateway received upstream failure or response timeout"
    ),
    IncidentFamily.NET_PARTITION_OR_BLACKHOLE: (
        "Network packet loss, routing black hole, or partition disrupting host connectivity"
    ),
}

FAMILY_HYPOTHESES_MAP = {
    IncidentFamily.NET_DNS_RESOLUTION_FAILURE: [
        "CoreDNS crash",
        "upstream DNS timeout",
        "misconfigured ndots",
        "missing DNS record",
        "ENI rate throttling",
    ],
    IncidentFamily.NET_CONNECTION_REFUSED: [
        "daemon crashed",
        "service bound to localhost",
        "pod unready",
        "port closed",
    ],
    IncidentFamily.NET_SOCKET_TIMEOUT: [
        "downstream slow query",
        "packet drops",
        "thread pool saturation",
        "unindexed remote query",
    ],
    IncidentFamily.NET_TLS_HANDSHAKE_FAILURE: [
        "certificate expired",
        "cipher mismatch",
        "missing client certificate",
        "untrusted root CA",
        "unsupported TLS version",
    ],
    IncidentFamily.NET_INGRESS_GATEWAY_TIMEOUT: [
        "upstream container crash",
        "backend GC pause",
        "upstream database bottleneck",
        "target timeout elapsed",
    ],
    IncidentFamily.NET_PARTITION_OR_BLACKHOLE: [
        "PMTU black hole",
        "conntrack table full",
        "BGP flap",
        "split brain",
        "transit gateway detachment",
    ],
}


# =========================================================================
# 1. NET_DNS_RESOLUTION_FAILURE
# =========================================================================

FAM_DNS = IncidentFamily.NET_DNS_RESOLUTION_FAILURE

SCEN_DNS = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Complete DNS outage across cluster; services unable to resolve database or auth hosts",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: DNS lookup failures on payment-gateway.production.svc:53 from {ip}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Intermittent DNS query retry on external analytics host; auto-recovered",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Single transient DNS lookup retry on internal metrics endpoint; resolved on first retry with 0 dropped packets",
    ),
]

RC_DNS_TRAIN = {
    "RC_TRAIN_1": "DNS resolution failure: resolver unable to resolve downstream dependency hostname in {service}.",
    "RC_TRAIN_2": "Domain name resolution error: target host lookup returned NXDOMAIN or failed to resolve from {ip}.",
    "RC_TRAIN_3": "DNS query timeout or failure resolving downstream service address in {service}.",
}
ACT_DNS_TRAIN = {
    "ACT_TRAIN_1": "Check CoreDNS pod status and autoscaling; verify service discovery hostname in {service}.",
    "ACT_TRAIN_2": "Verify downstream Kubernetes Service name, upstream nameserver connectivity, and kube-dns endpoints.",
    "ACT_TRAIN_3": "Inspect /etc/resolv.conf search domains, ndots configuration, and restart NodeLocal DNSCache daemonset.",
}

RC_DNS_VAL = {
    "RC_VAL_1": "Service discovery DNS query failure: target domain lookup returned NXDOMAIN or failed to resolve on {ip}.",
}
ACT_DNS_VAL = {
    "ACT_VAL_1": "Validate internal cluster DNS zone configuration and inspect DNS upstream forwarding rules in {service}.",
}

RC_DNS_TEST = {
    "RC_TEST_1": "DNS resolver timeout or upstream failure preventing target hostname resolution on {ip}.",
}
ACT_DNS_TEST = {
    "ACT_TEST_1": "Inspect local DNS resolver health, check upstream nameservers, and verify domain record existence for {service}.",
}

RC_DNS = {**RC_DNS_TRAIN, **RC_DNS_VAL, **RC_DNS_TEST}
ACT_DNS = {**ACT_DNS_TRAIN, **ACT_DNS_VAL, **ACT_DNS_TEST}

TEMPLATES_DNS = [
    _create_template("NET_DNS_01", FAM_DNS, "CoreDNS", "Go/CoreDNS", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] coredns[{ip}]: [ERROR] plugin/errors: 2 auth.production.svc.cluster.local. A: read udp 10.244.0.1:53: i/o timeout",
            f"[{ts}] [ERROR] [{service}] java.net.UnknownHostException: auth.production.svc.cluster.local: Name or service not known",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "plugin/errors: 2 auth.production.svc.cluster.local. A: read udp",
            "UnknownHostException: auth.production.svc.cluster.local: Name or service not known",
            impact_line,
        ], SCEN_DNS, RC_DNS, ACT_DNS, "COREDNS_UDP_TIMEOUT"),
    _create_template("NET_DNS_02", FAM_DNS, "Python Requests", "Python", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] urllib3.exceptions.MaxRetryError: HTTPSConnectionPool(host='api.internal.example.com', port=443): Max retries exceeded with url: /v1/billing (Caused by NewConnectionError('<urllib3.connection.HTTPSConnection object>: Failed to establish a new connection: [Errno -2] Name or service not known'))",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Failed to establish a new connection: [Errno -2] Name or service not known",
            "HTTPSConnectionPool(host='api.internal.example.com', port=443)",
            impact_line,
        ], SCEN_DNS, RC_DNS, ACT_DNS, "PYTHON_GETADDRINFO_UNKNOWN_HOST"),
    _create_template("NET_DNS_03", FAM_DNS, "Go net", "Go", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] dial tcp: lookup db-primary.production.svc on {ip}:53: no such host",
            f"[{ts}] [FATAL] [{service}] net.OpError: dns lookup failed for database target host",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "dial tcp: lookup db-primary.production.svc on",
            "no such host",
            impact_line,
        ], SCEN_DNS, RC_DNS, ACT_DNS, "GO_NET_LOOKUP_NO_SUCH_HOST"),
    _create_template("NET_DNS_04", FAM_DNS, "Node.js dns", "Node.js", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Error: getaddrinfo ENOTFOUND redis.internal.cache",
            f"[{ts}] [ERROR] [{service}] at GetAddrInfoReqWrap.onlookup [as oncomplete] (dns.js:{num}:26) on host {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Error: getaddrinfo ENOTFOUND redis.internal.cache",
            "onlookup [as oncomplete]",
            impact_line,
        ], SCEN_DNS, RC_DNS, ACT_DNS, "NODE_GETADDRINFO_ENOTFOUND"),
    _create_template("NET_DNS_05", FAM_DNS, "Kubernetes NodeLocal DNS", "Go/k8s", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] node-local-dns[{ip}]: [ERROR] plugin/forward: no upstream nameserver responded to query for 'orders-service.default.svc.cluster.local.'",
            f"[{ts}] [WARN] [{service}] Client request failed after {num*100}ms DNS timeout",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "node-local-dns",
            "no upstream nameserver responded to query",
            impact_line,
        ], SCEN_DNS, RC_DNS, ACT_DNS, "NODELOCAL_DNS_NO_UPSTREAM"),
    _create_template("NET_DNS_06", FAM_DNS, "Linux glibc", "C/glibc", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] resolver[5812]: res_query failed for inventory.internal: errno=110 Connection timed out to nameserver {ip}:53",
            f"[{ts}] [FATAL] [{service}] glibc getaddrinfo timed out: ndots:5 excessive search domain iterations",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "res_query failed for inventory.internal: errno=110 Connection timed out",
            "glibc getaddrinfo timed out: ndots:5",
            impact_line,
        ], SCEN_DNS, RC_DNS, ACT_DNS, "GLIBC_RESOLVER_TIMEOUT"),
    _create_template("NET_DNS_07", FAM_DNS, "Bind9 DNS", "C/Bind9", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] named[1092]: client @{ip} 10.244.1.25#51920 (kafka.service.internal): query failed (SERVFAIL) for kafka.service.internal/IN/A",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "named[1092]: client",
            "query failed (SERVFAIL) for kafka.service.internal/IN/A",
            impact_line,
        ], SCEN_DNS, RC_DNS, ACT_DNS, "BIND9_QUERY_SERVFAIL"),
    _create_template("NET_DNS_08", FAM_DNS, "Consul DNS", "Go/Consul", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] consul: [WARN] dns: rpc error: service 'payment-processor' does not exist in datacenter 'dc1' on {ip}:8600",
            f"[{ts}] [ERROR] [{service}] DNS lookup for payment-processor.service.consul returned NXDOMAIN",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "service 'payment-processor' does not exist in datacenter",
            "returned NXDOMAIN",
            impact_line,
        ], SCEN_DNS, RC_DNS, ACT_DNS, "CONSUL_DNS_NXDOMAIN"),
    _create_template("NET_DNS_09", FAM_DNS, "AWS Route53", "AWS/Route53", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] amazon-route53: Packet dropped: exceeded 1024 packets-per-second per ENI limit to VPC DNS server 10.0.0.2:53",
            f"[{ts}] [ERROR] [{service}] DNS query timeout: lookup failed for s3.us-east-1.amazonaws.com on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "exceeded 1024 packets-per-second per ENI limit to VPC DNS server",
            "DNS query timeout: lookup failed for",
            impact_line,
        ], SCEN_DNS, RC_DNS, ACT_DNS, "ROUTE53_ENI_PPS_THROTTLE"),
    _create_template("NET_DNS_10", FAM_DNS, "Unbound DNS", "C/Unbound", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] unbound: [8412:0] error: response for db.cluster.local. has bad answer: SERVFAIL from upstream root servers",
            f"[{ts}] [FATAL] [{service}] Local caching resolver failed: client {ip} received DNS RCODE 2 (Server failure)",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "unbound:",
            "has bad answer: SERVFAIL from upstream root servers",
            "received DNS RCODE 2 (Server failure)",
            impact_line,
        ], SCEN_DNS, RC_DNS, ACT_DNS, "UNBOUND_UPSTREAM_SERVFAIL"),
]


# =========================================================================
# 2. NET_CONNECTION_REFUSED
# =========================================================================

FAM_REF = IncidentFamily.NET_CONNECTION_REFUSED

SCEN_REF = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Target auth service completely offline on {ip}:8080; all inbound connections refused",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Connection refused to redis cache cluster on {ip}:6379; throughput degraded",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Temporary connection refused during rolling pod restart; traffic shifted to healthy replica",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Connection refused on optional telemetry probe port; primary request flow completely unaffected",
    ),
]

RC_REF_TRAIN = {
    "RC_TRAIN_1": "TCP connection refused: target host on {ip} rejected connection on destination port.",
    "RC_TRAIN_2": "Connection refused (ECONNREFUSED) attempting to reach downstream service socket on {ip}.",
    "RC_TRAIN_3": "Downstream endpoint connection refused on target port, indicating no listener active on {ip}.",
}
ACT_REF_TRAIN = {
    "ACT_TRAIN_1": "Verify target container process status, listening ports (netstat/ss), and readiness probes.",
    "ACT_TRAIN_2": "Check if service is bound to 0.0.0.0 rather than localhost and verify container port mapping in Kubernetes Service.",
    "ACT_TRAIN_3": "Restart target service on {ip} and verify endpoint registration in cluster routing tables.",
}

RC_REF_VAL = {
    "RC_VAL_1": "TCP connection refused: target port closed or server daemon not accepting connections on {ip}.",
}
ACT_REF_VAL = {
    "ACT_VAL_1": "Confirm downstream process health, inspect container logs, and verify port allocation on {ip}.",
}

RC_REF_TEST = {
    "RC_TEST_1": "Downstream endpoint process not accepting connections on destination socket {ip}.",
}
ACT_REF_TEST = {
    "ACT_TEST_1": "Inspect downstream process lifecycle, restart failing pod, and check service port definitions for {service}.",
}

RC_REF = {**RC_REF_TRAIN, **RC_REF_VAL, **RC_REF_TEST}
ACT_REF = {**ACT_REF_TRAIN, **ACT_REF_VAL, **ACT_REF_TEST}

TEMPLATES_CONN_REFUSED = [
    _create_template("NET_REF_01", FAM_REF, "Java Socket", "Java", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] java.net.ConnectException: Connection refused (Connection refused) to host {ip}:8080",
            f"[{ts}] [ERROR] [{service}] Failed to connect to downstream user-service: socket connect failed",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "java.net.ConnectException: Connection refused (Connection refused)",
            "Failed to connect to downstream",
            impact_line,
        ], SCEN_REF, RC_REF, ACT_REF, "JAVA_CONNECT_EXCEPTION_REFUSED"),
    _create_template("NET_REF_02", FAM_REF, "Python Requests", "Python", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] requests.exceptions.ConnectionError: HTTPConnectionPool(host='{ip}', port=5432): Max retries exceeded with url: / (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object>: Failed to establish a new connection: [Errno 111] Connection refused'))",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Failed to establish a new connection: [Errno 111] Connection refused",
            impact_line,
        ], SCEN_REF, RC_REF, ACT_REF, "PYTHON_ECONNREFUSED_5432"),
    _create_template("NET_REF_03", FAM_REF, "Node.js net", "Node.js", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Error: connect ECONNREFUSED {ip}:9200",
            f"[{ts}] [ERROR] [{service}] at TCPConnectWrap.afterConnect [as oncomplete] (net.js:{num}:14) while reaching Elasticsearch",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Error: connect ECONNREFUSED",
            "at TCPConnectWrap.afterConnect",
            impact_line,
        ], SCEN_REF, RC_REF, ACT_REF, "NODE_ECONNREFUSED_9200"),
    _create_template("NET_REF_04", FAM_REF, "Go net", "Go", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] dial tcp {ip}:6379: connect: connection refused",
            f"[{ts}] [FATAL] [{service}] Redis client failed connecting to cache node {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "dial tcp",
            "connect: connection refused",
            impact_line,
        ], SCEN_REF, RC_REF, ACT_REF, "GO_DIAL_TCP_REFUSED"),
    _create_template("NET_REF_05", FAM_REF, "cURL", "C/curl", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] curl: (7) Failed to connect to {ip} port 8000: Connection refused",
            f"[{ts}] [WARN] [{service}] Ingress healthcheck probe failed against local port 8000",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "curl: (7) Failed to connect to",
            "Connection refused",
            impact_line,
        ], SCEN_REF, RC_REF, ACT_REF, "CURL_7_CONNECT_REFUSED"),
    _create_template("NET_REF_06", FAM_REF, "PostgreSQL Client", "C/libpq", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] psycopg2.OperationalError: could not connect to server: Connection refused\n\tIs the server running on host \"{ip}\" and accepting\n\tTCP/IP connections on port 5432?",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "could not connect to server: Connection refused",
            "accepting\n\tTCP/IP connections on port 5432?",
            impact_line,
        ], SCEN_REF, RC_REF, ACT_REF, "PSYCOPG2_CONNECTION_REFUSED"),
    _create_template("NET_REF_07", FAM_REF, "Nginx Reverse Proxy", "C/Nginx", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] nginx: [error] 1409#0: *{num} connect() failed (111: Connection refused) while connecting to upstream, client: 10.244.0.12, server: api.example.com, request: \"POST /api/v1/orders HTTP/1.1\", upstream: \"http://{ip}:3000/api/v1/orders\"",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "connect() failed (111: Connection refused) while connecting to upstream",
            "upstream: \"http://",
            impact_line,
        ], SCEN_REF, RC_REF, ACT_REF, "NGINX_CONNECT_REFUSED_111"),
    _create_template("NET_REF_08", FAM_REF, "DotNet HttpClient", "C#/.NET", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] System.Net.Http.HttpRequestException: Connection refused (127.0.0.1:5000)",
            f"[{ts}] [ERROR] [{service}] ---> System.Net.Sockets.SocketException (111): Connection refused on {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "System.Net.Http.HttpRequestException: Connection refused",
            "SocketException (111): Connection refused on",
            impact_line,
        ], SCEN_REF, RC_REF, ACT_REF, "DOTNET_HTTP_CONNECT_REFUSED"),
    _create_template("NET_REF_09", FAM_REF, "gRPC Client", "Go/gRPC", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] rpc error: code = Unavailable desc = connection error: desc = \"transport: Error while dialing dial tcp {ip}:9090: connect: connection refused\"",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "rpc error: code = Unavailable desc = connection error: desc = \"transport: Error while dialing dial tcp",
            "connect: connection refused\"",
            impact_line,
        ], SCEN_REF, RC_REF, ACT_REF, "GRPC_UNAVAILABLE_CONNECT_REFUSED"),
    _create_template("NET_REF_10", FAM_REF, "Ruby TCPSocket", "Ruby", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Errno::ECONNREFUSED (Connection refused - connect(2) for \"{ip}\" port 443):",
            f"[{ts}] [WARN] [{service}] Faraday::ConnectionFailed: Connection refused to payment service",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Errno::ECONNREFUSED (Connection refused - connect(2)",
            impact_line,
        ], SCEN_REF, RC_REF, ACT_REF, "RUBY_ECONNREFUSED_443"),
]


# =========================================================================
# 3. NET_SOCKET_TIMEOUT
# =========================================================================

FAM_TIM = IncidentFamily.NET_SOCKET_TIMEOUT

SCEN_TIM = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Downstream payment processor socket timeout (>10000ms); 100% order checkout failed",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Read timeouts exceeded on 35% of requests to inventory service on {ip}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single read timeout on non-critical third-party currency conversion API; retried",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Transient socket timeout on non-essential audit log collector; queued to local buffer without drop",
    ),
]

RC_TIM_TRAIN = {
    "RC_TRAIN_1": "Network read or socket timeout waiting for downstream endpoint response in {service}.",
    "RC_TRAIN_2": "TCP socket timeout (ETIMEDOUT) while awaiting response from downstream target on {ip}.",
    "RC_TRAIN_3": "Downstream response duration exceeded configured client socket timeout threshold in {service}.",
}
ACT_TIM_TRAIN = {
    "ACT_TRAIN_1": "Investigate downstream service processing latency, database calls, and evaluate client socket timeout thresholds.",
    "ACT_TRAIN_2": "Tune TCP keepalive settings, profile downstream slow endpoints, and deploy retry with exponential backoff on {service}.",
    "ACT_TRAIN_3": "Profile downstream thread pool saturation and add caching to eliminate slow remote calls.",
}

RC_TIM_VAL = {
    "RC_VAL_1": "Socket read timeout: downstream server failed to return response bytes within allocated window on {ip}.",
}
ACT_TIM_VAL = {
    "ACT_VAL_1": "Profile downstream service performance and evaluate socket timeout thresholds for {service}.",
}

RC_TIM_TEST = {
    "RC_TEST_1": "Client connection or read timeout exceeded while awaiting downstream response headers on {ip}.",
}
ACT_TIM_TEST = {
    "ACT_TEST_1": "Adjust client timeout parameters and inspect downstream queue depth and thread pool saturation in {service}.",
}

RC_TIM = {**RC_TIM_TRAIN, **RC_TIM_VAL, **RC_TIM_TEST}
ACT_TIM = {**ACT_TIM_TRAIN, **ACT_TIM_VAL, **ACT_TIM_TEST}

TEMPLATES_SOCKET_TIMEOUT = [
    _create_template("NET_TIM_01", FAM_TIM, "Java Socket", "Java", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] java.net.SocketTimeoutException: Read timed out after {num*100}ms",
            f"[{ts}] [ERROR] [{service}] at java.base/sun.nio.ch.NioSocketImpl.timedRead(NioSocketImpl.java:283) connecting to {ip}:443",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "java.net.SocketTimeoutException: Read timed out after",
            "NioSocketImpl.timedRead",
            impact_line,
        ], SCEN_TIM, RC_TIM, ACT_TIM, "JAVA_SOCKET_READ_TIMEOUT"),
    _create_template("NET_TIM_02", FAM_TIM, "Python Requests", "Python", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] requests.exceptions.ReadTimeout: HTTPSConnectionPool(host='{ip}', port=443): Read timed out. (read timeout=10.0)",
            f"[{ts}] [WARN] [{service}] Remote gateway failed to return HTTP response headers in allocated window for id={hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "requests.exceptions.ReadTimeout: HTTPSConnectionPool",
            "Read timed out. (read timeout=",
            impact_line,
        ], SCEN_TIM, RC_TIM, ACT_TIM, "PYTHON_READ_TIMEOUT_HTTPS"),
    _create_template("NET_TIM_03", FAM_TIM, "Node.js net", "Node.js", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Error: connect ETIMEDOUT {ip}:8080",
            f"[{ts}] [ERROR] [{service}] at TCPConnectWrap.afterConnect [as oncomplete] (net.js:{num}:14)",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Error: connect ETIMEDOUT",
            "at TCPConnectWrap.afterConnect",
            impact_line,
        ], SCEN_TIM, RC_TIM, ACT_TIM, "NODE_CONNECT_ETIMEDOUT"),
    _create_template("NET_TIM_04", FAM_TIM, "Go http", "Go", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Get \"https://{ip}/api/v1/resource\": context deadline exceeded (Client.Timeout exceeded while awaiting headers)",
            f"[{ts}] [WARN] [{service}] HTTP client request canceled after {num*100}ms",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "context deadline exceeded (Client.Timeout exceeded while awaiting headers)",
            impact_line,
        ], SCEN_TIM, RC_TIM, ACT_TIM, "GO_HTTP_CONTEXT_DEADLINE_EXCEEDED"),
    _create_template("NET_TIM_05", FAM_TIM, "cURL", "C/curl", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] curl: (28) Operation timed out after 10000 milliseconds with 0 bytes received from {ip}",
            f"[{ts}] [FATAL] [{service}] Health probe timeout on backend container",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "curl: (28) Operation timed out after 10000 milliseconds with 0 bytes received",
            impact_line,
        ], SCEN_TIM, RC_TIM, ACT_TIM, "CURL_28_OPERATION_TIMED_OUT"),
    _create_template("NET_TIM_06", FAM_TIM, "DotNet HttpClient", "C#/.NET", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] System.Threading.Tasks.TaskCanceledException: The request was canceled due to the configured HttpClient.Timeout of 15 seconds elapsing.",
            f"[{ts}] [ERROR] [{service}] InnerException: System.TimeoutException: The operation has timed out on {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "The request was canceled due to the configured HttpClient.Timeout",
            "System.TimeoutException: The operation has timed out on",
            impact_line,
        ], SCEN_TIM, RC_TIM, ACT_TIM, "DOTNET_HTTPCLIENT_TASK_CANCELED"),
    _create_template("NET_TIM_07", FAM_TIM, "gRPC", "Java/gRPC", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] io.grpc.StatusRuntimeException: DEADLINE_EXCEEDED: deadline exceeded after 9.9999812s. [remote_addr={ip}:9090]",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "io.grpc.StatusRuntimeException: DEADLINE_EXCEEDED: deadline exceeded after",
            impact_line,
        ], SCEN_TIM, RC_TIM, ACT_TIM, "GRPC_DEADLINE_EXCEEDED"),
    _create_template("NET_TIM_08", FAM_TIM, "Ruby Net::HTTP", "Ruby", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Net::ReadTimeout with #<TCPSocket:(closed)> for {ip}:443 request_id={hex_id}",
            f"[{ts}] [WARN] [{service}] Faraday::TimeoutError: execution expired",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Net::ReadTimeout with #<TCPSocket:(closed)>",
            "Faraday::TimeoutError: execution expired",
            impact_line,
        ], SCEN_TIM, RC_TIM, ACT_TIM, "RUBY_NET_READ_TIMEOUT"),
    _create_template("NET_TIM_09", FAM_TIM, "OkHttp", "Java/OkHttp", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] java.net.SocketTimeoutException: timeout to {ip}:443",
            f"[{ts}] [ERROR] [{service}] at okhttp3.internal.http2.Http2Stream$StreamTimeout.timeoutExit(Http2Stream.kt:{num})",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "java.net.SocketTimeoutException: timeout to",
            "okhttp3.internal.http2.Http2Stream$StreamTimeout.timeoutExit",
            impact_line,
        ], SCEN_TIM, RC_TIM, ACT_TIM, "OKHTTP_SOCKET_TIMEOUT"),
    _create_template("NET_TIM_10", FAM_TIM, "aiohttp", "Python/asyncio", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] asyncio.exceptions.TimeoutError: Connection timeout occurred while reading response from http://{ip}:8080/stream",
            f"[{ts}] [WARN] [{service}] ClientSession request canceled after {num}s timeout",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "asyncio.exceptions.TimeoutError: Connection timeout occurred while reading response",
            "ClientSession request canceled after",
            impact_line,
        ], SCEN_TIM, RC_TIM, ACT_TIM, "AIOHTTP_ASYNC_READ_TIMEOUT"),
]


# =========================================================================
# 4. NET_TLS_HANDSHAKE_FAILURE
# =========================================================================

FAM_TLS = IncidentFamily.NET_TLS_HANDSHAKE_FAILURE

# Mechanism-isolated scenarios for TLS avoiding mixed failure causes:
SCEN_TLS_EXPIRED = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Expired TLS certificate blocking 100% of HTTPS ingress traffic across {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: SSL certificate expiration on internal backend service on {ip}:8443",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single staging endpoint TLS certificate expired; production endpoints unaffected",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Certificate validity period expired on isolated test domain on host {ip}; auto-renewal triggered with 0 customer impact",
    ),
]

SCEN_TLS_CIPHER = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: TLS handshake failure: client and server have no overlapping cipher suites across {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: SSL handshake failure due to cipher mismatch connecting to upstream partner on {ip}:8443",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Legacy client TLS handshake rejected due to incompatible cipher negotiation; modern clients OK",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Incompatible test cipher warning on internal staging endpoint; connection negotiated securely using fallback TLSv1.3",
    ),
]

SCEN_TLS_CLIENT = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Mutual TLS (mTLS) enforcement rejecting 100% of peer requests across {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Missing or untrusted client certificate during mTLS handshake on {ip}:8443",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single batch worker rejected due to missing client certificate; retrying authentication",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Optional mTLS handshake probe rejected on internal endpoint {ip}; public traffic unaffected",
    ),
]

SCEN_TLS_UNTRUSTED = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Untrusted certificate authority blocking all secure downstream connections in {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Self-signed certificate in chain rejected by strict TLS validator on {ip}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Auxiliary reporting endpoint rejected untrusted CA certificate; non-blocking",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Untrusted test certificate alert in staging container; production root truststore unaffected",
    ),
]

SCEN_TLS_PROTOCOL = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: TLS protocol version mismatch blocking connection to secure endpoint {ip}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Deprecated TLS protocol version rejected by edge policy on {service}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Legacy TLSv1.0 connection attempt blocked by server policy; clients notified to upgrade",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Diagnostic probe using legacy TLS protocol rejected by edge filter on {ip}; zero impact",
    ),
]

# Signature-specific split-aware root cause and action pools
# Cert expired:
RC_TLS_EXPIRED_TRAIN = {
    "RC_TRAIN_1": "TLS/X.509 server certificate validity period expired on {ip}.",
    "RC_TRAIN_2": "Expired SSL/TLS leaf certificate rejected during path validation in {service}.",
}
ACT_TLS_EXPIRED_TRAIN = {
    "ACT_TRAIN_1": "Renew and deploy updated TLS certificate; verify automated cert-manager renewals.",
    "ACT_TRAIN_2": "Rotate expired server certificate in secrets manager and reload ingress TLS secret for {service}.",
}

# Cipher / protocol mismatch:
RC_TLS_CIPHER_TRAIN = {
    "RC_TRAIN_1": "TLS handshake failure due to lack of overlapping cipher suites or unsupported protocol version with {ip}.",
    "RC_TRAIN_2": "Client and server failed TLS protocol negotiation; no shared cipher suites supported in {service}.",
}
ACT_TLS_CIPHER_TRAIN = {
    "ACT_TRAIN_1": "Update TLS protocol and cipher suite configuration to enable modern TLSv1.2 and TLSv1.3 ciphers.",
    "ACT_TRAIN_2": "Align allowed cipher list between client and reverse proxy for {service}.",
}

# Client cert / mutual TLS:
RC_TLS_CLIENT_TRAIN = {
    "RC_TRAIN_1": "Mutual TLS (mTLS) handshake failure: peer client did not provide required client certificate to {service}.",
}
ACT_TLS_CLIENT_TRAIN = {
    "ACT_TRAIN_1": "Configure client to present valid TLS client certificate and verify mTLS trust bundle for {service}.",
}

# Validation split (Self-signed cert / invalid cert procedure):
RC_TLS_VAL = {
    "RC_VAL_1": "TLS handshake rejected: untrusted self-signed certificate in chain or untrusted root CA on {ip}.",
}
ACT_TLS_VAL = {
    "ACT_VAL_1": "Import root CA into container truststore or replace self-signed certificate with signed CA certificate for {service}.",
}

# Test split (Protocol mismatch / cert renewal timeout):
RC_TLS_DISALLOWED_TEST = {
    "RC_TEST_1": "Client connection rejected: deprecated or disallowed TLS protocol version (TLSv1.0) on port 443.",
}
ACT_TLS_DISALLOWED_TEST = {
    "ACT_TEST_1": "Upgrade client library to TLSv1.2/TLSv1.3 or verify edge proxy TLS minimum version policy for {service}.",
}

RC_TLS_RENEW_TEST = {
    "RC_TEST_1": "Automated ACME certificate issuance timed out, causing ingress TLS secret expiration on {ip}.",
}
ACT_TLS_RENEW_TEST = {
    "ACT_TEST_1": "Investigate cert-manager ACME challenge solver routing and trigger manual certificate reissue for {service}.",
}

TEMPLATES_TLS = [
    _create_template("NET_TLS_01", FAM_TLS, "Java SSL", "Java", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num, cert_not_after_ts="", **kwargs: [
            f"[{ts}] [ERROR] [{service}] javax.net.ssl.SSLHandshakeException: PKIX path validation failed: java.security.cert.CertPathValidatorException: validity check failed: NotAfter: {cert_not_after_ts or '2026-09-14T00:00:00Z'}",
            f"[{ts}] [ERROR] [{service}] TLS certificate expired on endpoint {ip}:443",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "javax.net.ssl.SSLHandshakeException: PKIX path validation failed",
            "validity check failed: NotAfter:",
            impact_line,
        ], SCEN_TLS_EXPIRED, RC_TLS_EXPIRED_TRAIN, ACT_TLS_EXPIRED_TRAIN,
        signature_profile="JAVA_PKIX_CERT_EXPIRED",
        failure_mechanism="TLS_CERT_EXPIRED",
        expected_tokens=["javax.net.ssl.SSLHandshakeException", "certificate", "expired"],
        forbidden_tokens=["TLSv1.0", "cipher mismatch", "no shared cipher"]),
    _create_template("NET_TLS_02", FAM_TLS, "Python SSL", "Python", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired (_ssl.c:{num})",
            f"[{ts}] [ERROR] [{service}] Failed HTTPS connection to peer {ip}:443",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired",
            impact_line,
        ], SCEN_TLS_EXPIRED, RC_TLS_EXPIRED_TRAIN, ACT_TLS_EXPIRED_TRAIN,
        signature_profile="PYTHON_SSL_CERT_EXPIRED",
        failure_mechanism="TLS_CERT_EXPIRED",
        expected_tokens=["SSLCertVerificationError", "certificate has expired"],
        forbidden_tokens=["TLSv1.0", "cipher mismatch", "no shared cipher"]),
    _create_template("NET_TLS_03", FAM_TLS, "Node.js TLS", "Node.js", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] Error: certificate has expired",
            f"[{ts}] [ERROR] [{service}] at TLSSocket.onConnectSecure (_tls_wrap.js:{num}:34) (code: CERT_HAS_EXPIRED) on {ip}",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "Error: certificate has expired",
            "(code: CERT_HAS_EXPIRED)",
            impact_line,
        ], SCEN_TLS_EXPIRED, RC_TLS_EXPIRED_TRAIN, ACT_TLS_EXPIRED_TRAIN,
        signature_profile="NODE_TLS_CERT_EXPIRED",
        failure_mechanism="TLS_CERT_EXPIRED",
        expected_tokens=["Error: certificate has expired", "CERT_HAS_EXPIRED"],
        forbidden_tokens=["TLSv1.0", "cipher mismatch", "no shared cipher"]),
    _create_template("NET_TLS_04", FAM_TLS, "Go Crypto TLS", "Go", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] http: TLS handshake error from {ip}:49102: remote error: tls: handshake failure",
            f"[{ts}] [WARN] [{service}] crypto/tls: no shared cipher suites between client and server",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "http: TLS handshake error from",
            "remote error: tls: handshake failure",
            "crypto/tls: no shared cipher suites",
            impact_line,
        ], SCEN_TLS_CIPHER, RC_TLS_CIPHER_TRAIN, ACT_TLS_CIPHER_TRAIN,
        signature_profile="GO_TLS_NO_SHARED_CIPHER",
        failure_mechanism="TLS_CIPHER_MISMATCH",
        expected_tokens=["no shared cipher suites"],
        forbidden_tokens=["certificate expired", "NotAfter", "validity check failed"]),
    _create_template("NET_TLS_05", FAM_TLS, "OpenSSL / cURL", "C/OpenSSL", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] curl: (35) error:14094410:SSL routines:ssl3_read_bytes:sslv3 alert handshake failure while connecting to https://{ip}",
            f"[{ts}] [FATAL] [{service}] SSL connection could not be negotiated",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "curl: (35) error:14094410:SSL routines:ssl3_read_bytes:sslv3 alert handshake failure",
            impact_line,
        ], SCEN_TLS_CIPHER, RC_TLS_CIPHER_TRAIN, ACT_TLS_CIPHER_TRAIN,
        signature_profile="OPENSSL_HANDSHAKE_FAILURE",
        failure_mechanism="TLS_CIPHER_MISMATCH",
        expected_tokens=["alert handshake failure"],
        forbidden_tokens=["certificate expired", "NotAfter", "validity check failed"]),
    _create_template("NET_TLS_06", FAM_TLS, "Nginx TLS", "C/Nginx", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] nginx: [crit] 1902#0: *{num} SSL_do_handshake() failed (SSL: error:1417C0C7:SSL routines:tls_process_client_certificate:peer did not return a certificate) while SSL handshaking with client: {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "SSL_do_handshake() failed",
            "while SSL handshaking with client:",
            impact_line,
        ], SCEN_TLS_CLIENT, RC_TLS_CLIENT_TRAIN, ACT_TLS_CLIENT_TRAIN,
        signature_profile="NGINX_MTLS_MISSING_CLIENT_CERT",
        failure_mechanism="TLS_CLIENT_CERT_MISSING",
        expected_tokens=["tls_process_client_certificate", "peer did not return a certificate"],
        forbidden_tokens=["certificate expired", "cipher mismatch"]),
    _create_template("NET_TLS_07", FAM_TLS, "OpenSSL mTLS", "C/OpenSSL", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] OpenSSL: verify error:num=18:self-signed certificate in certificate chain on host {ip}:443",
            f"[{ts}] [FATAL] [{service}] Mutual TLS (mTLS) handshake terminated by peer validator",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "verify error:num=18:self-signed certificate in certificate chain",
            "Mutual TLS (mTLS) handshake terminated",
            impact_line,
        ], SCEN_TLS_UNTRUSTED, RC_TLS_VAL, ACT_TLS_VAL,
        signature_profile="OPENSSL_SELF_SIGNED_IN_CHAIN",
        failure_mechanism="TLS_UNTRUSTED_CA",
        expected_tokens=["self-signed certificate in certificate chain"],
        forbidden_tokens=["cipher mismatch", "TLSv1.0"]),
    _create_template("NET_TLS_08", FAM_TLS, "DotNet SslStream", "C#/.NET", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] System.Security.Authentication.AuthenticationException: The remote certificate is invalid according to the validation procedure on {ip}:8443",
            f"[{ts}] [ERROR] [{service}] SslStream.AuthenticateAsClientAsync failed",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "AuthenticationException: The remote certificate is invalid according to the validation procedure",
            impact_line,
        ], SCEN_TLS_UNTRUSTED, RC_TLS_VAL, ACT_TLS_VAL,
        signature_profile="DOTNET_SSL_REMOTE_CERT_INVALID",
        failure_mechanism="TLS_UNTRUSTED_CA",
        expected_tokens=["The remote certificate is invalid according to the validation procedure"],
        forbidden_tokens=["cipher mismatch", "TLSv1.0"]),
    _create_template("NET_TLS_09", FAM_TLS, "Envoy Proxy", "Envoy/C++", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [WARN] [{service}] envoy ssl: [downstream] remote {ip}:51202: TLS handshake failed: unsupported protocol or cipher mismatch",
            f"[{ts}] [ERROR] [{service}] Client attempting connection with disallowed TLSv1.0 on port 443",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "envoy ssl: [downstream] remote",
            "TLS handshake failed: unsupported protocol or cipher mismatch",
            impact_line,
        ], SCEN_TLS_PROTOCOL, RC_TLS_DISALLOWED_TEST, ACT_TLS_DISALLOWED_TEST,
        signature_profile="ENVOY_SSL_DISALLOWED_TLS10",
        failure_mechanism="TLS_PROTOCOL_VERSION_MISMATCH",
        expected_tokens=["unsupported protocol or cipher mismatch", "disallowed TLSv1.0"],
        forbidden_tokens=["NotAfter", "certificate expired"]),
    _create_template("NET_TLS_10", FAM_TLS, "cert-manager", "Go/k8s", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] cert-manager: Certificate {service}-tls failed issuance: ACME challenge solver timed out for domain api.example.com",
            f"[{ts}] [FATAL] [{service}] Ingress TLS secret expired without successful rotation on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "cert-manager: Certificate",
            "failed issuance: ACME challenge solver timed out",
            "Ingress TLS secret expired without successful rotation",
            impact_line,
        ], SCEN_TLS_EXPIRED, RC_TLS_RENEW_TEST, ACT_TLS_RENEW_TEST,
        signature_profile="CERT_MANAGER_ACME_TIMEOUT",
        failure_mechanism="TLS_ACME_RENEWAL_TIMEOUT",
        expected_tokens=["ACME challenge solver timed out"],
        forbidden_tokens=["cipher mismatch"]),
]


# =========================================================================
# 5. NET_INGRESS_GATEWAY_TIMEOUT
# =========================================================================

FAM_GTW = IncidentFamily.NET_INGRESS_GATEWAY_TIMEOUT

# 1. 504 Gateway Timeout specific scenarios and variants
SCEN_GTW_504 = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Ingress gateway returning 504 Gateway Timeout on 95% of incoming public requests",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Upstream response timeout spike (504 Gateway Timeout) on /api/v1/checkout on {ip}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single upstream gateway timeout (504) during rolling deployment update; retrying",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Isolated upstream 504 timeout on static asset probe; client received cached response",
    ),
]

RC_GTW_504_TRAIN = {
    "RC_TRAIN_1": "Ingress reverse proxy HTTP 504 Gateway Timeout: upstream backend pod failed to respond in {service}.",
    "RC_TRAIN_2": "Upstream service response duration exceeded reverse proxy gateway timeout on {ip}.",
    "RC_TRAIN_3": "Ingress controller timed out awaiting response headers from upstream pods in {service}.",
}
ACT_GTW_504_TRAIN = {
    "ACT_TRAIN_1": "Increase proxy read_timeout and proxy_connect_timeout; scale up upstream backend pods.",
    "ACT_TRAIN_2": "Inspect slow upstream transactions and optimize database query durations for {service}.",
    "ACT_TRAIN_3": "Check upstream pod CPU and thread pool saturation on {ip} causing gateway timeouts.",
}

# AWS ALB 504 Specific variants (Requirement 8)
RC_ALB_504 = {
    "RC_TRAIN_1": "AWS Application Load Balancer HTTP 504 Gateway Timeout: registered target on {ip} failed to respond before target response timeout elapsed.",
    "RC_TRAIN_2": "ALB target group response timeout exceeded while awaiting HTTP response headers from backend container on {ip}.",
    "RC_TRAIN_3": "Upstream backend container response latency exceeded ALB configured target connection and response timeout thresholds in {service}.",
}
ACT_ALB_504 = {
    "ACT_TRAIN_1": "Inspect ALB target health and backend container response latency; verify target response timeout attribute on target group.",
    "ACT_TRAIN_2": "Check ALB TargetResponseTime and TargetConnectionError metrics; investigate slow upstream dependencies on {ip}.",
    "ACT_TRAIN_3": "Review backend application thread pool utilization and tune ALB idle timeout and deregistration delay for {service}.",
}

RC_GTW_504_VAL = {
    "RC_VAL_1": "Reverse proxy HTTP 504 Gateway Timeout: upstream backend application timed out on {ip}.",
}
ACT_GTW_504_VAL = {
    "ACT_VAL_1": "Scale upstream application replicas and investigate backend GC pauses or thread pool exhaustion in {service}.",
}

# 2. 502 Bad Gateway specific scenarios and variants
SCEN_GTW_502 = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Ingress gateway returning 502 Bad Gateway on 90% of incoming customer traffic",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: 502 Bad Gateway spike on /api/v1/checkout via reverse proxy ingress on {ip}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Transient 502 Bad Gateway while restarting backend service container; retrying",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Ephemeral 502 Bad Gateway during pod rolling replacement; auto-resolved within 1s",
    ),
]

RC_GTW_502_TRAIN = {
    "RC_TRAIN_1": "HTTP 502 Bad Gateway: upstream server terminated TCP connection before sending response headers to {ip}.",
    "RC_TRAIN_2": "Backend service pod crashed or reset connection during HTTP request processing in {service}.",
    "RC_TRAIN_3": "Reverse proxy received invalid or empty response from upstream backend service on {ip}.",
}
ACT_GTW_502_TRAIN = {
    "ACT_TRAIN_1": "Check upstream pod health and restart failing backend service pods in {service}.",
    "ACT_TRAIN_2": "Inspect upstream application crash logs and verify backend keepalive timeout settings on {ip}.",
    "ACT_TRAIN_3": "Align upstream web server keepalive timeout with reverse proxy upstream idle timeout.",
}

RC_GTW_502_VAL = {
    "RC_VAL_1": "Application Gateway HTTP 502 Bad Gateway: backend server closed connection during handshake on {ip}.",
}
ACT_GTW_502_VAL = {
    "ACT_VAL_1": "Verify backend server TLS and TCP handshake configuration and probe responsiveness for {service}.",
}

RC_GTW_502_TEST = {
    "RC_TEST_1": "Reverse proxy HTTP 502 Bad Gateway: upstream connection refused on port 8080 on {ip}.",
}
ACT_GTW_502_TEST = {
    "ACT_TEST_1": "Verify backend service process is listening on port 8080 and check local firewall rules on {ip}.",
}

# 3. 503 Service Unavailable specific scenarios and variants
SCEN_GTW_503 = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Envoy proxy returning 503 Service Unavailable: upstream connection failure across {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: 503 Service Unavailable spike: upstream cluster connection resets on {ip}:8080",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Isolated 503 connection error during backend container drain; request retried",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Staging canary probe returned 503 during warmup; healthy endpoints available",
    ),
]

RC_GTW_503_TRAIN = {
    "RC_TRAIN_1": "HTTP 503 Service Unavailable: Envoy upstream connection failure and delayed connect error on {ip}.",
    "RC_TRAIN_2": "Upstream cluster connection reset before response started in {service}.",
    "RC_TRAIN_3": "Ingress proxy unable to establish TCP transport connection to upstream host {ip}.",
}
ACT_GTW_503_TRAIN = {
    "ACT_TRAIN_1": "Inspect Envoy upstream cluster health checks and verify backend pod readiness on {ip}.",
    "ACT_TRAIN_2": "Check network connectivity and security group egress rules between proxy and backend in {service}.",
    "ACT_TRAIN_3": "Review Envoy connection pool settings and upstream circuit breaker thresholds.",
}

# 4. 524 Origin Timeout specific scenarios and variants
SCEN_GTW_524 = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Cloudflare edge returning HTTP 524 A Timeout Occurred: origin server unresponsive",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Cloudflare 524 timeout spike on origin endpoint {ip}: origin took >100s to respond",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single analytical request timed out at edge (HTTP 524); origin query still running",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Non-critical batch export request triggered edge 524 timeout; retried asynchronously",
    ),
]

RC_GTW_524_TEST = {
    "RC_TEST_1": "Cloudflare HTTP 524: origin server connection timed out after exceeding 100-second edge response limit on {ip}.",
}
ACT_GTW_524_TEST = {
    "ACT_TEST_1": "Optimize origin server response processing time or offload long-running operations to asynchronous worker tasks.",
}


TEMPLATES_GATEWAY_TIMEOUT = [
    _create_template("NET_GTW_01", FAM_GTW, "Nginx Ingress", "C/Nginx", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] nginx: [error] 2910#0: *{num} upstream timed out (110: Connection timed out) while reading response header from upstream, client: 192.0.2.8, server: api.example.com, request: \"POST /api/checkout HTTP/1.1\", upstream: \"http://{ip}:8080/api/checkout\"",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "upstream timed out (110: Connection timed out) while reading response header from upstream",
            "upstream: \"http://",
            impact_line,
        ], SCEN_GTW_504, RC_GTW_504_TRAIN, ACT_GTW_504_TRAIN,
        signature_profile="NGINX_UPSTREAM_TIMED_OUT_504",
        failure_mechanism="HTTP_504_GATEWAY_TIMEOUT",
        expected_tokens=["upstream timed out"],
        forbidden_tokens=["502 Bad Gateway", "503 Service Unavailable"],
        expected_status_code=None),
    _create_template("NET_GTW_02", FAM_GTW, "Envoy Proxy", "Envoy/C++", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] [upstream_reset_before_response_started{{connection_failure,transport_failure_reason:delayed_connect_error:111}}] HTTP/1.1 503 UC 0 0 1002 - \"-\" \"curl/7.68.0\" \"{hex_id}\" \"api.example.com\" \"{ip}:8080\"",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "upstream_reset_before_response_started{connection_failure",
            "HTTP/1.1 503 UC",
            impact_line,
        ], SCEN_GTW_503, RC_GTW_503_TRAIN, ACT_GTW_503_TRAIN,
        signature_profile="ENVOY_UPSTREAM_RESET_503",
        failure_mechanism="HTTP_503_SERVICE_UNAVAILABLE",
        expected_tokens=["HTTP/1.1 503 UC"],
        forbidden_tokens=["504 Gateway Timeout", "502 Bad Gateway"],
        expected_status_code=503),
    _create_template("NET_GTW_03", FAM_GTW, "Traefik", "Go/Traefik", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] traefik: 504 Gateway Timeout: net/http: request canceled (Client.Timeout exceeded while awaiting headers) to backend http://{ip}:8080",
            f"[{ts}] [WARN] [{service}] Forwarding request id={hex_id} aborted by reverse proxy",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "504 Gateway Timeout: net/http: request canceled",
            "Client.Timeout exceeded while awaiting headers",
            impact_line,
        ], SCEN_GTW_504, RC_GTW_504_TRAIN, ACT_GTW_504_TRAIN,
        signature_profile="TRAEFIK_GATEWAY_TIMEOUT_504",
        failure_mechanism="HTTP_504_GATEWAY_TIMEOUT",
        expected_tokens=["504 Gateway Timeout"],
        forbidden_tokens=["502 Bad Gateway", "503 Service Unavailable"],
        expected_status_code=504),
    _create_template("NET_GTW_04", FAM_GTW, "AWS ALB", "AWS/ALB", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num, alb_event_ts="", **kwargs: [
            f"[{ts}] [ERROR] [{service}] aws-alb: h2 {alb_event_ts or ts} app/prod-alb/{hex_id} 198.51.100.10:49102 {ip}:8080 -1 -1 -1 504 - 240 0 \"POST https://api.example.com/orders HTTP/2.0\"",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "aws-alb: h2",
            "504 -",
            "POST https://api.example.com/orders HTTP/2.0",
            impact_line,
        ], SCEN_GTW_504, RC_ALB_504, ACT_ALB_504,
        signature_profile="AWS_ALB_504_TIMEOUT",
        failure_mechanism="HTTP_504_GATEWAY_TIMEOUT",
        expected_tokens=["aws-alb: h2", "504 -"],
        forbidden_tokens=["502 Bad Gateway", "503 Service Unavailable"],
        expected_status_code=504),
    _create_template("NET_GTW_05", FAM_GTW, "HAProxy", "C/HAProxy", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] haproxy[1041]: backend_servers/{service} {ip}:8080 0/0/0/-1/30000 504 194 - - sH-- 12/8/2/1/0 0/0 \"POST /checkout HTTP/1.1\"",
            f"[{ts}] [WARN] [{service}] Server response timeout flag 'sH' triggered after 30000ms",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "504 194 - - sH--",
            "Server response timeout flag 'sH' triggered",
            impact_line,
        ], SCEN_GTW_504, RC_GTW_504_TRAIN, ACT_GTW_504_TRAIN,
        signature_profile="HAPROXY_504_SH_TIMEOUT",
        failure_mechanism="HTTP_504_GATEWAY_TIMEOUT",
        expected_tokens=["504 194 - - sH--"],
        forbidden_tokens=["502 Bad Gateway", "503 Service Unavailable"],
        expected_status_code=504),
    _create_template("NET_GTW_06", FAM_GTW, "Google Cloud Load Balancer", "GCP/GCLB", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] gcp-gclb: statusDetails: \"backend_connection_closed_before_data_sent_to_client\", status: 502",
            f"[{ts}] [FATAL] [{service}] Backend service pod on {ip} terminated connection abruptly",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "statusDetails: \"backend_connection_closed_before_data_sent_to_client\", status: 502",
            "terminated connection abruptly",
            impact_line,
        ], SCEN_GTW_502, RC_GTW_502_TRAIN, ACT_GTW_502_TRAIN,
        signature_profile="GCLB_502_BACKEND_CLOSED",
        failure_mechanism="HTTP_502_BAD_GATEWAY",
        expected_tokens=["statusDetails: \"backend_connection_closed_before_data_sent_to_client\", status: 502"],
        forbidden_tokens=["504 Gateway Timeout", "503 Service Unavailable"],
        expected_status_code=502),
    _create_template("NET_GTW_07", FAM_GTW, "Kong Gateway", "Lua/Kong", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] kong: [error] 2410#0: *{num} [lua] responses.lua:128: sending 504 Gateway Timeout: connection timed out to upstream {ip}:8000",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "sending 504 Gateway Timeout: connection timed out to upstream",
            impact_line,
        ], SCEN_GTW_504, RC_GTW_504_VAL, ACT_GTW_504_VAL,
        signature_profile="KONG_504_UPSTREAM_TIMEOUT",
        failure_mechanism="HTTP_504_GATEWAY_TIMEOUT",
        expected_tokens=["sending 504 Gateway Timeout"],
        forbidden_tokens=["502 Bad Gateway", "503 Service Unavailable"],
        expected_status_code=504),
    _create_template("NET_GTW_08", FAM_GTW, "Azure App Gateway", "Azure/AppGW", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] ApplicationGatewayAccessLog: httpStatus=502 serverResponseLatency=0.000 timeTaken=20.000 backendPool={service}-pool target={ip}:8080",
            f"[{ts}] [ERROR] [{service}] Backend server closed connection during handshake",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "ApplicationGatewayAccessLog: httpStatus=502",
            "Backend server closed connection during handshake",
            impact_line,
        ], SCEN_GTW_502, RC_GTW_502_VAL, ACT_GTW_502_VAL,
        signature_profile="AZURE_APPGW_502_HANDSHAKE_DROP",
        failure_mechanism="HTTP_502_BAD_GATEWAY",
        expected_tokens=["ApplicationGatewayAccessLog: httpStatus=502"],
        forbidden_tokens=["504 Gateway Timeout", "503 Service Unavailable"],
        expected_status_code=502),
    _create_template("NET_GTW_09", FAM_GTW, "Cloudflare Edge", "Edge/Cloudflare", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] Cloudflare HTTP 524: A Timeout Occurred: Origin server {ip} did not respond within 100 seconds",
            f"[{ts}] [FATAL] [{service}] Edge proxy severed connection to origin for request {hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "Cloudflare HTTP 524: A Timeout Occurred: Origin server",
            "did not respond within 100 seconds",
            impact_line,
        ], SCEN_GTW_524, RC_GTW_524_TEST, ACT_GTW_524_TEST,
        signature_profile="CLOUDFLARE_524_ORIGIN_TIMEOUT",
        failure_mechanism="HTTP_524_ORIGIN_TIMEOUT",
        expected_tokens=["Cloudflare HTTP 524: A Timeout Occurred"],
        forbidden_tokens=["502 Bad Gateway", "503 Service Unavailable"],
        expected_status_code=524),
    _create_template("NET_GTW_10", FAM_GTW, "Caddy Server", "Go/Caddy", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num, **kwargs: [
            f"[{ts}] [ERROR] [{service}] caddy-proxy: HTTP 502 Bad Gateway: dial tcp {ip}:8080: connect: connection refused",
            f"[{ts}] [ERROR] [{service}] reverse_proxy handler failed to reach upstream target",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "caddy-proxy: HTTP 502 Bad Gateway: dial tcp",
            "reverse_proxy handler failed to reach upstream target",
            impact_line,
        ], SCEN_GTW_502, RC_GTW_502_TEST, ACT_GTW_502_TEST,
        signature_profile="CADDY_502_DIAL_REFUSED",
        failure_mechanism="HTTP_502_BAD_GATEWAY",
        expected_tokens=["HTTP 502 Bad Gateway"],
        forbidden_tokens=["504 Gateway Timeout", "503 Service Unavailable"],
        expected_status_code=502),
]


# =========================================================================
# 6. NET_PARTITION_OR_BLACKHOLE
# =========================================================================

FAM_PAR = IncidentFamily.NET_PARTITION_OR_BLACKHOLE

SCEN_PAR = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Network split-brain partition between zone-a and zone-b; nodes unreachable",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Large payload requests hanging indefinitely due to MTU black hole on {ip}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Intermittent packet loss (15%) between worker node and redis replica; investigating",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Single BGP hold timer flap on redundant secondary link; traffic instantly rerouted over primary path",
    ),
]

RC_PAR_TRAIN = {
    "RC_TRAIN_1": "Network partition or routing black hole dropping packets between cluster subnets on {ip}.",
    "RC_TRAIN_2": "Packet drop or routing failure preventing packet delivery across network segment in {service}.",
    "RC_TRAIN_3": "Network connectivity failure causing packet loss or unreachable destination on {ip}.",
}
ACT_PAR_TRAIN = {
    "ACT_TRAIN_1": "Investigate routing tables, conntrack capacity, and overlay network MTU (VXLAN/Geneve); verify inter-node connectivity.",
    "ACT_PAR_TRAIN_2": "Check Path MTU discovery, inspect TCP MSS clamping on network gateway, and verify MTU configuration.",
    "ACT_PAR_TRAIN_3": "Inspect firewall session table limits, check BGP peering status, and verify cross-availability-zone gateway reachability.",
}

RC_PAR_VAL = {
    "RC_VAL_1": "Network routing black hole or transit gateway disconnection dropping inter-subnet packets on {ip}.",
}
ACT_PAR_VAL = {
    "ACT_VAL_1": "Verify routing adjacency and cloud transit gateway route table attachments for {service}.",
}

RC_PAR_TEST = {
    "RC_TEST_1": "Network encapsulation MTU mismatch or routing split-brain causing packet loss on {ip}.",
}
ACT_PAR_TEST = {
    "ACT_TEST_1": "Review overlay network tunnel MTU, check BGP peering status, and verify interface route tables for {service}.",
}

RC_PAR = {**RC_PAR_TRAIN, **RC_PAR_VAL, **RC_PAR_TEST}
ACT_PAR = {**ACT_PAR_TRAIN, **ACT_PAR_VAL, **ACT_PAR_TEST}

TEMPLATES_PARTITION = [
    _create_template("NET_PAR_01", FAM_PAR, "Linux Kernel IP", "Linux/Kernel", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] kernel: Path MTU discovery failure: packet of size 1500 bytes dropped with DF (Don't Fragment) bit set on interface eth0 to {ip}",
            f"[{ts}] [ERROR] [{service}] TCP connection hangs indefinitely after TLS handshake on large payloads",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Path MTU discovery failure: packet of size 1500 bytes dropped with DF",
            "TCP connection hangs indefinitely after TLS handshake",
            impact_line,
        ], SCEN_PAR, RC_PAR, ACT_PAR, "LINUX_PMTU_BLACKHOLE_DF_DROP"),
    _create_template("NET_PAR_02", FAM_PAR, "Linux Routing", "Linux/IPRoute", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] connect: Network is unreachable to destination subnet 10.244.2.0/24 via gateway {ip}",
            f"[{ts}] [FATAL] [{service}] BGP route withdrawn by router daemon; no route to host",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "connect: Network is unreachable to destination subnet",
            "BGP route withdrawn by router daemon",
            impact_line,
        ], SCEN_PAR, RC_PAR, ACT_PAR, "LINUX_NETWORK_UNREACHABLE_BGP"),
    _create_template("NET_PAR_03", FAM_PAR, "Netfilter Conntrack", "Linux/Netfilter", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] kernel: nf_conntrack: table full, dropping packet from {ip}",
            f"[{ts}] [ERROR] [{service}] Conntrack table limit (262144) reached: incoming and outgoing TCP SYN packets dropped",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "nf_conntrack: table full, dropping packet",
            "Conntrack table limit",
            "reached: incoming and outgoing TCP SYN packets dropped",
            impact_line,
        ], SCEN_PAR, RC_PAR, ACT_PAR, "NETFILTER_CONNTRACK_TABLE_FULL"),
    _create_template("NET_PAR_04", FAM_PAR, "Calico VXLAN", "Linux/Calico", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] vxlan: encapsulation packet exceeds overlay interface vxlan.calico MTU (1440): dropped on host {ip}",
            f"[{ts}] [WARN] [{service}] Inter-pod communication stalled for payloads exceeding MSS",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "encapsulation packet exceeds overlay interface",
            "Inter-pod communication stalled for payloads exceeding MSS",
            impact_line,
        ], SCEN_PAR, RC_PAR, ACT_PAR, "CALICO_VXLAN_MTU_DROP"),
    _create_template("NET_PAR_05", FAM_PAR, "Flannel SDN", "Go/Flannel", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] flanneld[{ip}]: failed to sync subnet lease from etcd: context deadline exceeded (split brain)",
            f"[{ts}] [FATAL] [{service}] Node isolated from cluster SDN routing mesh",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "failed to sync subnet lease from etcd: context deadline exceeded",
            "Node isolated from cluster SDN routing mesh",
            impact_line,
        ], SCEN_PAR, RC_PAR, ACT_PAR, "FLANNEL_ETCD_SYNC_PARTITION"),
    _create_template("NET_PAR_06", FAM_PAR, "Linux TC", "Linux/TrafficControl", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] ping: {ip}: 64 packets transmitted, 12 received, 81.25% packet loss, time {num*100}ms",
            f"[{ts}] [WARN] [{service}] Asymmetric routing detected: return traffic routed through non-existent tunnel interface",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "packet loss, time",
            "Asymmetric routing detected: return traffic routed through non-existent tunnel",
            impact_line,
        ], SCEN_PAR, RC_PAR, ACT_PAR, "LINUX_ASYMMETRIC_ROUTE_PACKET_LOSS"),
    _create_template("NET_PAR_07", FAM_PAR, "AWS Transit Gateway", "AWS/TGW", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] aws-tgw: Blackhole route detected: destination CIDR 10.100.0.0/16 points to detached attachment {hex_id}",
            f"[{ts}] [FATAL] [{service}] Cross-VPC traffic to payment subnet {ip} dropped by transit gateway",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Blackhole route detected: destination CIDR",
            "Cross-VPC traffic to payment subnet",
            "dropped by transit gateway",
            impact_line,
        ], SCEN_PAR, RC_PAR, ACT_PAR, "AWS_TGW_BLACKHOLE_ROUTE"),
    _create_template("NET_PAR_08", FAM_PAR, "Cisco IOS", "Cisco/IOS", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] %BGP-5-ADJCHANGE: neighbor {ip} Down - BGP Notification sent, hold time expired",
            f"[{ts}] [FATAL] [{service}] Routing adjacency lost: primary core route flap causing traffic blackhole",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "%BGP-5-ADJCHANGE: neighbor",
            "Down - BGP Notification sent, hold time expired",
            "Routing adjacency lost: primary core route flap",
            impact_line,
        ], SCEN_PAR, RC_PAR, ACT_PAR, "CISCO_BGP_ADJACENCY_FLAP"),
    _create_template("NET_PAR_09", FAM_PAR, "OVN Kubernetes", "Linux/OVN", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] ovs-vswitchd: datapath dropped packet: size 1450 exceeds geneve tunnel interface mtu 1400 on {ip}",
            f"[{ts}] [WARN] [{service}] TCP MSS clamping missing on egress gateway; connections hanging",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "datapath dropped packet: size 1450 exceeds geneve tunnel interface mtu",
            "TCP MSS clamping missing on egress gateway",
            impact_line,
        ], SCEN_PAR, RC_PAR, ACT_PAR, "OVN_GENEVE_MTU_DROP"),
    _create_template("NET_PAR_10", FAM_PAR, "Keepalived VRRP", "C/Keepalived", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] Keepalived_vrrp[{ip}]: VRRP_Instance(VI_1) received lower priority advert 100, ours 150: SPLIT BRAIN detected",
            f"[{ts}] [FATAL] [{service}] Multiple nodes claiming Virtual IP 198.51.100.1; ARP poisoning and connection resets active",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "SPLIT BRAIN detected",
            "Multiple nodes claiming Virtual IP",
            impact_line,
        ], SCEN_PAR, RC_PAR, ACT_PAR, "VRRP_SPLIT_BRAIN_VIP"),
]


NETWORK_TEMPLATES: list[LogTemplate] = (
    TEMPLATES_DNS +
    TEMPLATES_CONN_REFUSED +
    TEMPLATES_SOCKET_TIMEOUT +
    TEMPLATES_TLS +
    TEMPLATES_GATEWAY_TIMEOUT +
    TEMPLATES_PARTITION
)

assert len(NETWORK_TEMPLATES) == 60, f"Expected 60 templates in NETWORK, got {len(NETWORK_TEMPLATES)}"
