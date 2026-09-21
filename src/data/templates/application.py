"""Structural log templates for the APPLICATION category (6 families, 60 templates).

Each family defines 10 templates: 6 TRAIN, 2 VALIDATION, 2 TEST.
Includes P4_LOW coverage, normalized metadata, and split-aware variant pools.
"""

from typing import Callable
from src.data.models import DatasetSplit, ImpactScenario, Severity
from src.data.templates.base import LogTemplate
from src.schemas.enums import IncidentFamily


FAM_LEAK = IncidentFamily.APP_MEMORY_LEAK
FAM_THP = IncidentFamily.APP_THREAD_POOL_EXHAUSTION
FAM_EXC = IncidentFamily.APP_UNHANDLED_EXCEPTION
FAM_SER = IncidentFamily.APP_SERIALIZATION_FAILURE
FAM_DI = IncidentFamily.APP_DEPENDENCY_INJECTION_FAILURE
FAM_SOF = IncidentFamily.APP_STACK_OVERFLOW

FAMILY_OBSERVED_MAP = {
    FAM_LEAK: "Application heap memory exhausted (OutOfMemoryError / heap limit reached), causing runtime crash or prolonged GC pauses.",
    FAM_THP: "Application worker thread pool saturated, causing incoming tasks to be rejected or queued indefinitely.",
    FAM_EXC: "Unhandled exception or panic during request processing resulting in internal server error (HTTP 500).",
    FAM_SER: "Payload deserialization or serialization failure due to schema mismatch, malformed bytes, or missing required fields.",
    FAM_DI: "Application startup failed due to unsatisfied bean, missing dependency provider, or circular dependency.",
    FAM_SOF: "Call stack limit exceeded (StackOverflowError / maximum call stack size exceeded) due to deep or infinite recursion.",
}

FAMILY_HYPOTHESES_MAP = {
    FAM_LEAK: ["unreleased object references", "unbounded cache growth", "event listener retention", "unclosed stream buffers", "circular references"],
    FAM_THP: ["blocking downstream calls", "spike in client requests", "deadlocked worker threads", "unreleased internal locks"],
    FAM_EXC: ["missing null check", "unvalidated input payload", "unhandled edge case"],
    FAM_SER: ["upstream producer contract change", "corrupted network payload", "incompatible reader/writer schema"],
    FAM_DI: ["misconfigured component scan", "missing configuration class", "circular bean reference"],
    FAM_SOF: ["unbounded recursion", "cyclic object traversal", "missing base case in recursive algorithm"],
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
# 1. APP_MEMORY_LEAK
# =========================================================================

SCEN_LEAK = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: JVM heap exhaustion causing multi-minute stop-the-world GC pauses; 100% gateway timeouts in {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Heap usage reached 96%; service {service} response latency elevated across endpoints",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: High frequency of full garbage collection cycles; minor latency degradation on {ip}",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Minor in-memory cache growth of 5MB in non-critical reporting module; auto-reclaimed during GC",
    ),
]

RC_LEAK_TRAIN = {
    "RC_TRAIN_1": "Application heap memory capacity exhausted in {service}, triggering OutOfMemoryError.",
    "RC_TRAIN_2": "Resident memory exceeded available application heap space on host {ip}, causing GC thrashing.",
    "RC_TRAIN_3": "Heap memory saturation causing persistent memory allocation failures in {service}.",
}
ACT_LEAK_TRAIN = {
    "ACT_TRAIN_1": "Capture application heap dump and analyze memory leak suspects, unreleased references, and unbounded caches.",
    "ACT_TRAIN_2": "Inspect heap memory allocation profile, check for circular object references, and adjust JVM/runtime memory flags.",
    "ACT_TRAIN_3": "Review stream buffer closures, evaluate event listener retention, and optimize object lifecycle in {service}.",
}

RC_LEAK_VAL = {
    "RC_VAL_1": "Progressive heap exhaustion triggered by lingering object references in {service}.",
}
ACT_LEAK_VAL = {
    "ACT_VAL_1": "Profile memory retention paths in {service} and verify garbage collection parameters on {ip}.",
}

RC_LEAK_TEST = {
    "RC_TEST_1": "Progressive memory allocation accumulation causing application memory exhaustion in {service} on {ip}.",
}
ACT_LEAK_TEST = {
    "ACT_TEST_1": "Analyze heap allocation profile for {service}, inspect memory leak suspects, and release static collection references.",
}

TEMPLATES_MEMORY_LEAK = [
    _create_template("APP_LEAK_01", FAM_LEAK, "Java", "JVM", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] java.lang.OutOfMemoryError: Java heap space",
            f"[{ts}] [WARN] [{service}] GC (Allocation Failure) [PSYoungGen: {num*10}M->{num*10}M(1024M)] [ParOldGen: 2040M->2040M(2048M)] on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "java.lang.OutOfMemoryError: Java heap space",
            "ParOldGen:",
            impact_line,
        ], SCEN_LEAK, RC_LEAK_TRAIN, ACT_LEAK_TRAIN, signature_profile="JAVA_HEAP_OOM_OLDGEN_FULL"),
    _create_template("APP_LEAK_02", FAM_LEAK, "Node.js", "V8", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] process.memoryUsage: heapUsed: 1489MB, heapTotal: 1512MB (external: {num*5}MB) on {ip}",
            f"[{ts}] [FATAL] [{service}] V8 memory leak detected: global array buffer holding {num*1000} disconnected WebSocket contexts",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "heapUsed: 1489MB, heapTotal: 1512MB",
            "V8 memory leak detected",
            impact_line,
        ], SCEN_LEAK, RC_LEAK_TRAIN, ACT_LEAK_TRAIN, signature_profile="NODEJS_V8_HEAP_LEAK"),
    _create_template("APP_LEAK_03", FAM_LEAK, "Python", "tracemalloc", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] tracemalloc: top memory consumer: /app/cache.py:42: size={num*50}MB, count={num*1000}",
            f"[{ts}] [ERROR] [{service}] Memory leak: persistent dict 'session_store' grew by {num}MB without key eviction on {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "tracemalloc: top memory consumer:",
            "Memory leak: persistent dict 'session_store' grew by",
            impact_line,
        ], SCEN_LEAK, RC_LEAK_TRAIN, ACT_LEAK_TRAIN, signature_profile="PYTHON_TRACEMALLOC_DICT_LEAK"),
    _create_template("APP_LEAK_04", FAM_LEAK, "Go", "pprof", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] pprof/heap: inuse_space reached {num*100}MB across {num*5000} allocated objects on host {ip}",
            f"[{ts}] [ERROR] [{service}] Goroutine leak suspected: active goroutines count is {num*1000} (baseline: 50)",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "pprof/heap: inuse_space reached",
            "Goroutine leak suspected: active goroutines count is",
            impact_line,
        ], SCEN_LEAK, RC_LEAK_TRAIN, ACT_LEAK_TRAIN, signature_profile="GO_HEAP_GOROUTINE_LEAK"),
    _create_template("APP_LEAK_05", FAM_LEAK, ".NET", "CLR", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] System.OutOfMemoryError: Insufficient memory to continue the execution of the program on {ip}",
            f"[{ts}] [WARN] [{service}] CLR GC Gen 2 heap size is {num*200}MB; Large Object Heap (LOH) fragmentation high",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "System.OutOfMemoryError: Insufficient memory to continue the execution",
            "Large Object Heap (LOH) fragmentation high",
            impact_line,
        ], SCEN_LEAK, RC_LEAK_TRAIN, ACT_LEAK_TRAIN, signature_profile="DOTNET_CLR_LOH_OOM"),
    _create_template("APP_LEAK_06", FAM_LEAK, "Java", "JVM/Metaspace", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] java.lang.OutOfMemoryError: Metaspace",
            f"[{ts}] [ERROR] [{service}] ClassLoader leak: {num*100} dynamic proxy classes loaded without garbage collection on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "java.lang.OutOfMemoryError: Metaspace",
            "ClassLoader leak:",
            impact_line,
        ], SCEN_LEAK, RC_LEAK_TRAIN, ACT_LEAK_TRAIN, signature_profile="JAVA_METASPACE_CLASSLOADER_LEAK"),
    _create_template("APP_LEAK_07", FAM_LEAK, "Python", "objgraph", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] objgraph: 450000 RequestContext instances uncollected in memory on {ip}",
            f"[{ts}] [ERROR] [{service}] Circular reference detected in middleware context preventing Python garbage collection",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "RequestContext instances uncollected in memory",
            "Circular reference detected in middleware context",
            impact_line,
        ], SCEN_LEAK, RC_LEAK_VAL, ACT_LEAK_VAL, signature_profile="PYTHON_CIRCULAR_REF_LEAK"),
    _create_template("APP_LEAK_08", FAM_LEAK, "Node.js", "heapdump", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] heapdump: generated /var/log/{service}/heap-{hex_id}.heapsnapshot (size: {num*100}MB)",
            f"[{ts}] [ERROR] [{service}] Retaining tree shows unevicted Map entries in connectionManager on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "heapdump: generated",
            "Retaining tree shows unevicted Map entries in connectionManager",
            impact_line,
        ], SCEN_LEAK, RC_LEAK_VAL, ACT_LEAK_VAL, signature_profile="NODEJS_MAP_RETAINING_TREE_LEAK"),
    _create_template("APP_LEAK_09", FAM_LEAK, "C++", "valgrind", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] valgrind: {num*10}MB in {num} blocks are definitely lost in loss record 1 of 5 on {ip}",
            f"[{ts}] [WARN] [{service}] malloc() without free() in PacketParser::processPayload(id={hex_id})",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "definitely lost in loss record",
            "malloc() without free() in PacketParser::processPayload",
            impact_line,
        ], SCEN_LEAK, RC_LEAK_TEST, ACT_LEAK_TEST, signature_profile="CPP_MALLOC_UNFREED_LEAK"),
    _create_template("APP_LEAK_10", FAM_LEAK, "Rust", "jemalloc", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] jemalloc: allocated: {num*100}MB, active: {num*120}MB, resident: {num*130}MB on {ip}",
            f"[{ts}] [ERROR] [{service}] Memory leak: Arc<RwLock<Buffer>> reference cycle prevented memory reclamation in thread {hex_id}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "jemalloc: allocated:",
            "Arc<RwLock<Buffer>> reference cycle prevented memory reclamation",
            impact_line,
        ], SCEN_LEAK, RC_LEAK_TEST, ACT_LEAK_TEST, signature_profile="RUST_ARC_CYCLE_LEAK"),
]


# =========================================================================
# 2. APP_THREAD_POOL_EXHAUSTION
# =========================================================================

SCEN_THP = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Web server thread pool 100% exhausted; HTTP requests queued or rejected across {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Worker thread pool active count at 200/200; request processing latency spiked on {ip}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Async task executor queue backlog exceeded 500 tasks; shedding low priority jobs",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Isolated worker thread rejection on background indexing task; retry worker processed task after 100ms",
    ),
]

RC_THP_TRAIN = {
    "RC_TRAIN_1": "Application worker thread pool capacity exhausted, preventing task execution in {service}.",
    "RC_TRAIN_2": "Maximum available worker thread execution limit reached on host {ip}, rejecting incoming tasks.",
    "RC_THP_TRAIN_3": "Worker thread pool exhaustion on {ip}, causing task execution rejection and queuing.",
}
ACT_THP_TRAIN = {
    "ACT_TRAIN_1": "Inspect thread dump for threads blocked on downstream HTTP/database calls or unreleased internal locks in {service}.",
    "ACT_TRAIN_2": "Tune max thread pool size, examine concurrency spikes, and implement circuit breakers on downstream dependencies.",
    "ACT_TRAIN_3": "Review worker queue capacity, inspect thread holding durations, and optimize asynchronous task scheduling.",
}

RC_THP_VAL = {
    "RC_VAL_1": "Thread pool task queue saturated causing task rejection in {service} on {ip}.",
}
ACT_THP_VAL = {
    "ACT_VAL_1": "Increase thread pool task queue capacity and scale application instances on {ip}.",
}

RC_THP_TEST = {
    "RC_TEST_1": "Worker thread pool exhaustion resulting in task rejection and request queuing in {service}.",
}
ACT_THP_TEST = {
    "ACT_TEST_1": "Review thread pool saturation metrics and implement request rate limiting for {service}.",
}

TEMPLATES_THREAD_POOL = [
    _create_template("APP_THP_01", FAM_THP, "Tomcat", "JVM", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] org.apache.tomcat.util.threads.ThreadPoolExecutor: All threads (200) are currently busy, waiting. Total requests: {num*100}",
            f"[{ts}] [WARN] [{service}] Endpoint /checkout request queue full: connection rejected on {ip}:8080",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "All threads (200) are currently busy, waiting",
            "request queue full: connection rejected on",
            impact_line,
        ], SCEN_THP, RC_THP_TRAIN, ACT_THP_TRAIN, signature_profile="TOMCAT_THREAD_POOL_EXHAUSTED"),
    _create_template("APP_THP_02", FAM_THP, "Java/Spring", "JVM", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] java.util.concurrent.RejectedExecutionException: Task com.localops.task.ProcessPayment@{hex_id} rejected from ThreadPoolExecutor [Running, pool size = 50, active threads = 50, queued tasks = 1000]",
            f"[{ts}] [FATAL] [{service}] Thread pool saturation on host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "RejectedExecutionException: Task",
            "active threads = 50, queued tasks = 1000",
            impact_line,
        ], SCEN_THP, RC_THP_TRAIN, ACT_THP_TRAIN, signature_profile="JAVA_REJECTED_EXECUTION_EXCEPTION"),
    _create_template("APP_THP_03", FAM_THP, "Python", "gunicorn", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [CRITICAL] [{service}] [CRITICAL] WORKER TIMEOUT (pid:{num*100}) on host {ip}",
            f"[{ts}] [ERROR] [{service}] gunicorn.error: Worker thread stalled for {num}s on synchronous HTTP call; killing worker",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "[CRITICAL] WORKER TIMEOUT",
            "Worker thread stalled for",
            impact_line,
        ], SCEN_THP, RC_THP_TRAIN, ACT_THP_TRAIN, signature_profile="GUNICORN_WORKER_TIMEOUT"),
    _create_template("APP_THP_04", FAM_THP, "Python", "uvicorn", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] asyncio: Task was destroyed but it is pending! Task count: {num*1000} backlog",
            f"[{ts}] [WARN] [{service}] uvicorn.error: Event loop execution blocked for {num*50}ms by synchronous blocking function on {ip}",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Task was destroyed but it is pending!",
            "Event loop execution blocked for",
            impact_line,
        ], SCEN_THP, RC_THP_TRAIN, ACT_THP_TRAIN, signature_profile="UVICORN_EVENT_LOOP_BLOCKED"),
    _create_template("APP_THP_05", FAM_THP, ".NET", "CLR", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] System.InvalidOperationException: ThreadPool starvation detected: 0 available worker threads out of 100 on {ip}",
            f"[{ts}] [WARN] [{service}] ThreadPool.GetAvailableThreads returned min threads: pending work items: {num}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ThreadPool starvation detected: 0 available worker threads",
            "pending work items:",
            impact_line,
        ], SCEN_THP, RC_THP_TRAIN, ACT_THP_TRAIN, signature_profile="DOTNET_THREADPOOL_STARVATION"),
    _create_template("APP_THP_06", FAM_THP, "Node.js", "libuv", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] libuv: UV_THREADPOOL_SIZE=4 exhausted; DNS resolution and crypto calls queuing (queue depth: {num})",
            f"[{ts}] [WARN] [{service}] Worker threads latency spike: crypto.pbkdf2 taking > 5000ms on {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "UV_THREADPOOL_SIZE=4 exhausted",
            "DNS resolution and crypto calls queuing",
            impact_line,
        ], SCEN_THP, RC_THP_TRAIN, ACT_THP_TRAIN, signature_profile="LIBUV_THREADPOOL_SIZE_EXHAUSTED"),
    _create_template("APP_THP_07", FAM_THP, "Java", "Jetty", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] org.eclipse.jetty.util.thread.QueuedThreadPool: QueuedThreadPool[qtp{hex_id}]@200/200,jobs={num*10} is at max capacity on {ip}",
            f"[{ts}] [ERROR] [{service}] Jetty Server rejected incoming connection: Insufficient threads in pool",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "QueuedThreadPool[qtp",
            "is at max capacity on",
            "Insufficient threads in pool",
            impact_line,
        ], SCEN_THP, RC_THP_VAL, ACT_THP_VAL, signature_profile="JETTY_QUEUED_THREAD_POOL_MAX"),
    _create_template("APP_THP_08", FAM_THP, "Go", "goroutines", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] worker pool: worker_count: 64, job_queue: 5000 (channel full: worker queue blocked) on {ip}",
            f"[{ts}] [WARN] [{service}] HTTP handler dropped request {hex_id}: server worker pool saturated",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "worker_count: 64, job_queue: 5000 (channel full: worker queue blocked)",
            "server worker pool saturated",
            impact_line,
        ], SCEN_THP, RC_THP_VAL, ACT_THP_VAL, signature_profile="GO_WORKER_CHANNEL_FULL"),
    _create_template("APP_THP_09", FAM_THP, "Celery", "Python", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] celery.worker: Task queue full: Celery worker concurrency limit (16) reached on host {ip}",
            f"[{ts}] [WARN] [{service}] Unacknowledged tasks piling up: 850 tasks waiting for available worker process",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Task queue full: Celery worker concurrency limit",
            "tasks waiting for available worker process",
            impact_line,
        ], SCEN_THP, RC_THP_TEST, ACT_THP_TEST, signature_profile="CELERY_WORKER_CONCURRENCY_REACHED"),
    _create_template("APP_THP_10", FAM_THP, "Ruby", "Puma", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] puma: thread pool capacity exhausted (max: 16, current: 16, backlog: {num*10}) on {ip}",
            f"[{ts}] [WARN] [{service}] Client request dropped: Puma server request backlog full",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "thread pool capacity exhausted (max: 16, current: 16, backlog:",
            "Puma server request backlog full",
            impact_line,
        ], SCEN_THP, RC_THP_TEST, ACT_THP_TEST, signature_profile="PUMA_THREAD_POOL_EXHAUSTED"),
]


# =========================================================================
# 3. APP_UNHANDLED_EXCEPTION
# =========================================================================

FAM_EXC = IncidentFamily.APP_UNHANDLED_EXCEPTION

SCEN_EXC = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: 100% of order submissions crashing with 500 Internal Server Error in {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Unhandled exception spike causing 40% request failures on checkout endpoint on {ip}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Isolated unhandled NullPointer in auxiliary telemetry handler; request failed gracefully",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Handled exception in non-critical user preference parsing; fell back to default profile",
    ),
]

RC_EXC_TRAIN = {
    "RC_TRAIN_1": "Unhandled application exception in request handler resulting in HTTP 500 error in {service}.",
    "RC_TRAIN_2": "Null pointer or nil object dereference in processing logic on host {ip}.",
    "RC_TRAIN_3": "Unchecked runtime exception crashing application request execution thread.",
}
ACT_EXC_TRAIN = {
    "ACT_TRAIN_1": "Examine exception stack trace and add null checks / input validation in {service}.",
    "ACT_TRAIN_2": "Deploy hotfix addressing unhandled runtime condition in request handling routine.",
    "ACT_EXC_TRAIN_3": "Wrap critical execution blocks with defensive try-catch handlers and add integration tests.",
}

RC_EXC_VAL = {
    "RC_VAL_1": "Uncaught runtime exception causing request failure in {service} on host {ip}.",
}
ACT_EXC_VAL = {
    "ACT_VAL_1": "Inspect application stack trace and deploy patch for unhandled exception in {service}.",
}

RC_EXC_TEST = {
    "RC_TEST_1": "Unhandled runtime failure terminating request execution in {service}.",
}
ACT_EXC_TEST = {
    "ACT_TEST_1": "Fix bug in exception-raising code path and verify test coverage for edge case in {service}.",
}

TEMPLATES_UNHANDLED_EXCEPTION = [
    _create_template("APP_EXC_01", FAM_EXC, "Java", "JVM", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] java.lang.NullPointerException: Cannot invoke \"String.length()\" because \"account.getEmail()\" is null",
            f"[{ts}] [ERROR] [{service}] at com.localops.service.AccountService.validateAccount(AccountService.java:{num}) on host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "java.lang.NullPointerException: Cannot invoke",
            "at com.localops.service.AccountService.validateAccount",
            impact_line,
        ], SCEN_EXC, RC_EXC_TRAIN, ACT_EXC_TRAIN, signature_profile="JAVA_NULL_POINTER_EXCEPTION"),
    _create_template("APP_EXC_02", FAM_EXC, "Python", "FastAPI", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Traceback (most recent call last): File \"/app/routers/payment.py\", line 84, in process_payment",
            f"[{ts}] [ERROR] [{service}] ZeroDivisionError: division by zero in calculate_fee(amount={num}) on {ip}",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Traceback (most recent call last):",
            "ZeroDivisionError: division by zero",
            impact_line,
        ], SCEN_EXC, RC_EXC_TRAIN, ACT_EXC_TRAIN, signature_profile="PYTHON_ZERO_DIVISION_ERROR"),
    _create_template("APP_EXC_03", FAM_EXC, "Node.js", "Express", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] TypeError: Cannot read properties of undefined (reading 'billing_address')",
            f"[{ts}] [ERROR] [{service}] at formatInvoice (/app/dist/invoice.js:{num}:18) while handling request {hex_id} on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "TypeError: Cannot read properties of undefined (reading 'billing_address')",
            "while handling request",
            impact_line,
        ], SCEN_EXC, RC_EXC_TRAIN, ACT_EXC_TRAIN, signature_profile="NODEJS_TYPEERROR_UNDEFINED"),
    _create_template("APP_EXC_04", FAM_EXC, "Go", "Gin", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] [Recovery] panic recovered: runtime error: index out of range [{num}] with length 5",
            f"[{ts}] [ERROR] [{service}] goroutine 42 [running]: github.com/gin-gonic/gin.(*Context).Next(0x{hex_id}) on {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "panic recovered: runtime error: index out of range",
            "github.com/gin-gonic/gin",
            impact_line,
        ], SCEN_EXC, RC_EXC_TRAIN, ACT_EXC_TRAIN, signature_profile="GO_INDEX_OUT_OF_RANGE_PANIC"),
    _create_template("APP_EXC_05", FAM_EXC, "Ruby", "Rails", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] ActionView::Template::Error: undefined method `total_amount' for nil:NilClass",
            f"[{ts}] [ERROR] [{service}] app/views/orders/show.html.erb:14:in `_app_views_orders_show_html_erb' on host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ActionView::Template::Error: undefined method",
            "for nil:NilClass",
            impact_line,
        ], SCEN_EXC, RC_EXC_TRAIN, ACT_EXC_TRAIN, signature_profile="RAILS_NIL_CLASS_METHOD_ERROR"),
    _create_template("APP_EXC_06", FAM_EXC, ".NET", "ASP.NET", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] System.NullReferenceException: Object reference not set to an instance of an object.",
            f"[{ts}] [ERROR] [{service}] at LocalOps.Controllers.CheckoutController.SubmitOrder(OrderRequest req) in /src/Controllers/Checkout.cs:line {num} on {ip}",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "System.NullReferenceException: Object reference not set to an instance of an object.",
            "LocalOps.Controllers.CheckoutController.SubmitOrder",
            impact_line,
        ], SCEN_EXC, RC_EXC_TRAIN, ACT_EXC_TRAIN, signature_profile="DOTNET_NULL_REFERENCE_EXCEPTION"),
    _create_template("APP_EXC_07", FAM_EXC, "Python", "Django", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] django.request: Internal Server Error: /api/v1/user/profile/",
            f"[{ts}] [ERROR] [{service}] AttributeError: 'AnonymousUser' object has no attribute 'profile_id' for request {hex_id} on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Internal Server Error: /api/v1/user/profile/",
            "AttributeError: 'AnonymousUser' object has no attribute",
            impact_line,
        ], SCEN_EXC, RC_EXC_VAL, ACT_EXC_VAL, signature_profile="DJANGO_ANONYMOUS_USER_ATTRIBUTE_ERROR"),
    _create_template("APP_EXC_08", FAM_EXC, "Rust", "Actix", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] actix_web::middleware::logger: panic in request handler: called `Option::unwrap()` on a `None` value",
            f"[{ts}] [FATAL] [{service}] thread 'actix-rt:worker-1' panicked at src/handlers/payment.rs:{num}:24 on {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "panic in request handler: called `Option::unwrap()` on a `None` value",
            "thread 'actix-rt:worker-1' panicked",
            impact_line,
        ], SCEN_EXC, RC_EXC_VAL, ACT_EXC_VAL, signature_profile="ACTIX_OPTION_UNWRAP_NONE_PANIC"),
    _create_template("APP_EXC_09", FAM_EXC, "PHP", "Laravel", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [CRITICAL] [{service}] production.ERROR: Call to a member function getStatus() on null {{\"exception\":\"[object] (Error(code: 0): Call to a member function getStatus() on null at /var/www/app/Http/Controllers/OrderController.php:{num})\"}}",
            f"[{ts}] [ERROR] [{service}] Request {hex_id} failed on node {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Call to a member function getStatus() on null",
            "OrderController.php:",
            impact_line,
        ], SCEN_EXC, RC_EXC_TEST, ACT_EXC_TEST, signature_profile="LARAVEL_MEMBER_FUNCTION_ON_NULL"),
    _create_template("APP_EXC_10", FAM_EXC, "Go", "net/http", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] http: panic serving {ip}:49202: runtime error: invalid memory address or nil pointer dereference",
            f"[{ts}] [FATAL] [{service}] goroutine {num} [running]: main.(*Server).handleCheckout(0x{hex_id}, ...)",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "http: panic serving",
            "runtime error: invalid memory address or nil pointer dereference",
            impact_line,
        ], SCEN_EXC, RC_EXC_TEST, ACT_EXC_TEST, signature_profile="GO_HTTP_NIL_POINTER_PANIC"),
]


# =========================================================================
# 4. APP_SERIALIZATION_FAILURE
# =========================================================================

FAM_SER = IncidentFamily.APP_SERIALIZATION_FAILURE

SCEN_SER = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: All webhook ingestion failing; upstream payload changes broke schema parser on {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: 30% serialization failure rate on payment callback handler",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single malformed JSON request dropped by API parser; bad client payload",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Handled serialization warning on non-critical optional attribute; defaulted field successfully",
    ),
]

RC_SER_TRAIN = {
    "RC_TRAIN_1": "Payload deserialization failure caused by schema mismatch or malformed JSON payload in {service}.",
    "RC_TRAIN_2": "Upstream service returned unexpected HTML error page instead of expected JSON payload on {ip}.",
    "RC_TRAIN_3": "Protocol buffer or Avro schema evolution breaking backward compatibility in {service}.",
}
ACT_SER_TRAIN = {
    "ACT_TRAIN_1": "Validate upstream request payload against OpenAPI schema and enforce strict request body validation.",
    "ACT_SER_TRAIN_2": "Handle non-JSON responses defensively and configure downstream HTTP error status checks.",
    "ACT_TRAIN_3": "Update protobuf/JSON schema definitions with backward-compatible default fields.",
}

RC_SER_VAL = {
    "RC_VAL_1": "Data format parsing error due to corrupt or schema-incompatible payload on host {ip}.",
}
ACT_SER_VAL = {
    "ACT_VAL_1": "Verify payload format compatibility and update deserializer schema configuration on {ip}.",
}

RC_SER_TEST_DEFAULT = {
    "RC_TEST_1": "Payload decode error caused by incompatible wire format or protocol specification mismatch on {ip}.",
}
ACT_SER_TEST_DEFAULT = {
    "ACT_TEST_1": "Inspect payload wire format and ensure sender and receiver schema definitions match.",
}

# Specific technology-appropriate variants for Rust serde_json missing field (APP_SER_09)
RC_SER_RUST_MISSING_FIELD = {
    "RC_TEST_1": "JSON deserialization failure due to missing required field `customer_id` in client payload for {service}.",
}
ACT_SER_RUST_MISSING_FIELD = {
    "ACT_TEST_1": "Verify client sends required `customer_id` field or mark the struct field as Option in Rust deserializer.",
}

TEMPLATES_SERIALIZATION = [
    _create_template("APP_SER_01", FAM_SER, "Java/Jackson", "JVM", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] com.fasterxml.jackson.databind.JsonMappingException: Unexpected character ('<' (code 60)): expected a valid value (JSON String, Number, Array, Object or token)",
            f"[{ts}] [ERROR] [{service}] Failed to deserialize HTTP response body: expected JSON, received HTML error page from {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "com.fasterxml.jackson.databind.JsonMappingException: Unexpected character ('<'",
            "Failed to deserialize HTTP response body: expected JSON, received HTML",
            impact_line,
        ], SCEN_SER, RC_SER_TRAIN, ACT_SER_TRAIN, signature_profile="JACKSON_UNEXPECTED_HTML_CHAR"),
    _create_template("APP_SER_02", FAM_SER, "Python/Pydantic", "CPython", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] pydantic.error_wrappers.ValidationError: 1 validation error for OrderPayload",
            f"[{ts}] [ERROR] [{service}] transaction_amount: field required [type=value_error.missing, input_value={{'order_id': '{hex_id}'}}]",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "pydantic.error_wrappers.ValidationError: 1 validation error for OrderPayload",
            "field required [type=value_error.missing",
            impact_line,
        ], SCEN_SER, RC_SER_TRAIN, ACT_SER_TRAIN, signature_profile="PYDANTIC_FIELD_REQUIRED_MISSING"),
    _create_template("APP_SER_03", FAM_SER, "Go/Protobuf", "Go", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] proto: cannot parse invalid wire-format data in message OrderEvent",
            f"[{ts}] [ERROR] [{service}] proto.Unmarshal failed: wire type 7 exceeds maximum permitted on {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "proto: cannot parse invalid wire-format data",
            "proto.Unmarshal failed",
            impact_line,
        ], SCEN_SER, RC_SER_TRAIN, ACT_SER_TRAIN, signature_profile="PROTOBUF_INVALID_WIRE_FORMAT"),
    _create_template("APP_SER_04", FAM_SER, "Node.js", "V8", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] SyntaxError: Unexpected token < in JSON at position 0",
            f"[{ts}] [ERROR] [{service}] at JSON.parse (<anonymous>) while parsing body from upstream gateway {ip}",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "SyntaxError: Unexpected token < in JSON at position 0",
            "while parsing body from upstream gateway",
            impact_line,
        ], SCEN_SER, RC_SER_TRAIN, ACT_SER_TRAIN, signature_profile="NODEJS_JSON_PARSE_UNEXPECTED_TOKEN"),
    _create_template("APP_SER_05", FAM_SER, ".NET", "System.Text.Json", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] System.Text.Json.JsonException: The JSON value could not be converted to System.Int64. Path: $.orderId | LineNumber: {num}",
            f"[{ts}] [ERROR] [{service}] Deserialization aborted for incoming transaction request id {hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "System.Text.Json.JsonException: The JSON value could not be converted",
            "Deserialization aborted for incoming transaction request",
            impact_line,
        ], SCEN_SER, RC_SER_TRAIN, ACT_SER_TRAIN, signature_profile="DOTNET_JSON_INT64_CONVERSION_ERROR"),
    _create_template("APP_SER_06", FAM_SER, "Apache Avro", "JVM", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] org.apache.avro.AvroTypeException: Found string, expecting union; schema resolution failed",
            f"[{ts}] [ERROR] [{service}] Incompatible reader and writer schemas for topic orders-avro on {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "org.apache.avro.AvroTypeException: Found string, expecting union",
            "Incompatible reader and writer schemas",
            impact_line,
        ], SCEN_SER, RC_SER_TRAIN, ACT_SER_TRAIN, signature_profile="AVRO_SCHEMA_RESOLUTION_FAILED"),
    _create_template("APP_SER_07", FAM_SER, "Python/Msgpack", "CPython", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] msgpack.exceptions.FormatError: invalid byte: 0x48 in format header",
            f"[{ts}] [ERROR] [{service}] Unpack failed: Corrupt binary payload from upstream RPC peer {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "msgpack.exceptions.FormatError: invalid byte:",
            "Corrupt binary payload from upstream RPC peer",
            impact_line,
        ], SCEN_SER, RC_SER_VAL, ACT_SER_VAL, signature_profile="MSGPACK_FORMAT_HEADER_CORRUPT"),
    _create_template("APP_SER_08", FAM_SER, "Java/Jackson", "JVM", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] com.fasterxml.jackson.databind.exc.UnrecognizedPropertyException: Unrecognized field \"discountCode\" (class com.localops.dto.OrderDTO), not marked as ignorable",
            f"[{ts}] [WARN] [{service}] Strict JSON deserialization rejected request {hex_id}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "UnrecognizedPropertyException: Unrecognized field",
            "Strict JSON deserialization rejected request",
            impact_line,
        ], SCEN_SER, RC_SER_VAL, ACT_SER_VAL, signature_profile="JACKSON_UNRECOGNIZED_FIELD_REJECTED"),
    _create_template("APP_SER_09", FAM_SER, "Rust/Serde", "Rust", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] serde_json::error::Error: missing field `customer_id` at line 1 column {num}",
            f"[{ts}] [ERROR] [{service}] Failed parsing JSON body from client on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "serde_json::error::Error: missing field `customer_id`",
            "Failed parsing JSON body from client on",
            impact_line,
        ], SCEN_SER, RC_SER_RUST_MISSING_FIELD, ACT_SER_RUST_MISSING_FIELD, signature_profile="RUST_SERDE_JSON_MISSING_FIELD"),
    _create_template("APP_SER_10", FAM_SER, "Apache Thrift", "C++", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] apache::thrift::protocol::TProtocolException: Bad version identifier in TBinaryProtocol::readMessageBegin on {ip}",
            f"[{ts}] [FATAL] [{service}] Thrift transport decode error: binary header mismatch",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "TProtocolException: Bad version identifier in TBinaryProtocol::readMessageBegin",
            "Thrift transport decode error: binary header mismatch",
            impact_line,
        ], SCEN_SER, RC_SER_TEST_DEFAULT, ACT_SER_TEST_DEFAULT, signature_profile="THRIFT_BAD_VERSION_IDENTIFIER"),
]


# =========================================================================
# 5. APP_STACK_OVERFLOW
# =========================================================================

FAM_STK = IncidentFamily.APP_STACK_OVERFLOW

SCEN_STK = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Recursive call crashing API worker threads; 100% thread termination in {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Call stack exhaustion on complex JSON recursive resolver on {ip}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Stack overflow in non-critical regex tree validation; worker restarted",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Deep recursion guard triggered and aborted safely; returned 400 Bad Request to client without crash",
    ),
]

RC_STK_TRAIN = {
    "RC_TRAIN_1": "Infinite recursion in application function without terminating base condition in {service}.",
    "RC_TRAIN_2": "Circular object graph traversal triggering call stack frame overflow in {service}.",
    "RC_TRAIN_3": "Recursive regex evaluation or unconstrained tree parsing exhausting call stack on {ip}.",
}
ACT_STK_TRAIN = {
    "ACT_TRAIN_1": "Add recursion termination base condition or convert recursive routine to iterative loop.",
    "ACT_TRAIN_2": "Add cycle detection visited set to circular graph serializer in {service}.",
    "ACT_TRAIN_3": "Limit maximum recursion depth and increase stack size configuration.",
}

RC_STK_VAL = {
    "RC_VAL_1": "Call stack frame limit exceeded due to deep recursive calls in {service} on host {ip}.",
}
ACT_STK_VAL = {
    "ACT_VAL_1": "Refactor recursive method to iterative data structures to prevent call stack overflow.",
}

RC_STK_TEST = {
    "RC_TEST_1": "Unbounded recursive traversal exhausting available call stack memory in {service}.",
}
ACT_STK_TEST = {
    "ACT_TEST_1": "Implement recursion depth guard and cycle detection in application logic for {service}.",
}

TEMPLATES_STACK_OVERFLOW = [
    _create_template("APP_STK_01", FAM_STK, "Java", "JVM", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] java.lang.StackOverflowError",
            f"[{ts}] [ERROR] [{service}] at com.localops.model.Category.getChildren(Category.java:{num}) - repeated 1024 times on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "java.lang.StackOverflowError",
            "repeated 1024 times on",
            impact_line,
        ], SCEN_STK, RC_STK_TRAIN, ACT_STK_TRAIN, signature_profile="JAVA_STACK_OVERFLOW_ERROR"),
    _create_template("APP_STK_02", FAM_STK, "Python", "CPython", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] RecursionError: maximum recursion depth exceeded while calling a Python object",
            f"[{ts}] [ERROR] [{service}] File \"/app/tree.py\", line 52, in traverse (repeated {num*10} times) on host {ip}",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "RecursionError: maximum recursion depth exceeded while calling a Python object",
            impact_line,
        ], SCEN_STK, RC_STK_TRAIN, ACT_STK_TRAIN, signature_profile="PYTHON_RECURSION_ERROR_DEPTH_EXCEEDED"),
    _create_template("APP_STK_03", FAM_STK, "Node.js", "V8", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] RangeError: Maximum call stack size exceeded",
            f"[{ts}] [FATAL] [{service}] at resolveDependency (/app/dist/graph.js:88:14) on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "RangeError: Maximum call stack size exceeded",
            "at resolveDependency",
            impact_line,
        ], SCEN_STK, RC_STK_TRAIN, ACT_STK_TRAIN, signature_profile="NODEJS_RANGE_ERROR_CALL_STACK"),
    _create_template("APP_STK_04", FAM_STK, "Go", "Go-runtime", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] runtime: goroutine stack exceeds 1000000000-byte limit",
            f"[{ts}] [FATAL] [{service}] fatal error: stack overflow on host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "runtime: goroutine stack exceeds 1000000000-byte limit",
            "fatal error: stack overflow on host",
            impact_line,
        ], SCEN_STK, RC_STK_TRAIN, ACT_STK_TRAIN, signature_profile="GO_GOROUTINE_STACK_OVERFLOW"),
    _create_template("APP_STK_05", FAM_STK, ".NET", "CLR", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] Process is terminating due to StackOverflowException.",
            f"[{ts}] [ERROR] [{service}] at LocalOps.Rules.Evaluator.EvaluateCondition(RuleNode node) on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Process is terminating due to StackOverflowException.",
            "EvaluateCondition(RuleNode node) on",
            impact_line,
        ], SCEN_STK, RC_STK_TRAIN, ACT_STK_TRAIN, signature_profile="DOTNET_STACK_OVERFLOW_EXCEPTION"),
    _create_template("APP_STK_06", FAM_STK, "Ruby", "YARV", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] SystemStackError: stack level too deep",
            f"[{ts}] [ERROR] [{service}] /app/app/models/category.rb:28:in `ancestors' on host {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "SystemStackError: stack level too deep",
            impact_line,
        ], SCEN_STK, RC_STK_TRAIN, ACT_STK_TRAIN, signature_profile="RUBY_SYSTEM_STACK_ERROR_DEEP"),
    _create_template("APP_STK_07", FAM_STK, "C++", "native", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] Segmentation fault: SIGSEGV (Address boundary error, stack pointer 0x7fff{hex_id} exceeded guard page) on {ip}",
            f"[{ts}] [ERROR] [{service}] Infinite recursion in JSONAST::clone()",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Segmentation fault: SIGSEGV (Address boundary error, stack pointer",
            "exceeded guard page",
            impact_line,
        ], SCEN_STK, RC_STK_VAL, ACT_STK_VAL, signature_profile="CPP_STACK_POINTER_GUARD_PAGE_SEGV"),
    _create_template("APP_STK_08", FAM_STK, "Rust", "rustc", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] fatal runtime error: stack overflow",
            f"[{ts}] [ERROR] [{service}] thread 'main' has overflowed its stack during recursive descent parsing on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "fatal runtime error: stack overflow",
            "has overflowed its stack during recursive descent parsing",
            impact_line,
        ], SCEN_STK, RC_STK_VAL, ACT_STK_VAL, signature_profile="RUST_STACK_OVERFLOW_DESCENT_PARSER"),
    _create_template("APP_STK_09", FAM_STK, "Python", "regex", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] re.error: catastrophic backtracking: maximum recursion depth exceeded during pattern matching on {ip}",
            f"[{ts}] [FATAL] [{service}] Regex pattern (a+)+$ stalled and crashed evaluation thread for request {hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "re.error: catastrophic backtracking: maximum recursion depth exceeded",
            impact_line,
        ], SCEN_STK, RC_STK_TEST, ACT_STK_TEST, signature_profile="PYTHON_REGEX_CATASTROPHIC_BACKTRACKING"),
    _create_template("APP_STK_10", FAM_STK, "Java", "Nashorn", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] jdk.nashorn.internal.runtime.ECMAException: RangeError: Maximum call stack size exceeded",
            f"[{ts}] [ERROR] [{service}] User-defined script execution terminated: stack overflow in engine evaluation on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "RangeError: Maximum call stack size exceeded",
            "User-defined script execution terminated: stack overflow",
            impact_line,
        ], SCEN_STK, RC_STK_TEST, ACT_STK_TEST, signature_profile="NASHORN_JS_CALL_STACK_EXCEEDED"),
]


# =========================================================================
# 6. APP_DEPENDENCY_INJECTION_FAILURE
# =========================================================================

FAM_DI = IncidentFamily.APP_DEPENDENCY_INJECTION_FAILURE

SCEN_DI = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Spring ApplicationContext failure; backend service unable to start on cluster",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Dependency injection container crashed on startup; deployment failed rollout",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Lazy-initialized optional bean failed injection; falling back to stub service",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Optional telemetry dependency injection failed; defaulted to no-op telemetry provider",
    ),
]

RC_DI_TRAIN = {
    "RC_TRAIN_1": "Dependency injection container failure caused by circular bean dependency or missing bean definition in {service}.",
    "RC_TRAIN_2": "Unsatisfied dependency: No qualifying bean found for autowired candidate in {service}.",
    "RC_TRAIN_3": "Bean creation exception during dependency graph resolution on host {ip}.",
}
ACT_DI_TRAIN = {
    "ACT_TRAIN_1": "Refactor circular dependencies using @Lazy or setter injection in {service}.",
    "ACT_TRAIN_2": "Declare missing bean configuration in ApplicationContext and verify component scanning path.",
    "ACT_TRAIN_3": "Check interface implementations and annotate unambiguous primary bean with @Primary.",
}

RC_DI_VAL = {
    "RC_VAL_1": "Application framework failed to inject required dependency during startup on {ip}.",
}
ACT_DI_VAL = {
    "ACT_VAL_1": "Verify dependency injection provider bindings and component annotations in {service}.",
}

RC_DI_TEST = {
    "RC_TEST_1": "Missing dependency registration or lifecycle initialization failure in {service} on {ip}.",
}
ACT_DI_TEST = {
    "ACT_TEST_1": "Register missing service implementation in DI container configuration for {service}.",
}

TEMPLATES_DEPENDENCY_INJECTION = [
    _create_template("APP_DI_01", FAM_DI, "Java/Spring", "JVM", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] org.springframework.beans.factory.UnsatisfiedDependencyException: Error creating bean with name 'orderController': Unsatisfied dependency expressed through field 'paymentService'",
            f"[{ts}] [ERROR] [{service}] Nested: NoSuchBeanDefinitionException: No qualifying bean of type 'com.localops.PaymentService' available on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "UnsatisfiedDependencyException: Error creating bean with name 'orderController'",
            "NoSuchBeanDefinitionException: No qualifying bean of type",
            impact_line,
        ], SCEN_DI, RC_DI_TRAIN, ACT_DI_TRAIN, signature_profile="SPRING_UNSATISFIED_DEPENDENCY_EXCEPTION"),
    _create_template("APP_DI_02", FAM_DI, "Java/Spring", "JVM", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] org.springframework.beans.factory.BeanCurrentlyInCreationException: Error creating bean with name 'serviceA': Requested bean is currently in creation: Is there an unresolvable circular reference?",
            f"[{ts}] [ERROR] [{service}] Circular dependency detected between ServiceA and ServiceB on host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "BeanCurrentlyInCreationException: Error creating bean with name",
            "Is there an unresolvable circular reference?",
            impact_line,
        ], SCEN_DI, RC_DI_TRAIN, ACT_DI_TRAIN, signature_profile="SPRING_CIRCULAR_BEAN_DEPENDENCY"),
    _create_template("APP_DI_03", FAM_DI, ".NET", "Microsoft.Extensions.DI", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] System.InvalidOperationException: Unable to resolve service for type 'LocalOps.Services.IPaymentGateway' while attempting to activate 'LocalOps.Controllers.OrdersController'.",
            f"[{ts}] [FATAL] [{service}] Dependency injection startup failed on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Unable to resolve service for type 'LocalOps.Services.IPaymentGateway'",
            "while attempting to activate",
            impact_line,
        ], SCEN_DI, RC_DI_TRAIN, ACT_DI_TRAIN, signature_profile="DOTNET_UNABLE_TO_RESOLVE_SERVICE_TYPE"),
    _create_template("APP_DI_04", FAM_DI, "Angular", "Node.js", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] NullInjectorError: R3InjectorError(AppServerModule)[AuthService -> HttpClient -> HttpClient]: NullInjectorError: No provider for HttpClient!",
            f"[{ts}] [FATAL] [{service}] Server-side rendering crashed due to missing HttpClientModule provider on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "NullInjectorError: R3InjectorError(AppServerModule)",
            "No provider for HttpClient!",
            impact_line,
        ], SCEN_DI, RC_DI_TRAIN, ACT_DI_TRAIN, signature_profile="ANGULAR_NULL_INJECTOR_ERROR"),
    _create_template("APP_DI_05", FAM_DI, "NestJS", "Node.js", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] [ExceptionHandler] Nest can't resolve dependencies of the OrderService (?). Please make sure that the argument DatabaseConnection at index [0] is available in the OrderModule context.",
            f"[{ts}] [FATAL] [{service}] Nest application initialization failed on {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Nest can't resolve dependencies of the OrderService",
            "Please make sure that the argument DatabaseConnection",
            impact_line,
        ], SCEN_DI, RC_DI_TRAIN, ACT_DI_TRAIN, signature_profile="NESTJS_UNRESOLVED_DEPENDENCY"),
    _create_template("APP_DI_06", FAM_DI, "Python", "injector", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] injector.UnsatisfiedRequirement: Unsatisfied requirement: <class 'app.interfaces.IEmailSender'>",
            f"[{ts}] [ERROR] [{service}] Dependency injection failure while binding dependencies in AppModule on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "injector.UnsatisfiedRequirement: Unsatisfied requirement:",
            "Dependency injection failure while binding dependencies",
            impact_line,
        ], SCEN_DI, RC_DI_TRAIN, ACT_DI_TRAIN, signature_profile="PYTHON_INJECTOR_UNSATISFIED_REQ"),
    _create_template("APP_DI_07", FAM_DI, "Go/Wire", "Go", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] wire: no provider found for *database.Connection (required by *server.Server)",
            f"[{ts}] [FATAL] [{service}] compile-time dependency injection generation failed for service on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "wire: no provider found for *database.Connection",
            impact_line,
        ], SCEN_DI, RC_DI_VAL, ACT_DI_VAL, signature_profile="GO_WIRE_NO_PROVIDER_FOUND"),
    _create_template("APP_DI_08", FAM_DI, "Java/CDI", "Jakarta", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] org.jboss.weld.exceptions.DeploymentException: WELD-001408: Unsatisfied dependencies for type SecurityManager with qualifiers @Default at injection point on {ip}",
            f"[{ts}] [FATAL] [{service}] Enterprise application deployment failed",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "WELD-001408: Unsatisfied dependencies for type SecurityManager",
            impact_line,
        ], SCEN_DI, RC_DI_VAL, ACT_DI_VAL, signature_profile="WELD_UNSATISFIED_DEPENDENCIES_CDI"),
    _create_template("APP_DI_09", FAM_DI, "PHP", "PHP-DI", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] DI\\Definition\\Exception\\InvalidDefinition: Entry \"App\\Billing\\StripeClient\" cannot be resolved: parameter \"apiKey\" has no value defined on {ip}",
            f"[{ts}] [FATAL] [{service}] Container compilation aborted for application",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Entry \"App\\Billing\\StripeClient\" cannot be resolved",
            "parameter \"apiKey\" has no value defined",
            impact_line,
        ], SCEN_DI, RC_DI_TEST, ACT_DI_TEST, signature_profile="PHP_DI_INVALID_DEFINITION_API_KEY"),
    _create_template("APP_DI_10", FAM_DI, "Java/Dagger", "JVM", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] [Dagger/MissingBinding] com.localops.repo.UserRepository cannot be provided without an @Provides-annotated method on {ip}",
            f"[{ts}] [FATAL] [{service}] Dagger AppComponent graph validation failed",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "[Dagger/MissingBinding] com.localops.repo.UserRepository cannot be provided",
            impact_line,
        ], SCEN_DI, RC_DI_TEST, ACT_DI_TEST, signature_profile="DAGGER_MISSING_BINDING_GRAPH"),
]


APPLICATION_TEMPLATES: list[LogTemplate] = (
    TEMPLATES_MEMORY_LEAK +
    TEMPLATES_THREAD_POOL +
    TEMPLATES_UNHANDLED_EXCEPTION +
    TEMPLATES_SERIALIZATION +
    TEMPLATES_STACK_OVERFLOW +
    TEMPLATES_DEPENDENCY_INJECTION
)

assert len(APPLICATION_TEMPLATES) == 60, f"Expected 60 templates in APPLICATION, got {len(APPLICATION_TEMPLATES)}"
