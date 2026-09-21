# Runbook: Application CrashLoopBackOff

- **Incident Type**: APPLICATION
- **Affected Services**: payment-processor, auth-service, order-api, user-management
- **Severity Default**: P2_HIGH
- **Keywords**: CrashLoopBackOff, back-off restarting failed container, exit code 1, UnhandledException, panic, runtime error

## Symptoms
- Pod status shows `CrashLoopBackOff` in `kubectl get pods`.
- Container restarts repeatedly immediately following startup probe or entrypoint execution.
- Readiness checks consistently fail, preventing the pod from receiving traffic.

## Root Cause Diagnosis
1. Fetch previous container logs before termination:
   `kubectl logs <pod_name> --previous`
2. Check recent configuration map or secret changes that might contain syntax errors or missing environment variables.
3. Validate downstream dependency reachability (e.g. database host unreachable during startup migration).
4. Inspect entrypoint command and permission issues on mounted volumes.

## Immediate Mitigation
1. If caused by a bad recent deployment, rollback to the previous stable release:
   `kubectl rollout undo deployment/<deployment_name>`
2. If due to a missing environment variable or secret key, update the Secret/ConfigMap and trigger a rolling restart.
3. If database migrations failed halfway, run the manual schema reconciliation script.

## Long-Term Remediation
- Implement graceful degradation during startup when non-critical dependencies are temporarily unavailable.
- Add pre-deployment integration tests validating configuration schemas and secrets.
- Configure startup probes with appropriate initial delays to prevent premature kill signals.
