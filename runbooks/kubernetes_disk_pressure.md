# Runbook: Kubernetes Node Disk Pressure

- **Incident Type**: INFRASTRUCTURE
- **Affected Services**: kubelet, node-exporter, logging-agent, cluster-nodes
- **Severity Default**: P2_HIGH
- **Keywords**: NodeHasDiskPressure, DiskPressure, eviction manager, ephemeral-storage limit exceeded, no space left on device

## Symptoms
- Node condition reports `DiskPressure: True` in `kubectl describe node <node_name>`.
- Kubelet initiates aggressive pod eviction: `The node had condition: [NodeHasDiskPressure]`.
- System logs record `write /var/lib/docker/...: no space left on device`.
- Pod scheduling on the affected node ceases due to taint `node.kubernetes.io/disk-pressure`.

## Root Cause Diagnosis
1. Check disk utilization per filesystem on the node: `df -h /var/lib/kubelet /var/log /var/lib/containerd`.
2. Inspect large unrotated container log files under `/var/log/pods/` and `/var/log/containers/`.
3. Check orphaned container images or dangling layers: `crictl images` or `docker system df`.
4. Identify pods consuming high ephemeral storage with `kubectl top pods --containers`.

## Immediate Mitigation
1. Prune unused images and stopped containers on the node:
   `crictl rmi --prune`
2. Truncate unrotated log files:
   `find /var/log/pods/ -name "*.log" -size +1G -exec truncate -s 100M {} \;`
3. Remove stale build caches or temporary debug artifacts from host volumes.

## Long-Term Remediation
- Configure kubelet eviction thresholds properly (`imageGCHighThresholdPercent: 80`, `imageGCLowThresholdPercent: 70`).
- Ensure container log rotation is enforced in `/etc/docker/daemon.json` or containerd config.
- Enforce `ephemeral-storage` resource requests and limits in pod specs.
