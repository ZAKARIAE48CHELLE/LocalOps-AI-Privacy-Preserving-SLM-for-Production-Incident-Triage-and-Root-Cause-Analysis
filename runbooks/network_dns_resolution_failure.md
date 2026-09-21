# Runbook: DNS Resolution and CoreDNS Failure

- **Incident Type**: NETWORK
- **Affected Services**: coredns, kube-dns, egress-proxy, api-clients
- **Severity Default**: P1_CRITICAL
- **Keywords**: dial tcp: lookup: no such host, Temporary failure in name resolution, CoreDNS upstream timeout, SERVFAIL, NXDOMAIN

## Symptoms
- Applications throw `lookup <service_name>: no such host` or `Temporary failure in name resolution`.
- Inter-pod communication halts across namespaces.
- CoreDNS pod logs report `[ERROR] plugin/errors: 2 <host> A: read udp <ip>: i/o timeout`.

## Root Cause Diagnosis
1. Verify CoreDNS pod status and resource utilization:
   `kubectl get pods -n kube-system -l k8s-app=kube-dns`
   `kubectl top pods -n kube-system -l k8s-app=kube-dns`
2. Test internal cluster resolution from a diagnostic pod:
   `kubectl run -it --rm --restart=Never dns-test --image=busybox:1.28 -- nslookup kubernetes.default`
3. Check upstream nameserver connectivity configured in `/etc/resolv.conf` or CoreDNS Corefile.
4. Inspect Conntrack table utilization on cluster worker nodes:
   `sysctl net.netfilter.nf_conntrack_count`

## Immediate Mitigation
1. Scale up CoreDNS deployment replicas to absorb query spikes:
   `kubectl scale deployment/coredns -n kube-system --replicas=5`
2. Restart unresponsive CoreDNS pods:
   `kubectl rollout restart deployment/coredns -n kube-system`
3. Enable NodeLocal DNSCache if not already enabled to reduce UDP connection tracking saturation.

## Long-Term Remediation
- Deploy NodeLocal DNSCache across all cluster nodes to serve DNS lookups locally over TCP.
- Tune `ndots:5` in application pod `dnsConfig` to reduce repetitive iterative search path lookups.
- Configure upstream recursive resolvers with robust redundancy and health monitoring.
