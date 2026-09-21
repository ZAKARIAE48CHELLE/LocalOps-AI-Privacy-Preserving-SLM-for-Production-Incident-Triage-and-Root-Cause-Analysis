# Runbook: Kubernetes Container OOMKilled

- **Incident Type**: INFRASTRUCTURE
- **Affected Services**: data-ingest, ml-worker, report-generator, search-indexer
- **Severity Default**: P1_CRITICAL
- **Keywords**: OOMKilled, exit code 137, terminated with exit code 137, Memory cgroup out of memory, memory limit exceeded

## Symptoms
- Pod status transitions to `OOMKilled` with exit code 137.
- `kubectl describe pod <pod_name>` shows `Last State: Terminated, Reason: OOMKilled, Exit Code: 137`.
- Container restarts abruptly during large batch processing or memory spikes.
- Service intermittently loses processing capacity as pods flap.

## Root Cause Diagnosis
1. Inspect container termination status and exit code:
   `kubectl get pods -l app=<service> -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[*].lastState.terminated.reason}{"\n"}{end}'`
2. Compare historical memory consumption against configured limits in Prometheus: `container_memory_working_set_bytes`.
3. Check for application memory leaks (unbounded collections, uncollected heap buffers, native memory leaks).
4. Verify if recent batch payloads or chunk sizes exceeded expected ingestion limits.

## Immediate Mitigation
1. Patch the deployment's memory limits temporarily to restore availability:
   `kubectl set resources deployment/<deployment_name> --limits=memory=4Gi --requests=memory=2Gi`
2. Scale up replica count to distribute high-volume payloads across more pods:
   `kubectl scale deployment/<deployment_name> --replicas=<count>`
3. Pause heavy non-essential background batch workers.

## Long-Term Remediation
- Set appropriate JVM heap flags (`-XX:MaxRAMPercentage=75.0`) or memory limits in container runtimes.
- Implement memory-efficient streaming processing rather than loading entire payloads into RAM.
- Establish Vertical Pod Autoscaler (VPA) in recommendation mode to establish baseline resource sizing.
