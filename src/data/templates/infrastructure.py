"""Structural log templates for the INFRASTRUCTURE category (6 families, 60 templates).

Each family defines 10 templates: 6 TRAIN, 2 VALIDATION, 2 TEST.
Includes P4_LOW coverage, normalized metadata, and split-aware variant pools.
"""

from typing import Callable
from src.data.models import DatasetSplit, ImpactScenario, Severity
from src.data.templates.base import LogTemplate
from src.schemas.enums import IncidentFamily


FAM_OOM = IncidentFamily.INFRA_POD_OOMKILLED
FAM_CPU = IncidentFamily.INFRA_CPU_THROTTLING
FAM_INO = IncidentFamily.INFRA_INODE_EXHAUSTION
FAM_NNR = IncidentFamily.INFRA_NODE_NOT_READY
FAM_CLB = IncidentFamily.INFRA_CRASHLOOP_BACKOFF
FAM_EVI = IncidentFamily.INFRA_STORAGE_EVICTION

FAMILY_OBSERVED_MAP = {
    FAM_OOM: "Container or process terminated by kernel/cgroup out-of-memory killer (exit code 137) after exceeding memory limits.",
    FAM_CPU: "Container execution throttled by Linux CFS quota scheduler after consuming allocated CPU bandwidth limits.",
    FAM_INO: "Filesystem inode table reached 100% capacity (zero free inodes), preventing new file and socket creation.",
    FAM_NNR: "Kubernetes node controller transitioned node status to NotReady due to node condition or kubelet heartbeat loss.",
    FAM_CLB: "Container process repeatedly exited with non-zero exit code, triggering Kubernetes CrashLoopBackOff restart back-off.",
    FAM_EVI: "Pod evicted by kubelet after node ephemeral storage or volume threshold exceeded high watermark limit.",
}

FAMILY_HYPOTHESES_MAP = {
    FAM_OOM: ["application memory leak", "runaway memory allocation", "unbounded caching", "under-provisioned container memory limit"],
    FAM_CPU: ["infinite compute loop", "unoptimized compute workload", "high computational workload", "thread pool contention"],
    FAM_INO: ["millions of unpurged temporary files", "session file accumulation", "runaway logger"],
    FAM_NNR: ["network partition", "hardware failure", "kernel panic", "switch reboot"],
    FAM_CLB: ["missing environment variable", "unhandled startup crash", "configuration syntax error"],
    FAM_EVI: ["runaway container logs", "unmounted host path accumulation", "ephemeral volume saturation"],
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
# 1. INFRA_POD_OOMKILLED
# =========================================================================

SCEN_OOM = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: All 4 active pods for {service} terminated by OOMKiller; service completely unresponsive",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Container {service}-{hex_id} killed with exit code 137; pod restarting",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single background batch pod terminated by cgroup OOM; rescheduling",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Isolated auxiliary metrics agent container terminated by OOMKiller; automatically restarted with 0 service impact",
    ),
]

RC_OOM_TRAIN = {
    "RC_TRAIN_1": "Container memory consumption exceeded configured cgroup limit causing termination (exit code 137) in {service}.",
    "RC_TRAIN_2": "Process resident memory surpassed container memory limits on host {ip}.",
    "RC_TRAIN_3": "Container memory limit exceeded, causing runtime kernel OOM killer termination for {service}.",
}
ACT_OOM_TRAIN = {
    "ACT_TRAIN_1": "Inspect application heap profiling, investigate memory allocation patterns, and adjust container memory limits.",
    "ACT_TRAIN_2": "Analyze process resident memory growth for leaks or unbounded caching; tune runtime memory flags.",
    "ACT_TRAIN_3": "Review memory limits against peak workload demand and configure Horizontal Pod Autoscaler.",
}

RC_OOM_VAL = {
    "RC_VAL_1": "Container terminated by runtime OOM killer after exceeding allocated cgroup memory limit.",
}
ACT_OOM_VAL = {
    "ACT_VAL_1": "Adjust container memory limits and monitor resident memory usage under load on {ip}.",
}

RC_OOM_TEST = {
    "RC_TEST_1": "Memory threshold exceeded causing container cgroup eviction and SIGKILL on host {ip}.",
}
ACT_OOM_TEST = {
    "ACT_TEST_1": "Inspect memory limit configuration in deployment specification for {service}.",
}

TEMPLATES_OOM = [
    _create_template("INF_OOM_01", FAM_OOM, "Kubernetes", "containerd", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] kubelet[{ip}]: container \"api-server\" in pod \"{service}-{hex_id}\" terminated with exit code 137",
            f"[{ts}] [WARN] [{service}] kernel: Memory cgroup out of memory: Killed process {num*10} (python3) total-vm:{num*1024}kB, anon-rss:{num*512}kB",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "terminated with exit code 137",
            "Memory cgroup out of memory: Killed process",
            impact_line,
        ], SCEN_OOM, RC_OOM_TRAIN, ACT_OOM_TRAIN, signature_profile="K8S_CONTAINER_EXIT_137"),
    _create_template("INF_OOM_02", FAM_OOM, "Docker", "containerd", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] dockerd: Container {hex_id} failed to run: OOMKilled: true, ExitCode: 137",
            f"[{ts}] [WARN] [{service}] docker-events: die container={service}-{hex_id} (exitCode=137, oomKilled=true)",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "OOMKilled: true, ExitCode: 137",
            "die container=",
            impact_line,
        ], SCEN_OOM, RC_OOM_TRAIN, ACT_OOM_TRAIN, signature_profile="DOCKER_OOMKILLED_EVENT"),
    _create_template("INF_OOM_03", FAM_OOM, "Linux", "cgroup-v2", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] systemd[1]: /sys/fs/cgroup/system.slice/{service}.service: oom-kill: constraint=CONSTRAINT_MEMCG",
            f"[{ts}] [FATAL] [{service}] kernel: invoked oom-killer: gfp_mask=0x1100cca(GFP_HIGHUSER_MOVABLE), order=0, oom_score_adj=998 on host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "oom-kill: constraint=CONSTRAINT_MEMCG",
            "invoked oom-killer:",
            impact_line,
        ], SCEN_OOM, RC_OOM_TRAIN, ACT_OOM_TRAIN, signature_profile="SYSTEMD_CGROUP_OOM_KILL"),
    _create_template("INF_OOM_04", FAM_OOM, "Java", "JVM/CGroup", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] OpenJDK 64-Bit Server VM warning: INFO: os::commit_memory(0x{hex_id}, {num}MB) failed; error='Cannot allocate memory' (errno=12)",
            f"[{ts}] [ERROR] [{service}] Kubelet killed pod {service}-{hex_id} due to cgroup limit enforcement on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "failed; error='Cannot allocate memory' (errno=12)",
            "killed pod",
            "due to cgroup limit enforcement",
            impact_line,
        ], SCEN_OOM, RC_OOM_TRAIN, ACT_OOM_TRAIN, signature_profile="JVM_COMMIT_MEMORY_ERRNO_12"),
    _create_template("INF_OOM_05", FAM_OOM, "Node.js", "V8", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] <--- Last few GCs ---> [node {hex_id}] {num} ms: Mark-sweep {num*2} MB -> {num*2} MB",
            f"[{ts}] [FATAL] [{service}] <--- JS stacktrace ---> FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory",
            impact_line,
        ], SCEN_OOM, RC_OOM_TRAIN, ACT_OOM_TRAIN, signature_profile="NODEJS_HEAP_OOM_CRASH"),
    _create_template("INF_OOM_06", FAM_OOM, "Kubernetes", "kubelet", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] kubelet[{ip}]: Pod {service}-{hex_id} memory limit 512Mi exceeded (current usage: 524Mi)",
            f"[{ts}] [ERROR] [{service}] Container {service} in pod {service}-{hex_id} marked as OOMKilled; restart count {num}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "memory limit 512Mi exceeded",
            "marked as OOMKilled; restart count",
            impact_line,
        ], SCEN_OOM, RC_OOM_TRAIN, ACT_OOM_TRAIN, signature_profile="K8S_POD_MEMORY_LIMIT_EXCEEDED"),
    _create_template("INF_OOM_07", FAM_OOM, "Go", "Go-runtime", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] runtime: out of memory: cannot allocate {num}MB (total allocated {num*8}MB)",
            f"[{ts}] [FATAL] [{service}] fatal error: out of memory on node {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "runtime: out of memory: cannot allocate",
            "fatal error: out of memory on node",
            impact_line,
        ], SCEN_OOM, RC_OOM_VAL, ACT_OOM_VAL, signature_profile="GO_RUNTIME_OUT_OF_MEMORY"),
    _create_template("INF_OOM_08", FAM_OOM, "Python", "CPython", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] MemoryError: unable to allocate array with shape ({num}, 1000000) and data type float64",
            f"[{ts}] [ERROR] [{service}] Process terminated by kernel SIGKILL (exit status 137) on host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "MemoryError: unable to allocate array with shape",
            "Process terminated by kernel SIGKILL (exit status 137)",
            impact_line,
        ], SCEN_OOM, RC_OOM_VAL, ACT_OOM_VAL, signature_profile="PYTHON_MEMORY_ERROR_SIGKILL_137"),
    _create_template("INF_OOM_09", FAM_OOM, "Linux", "kernel-mm", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] kernel: [{num*100}.129] Out of memory: Kill process {num*2} (worker) score 950 or sacrifice child",
            f"[{ts}] [CRITICAL] [{service}] kernel: Killed process {num*2} (worker) total-vm:4194304kB, anon-rss:3145728kB on {ip}",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Out of memory: Kill process",
            "Killed process",
            impact_line,
        ], SCEN_OOM, RC_OOM_TEST, ACT_OOM_TEST, signature_profile="KERNEL_OOM_KILL_PROCESS"),
    _create_template("INF_OOM_10", FAM_OOM, "Kubernetes", "cgroups", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] cgroup: memory.max reached for slice kubepods-burstable-pod{hex_id}.slice on {ip}",
            f"[{ts}] [WARN] [{service}] Event: reason: OOMKilling pod: {service}-{hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "memory.max reached for slice",
            "Event: reason: OOMKilling pod:",
            impact_line,
        ], SCEN_OOM, RC_OOM_TEST, ACT_OOM_TEST, signature_profile="K8S_CGROUP_MEMORY_MAX_OOM"),
]


# =========================================================================
# 2. INFRA_CPU_THROTTLING
# =========================================================================

FAM_CPU = IncidentFamily.INFRA_CPU_THROTTLING

SCEN_CPU = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Severe CPU throttling causing 15s p99 latency; customer request queue overflowing in {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: 85% of CPU periods throttled on pod {service}-{hex_id}; processing bottleneck",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Moderate CPU throttling (25%) detected during batch report generation",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Minor CPU limit throttling of 4% on background log forwarder; service latency unaffected",
    ),
]

RC_CPU_TRAIN = {
    "RC_TRAIN_1": "Container execution throttled by CFS quota limits after consuming allocated CPU bandwidth in {service}.",
    "RC_TRAIN_2": "CPU quota limit reached on host {ip}, causing CFS scheduler throttling of container threads.",
    "RC_TRAIN_3": "Container process consumed allocated CPU quota bandwidth on {ip}, triggering throttling.",
}
ACT_CPU_TRAIN = {
    "ACT_TRAIN_1": "Inspect thread CPU profiling for unoptimized compute loops or spinlocks; adjust cgroup CPU quota.",
    "ACT_TRAIN_2": "Evaluate computational workload demands, review thread concurrency, and scale replicas.",
    "ACT_TRAIN_3": "Analyze burst processing requirements and increase CPU limits or tune CFS period.",
}

RC_CPU_VAL = {
    "RC_VAL_1": "Container CPU throttling triggered by CFS bandwidth quota restrictions on node {ip}.",
}
ACT_CPU_VAL = {
    "ACT_VAL_1": "Raise CPU limit quota in deployment manifest and monitor container cpu_stat on {ip}.",
}

RC_CPU_TEST = {
    "RC_TEST_1": "CFS scheduler quota enforcement throttling container processing threads on {ip}.",
}
ACT_CPU_TEST = {
    "ACT_TEST_1": "Tune CPU limit ceiling or configure Horizontal Pod Autoscaler for {service}.",
}

TEMPLATES_CPU_THROTTLING = [
    _create_template("INF_CPU_01", FAM_CPU, "Linux", "cgroup-cfs", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] cgroup.cpu: nr_throttled: {num*100}, throttled_time: {num*5000000}ns on container {hex_id}",
            f"[{ts}] [ERROR] [{service}] Container CPU throttling rate is 92.4% over last 60s on host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "nr_throttled:",
            "throttled_time:",
            "CPU throttling rate is",
            impact_line,
        ], SCEN_CPU, RC_CPU_TRAIN, ACT_CPU_TRAIN, signature_profile="LINUX_CFS_CPU_THROTTLED"),
    _create_template("INF_CPU_02", FAM_CPU, "Kubernetes", "kubelet", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] kubelet[{ip}]: Container \"{service}\" in pod \"{service}-{hex_id}\" throttled for {num*50}ms in 100ms CFS quota window",
            f"[{ts}] [ERROR] [{service}] Pod CPU limit (500m) saturated; latency degrading",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "throttled for",
            "in 100ms CFS quota window",
            impact_line,
        ], SCEN_CPU, RC_CPU_TRAIN, ACT_CPU_TRAIN, signature_profile="K8S_CFS_QUOTA_WINDOW_THROTTLED"),
    _create_template("INF_CPU_03", FAM_CPU, "Prometheus", "cadvisor", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] PrometheusAlert: ContainerCpuThrottlingHigh: container_cpu_cfs_throttled_periods_total / periods_total > 80% on {ip}",
            f"[{ts}] [ERROR] [{service}] Service {service} CPU exhaustion: container throttled {num} periods",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ContainerCpuThrottlingHigh:",
            "container_cpu_cfs_throttled_periods_total",
            impact_line,
        ], SCEN_CPU, RC_CPU_TRAIN, ACT_CPU_TRAIN, signature_profile="CADVISOR_CPU_THROTTLING_HIGH"),
    _create_template("INF_CPU_04", FAM_CPU, "Java", "JVM", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] java.lang.management.OperatingSystemMXBean: ProcessCpuLoad=0.99, SystemCpuLoad=0.98 on {ip}",
            f"[{ts}] [ERROR] [{service}] Garbage collection pause time degraded: GC threads stalled due to CPU throttling ({num}ms pause)",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ProcessCpuLoad=0.99",
            "GC threads stalled due to CPU throttling",
            impact_line,
        ], SCEN_CPU, RC_CPU_TRAIN, ACT_CPU_TRAIN, signature_profile="JVM_GC_CPU_THROTTLED"),
    _create_template("INF_CPU_05", FAM_CPU, "Go", "Go-runtime", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] runtime: GOMAXPROCS=2 but host container throttled by CFS quota on {ip}",
            f"[{ts}] [ERROR] [{service}] Goroutine scheduler latency spike: runqueue wait time > {num*10}ms",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "host container throttled by CFS quota",
            "Goroutine scheduler latency spike:",
            impact_line,
        ], SCEN_CPU, RC_CPU_TRAIN, ACT_CPU_TRAIN, signature_profile="GO_RUNTIME_CFS_THROTTLED"),
    _create_template("INF_CPU_06", FAM_CPU, "Node.js", "libuv", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] event-loop-lag: Event loop delay is {num*20}ms (threshold: 50ms) on {ip}",
            f"[{ts}] [ERROR] [{service}] Container CPU quota reached: libuv threadpool stalled on host {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Event loop delay is",
            "Container CPU quota reached: libuv threadpool stalled",
            impact_line,
        ], SCEN_CPU, RC_CPU_TRAIN, ACT_CPU_TRAIN, signature_profile="NODEJS_EVENT_LOOP_LAG_THROTTLED"),
    _create_template("INF_CPU_07", FAM_CPU, "Docker", "containerd", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] dockerd: container {hex_id} cpu.cfs_quota_us/cpu.cfs_period_us throttle ratio reached 0.88",
            f"[{ts}] [ERROR] [{service}] cpu throttling detected for {service} on host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "cpu.cfs_quota_us/cpu.cfs_period_us throttle ratio reached",
            "cpu throttling detected for",
            impact_line,
        ], SCEN_CPU, RC_CPU_VAL, ACT_CPU_VAL, signature_profile="DOCKER_CFS_QUOTA_RATIO_EXCEEDED"),
    _create_template("INF_CPU_08", FAM_CPU, "Linux", "sysstat", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] mpstat: %usr 99.1, %sys 0.8, %steal {num}.2 on host {ip}",
            f"[{ts}] [ERROR] [{service}] High CPU steal and cgroup throttling reported on instance {hex_id}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "mpstat: %usr 99.1",
            "High CPU steal and cgroup throttling reported",
            impact_line,
        ], SCEN_CPU, RC_CPU_VAL, ACT_CPU_VAL, signature_profile="SYSSTAT_HIGH_CPU_STEAL_THROTTLED"),
    _create_template("INF_CPU_09", FAM_CPU, "AWS EC2", "cloudwatch", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] cloudwatch: CPUCreditBalance=0.00 for burstable instance i-{hex_id} on {ip}",
            f"[{ts}] [ERROR] [{service}] CPUCreditSurgeCharge triggered; baseline CPU performance capped at 10%",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "CPUCreditBalance=0.00 for burstable instance",
            "baseline CPU performance capped at",
            impact_line,
        ], SCEN_CPU, RC_CPU_TEST, ACT_CPU_TEST, signature_profile="AWS_EC2_T3_CPU_CREDIT_EXHAUSTED"),
    _create_template("INF_CPU_10", FAM_CPU, "Kubernetes", "kubelet", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] kubelet[{ip}]: pod {service}-{hex_id} container {service} hit cpu.cfs_quota_us limit {num} times in 1m",
            f"[{ts}] [WARN] [{service}] Pod responsiveness degraded due to strict CFS quota throttling",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "hit cpu.cfs_quota_us limit",
            "Pod responsiveness degraded due to strict CFS quota throttling",
            impact_line,
        ], SCEN_CPU, RC_CPU_TEST, ACT_CPU_TEST, signature_profile="K8S_STRICT_CFS_QUOTA_THROTTLING"),
]


# =========================================================================
# 3. INFRA_INODE_EXHAUSTION
# =========================================================================

FAM_INO = IncidentFamily.INFRA_INODE_EXHAUSTION

SCEN_INO = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: 100% inode exhaustion; applications unable to create sockets or write files across {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Root volume free inodes at 0.05% on host {ip}; service degradation starting",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Inode exhaustion isolated to temporary testing directory on {service}; non-critical",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Scratch directory inode quota exhausted on host {ip}; non-critical test artifact creation failed while main services unaffected",
    ),
]

RC_INO_TRAIN = {
    "RC_TRAIN_1": "Filesystem inode capacity exhausted (zero free inodes) on volume hosting {service} on host {ip}.",
    "RC_TRAIN_2": "Inability to create files or network sockets due to zero available inodes on host {ip}.",
    "RC_TRAIN_3": "Filesystem inode table reached 100% capacity on {ip}, preventing new file creation.",
}
ACT_INO_TRAIN = {
    "ACT_TRAIN_1": "Inspect directory file counts (temporary files, session stores, caches) and purge obsolete files.",
    "ACT_INO_TRAIN_2": "Identify directories containing millions of tiny stale files; implement automated cleanup cron jobs.",
    "ACT_TRAIN_3": "Reformat filesystem with higher inode density or switch to dynamic-inode filesystem.",
}

RC_INO_VAL = {
    "RC_VAL_1": "Filesystem inode table capacity exhausted preventing file creation on node {ip}.",
}
ACT_INO_VAL = {
    "ACT_VAL_1": "Purge obsolete temporary files and verify inode utilization with df -i on {ip}.",
}

RC_INO_TEST = {
    "RC_TEST_1": "Zero available inodes remaining on filesystem volume hosting {service} on {ip}.",
}
ACT_INO_TEST = {
    "ACT_TEST_1": "Clean up orphaned temporary files and expand filesystem inode allotment on {ip}.",
}

TEMPLATES_INODE = [
    _create_template("INF_INO_01", FAM_INO, "Linux", "ext4", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] open(\"/tmp/session_{hex_id}.tmp\", O_CREAT|O_WRONLY): No space left on device",
            f"[{ts}] [WARN] [{service}] df -i: /dev/sda1 100% inode utilization (used: 4000000, free: 0)",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "open(\"/tmp/session_",
            "No space left on device",
            "100% inode utilization",
            impact_line,
        ], SCEN_INO, RC_INO_TRAIN, ACT_INO_TRAIN, signature_profile="EXT4_NO_FREE_INODES"),
    _create_template("INF_INO_02", FAM_INO, "Python", "CPython", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] OSError: [Errno 28] No space left on device while creating socket or lockfile",
            f"[{ts}] [WARN] [{service}] statvfs(/var/log): f_favail=0, f_ffree=0 (free inodes exhausted on host {ip})",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "OSError: [Errno 28] No space left on device while creating socket",
            "free inodes exhausted on host",
            impact_line,
        ], SCEN_INO, RC_INO_TRAIN, ACT_INO_TRAIN, signature_profile="PYTHON_OSERROR_ERRNO_28_INODES"),
    _create_template("INF_INO_03", FAM_INO, "Kubernetes", "kubelet", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] kubelet[{ip}]: NodeCondition: InodePressure=True, message: \"node has insufficient inodes\"",
            f"[{ts}] [WARN] [{service}] EvictionManager: node {ip} in InodePressure condition; attempting pod eviction",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "NodeCondition: InodePressure=True, message: \"node has insufficient inodes\"",
            "in InodePressure condition; attempting pod eviction",
            impact_line,
        ], SCEN_INO, RC_INO_TRAIN, ACT_INO_TRAIN, signature_profile="K8S_NODE_INODE_PRESSURE"),
    _create_template("INF_INO_04", FAM_INO, "Java", "JVM", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] java.io.IOException: No space left on device creating temp file in /var/run/{service}",
            f"[{ts}] [FATAL] [{service}] java.nio.file.FileSystemException: /var/run/{service}/pipe_{hex_id}: No space left on device (inode full)",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "java.io.IOException: No space left on device creating temp file",
            "No space left on device (inode full)",
            impact_line,
        ], SCEN_INO, RC_INO_TRAIN, ACT_INO_TRAIN, signature_profile="JAVA_IO_INODE_FULL"),
    _create_template("INF_INO_05", FAM_INO, "Docker", "overlay2", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] dockerd: failed to create container {hex_id}: error creating overlay mount: no space left on device (free inodes: 0)",
            f"[{ts}] [WARN] [{service}] /var/lib/docker/overlay2: inode table exhausted on node {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "error creating overlay mount: no space left on device (free inodes: 0)",
            "inode table exhausted on node",
            impact_line,
        ], SCEN_INO, RC_INO_TRAIN, ACT_INO_TRAIN, signature_profile="DOCKER_OVERLAY2_INODES_EXHAUSTED"),
    _create_template("INF_INO_06", FAM_INO, "Nginx", "C", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] nginx: [crit] 19284#0: open() \"/var/cache/nginx/client_temp/{hex_id}\" failed (28: No space left on device)",
            f"[{ts}] [WARN] [{service}] FastCGI cache failed to write temporary spool: disk has 40GB free bytes but 0 inodes",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "open() \"/var/cache/nginx/client_temp/",
            "failed (28: No space left on device)",
            "disk has 40GB free bytes but 0 inodes",
            impact_line,
        ], SCEN_INO, RC_INO_TRAIN, ACT_INO_TRAIN, signature_profile="NGINX_CACHE_TEMP_NO_INODES"),
    _create_template("INF_INO_07", FAM_INO, "Systemd", "journald", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] systemd-journald[841]: Failed to create new journal file /var/log/journal/{hex_id}: No space left on device",
            f"[{ts}] [WARN] [{service}] Inode exhaustion on /var filesystem; dropping incoming syslog streams on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Failed to create new journal file",
            "No space left on device",
            "Inode exhaustion on /var filesystem",
            impact_line,
        ], SCEN_INO, RC_INO_VAL, ACT_INO_VAL, signature_profile="SYSTEMD_JOURNAL_INODE_FULL"),
    _create_template("INF_INO_08", FAM_INO, "Go", "Go-runtime", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] os.Create(/tmp/lock_{hex_id}): write error: no space left on device (inodes full)",
            f"[{ts}] [FATAL] [{service}] cannot spawn worker subprocess: pipe creation failed on {ip}",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "os.Create(/tmp/lock_",
            "no space left on device (inodes full)",
            impact_line,
        ], SCEN_INO, RC_INO_VAL, ACT_INO_VAL, signature_profile="GO_OS_CREATE_INODES_FULL"),
    _create_template("INF_INO_09", FAM_INO, "FreeBSD", "UFS", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] kernel: /data: out of inodes: volume reached max inode count (used {num*100000})",
            f"[{ts}] [ERROR] [{service}] creat() returned ENOSPC on host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "kernel: /data: out of inodes",
            "creat() returned ENOSPC on host",
            impact_line,
        ], SCEN_INO, RC_INO_TEST, ACT_INO_TEST, signature_profile="FREEBSD_UFS_OUT_OF_INODES"),
    _create_template("INF_INO_10", FAM_INO, "Ceph", "CephFS", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] ceph-mds[{ip}]: cluster inode quota breached: MDS client evicted due to inode exhaustion",
            f"[{ts}] [WARN] [{service}] POSIX mount /mnt/shared: inode usage 100% on pool {hex_id}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "cluster inode quota breached: MDS client evicted due to inode exhaustion",
            "inode usage 100% on pool",
            impact_line,
        ], SCEN_INO, RC_INO_TEST, ACT_INO_TEST, signature_profile="CEPH_MDS_INODE_QUOTA_BREACHED"),
]


# =========================================================================
# 4. INFRA_NODE_NOT_READY
# =========================================================================

SCEN_NNR = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Primary worker node host-{ip} NotReady; 15 production pods evicted and terminating",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Worker node {ip} lost heartbeat to control plane; rescheduling pods",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single spot instance node NotReady during cloud rebalance; replacements launched",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Standby batch worker node {ip} transitioned to NotReady; cordoned automatically with zero production pod evictions",
    ),
]

RC_NNR_TRAIN = {
    "RC_TRAIN_1": "Kubernetes worker node transitioned to NotReady due to kubelet heartbeat timeout on {ip}.",
    "RC_TRAIN_2": "Kubelet process unresponsive on node {ip}, preventing node status updates to control plane.",
    "RC_TRAIN_3": "Node network plugin or CNI failure causing node status to report NotReady.",
}
ACT_NNR_TRAIN = {
    "ACT_TRAIN_1": "Investigate kubelet status and node systemd logs on {ip}; cordon and restart kubelet daemon.",
    "ACT_TRAIN_2": "Drain node pods to healthy instances, inspect container runtime health, and restart kubelet.",
    "ACT_TRAIN_3": "Inspect node network connectivity and restart CNI plugin daemonset.",
}

RC_NNR_VAL = {
    "RC_VAL_1": "Worker node marked NotReady due to underlying instance status check failure or daemon crash on {ip}.",
}
ACT_NNR_VAL = {
    "ACT_VAL_1": "Check cloud provider instance health and restart kubelet service on host {ip}.",
}

RC_NNR_TEST_DEFAULT = {
    "RC_TEST_1": "Cluster worker node reported NotReady status causing pod rescheduling away from {ip}.",
}
ACT_NNR_TEST_DEFAULT = {
    "ACT_TEST_1": "Verify node system health and restore compute instance connectivity on {ip}.",
}

# Dedicated technology-specific variants for GKE NodeNotReady with DiskPressure (INF_NNR_09)
RC_NNR_GKE_DISK = {
    "RC_TEST_1": "GKE worker node marked NotReady due to KubeletHasDiskPressure condition on host {ip}.",
}
ACT_NNR_GKE_DISK = {
    "ACT_TEST_1": "Inspect and clean up container images and ephemeral disk space on node {ip}, and verify kubelet eviction thresholds.",
}

TEMPLATES_NODE_NOT_READY = [
    _create_template("INF_NNR_01", FAM_NNR, "Kubernetes", "kube-controller", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] kube-controller-manager: Node node-{ip} has not reported status in 40s (last heartbeat: {num}s ago)",
            f"[{ts}] [WARN] [{service}] NodeCondition: Ready=False, reason: KubeletNotReady, message: \"kubelet stopped posting node status\"",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "has not reported status in 40s",
            "Ready=False, reason: KubeletNotReady",
            impact_line,
        ], SCEN_NNR, RC_NNR_TRAIN, ACT_NNR_TRAIN, signature_profile="K8S_KUBELET_STOPPED_POSTING_STATUS"),
    _create_template("INF_NNR_02", FAM_NNR, "Kubernetes", "cni-plugin", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] kubelet[{ip}]: runtime network not ready: NetworkReady=false reason: NetworkPluginNotReady",
            f"[{ts}] [FATAL] [{service}] cni-plugin failed to set up pod network sandbox on host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "runtime network not ready: NetworkReady=false reason: NetworkPluginNotReady",
            "cni-plugin failed to set up pod network sandbox",
            impact_line,
        ], SCEN_NNR, RC_NNR_TRAIN, ACT_NNR_TRAIN, signature_profile="K8S_CNI_NETWORK_PLUGIN_NOT_READY"),
    _create_template("INF_NNR_03", FAM_NNR, "containerd", "C/gRPC", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] containerd: grpc connection failed on /run/containerd/containerd.sock: context deadline exceeded",
            f"[{ts}] [ERROR] [{service}] kubelet[{ip}]: failed to inspect container runtime status: transport is closing",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "grpc connection failed on /run/containerd/containerd.sock: context deadline exceeded",
            "failed to inspect container runtime status",
            impact_line,
        ], SCEN_NNR, RC_NNR_TRAIN, ACT_NNR_TRAIN, signature_profile="CONTAINERD_GRPC_DEADLINE_EXCEEDED"),
    _create_template("INF_NNR_04", FAM_NNR, "Linux", "kernel", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [EMERG] [{service}] kernel: [{num*500}.129] INFO: task containerd:{num} blocked for more than 120 seconds",
            f"[{ts}] [CRITICAL] [{service}] kernel: \"echo 0 > /proc/sys/kernel/hung_task_timeout_secs\" to disable this message on {ip}",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "INFO: task containerd:",
            "blocked for more than 120 seconds",
            impact_line,
        ], SCEN_NNR, RC_NNR_TRAIN, ACT_NNR_TRAIN, signature_profile="KERNEL_TASK_BLOCKED_120S"),
    _create_template("INF_NNR_05", FAM_NNR, "Kubernetes", "node-problem-detector", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] node-problem-detector: KernelDeadlock condition detected on host {ip}",
            f"[{ts}] [WARN] [{service}] NodeStatus changed: Ready=False, DiskDeadlock=True, KubeletUnresponsive",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "KernelDeadlock condition detected on host",
            "Ready=False, DiskDeadlock=True",
            impact_line,
        ], SCEN_NNR, RC_NNR_TRAIN, ACT_NNR_TRAIN, signature_profile="K8S_NPD_KERNEL_DEADLOCK"),
    _create_template("INF_NNR_06", FAM_NNR, "Linux", "ext4-fs", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [EMERG] [{service}] kernel: EXT4-fs error (device sda1): ext4_lookup: deleted inode referenced",
            f"[{ts}] [FATAL] [{service}] Remounting filesystem read-only on node {ip}; kubelet terminated",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "EXT4-fs error (device sda1):",
            "Remounting filesystem read-only on node",
            impact_line,
        ], SCEN_NNR, RC_NNR_TRAIN, ACT_NNR_TRAIN, signature_profile="LINUX_FS_REMOUNT_READONLY"),
    _create_template("INF_NNR_07", FAM_NNR, "AWS EC2", "cloudwatch", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [CRITICAL] [{service}] cloudwatch: InstanceStatusCheckFailed: ec2 instance i-{hex_id} failed reachability check on {ip}",
            f"[{ts}] [ERROR] [{service}] Node marked NotReady by AWS cloud provider controller",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "InstanceStatusCheckFailed: ec2 instance",
            "failed reachability check on",
            impact_line,
        ], SCEN_NNR, RC_NNR_VAL, ACT_NNR_VAL, signature_profile="AWS_EC2_INSTANCE_STATUS_CHECK_FAILED"),
    _create_template("INF_NNR_08", FAM_NNR, "Systemd", "kubelet", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] systemd[1]: kubelet.service: Main process exited, code=dumped, status=6/ABRT",
            f"[{ts}] [ERROR] [{service}] systemd[1]: kubelet.service: Failed with result 'core-dump' on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "kubelet.service: Main process exited, code=dumped, status=6/ABRT",
            "Failed with result 'core-dump' on",
            impact_line,
        ], SCEN_NNR, RC_NNR_VAL, ACT_NNR_VAL, signature_profile="SYSTEMD_KUBELET_CORE_DUMP"),
    _create_template("INF_NNR_09", FAM_NNR, "GKE", "k8s-node-controller", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] gke-node-controller: node gke-cluster-pool-{hex_id} status set to NotReady: KubeletHasDiskPressure",
            f"[{ts}] [WARN] [{service}] Evicting pods from degraded GKE node {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "status set to NotReady: KubeletHasDiskPressure",
            "Evicting pods from degraded GKE node",
            impact_line,
        ], SCEN_NNR, RC_NNR_GKE_DISK, ACT_NNR_GKE_DISK, signature_profile="GKE_NODE_DISK_PRESSURE_NOTREADY"),
    _create_template("INF_NNR_10", FAM_NNR, "VMware", "vSphere-HA", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] vSphere-HA: lost network heartbeat from host {ip}: VM guest OS presumed crashed",
            f"[{ts}] [FATAL] [{service}] Node status changed to NotReady across cluster {hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "vSphere-HA: lost network heartbeat from host",
            "Node status changed to NotReady across cluster",
            impact_line,
        ], SCEN_NNR, RC_NNR_TEST_DEFAULT, ACT_NNR_TEST_DEFAULT, signature_profile="VMWARE_LOST_NETWORK_HEARTBEAT"),
]


# =========================================================================
# 5. INFRA_CRASHLOOP_BACKOFF
# =========================================================================

SCEN_CLB = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: 0/3 replicas running for {service}; pods in continuous CrashLoopBackOff",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Deployment rollout stalled; new pod {service}-{hex_id} failing startup",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single canary pod in CrashLoopBackOff; production traffic routed to stable version",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Canary container exited with non-zero status; traffic automatically redirected to stable deployment",
    ),
]

RC_CLB_TRAIN = {
    "RC_TRAIN_1": "Container failing initialization and repeatedly crashing upon startup in {service}.",
    "RC_TRAIN_2": "Container process exited with non-zero exit code during startup, triggering restart back-off in {service}.",
    "RC_TRAIN_3": "Container entrypoint failed during initialization, causing pod CrashLoopBackOff on {ip}.",
}
ACT_CLB_TRAIN = {
    "ACT_TRAIN_1": "Inspect previous container logs with kubectl logs --previous to identify startup error.",
    "ACT_TRAIN_2": "Verify mandatory environment variables, ConfigMap mounts, and configuration parameters in pod specification.",
    "ACT_TRAIN_3": "Check container image binary entrypoint path, executable permissions, and container startup arguments.",
}

RC_CLB_VAL = {
    "RC_VAL_1": "Application initialization failure during container boot triggering CrashLoopBackOff on host {ip}.",
}
ACT_CLB_VAL = {
    "ACT_VAL_1": "Inspect container exit code and verify application bootstrap dependencies for {service}.",
}

RC_CLB_TEST_DEFAULT = {
    "RC_TEST_1": "Runtime panic during application initialization causing repeated container crash in {service}.",
}
ACT_CLB_TEST_DEFAULT = {
    "ACT_TEST_1": "Review stack trace in startup crash logs and test binary initialization locally for {service}.",
}

# Specific technology-appropriate variants for Node.js SyntaxError (INF_CLB_09)
RC_CLB_NODE_SYNTAX = {
    "RC_TEST_1": "SyntaxError unexpected token during JavaScript module execution causing container crash in {service}.",
}
ACT_CLB_NODE_SYNTAX = {
    "ACT_TEST_1": "Fix syntax error in server entrypoint script and rebuild container image for {service}.",
}

TEMPLATES_CRASHLOOP = [
    _create_template("INF_CLB_01", FAM_CLB, "Kubernetes", "kubelet", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] kubelet[{ip}]: Error: failed to start container \"{service}\": Error response from daemon: failed to create task",
            f"[{ts}] [WARN] [{service}] Back-off restarting failed container \"{service}\" in pod \"{service}-{hex_id}\"",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "failed to start container",
            "Back-off restarting failed container",
            impact_line,
        ], SCEN_CLB, RC_CLB_TRAIN, ACT_CLB_TRAIN, signature_profile="K8S_FAILED_TO_START_CONTAINER"),
    _create_template("INF_CLB_02", FAM_CLB, "Kubernetes", "k8s-runtime", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] Container \"{service}\" terminated with exit code 1 (reason: Error) on host {ip}",
            f"[{ts}] [ERROR] [{service}] pod \"{service}-{hex_id}\" state: Waiting, reason: CrashLoopBackOff (restart count: {num})",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "terminated with exit code 1 (reason: Error)",
            "state: Waiting, reason: CrashLoopBackOff",
            impact_line,
        ], SCEN_CLB, RC_CLB_TRAIN, ACT_CLB_TRAIN, signature_profile="K8S_CRASHLOOP_BACKOFF_EXIT_1"),
    _create_template("INF_CLB_03", FAM_CLB, "Python", "CPython", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] KeyError: 'DATABASE_URL' environment variable is required but not set",
            f"[{ts}] [ERROR] [{service}] Container startup failed in 120ms; kubelet entering CrashLoopBackOff for pod {service}-{hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "KeyError: 'DATABASE_URL' environment variable is required",
            "entering CrashLoopBackOff for pod",
            impact_line,
        ], SCEN_CLB, RC_CLB_TRAIN, ACT_CLB_TRAIN, signature_profile="PYTHON_KEYERROR_MISSING_ENV"),
    _create_template("INF_CLB_04", FAM_CLB, "Docker", "entrypoint", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] standard_init_linux.go:228: exec user process caused: no such file or directory",
            f"[{ts}] [WARN] [{service}] kubelet[{ip}]: Container \"{service}\" exited with status 127; back-off restart scheduled",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "exec user process caused: no such file or directory",
            "exited with status 127; back-off restart scheduled",
            impact_line,
        ], SCEN_CLB, RC_CLB_TRAIN, ACT_CLB_TRAIN, signature_profile="DOCKER_EXEC_NO_SUCH_FILE_127"),
    _create_template("INF_CLB_05", FAM_CLB, "Kubernetes", "liveness-probe", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] kubelet[{ip}]: Liveness probe failed: HTTP probe failed with statuscode: 500",
            f"[{ts}] [ERROR] [{service}] Container \"{service}\" failed liveness probe 3 times; killing and restarting container (crashlooping)",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Liveness probe failed: HTTP probe failed with statuscode: 500",
            "killing and restarting container (crashlooping)",
            impact_line,
        ], SCEN_CLB, RC_CLB_TRAIN, ACT_CLB_TRAIN, signature_profile="K8S_LIVENESS_PROBE_HTTP_500"),
    _create_template("INF_CLB_06", FAM_CLB, "Kubernetes", "startup-probe", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Startup probe failed: connection refused to {ip}:8080 after {num*10}s",
            f"[{ts}] [FATAL] [{service}] Pod {service}-{hex_id} exceeded startupProbe failureThreshold (30); container restart in progress",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Startup probe failed: connection refused",
            "exceeded startupProbe failureThreshold",
            impact_line,
        ], SCEN_CLB, RC_CLB_TRAIN, ACT_CLB_TRAIN, signature_profile="K8S_STARTUP_PROBE_TIMEOUT"),
    _create_template("INF_CLB_07", FAM_CLB, "Linux", "container-linux", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] container_linux.go:380: starting container process caused: permission denied: /entrypoint.sh",
            f"[{ts}] [ERROR] [{service}] Container failed to start: ExitCode 126; backing off container restarts on node {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "starting container process caused: permission denied: /entrypoint.sh",
            "ExitCode 126; backing off container restarts",
            impact_line,
        ], SCEN_CLB, RC_CLB_VAL, ACT_CLB_VAL, signature_profile="CONTAINER_PERMISSION_DENIED_126"),
    _create_template("INF_CLB_08", FAM_CLB, "Java/Spring", "JVM", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] org.springframework.boot.SpringApplication: Application run failed: ApplicationContextException: Unable to start embedded web server",
            f"[{ts}] [ERROR] [{service}] JVM terminated with status 1; kubelet status: CrashLoopBackOff for pod {service}-{hex_id}",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Application run failed: ApplicationContextException: Unable to start embedded web server",
            "CrashLoopBackOff for pod",
            impact_line,
        ], SCEN_CLB, RC_CLB_VAL, ACT_CLB_VAL, signature_profile="SPRING_BOOT_APP_CONTEXT_FAILURE"),
    _create_template("INF_CLB_09", FAM_CLB, "Node.js", "V8", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] /app/dist/server.js:14: SyntaxError: Unexpected token '?'",
            f"[{ts}] [ERROR] [{service}] Node process exited with code 1; Kubernetes entering CrashLoopBackOff for {service}-{hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "SyntaxError: Unexpected token",
            "Kubernetes entering CrashLoopBackOff for",
            impact_line,
        ], SCEN_CLB, RC_CLB_NODE_SYNTAX, ACT_CLB_NODE_SYNTAX, signature_profile="NODEJS_SYNTAX_ERROR_CRASH"),
    _create_template("INF_CLB_10", FAM_CLB, "Go", "Go-runtime", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] panic: runtime error: invalid memory address or nil pointer dereference in main.init()",
            f"[{ts}] [FATAL] [{service}] container exited with status 2; pod {service}-{hex_id} back-off restart 5m0s",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "panic: runtime error: invalid memory address or nil pointer dereference in main.init()",
            "back-off restart",
            impact_line,
        ], SCEN_CLB, RC_CLB_TEST_DEFAULT, ACT_CLB_TEST_DEFAULT, signature_profile="GO_NIL_POINTER_INIT_PANIC"),
]


# =========================================================================
# 6. INFRA_STORAGE_EVICTION
# =========================================================================

SCEN_EVI = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Ephemeral storage exhaustion on node {ip}; all 12 worker pods evicted immediately",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Pod {service}-{hex_id} evicted by kubelet; local scratch volume full",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single pod evicted due to disk pressure; rescheduled on spare worker node",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Ephemeral storage limit exceeded on non-critical batch worker {service}-{hex_id}; pod evicted and rescheduled with zero user disruption",
    ),
]

RC_EVI_TRAIN = {
    "RC_TRAIN_1": "Pod evicted by kubelet due to local ephemeral storage usage exceeding configured limit in {service}.",
    "RC_TRAIN_2": "Container filesystem storage usage exceeded allowable quota on {ip}, triggering pod eviction.",
    "RC_TRAIN_3": "Node disk pressure triggered proactive pod eviction to protect system disk.",
}
ACT_EVI_TRAIN = {
    "ACT_TRAIN_1": "Increase ephemeral-storage limits in pod resources and configure emptyDir size limits.",
    "ACT_TRAIN_2": "Inspect container write locations for large temporary logs or cache files, and redirect writes to persistent volumes.",
    "ACT_TRAIN_3": "Clean up unmanaged container disk usage and configure log rotation in {service}.",
}

RC_EVI_VAL = {
    "RC_VAL_1": "Kubelet evicted pod after ephemeral storage capacity threshold was breached on host {ip}.",
}
ACT_EVI_VAL = {
    "ACT_VAL_1": "Increase pod ephemeral-storage requests/limits and verify node disk capacity on {ip}.",
}

RC_EVI_TEST = {
    "RC_TEST_1": "Container evicted by node eviction manager due to local disk space starvation on {ip}.",
}
ACT_EVI_TEST = {
    "ACT_TEST_1": "Inspect local container filesystem growth and mount dedicated storage volume for {service}.",
}

TEMPLATES_STORAGE_EVICTION = [
    _create_template("INF_EVI_01", FAM_EVI, "Kubernetes", "kubelet", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] kubelet[{ip}]: Pod \"{service}-{hex_id}\" local ephemeral storage usage exceeds limit of 2Gi (usage: 2.4Gi)",
            f"[{ts}] [ERROR] [{service}] EvictionManager: pod \"{service}-{hex_id}\" evicted due to ephemeral-storage threshold",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "local ephemeral storage usage exceeds limit",
            "evicted due to ephemeral-storage threshold",
            impact_line,
        ], SCEN_EVI, RC_EVI_TRAIN, ACT_EVI_TRAIN, signature_profile="K8S_EPHEMERAL_STORAGE_EVICTION"),
    _create_template("INF_EVI_02", FAM_EVI, "Kubernetes", "disk-pressure", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] kubelet[{ip}]: Node condition DiskPressure is true; starting eviction of burstable pods",
            f"[{ts}] [ERROR] [{service}] Evicting pod \"{service}-{hex_id}\" to reclaim node disk space on root filesystem",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Node condition DiskPressure is true; starting eviction",
            "to reclaim node disk space on root filesystem",
            impact_line,
        ], SCEN_EVI, RC_EVI_TRAIN, ACT_EVI_TRAIN, signature_profile="K8S_NODE_DISK_PRESSURE_EVICTION"),
    _create_template("INF_EVI_03", FAM_EVI, "Kubernetes", "emptyDir", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] kubelet[{ip}]: volume \"scratch-data\" (emptyDir) exceeds sizeLimit 500Mi (used: {num}Mi)",
            f"[{ts}] [FATAL] [{service}] Pod {service}-{hex_id} evicted: emptyDir volume size limit exceeded",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "exceeds sizeLimit 500Mi",
            "evicted: emptyDir volume size limit exceeded",
            impact_line,
        ], SCEN_EVI, RC_EVI_TRAIN, ACT_EVI_TRAIN, signature_profile="K8S_EMPTYDIR_SIZE_LIMIT_EXCEEDED"),
    _create_template("INF_EVI_04", FAM_EVI, "Docker", "containerd", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] dockerd: disk space alert: container write layer size {num}GB on node {ip} exceeded quota",
            f"[{ts}] [WARN] [{service}] Stopping container {service}-{hex_id}: storage eviction policy enforced",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "container write layer size",
            "exceeded quota",
            "storage eviction policy enforced",
            impact_line,
        ], SCEN_EVI, RC_EVI_TRAIN, ACT_EVI_TRAIN, signature_profile="DOCKER_WRITE_LAYER_QUOTA_EXCEEDED"),
    _create_template("INF_EVI_05", FAM_EVI, "Kubernetes", "log-volume", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] kubelet[{ip}]: container log file /var/log/pods/{service}_{hex_id} size {num}GB exceeds limit",
            f"[{ts}] [ERROR] [{service}] Pod {service}-{hex_id} evicted: container log volume full",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "container log file",
            "exceeds limit",
            "evicted: container log volume full",
            impact_line,
        ], SCEN_EVI, RC_EVI_TRAIN, ACT_EVI_TRAIN, signature_profile="K8S_POD_LOG_VOLUME_FULL_EVICTION"),
    _create_template("INF_EVI_06", FAM_EVI, "Linux", "cgroup-fs", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] kernel: cgroup storage quota reached for container {hex_id} on {ip}",
            f"[{ts}] [ERROR] [{service}] systemd: killing task {num} due to cgroup disk constraint",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "cgroup storage quota reached for container",
            "killing task",
            "due to cgroup disk constraint",
            impact_line,
        ], SCEN_EVI, RC_EVI_TRAIN, ACT_EVI_TRAIN, signature_profile="LINUX_CGROUP_STORAGE_QUOTA"),
    _create_template("INF_EVI_07", FAM_EVI, "Kubernetes", "image-gc", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] kubelet[{ip}]: image garbage collection failed: disk usage 92% exceeds high threshold (85%)",
            f"[{ts}] [WARN] [{service}] Node has low disk space; evicting pod {service}-{hex_id}",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "image garbage collection failed: disk usage",
            "evicting pod",
            impact_line,
        ], SCEN_EVI, RC_EVI_VAL, ACT_EVI_VAL, signature_profile="K8S_IMAGE_GC_FAILED_EVICTION"),
    _create_template("INF_EVI_08", FAM_EVI, "AWS ECS", "ecs-agent", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] ecs-agent[{ip}]: task {hex_id} root volume utilization 100%; task stopped: CannotPullContainerError",
            f"[{ts}] [CRITICAL] [{service}] ECS task {service} evicted due to local volume exhaustion",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "root volume utilization 100%; task stopped",
            "ECS task",
            "evicted due to local volume exhaustion",
            impact_line,
        ], SCEN_EVI, RC_EVI_VAL, ACT_EVI_VAL, signature_profile="AWS_ECS_TASK_VOLUME_EXHAUSTION"),
    _create_template("INF_EVI_09", FAM_EVI, "Nomad", "nomad-client", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] nomad.client: alloc {hex_id}: disk limit exceeded: 2048MB > 2000MB on host {ip}",
            f"[{ts}] [WARN] [{service}] nomad: task {service} evicted and failed: AllocDiskExceeded",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "disk limit exceeded: 2048MB > 2000MB on host",
            "evicted and failed: AllocDiskExceeded",
            impact_line,
        ], SCEN_EVI, RC_EVI_TEST, ACT_EVI_TEST, signature_profile="NOMAD_ALLOC_DISK_EXCEEDED_EVICTION"),
    _create_template("INF_EVI_10", FAM_EVI, "Kubernetes", "kubelet", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] kubelet[{ip}]: attempt to evict pod {service}-{hex_id} due to hard eviction threshold nodefs.available<10%",
            f"[{ts}] [FATAL] [{service}] Pod status changed to Failed, message: \"Pod The node was low on resource: ephemeral-storage.\"",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "hard eviction threshold nodefs.available<10%",
            "Pod The node was low on resource: ephemeral-storage.",
            impact_line,
        ], SCEN_EVI, RC_EVI_TEST, ACT_EVI_TEST, signature_profile="K8S_HARD_EVICTION_NODEFS_LOW"),
]


INFRASTRUCTURE_TEMPLATES: list[LogTemplate] = (
    TEMPLATES_OOM +
    TEMPLATES_CPU_THROTTLING +
    TEMPLATES_INODE +
    TEMPLATES_NODE_NOT_READY +
    TEMPLATES_CRASHLOOP +
    TEMPLATES_STORAGE_EVICTION
)

assert len(INFRASTRUCTURE_TEMPLATES) == 60, f"Expected 60 templates in INFRASTRUCTURE, got {len(INFRASTRUCTURE_TEMPLATES)}"
