# Runbook: Application Thread Deadlock and CPU Starvation

- **Incident Type**: APPLICATION
- **Affected Services**: billing-engine, inventory-service, workflow-orchestrator
- **Severity Default**: P1_CRITICAL
- **Keywords**: deadlock, found 1 deadlock, Thread-Deadlock, lock acquisition timeout, synchronized block starvation, CPU 100%

## Symptoms
- JVM or process threads lock up; throughput plummets to zero while CPU or thread count remains elevated.
- Logs display `Found 1 deadlock` in thread dump or `LockAcquisitionException`.
- HTTP endpoints stop responding with `504 Gateway Timeout` or socket read timeouts.

## Root Cause Diagnosis
1. Generate a thread dump on the running JVM:
   `jcmd <pid> Thread.print > /tmp/threaddump.txt` or `kill -3 <pid>`
2. Inspect the deadlock section at the bottom of the thread dump for cyclic lock dependencies (`waiting to lock <0x...> which is held by thread X`).
3. Examine nested synchronization locks or inverse locking orders across concurrently executed codepaths.

## Immediate Mitigation
1. Restart the stalled container or pod instance to clear the deadlocked threads:
   `kubectl delete pod <pod_name>`
2. Drain traffic from the deadlocked node to prevent cascading client timeout buildup.
3. Lower thread pool max limit temporarily if thread explosion is exacerbating contention.

## Long-Term Remediation
- Eliminate nested synchronous locks across shared mutable state.
- Enforce strict hierarchical ordering of acquired locks across all calling services.
- Replace coarse-grained synchronization with lock-free concurrency utilities (`java.util.concurrent`, atomic references, read-write locks with bounded timeouts).
