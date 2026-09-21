# Runbook: TLS Certificate Expiration and Handshake Failure

- **Incident Type**: SECURITY
- **Affected Services**: ingress-nginx, edge-proxy, api-gateway, payment-gateway
- **Severity Default**: P1_CRITICAL
- **Keywords**: CERT_HAS_EXPIRED, certificate has expired, SSL handshake failed, SEC_ERROR_EXPIRED_CERTIFICATE, x509: certificate has expired

## Symptoms
- Clients and external consumers receive `SSL handshake failed: CERT_HAS_EXPIRED` or `x509: certificate has expired`.
- External traffic to edge proxies or internal mTLS between microservices is completely blocked.
- Browser and mobile clients fail with security warnings.

## Root Cause Diagnosis
1. Inspect the certificate expiration timestamp on the target endpoint:
   `echo | openssl s_client -servername <hostname> -connect <hostname>:443 2>/dev/null | openssl x509 -noout -dates`
2. Check automated cert-manager or Let's Encrypt renewal logs in Kubernetes:
   `kubectl get certificate,certificaterequest,order,challenge -A`
   `kubectl logs -n cert-manager deploy/cert-manager`
3. Verify if ACME challenge validation failed due to DNS record drift or firewall rules blocking port 80.

## Immediate Mitigation
1. Force cert-manager to renew the expired certificate immediately:
   `cmctl renew <certificate_name> -n <namespace>`
2. If cert-manager is failing ACME challenges, manually inject a valid wildcard fallback certificate into the secret:
   `kubectl create secret tls <tls-secret-name> --cert=cert.pem --key=key.pem --dry-run=client -o yaml | kubectl apply -f -`
3. Reload ingress controller pods to pick up the updated secret without full cluster restart:
   `kubectl rollout restart deployment/ingress-nginx-controller -n ingress-nginx`

## Long-Term Remediation
- Set Prometheus alerts on `certmanager_certificate_expiration_timestamp_seconds` at 30, 14, and 7 days prior to expiry.
- Enable automatic renewal 30 days before expiration in cert-manager spec (`renewBefore: 720h`).
- Establish automated smoke tests checking SSL endpoint validity across staging and production domains.
