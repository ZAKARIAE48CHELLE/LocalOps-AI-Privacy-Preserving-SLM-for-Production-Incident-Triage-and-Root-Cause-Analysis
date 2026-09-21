"""Structural log templates for the SECURITY category (6 families, 60 templates).

Each family defines 10 templates: 6 TRAIN, 2 VALIDATION, 2 TEST.
Includes P4_LOW coverage, normalized metadata, and split-aware variant pools.
"""

from typing import Callable
from src.data.models import DatasetSplit, ImpactScenario, Severity
from src.data.templates.base import LogTemplate
from src.schemas.enums import IncidentFamily


FAM_TOK = IncidentFamily.SEC_CREDENTIAL_OR_TOKEN_EXPIRATION
FAM_RBC = IncidentFamily.SEC_PERMISSION_OR_RBAC_DENIED
FAM_LAK = IncidentFamily.SEC_SECRET_LEAKAGE
FAM_BRU = IncidentFamily.SEC_BRUTE_FORCE_ATTACK
FAM_CRS = IncidentFamily.SEC_CORS_POLICY_BLOCK
FAM_SSR = IncidentFamily.SEC_SSRF_OR_EGRESS_VIOLATION

FAMILY_OBSERVED_MAP = {
    FAM_TOK: "Authentication request rejected due to expired access token, certificate, or API credential.",
    FAM_RBC: "Authorization failed with HTTP 403 / AccessDenied due to missing required permissions or RBAC role.",
    FAM_LAK: "Plaintext credential, API key, or private secret exposed in application log output or diagnostics.",
    FAM_BRU: "High volume of failed authentication attempts exceeding rate-limit threshold detected from client IP.",
    FAM_CRS: "Cross-origin request blocked by browser or API gateway due to missing or disallowed Access-Control-Allow-Origin header.",
    FAM_SSR: "Outbound network request to restricted destination (e.g. link-local 169.254.169.254) blocked by security policy.",
}

FAMILY_HYPOTHESES_MAP = {
    FAM_TOK: ["failed token rotation daemon", "stale client cache", "misconfigured clock skew"],
    FAM_RBC: ["missing IAM role binding", "unauthorized service account", "privilege mismatch"],
    FAM_LAK: ["improper logging configuration", "debug mode enabled in production", "missing secret masking"],
    FAM_BRU: ["credential stuffing attack", "distributed dictionary attack", "compromised client botnet"],
    FAM_CRS: ["misconfigured origin whitelist", "missing preflight OPTIONS handler", "domain typo"],
    FAM_SSR: ["server-side request forgery attempt", "unvalidated user-supplied redirect", "malicious payload"],
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
# 1. SEC_CREDENTIAL_OR_TOKEN_EXPIRATION
# =========================================================================

SCEN_TOK = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: 100% of outbound payment gateway calls failing with 401 Unauthorized; API key expired",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: JWT signature verification failure spike; auth token expired for {service}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single service account token expired; background sync worker failing authentication",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Deprecated canary auth token expired without customer impact; background refresher renewed token",
    ),
]

RC_TOK_TRAIN = {
    "RC_TRAIN_1": "OAuth access token or API credential expired, causing authentication rejection in {service}.",
    "RC_TRAIN_2": "Expired JWT authentication token rejected by downstream authorization server on {ip}.",
    "RC_TRAIN_3": "Service account credentials expired, preventing authenticated API communication in {service}.",
}
ACT_TOK_TRAIN = {
    "ACT_TRAIN_1": "Trigger OAuth token refresh flow, verify automated rotation daemons, and inspect credential cache for {service}.",
    "ACT_TRAIN_2": "Rotate API keys immediately in secret manager and restart dependent worker pods.",
    "ACT_TRAIN_3": "Verify authentication provider JWKS endpoint reachability and refresh token cache.",
}

RC_TOK_VAL = {
    "RC_VAL_1": "Authentication token expired; cryptographic signature verification failed during API handshake on {ip}.",
}
ACT_TOK_VAL = {
    "ACT_VAL_1": "Validate token lifetime settings in identity provider and deploy renewed credentials to {service}.",
}

RC_TOK_TEST = {
    "RC_TEST_1": "Client credentials or security token lifetime elapsed, causing rejected requests on {ip}.",
}
ACT_TOK_TEST = {
    "ACT_TEST_1": "Issue fresh credentials from authorization server and confirm automated refresh daemon health for {service}.",
}

RC_TOK = {**RC_TOK_TRAIN, **RC_TOK_VAL, **RC_TOK_TEST}
ACT_TOK = {**ACT_TOK_TRAIN, **ACT_TOK_VAL, **ACT_TOK_TEST}

TEMPLATES_TOKEN = [
    _create_template("SEC_TOK_01", FAM_TOK, "OAuth/JWT", "Java/Spring", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num, token_expiry_ts="", **kwargs: [
            f"[{ts}] [WARN] [{service}] org.springframework.security.oauth2.jwt.JwtValidationException: An error occurred while attempting to decode the Jwt: Jwt expired at {token_expiry_ts or '2026-09-14T08:00:00Z'}",
            f"[{ts}] [ERROR] [{service}] HTTP 401 Unauthorized: token_expired: The access token expired {num} seconds ago",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "JwtValidationException: An error occurred while attempting to decode the Jwt: Jwt expired",
            "HTTP 401 Unauthorized: token_expired",
            impact_line,
        ], SCEN_TOK, RC_TOK, ACT_TOK,
        signature_profile="SPRING_JWT_EXPIRED",
        failure_mechanism="TOKEN_EXPIRED",
        expected_tokens=["JwtValidationException", "token_expired"],
        forbidden_tokens=["CORS", "brute-force", "credential stuffing"],
        expected_status_code=401),
    _create_template("SEC_TOK_02", FAM_TOK, "OAuth/JWT", "Python/FastAPI", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] jwt.exceptions.ExpiredSignatureError: Signature has expired for bearer token id {hex_id}",
            f"[{ts}] [WARN] [{service}] AuthMiddleware: rejected request from client {ip}: 401 TokenExpired",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "jwt.exceptions.ExpiredSignatureError: Signature has expired",
            "401 TokenExpired",
            impact_line,
        ], SCEN_TOK, RC_TOK, ACT_TOK, "PYJWT_SIGNATURE_EXPIRED"),
    _create_template("SEC_TOK_03", FAM_TOK, "AWS STS", "Python/Boto3", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] botocore.exceptions.ClientError: An error occurred (ExpiredToken): The security token included in the request is expired",
            f"[{ts}] [ERROR] [{service}] STS assume-role session token expired on {ip}; S3 put_object aborted",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "An error occurred (ExpiredToken): The security token included in the request is expired",
            "STS assume-role session token expired",
            impact_line,
        ], SCEN_TOK, RC_TOK, ACT_TOK, "AWS_STS_TOKEN_EXPIRED"),
    _create_template("SEC_TOK_04", FAM_TOK, "Stripe API", "Node.js", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] StripeAuthenticationError: Invalid API Key provided: sk_live_synth_{hex_id} has expired or been revoked",
            f"[{ts}] [ERROR] [{service}] Failed charging customer payment method: 401 Unauthorized response from api.stripe.com on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "StripeAuthenticationError: Invalid API Key provided",
            "has expired or been revoked",
            impact_line,
        ], SCEN_TOK, RC_TOK, ACT_TOK, "STRIPE_API_KEY_REVOKED"),
    _create_template("SEC_TOK_05", FAM_TOK, "HashiCorp Vault", "Python/Hvac", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] hvac.exceptions.Forbidden: 403 Forbidden: permission denied (Vault client token has expired at ttl 72h)",
            f"[{ts}] [FATAL] [{service}] Secret lease renewal failed for database credentials on {ip}:8200",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Vault client token has expired",
            "Secret lease renewal failed",
            impact_line,
        ], SCEN_TOK, RC_TOK, ACT_TOK, "VAULT_TOKEN_TTL_EXPIRED"),
    _create_template("SEC_TOK_06", FAM_TOK, "Google Cloud IAM", "Python/GoogleAuth", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] google.auth.exceptions.RefreshError: ('invalid_grant: Token has been expired or revoked.', {{'error': 'invalid_grant'}})",
            f"[{ts}] [ERROR] [{service}] Service account credentials refresh aborted on {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "RefreshError: ('invalid_grant: Token has been expired or revoked.'",
            "Service account credentials refresh aborted",
            impact_line,
        ], SCEN_TOK, RC_TOK, ACT_TOK, "GCP_REFRESH_TOKEN_EXPIRED"),
    _create_template("SEC_TOK_07", FAM_TOK, "Kubernetes API", "Go/client-go", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] k8s.io/client-go: Unauthorized 401: token expired or bound service account token invalidated on {ip}",
            f"[{ts}] [ERROR] [{service}] Failed communicating with kubernetes apiserver: ServiceAccount token expired",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Unauthorized 401: token expired or bound service account token invalidated",
            "ServiceAccount token expired",
            impact_line,
        ], SCEN_TOK, RC_TOK, ACT_TOK, "K8S_SA_TOKEN_EXPIRED"),
    _create_template("SEC_TOK_08", FAM_TOK, "GitHub App API", "Ruby/Octokit", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num, token_expiry_ts="", **kwargs: [
            f"[{ts}] [ERROR] [{service}] Octokit::Unauthorized: 401 - Bad credentials: The installation access token expired at {token_expiry_ts or '2026-09-14T09:00:00Z'}",
            f"[{ts}] [WARN] [{service}] Webhook dispatch aborted due to expired token for installation id={hex_id}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num, **kwargs: [
            "401 - Bad credentials: The installation access token expired",
            impact_line,
        ], SCEN_TOK, RC_TOK, ACT_TOK,
        signature_profile="GITHUB_INSTALLATION_TOKEN_EXPIRED",
        failure_mechanism="TOKEN_EXPIRED",
        expected_tokens=["Octokit::Unauthorized: 401"],
        forbidden_tokens=["CORS", "brute-force"],
        expected_status_code=401),
    _create_template("SEC_TOK_09", FAM_TOK, "Azure Active Directory", "C#/.NET", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Azure.Identity.AuthenticationFailedException: AADSTS7000222: The provided client secret keys for app {hex_id} are expired.",
            f"[{ts}] [ERROR] [{service}] Azure AD token acquisition failed on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "AADSTS7000222: The provided client secret keys for app",
            "are expired.",
            impact_line,
        ], SCEN_TOK, RC_TOK, ACT_TOK, "AZURE_AD_CLIENT_SECRET_EXPIRED"),
    _create_template("SEC_TOK_10", FAM_TOK, "SendGrid API", "Python", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [FATAL] [{service}] python_http_client.exceptions.UnauthorizedError: HTTP Error 401: Unauthorized: The provided SendGrid API key has expired",
            f"[{ts}] [ERROR] [{service}] Email delivery pipeline halted on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "UnauthorizedError: HTTP Error 401: Unauthorized: The provided SendGrid API key has expired",
            "Email delivery pipeline halted",
            impact_line,
        ], SCEN_TOK, RC_TOK, ACT_TOK, "SENDGRID_API_KEY_EXPIRED"),
]


# =========================================================================
# 2. SEC_PERMISSION_OR_RBAC_DENIED
# =========================================================================

SCEN_RBC = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: S3 audit bucket access denied across all nodes; compliance and order writing blocked in {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Permission denied for {service} writing to metrics pubsub topic; monitoring degraded",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Non-privileged user account attempted admin role action; blocked by RBAC policy",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Routine probe denied read access to deprecated metadata endpoint; fallback path handled request",
    ),
]

RC_RBC_TRAIN = {
    "RC_TRAIN_1": "Insufficient IAM role permissions or RBAC authorization failure accessing cloud resource in {service}.",
    "RC_TRAIN_2": "Kubernetes ServiceAccount lacking cluster role privileges for required API operation on {ip}.",
    "RC_TRAIN_3": "Authorization failure: service account lacks necessary access permissions for requested resource in {service}.",
}
ACT_RBC_TRAIN = {
    "ACT_TRAIN_1": "Update IAM policy / Kubernetes ClusterRole to grant required permission to {service} service account.",
    "ACT_TRAIN_2": "Audit recent RBAC deployments and restore missing resource action permissions.",
    "ACT_TRAIN_3": "Verify AWS IAM / GCP policy binding for {service} workload identity.",
}

RC_RBC_VAL = {
    "RC_VAL_1": "RBAC admission controller or role binding denied operation due to missing authorization privileges.",
}
ACT_RBC_VAL = {
    "ACT_VAL_1": "Review role bindings and security context constraints for service principal on {ip}.",
}

RC_RBC_TEST = {
    "RC_TEST_1": "Resource authorization failure: principal rejected by destination security policy on {ip}.",
}
ACT_RBC_TEST = {
    "ACT_TEST_1": "Grant required least-privilege permission in policy configuration and redeploy {service}.",
}

RC_RBC = {**RC_RBC_TRAIN, **RC_RBC_VAL, **RC_RBC_TEST}
ACT_RBC = {**ACT_RBC_TRAIN, **ACT_RBC_VAL, **ACT_RBC_TEST}

TEMPLATES_RBAC = [
    _create_template("SEC_RBC_01", FAM_RBC, "AWS IAM", "Python/Boto3", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] botocore.exceptions.ClientError: An error occurred (AccessDenied) when calling the PutObject operation: User: arn:aws:iam::123456789012:role/{service}-role is not authorized to perform: s3:PutObject on resource: \"arn:aws:s3:::production-records/{hex_id}\"",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "An error occurred (AccessDenied) when calling the PutObject operation",
            "is not authorized to perform: s3:PutObject",
            impact_line,
        ], SCEN_RBC, RC_RBC, ACT_RBC, "AWS_IAM_S3_ACCESS_DENIED"),
    _create_template("SEC_RBC_02", FAM_RBC, "Kubernetes RBAC", "Go/apiserver", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] apiserver[{ip}]: Forbidden 403: pods \"{service}-{hex_id}\" is forbidden: User \"system:serviceaccount:production:{service}\" cannot list resource \"secrets\" in API group \"\" at the cluster scope",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Forbidden 403: pods",
            "cannot list resource \"secrets\" in API group \"\" at the cluster scope",
            impact_line,
        ], SCEN_RBC, RC_RBC, ACT_RBC, "K8S_RBAC_FORBIDDEN_SECRETS"),
    _create_template("SEC_RBC_03", FAM_RBC, "Google Cloud IAM", "Python/GooglePubSub", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] google.api_core.exceptions.PermissionDenied: 403 Permission 'pubsub.topics.publish' denied on resource '//pubsub.googleapis.com/projects/prod/topics/orders' on {ip}",
            f"[{ts}] [ERROR] [{service}] Identity svc-{service}@prod.iam.gserviceaccount.com lacks roles/pubsub.publisher",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "PermissionDenied: 403 Permission 'pubsub.topics.publish' denied",
            "lacks roles/pubsub.publisher",
            impact_line,
        ], SCEN_RBC, RC_RBC, ACT_RBC, "GCP_IAM_PUBSUB_PERMISSION_DENIED"),
    _create_template("SEC_RBC_04", FAM_RBC, "Spring Security", "Java/Spring", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] org.springframework.security.access.AccessDeniedException: Access is denied: User principal does not have required authority 'ROLE_ADMIN'",
            f"[{ts}] [ERROR] [{service}] Authorization failure in MethodSecurityInterceptor for /api/admin/reconcile from {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "org.springframework.security.access.AccessDeniedException: Access is denied",
            "does not have required authority 'ROLE_ADMIN'",
            impact_line,
        ], SCEN_RBC, RC_RBC, ACT_RBC, "SPRING_ROLE_ACCESS_DENIED"),
    _create_template("SEC_RBC_05", FAM_RBC, "HashiCorp Vault", "Go/Vault", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] vault-server[{ip}]: core: permission denied: path \"secret/data/production/database\" requested by token id={hex_id}",
            f"[{ts}] [FATAL] [{service}] AppRole policy restriction prevents {service} reading database secret",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "core: permission denied: path \"secret/data/production/database\"",
            "AppRole policy restriction prevents",
            impact_line,
        ], SCEN_RBC, RC_RBC, ACT_RBC, "VAULT_APPROLE_PERMISSION_DENIED"),
    _create_template("SEC_RBC_06", FAM_RBC, "Azure Key Vault", "C#/.NET", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Azure.RequestFailedException: The client '{hex_id}' with object id does not have authorization to perform action 'Microsoft.KeyVault/vaults/secrets/read' over scope on {ip}",
            f"[{ts}] [ERROR] [{service}] HTTP status 403: Forbidden on KeyVault request",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "does not have authorization to perform action 'Microsoft.KeyVault/vaults/secrets/read'",
            "HTTP status 403: Forbidden on KeyVault request",
            impact_line,
        ], SCEN_RBC, RC_RBC, ACT_RBC, "AZURE_KEYVAULT_FORBIDDEN"),
    _create_template("SEC_RBC_07", FAM_RBC, "OPA Gatekeeper", "Go/Gatekeeper", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] admission-webhook \"gatekeeper.security.org\": admission webhook denied the request: [container-must-not-run-as-root] Container {service} is attempting to run as root on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "admission webhook denied the request: [container-must-not-run-as-root]",
            "Container",
            "is attempting to run as root on",
            impact_line,
        ], SCEN_RBC, RC_RBC, ACT_RBC, "OPA_GATEKEEPER_NONROOT_DENIED"),
    _create_template("SEC_RBC_08", FAM_RBC, "PostgreSQL", "C/Engine", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] postgres[9412]: ERROR: permission denied for table \"customer_vault\" for user \"app_{service}\"",
            f"[{ts}] [FATAL] [{service}] Query aborted: lack of SELECT privilege on sensitive table from {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "ERROR: permission denied for table \"customer_vault\"",
            "lack of SELECT privilege on sensitive table",
            impact_line,
        ], SCEN_RBC, RC_RBC, ACT_RBC, "POSTGRES_TABLE_PERMISSION_DENIED"),
    _create_template("SEC_RBC_09", FAM_RBC, "Istio Service Mesh", "Envoy/C++", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] envoy rbac: enforced denied, matched policy: none for peer principal cluster.local/ns/default/sa/{service}",
            f"[{ts}] [ERROR] [{service}] Istio AuthorizationPolicy rejected connection to billing-service from {ip}: 403 RBAC: access denied",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "envoy rbac: enforced denied, matched policy:",
            "403 RBAC: access denied",
            impact_line,
        ], SCEN_RBC, RC_RBC, ACT_RBC, "ISTIO_AUTHORIZATION_POLICY_DENIED"),
    _create_template("SEC_RBC_10", FAM_RBC, "OpenStack Keystone", "Python", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] keystoneclient.exceptions.Forbidden: 403 Forbidden: You are not authorized to perform the requested action: identity:create_trust on {ip}",
            f"[{ts}] [FATAL] [{service}] RBAC policy rule check failed for user {hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "403 Forbidden: You are not authorized to perform the requested action: identity:create_trust",
            "RBAC policy rule check failed",
            impact_line,
        ], SCEN_RBC, RC_RBC, ACT_RBC, "KEYSTONE_IDENTITY_FORBIDDEN"),
]


# =========================================================================
# 3. SEC_SECRET_LEAKAGE
# =========================================================================

SCEN_LAK = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: Live production AWS root secret key detected in public log stream from {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Stripe API secret key logged in plaintext on host {ip}; immediate rotation required",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Test environment sandbox API key found in debug log output; rotation scheduled",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Masked redaction placeholder logged in test harness; zero sensitive bytes exposed",
    ),
]

RC_LAK_TRAIN = {
    "RC_TRAIN_1": "Plaintext secret token or private credential inadvertently printed in application logs in {service}.",
    "RC_TRAIN_2": "Sensitive credentials or API keys emitted in plaintext to application log output from {ip}.",
    "RC_TRAIN_3": "Unsanitized HTTP request headers exposing Authorization bearer tokens in log output for {service}.",
}
ACT_LAK_TRAIN = {
    "ACT_TRAIN_1": "Revoke and rotate exposed credential immediately; scrub log indexes and reduce log verbosity.",
    "ACT_TRAIN_2": "Deploy log mask regex filter to strip sensitive tokens before forwarding to central logging.",
    "ACT_TRAIN_3": "Review logging framework serializers to sanitize authorization headers and credentials.",
}

RC_LAK_VAL = {
    "RC_VAL_1": "Sensitive credential string output to stdout by application logging handler on {ip}.",
}
ACT_LAK_VAL = {
    "ACT_VAL_1": "Invalidate leaked key in provider console and configure log scrubbing patterns for {service}.",
}

RC_LAK_TEST = {
    "RC_TEST_1": "Unmasked secret key or token exposed in plaintext container log stream on host {ip}.",
}
ACT_LAK_TEST = {
    "ACT_TEST_1": "Immediately roll compromised token, purge logging indexes, and enforce log sanitization middleware in {service}.",
}

RC_LAK = {**RC_LAK_TRAIN, **RC_LAK_VAL, **RC_LAK_TEST}
ACT_LAK = {**ACT_LAK_TRAIN, **ACT_LAK_VAL, **ACT_LAK_TEST}

TEMPLATES_SECRET_LEAK = [
    _create_template("SEC_LAK_01", FAM_LAK, "AWS DLP Scanner", "Go", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] dlp-scanner: DataLossPrevention violation: Pattern MATCH [AWS_SECRET_ACCESS_KEY] in stdout stream from {ip}",
            f"[{ts}] [WARN] [{service}] Found sensitive credential pattern: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY' in log line {num}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "DataLossPrevention violation: Pattern MATCH [AWS_SECRET_ACCESS_KEY]",
            "Found sensitive credential pattern:",
            impact_line,
        ], SCEN_LAK, RC_LAK, ACT_LAK, "DLP_AWS_SECRET_KEY_EXPOSED"),
    _create_template("SEC_LAK_02", FAM_LAK, "Gitleaks", "Go", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] gitleaks: Rule: stripe-api-token secret found in container log payload: 'sk_live_synth_{hex_id}_abcdef'",
            f"[{ts}] [WARN] [{service}] Plaintext credential exposed by {service} logging handler on {ip}",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Rule: stripe-api-token secret found in container log payload",
            "Plaintext credential exposed by",
            impact_line,
        ], SCEN_LAK, RC_LAK, ACT_LAK, "GITLEAKS_STRIPE_TOKEN_EXPOSED"),
    _create_template("SEC_LAK_03", FAM_LAK, "FastAPI Debug", "Python/FastAPI", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [DEBUG] [{service}] Request headers dump: {{'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.{hex_id}.signature'}}",
            f"[{ts}] [WARN] [{service}] SecurityAudit: Plaintext bearer token dumped to stdout by debug logger on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Request headers dump: {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.",
            "Plaintext bearer token dumped to stdout by debug logger",
            impact_line,
        ], SCEN_LAK, RC_LAK, ACT_LAK, "FASTAPI_DEBUG_AUTH_HEADER_LEAK"),
    _create_template("SEC_LAK_04", FAM_LAK, "Spring DataSource", "Java/Spring", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Failed to connect to DataSource: jdbc:postgresql://dbadmin:SuperSecretPassword123!@{ip}:5432/production_db",
            f"[{ts}] [WARN] [{service}] Credential exposed in exception stack trace for {service}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Failed to connect to DataSource: jdbc:postgresql://dbadmin:SuperSecretPassword123!@",
            "Credential exposed in exception stack trace",
            impact_line,
        ], SCEN_LAK, RC_LAK, ACT_LAK, "SPRING_JDBC_URI_PASSWORD_LEAK"),
    _create_template("SEC_LAK_05", FAM_LAK, "Audit Daemon", "C/Linux", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] audit-daemon: Sensitive pattern found: '-----BEGIN RSA PRIVATE KEY-----' logged on host {ip}",
            f"[{ts}] [FATAL] [{service}] RSA private key material emitted in application debug trace for request {hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Sensitive pattern found: '-----BEGIN RSA PRIVATE KEY-----'",
            "RSA private key material emitted in application debug trace",
            impact_line,
        ], SCEN_LAK, RC_LAK, ACT_LAK, "AUDIT_RSA_PRIVATE_KEY_LEAK"),
    _create_template("SEC_LAK_06", FAM_LAK, "Node.js Config", "Node.js", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] config: initialized JWTVerifier with secret: 'jwt_signing_key_secret_2026_{hex_id}' on {ip}",
            f"[{ts}] [ERROR] [{service}] SecretLeakageDetector: High confidence signing key exposed in log stream",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "initialized JWTVerifier with secret: 'jwt_signing_key_secret_2026_",
            "High confidence signing key exposed in log stream",
            impact_line,
        ], SCEN_LAK, RC_LAK, ACT_LAK, "NODE_JWT_SIGNING_KEY_LEAK"),
    _create_template("SEC_LAK_07", FAM_LAK, "Slack Webhook", "Python", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] dispatching notification to: https://hooks.slack.com/services/T00000000/B00000000/{hex_id}secretToken",
            f"[{ts}] [ERROR] [{service}] DLP: Insecure incoming webhook URL printed in application log from {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "https://hooks.slack.com/services/T00000000/B00000000/",
            "Insecure incoming webhook URL printed in application log",
            impact_line,
        ], SCEN_LAK, RC_LAK, ACT_LAK, "SLACK_WEBHOOK_URL_LEAK"),
    _create_template("SEC_LAK_08", FAM_LAK, "Git Sync", "Git/Linux", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] git-clone: authentication failed for https://ghp_synthSecretToken{hex_id}@github.com/org/repo.git",
            f"[{ts}] [FATAL] [{service}] GitHub Personal Access Token leaked in git error message on host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "https://ghp_synthSecretToken",
            "GitHub Personal Access Token leaked in git error message",
            impact_line,
        ], SCEN_LAK, RC_LAK, ACT_LAK, "GIT_PAT_URI_LEAK"),
    _create_template("SEC_LAK_09", FAM_LAK, "OpenAI SDK", "Python", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] LLMClient initialized with api_key='sk-synthProj-{hex_id}98124abcdef' on host {ip}",
            f"[{ts}] [FATAL] [{service}] Security Scanner: Exposed OpenAI API Key detected in container logs",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "LLMClient initialized with api_key='sk-synthProj-",
            "Exposed OpenAI API Key detected in container logs",
            impact_line,
        ], SCEN_LAK, RC_LAK, ACT_LAK, "OPENAI_API_KEY_LEAK"),
    _create_template("SEC_LAK_10", FAM_LAK, "Redis Client", "Go", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] redis: connection string: redis://:SuperSecretRedisPass2026@{ip}:6379/0 connection reset",
            f"[{ts}] [FATAL] [{service}] Plaintext Redis AUTH password logged in error message for {service}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "redis://:SuperSecretRedisPass2026@",
            "Plaintext Redis AUTH password logged in error message",
            impact_line,
        ], SCEN_LAK, RC_LAK, ACT_LAK, "REDIS_AUTH_URI_LEAK"),
]


# =========================================================================
# 4. SEC_BRUTE_FORCE_ATTACK
# =========================================================================

SCEN_BRU = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: 15,000 failed login attempts/minute; auth servers saturated and degrading legitimate logins",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Brute force attack detected on /api/v1/auth; 850 failed attempts from {ip}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Single IP exceeded failed login threshold; automatically isolated by fail2ban",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Isolated failed login attempt from known QA probe; threshold remains within normal baseline",
    ),
]

RC_BRU_TRAIN = {
    "RC_TRAIN_1": "Distributed credential stuffing / brute-force authentication attack targeting login endpoints on {service}.",
    "RC_TRAIN_2": "High volume of failed authentication attempts exceeding rate limits targeting {ip}.",
    "RC_TRAIN_3": "High-frequency dictionary attack against user authentication API on {service}.",
}
ACT_BRU_TRAIN = {
    "ACT_TRAIN_1": "Enable WAF IP rate-limiting rules, investigate botnet signatures, enforce CAPTCHA on login endpoints, and block offending subnet.",
    "ACT_TRAIN_2": "Temporarily throttle failed login attempts and trigger automated account lockout.",
    "ACT_TRAIN_3": "Ban malicious IP address ranges at cloud CDN/edge firewall and notify security operations.",
}

RC_BRU_VAL = {
    "RC_VAL_1": "Automated brute-force password spraying targeting authentication services on {ip}.",
}
ACT_VAL_1 = {
    "ACT_VAL_1": "Activate edge rate limiting and enforce multi-factor authentication for affected accounts on {service}.",
}

RC_BRU_TEST = {
    "RC_TEST_1": "High-volume credential stuffing attack attempting unauthorized access on {ip}.",
}
ACT_BRU_TEST = {
    "ACT_TEST_1": "Enforce bot management challenge at edge gateway and block offending IP CIDR blocks for {service}.",
}

RC_BRU = {**RC_BRU_TRAIN, **RC_BRU_VAL, **RC_BRU_TEST}
ACT_BRU = {**ACT_BRU_TRAIN, **ACT_VAL_1, **ACT_BRU_TEST}

TEMPLATES_BRUTE_FORCE = [
    _create_template("SEC_BRU_01", FAM_BRU, "Cloud WAF", "Nginx/Lua", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] WAF: Rate-limit block triggered: 4,500 failed login attempts in 60s for /api/v1/auth/login from ip {ip}",
            f"[{ts}] [WARN] [{service}] ThreatIntelligence: Credential stuffing attack signature detected against {service}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "WAF: Rate-limit block triggered:",
            "failed login attempts in 60s for /api/v1/auth/login from ip",
            impact_line,
        ], SCEN_BRU, RC_BRU, ACT_BRU, "WAF_LOGIN_RATE_LIMIT_BLOCK"),
    _create_template("SEC_BRU_02", FAM_BRU, "FastAPI Auth", "Python/FastAPI", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] SecurityEvent: 200 consecutive failed authentication attempts for username 'admin' from {ip}",
            f"[{ts}] [ERROR] [{service}] BruteForceDetector: Rapid authentication failure threshold exceeded for client id={hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "consecutive failed authentication attempts for username 'admin'",
            "Rapid authentication failure threshold exceeded",
            impact_line,
        ], SCEN_BRU, RC_BRU, ACT_BRU, "FASTAPI_AUTH_FAILURE_SPIKE"),
    _create_template("SEC_BRU_03", FAM_BRU, "Fail2ban", "Python/Linux", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] fail2ban.actions[812]: NOTICE [sshd] Ban {ip}: 5 failures in 10m",
            f"[{ts}] [ERROR] [{service}] SSH brute force dictionary attack detected on bastion host {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "fail2ban.actions[812]: NOTICE",
            "SSH brute force dictionary attack detected",
            impact_line,
        ], SCEN_BRU, RC_BRU, ACT_BRU, "FAIL2BAN_SSH_BRUTE_FORCE"),
    _create_template("SEC_BRU_04", FAM_BRU, "Spring Security", "Java/Spring", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] org.springframework.security.authentication.BadCredentialsException: Bad credentials (attempt count: {num}) from {ip}",
            f"[{ts}] [ALERT] [{service}] AccountLockoutService: Temporary lockout triggered for target accounts across {service}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "BadCredentialsException: Bad credentials (attempt count:",
            "AccountLockoutService: Temporary lockout triggered",
            impact_line,
        ], SCEN_BRU, RC_BRU, ACT_BRU, "SPRING_ACCOUNT_LOCKOUT"),
    _create_template("SEC_BRU_05", FAM_BRU, "Nginx Ingress", "C/Nginx", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] nginx: [error] 1042#0: *{num} limiting requests, excess: 50.120 by zone \"login_limit\", client: {ip}, server: api.example.com, request: \"POST /oauth/token HTTP/1.1\"",
            f"[{ts}] [WARN] [{service}] Ingress gateway throttling suspected brute-force traffic stream",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "limiting requests, excess:",
            "by zone \"login_limit\", client:",
            impact_line,
        ], SCEN_BRU, RC_BRU, ACT_BRU, "NGINX_LIMIT_REQ_AUTH"),
    _create_template("SEC_BRU_06", FAM_BRU, "Cloudflare WAF", "Edge/Cloudflare", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] Cloudflare-Security: Automated Managed Challenge triggered on zone example.com: {num*100} requests flagged as automated botnet",
            f"[{ts}] [ERROR] [{service}] High volume brute force traffic targeting {service} endpoints on {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Automated Managed Challenge triggered on zone",
            "requests flagged as automated botnet",
            impact_line,
        ], SCEN_BRU, RC_BRU, ACT_BRU, "CLOUDFLARE_MANAGED_CHALLENGE"),
    _create_template("SEC_BRU_07", FAM_BRU, "Keycloak", "Java/Keycloak", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] org.keycloak.services.managers.BruteForceProtector: IP {ip} temporarily locked out: {num} invalid credentials in last 5 minutes",
            f"[{ts}] [ERROR] [{service}] Keycloak authentication server under distributed credential spray attack",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "BruteForceProtector: IP",
            "temporarily locked out:",
            "distributed credential spray attack",
            impact_line,
        ], SCEN_BRU, RC_BRU, ACT_BRU, "KEYCLOAK_BRUTE_FORCE_PROTECTOR"),
    _create_template("SEC_BRU_08", FAM_BRU, "Envoy Proxy", "Envoy/C++", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] envoy ratelimit: [auth-service] client {ip} reached 429 Too Many Requests: 100/100 threshold reached on /login",
            f"[{ts}] [FATAL] [{service}] Downstream authentication pool protected by edge rate limiter for {service}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "envoy ratelimit: [auth-service] client",
            "reached 429 Too Many Requests",
            impact_line,
        ], SCEN_BRU, RC_BRU, ACT_BRU, "ENVOY_RATELIMIT_AUTH"),
    _create_template("SEC_BRU_09", FAM_BRU, "AWS Cognito", "AWS/Java", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] com.amazonaws.services.cognitoidp.model.PasswordResetRequiredException: Password reset required: TooManyFailedAttemptsException from source IP {ip}",
            f"[{ts}] [WARN] [{service}] Cognito user pool risk assessment elevated to HIGH for client {hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Password reset required: TooManyFailedAttemptsException from source IP",
            "Cognito user pool risk assessment elevated to HIGH",
            impact_line,
        ], SCEN_BRU, RC_BRU, ACT_BRU, "COGNITO_FAILED_ATTEMPTS_LOCKOUT"),
    _create_template("SEC_BRU_10", FAM_BRU, "Redis RateLimiter", "Go", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] auth_limiter: IP {ip} exceeded sliding window allowance: {num*10} attempts / 60s",
            f"[{ts}] [ALERT] [{service}] SecurityMiddleware: dropped incoming credential spray connection id={hex_id}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "exceeded sliding window allowance:",
            "dropped incoming credential spray connection",
            impact_line,
        ], SCEN_BRU, RC_BRU, ACT_BRU, "REDIS_SLIDING_WINDOW_AUTH_LIMIT"),
]


# =========================================================================
# 5. SEC_CORS_POLICY_BLOCK
# =========================================================================

FAM_COR = IncidentFamily.SEC_CORS_POLICY_BLOCK

SCEN_COR = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: All web frontend users blocked from calling backend APIs; global CORS policy failure",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: CORS preflight requests rejected for customer portal frontend on {service}",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Development origin http://localhost:3000 rejected by production CORS policy",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Disallowed origin request from automated health monitor; expected CORS behavior",
    ),
]

RC_COR_TRAIN = {
    "RC_TRAIN_1": "Cross-Origin Resource Sharing (CORS) policy block due to missing or mismatched Access-Control-Allow-Origin header in {service}.",
    "RC_TRAIN_2": "Preflight OPTIONS request failed or origin rejected by API gateway security configuration for {service}.",
    "RC_TRAIN_3": "Misconfigured allowed origins list after production domain migration on {ip}.",
}
ACT_COR_TRAIN = {
    "ACT_TRAIN_1": "Update backend CORS middleware configuration to include allowed origin in Access-Control-Allow-Origin header.",
    "ACT_TRAIN_2": "Configure API gateway to respond to preflight OPTIONS requests with valid CORS headers.",
    "ACT_TRAIN_3": "Add production frontend domain to CORS allowed origins whitelist in {service}.",
}

RC_COR_VAL = {
    "RC_VAL_1": "CORS preflight validation rejected due to unlisted client domain in gateway origin policy on {ip}.",
}
ACT_COR_VAL = {
    "ACT_VAL_1": "Inspect allowed headers and origins in reverse proxy CORS filter and whitelist client domain for {service}.",
}

RC_COR_TEST = {
    "RC_TEST_1": "Cross-origin browser request rejected due to missing or mismatched Access-Control headers from {ip}.",
}
ACT_COR_TEST = {
    "ACT_TEST_1": "Verify preflight OPTIONS handling and ensure required origin is declared in Access-Control-Allow-Origin for {service}.",
}

RC_COR = {**RC_COR_TRAIN, **RC_COR_VAL, **RC_COR_TEST}
ACT_COR = {**ACT_COR_TRAIN, **ACT_COR_VAL, **ACT_COR_TEST}

TEMPLATES_CORS = [
    _create_template("SEC_COR_01", FAM_COR, "Web Browser CORS", "Browser/HTTP", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Access to fetch at 'https://api.example.com/orders' from origin 'https://app.example.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.",
            f"[{ts}] [WARN] [{service}] Failed to load resource: net::ERR_FAILED from {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present",
            "net::ERR_FAILED",
            impact_line,
        ], SCEN_COR, RC_COR, ACT_COR, "BROWSER_CORS_MISSING_HEADER"),
    _create_template("SEC_COR_02", FAM_COR, "Spring CORS", "Java/Spring", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] org.springframework.web.cors.DefaultCorsProcessor: Reject: 'https://checkout.example.com' origin is not allowed",
            f"[{ts}] [ERROR] [{service}] HTTP 403 Forbidden: CORS preflight request rejected for endpoint /api/v1/checkout on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "DefaultCorsProcessor: Reject:",
            "origin is not allowed",
            "CORS preflight request rejected",
            impact_line,
        ], SCEN_COR, RC_COR, ACT_COR, "SPRING_CORS_ORIGIN_REJECTED"),
    _create_template("SEC_COR_03", FAM_COR, "FastAPI CORS", "Python/Starlette", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] starlette.middleware.cors: Origin 'https://portal.example.com' not in allow_origins list ['https://app.example.com']",
            f"[{ts}] [ERROR] [{service}] CORS check failed: Disallowed cross-origin request from client {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "starlette.middleware.cors: Origin",
            "not in allow_origins list",
            "CORS check failed: Disallowed cross-origin request",
            impact_line,
        ], SCEN_COR, RC_COR, ACT_COR, "FASTAPI_CORS_ALLOW_ORIGINS_MISMATCH"),
    _create_template("SEC_COR_04", FAM_COR, "Express CORS", "Node.js/Express", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Error: Not allowed by CORS: Origin https://staging-ui.example.com is unauthorized",
            f"[{ts}] [WARN] [{service}] corsMiddleware: rejected incoming preflight OPTIONS from {ip} for {service}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Error: Not allowed by CORS: Origin",
            "rejected incoming preflight OPTIONS",
            impact_line,
        ], SCEN_COR, RC_COR, ACT_COR, "EXPRESS_CORS_DISALLOWED_ORIGIN"),
    _create_template("SEC_COR_05", FAM_COR, "Nginx", "C/Nginx", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] nginx: [warn] 4910#0: upstream response missing Access-Control-Allow-Origin header for origin: https://store.example.com",
            f"[{ts}] [WARN] [{service}] Client browser on {ip} received 200 OK without CORS headers; response unreadable by JavaScript",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "upstream response missing Access-Control-Allow-Origin header for origin",
            "without CORS headers; response unreadable by JavaScript",
            impact_line,
        ], SCEN_COR, RC_COR, ACT_COR, "NGINX_CORS_HEADER_MISSING"),
    _create_template("SEC_COR_06", FAM_COR, "Django CORS", "Python/Django", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] corsheaders: Origin 'https://dashboard.example.com' not found in CORS_ALLOWED_ORIGINS",
            f"[{ts}] [ERROR] [{service}] Disallowing cross-site request headers on /api/v2/metrics request={hex_id} from {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "corsheaders: Origin",
            "not found in CORS_ALLOWED_ORIGINS",
            "Disallowing cross-site request headers",
            impact_line,
        ], SCEN_COR, RC_COR, ACT_COR, "DJANGO_CORS_ORIGIN_NOT_ALLOWED"),
    _create_template("SEC_COR_07", FAM_COR, "AWS API Gateway", "AWS/HTTP", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] aws-apigateway: Execution failed due to configuration error: Missing Access-Control-Allow-Origin header on 4xx response from mock integration",
            f"[{ts}] [ERROR] [{service}] Preflight OPTIONS request failed with 500 Internal Server Error for origin https://app.example.com on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Missing Access-Control-Allow-Origin header on 4xx response",
            "Preflight OPTIONS request failed with",
            impact_line,
        ], SCEN_COR, RC_COR, ACT_COR, "AWS_APIGW_CORS_INTEGRATION_ERROR"),
    _create_template("SEC_COR_08", FAM_COR, "ASP.NET Core", "C#/.NET", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] Microsoft.AspNetCore.Cors.Infrastructure.CorsService: The policy 'DefaultPolicy' does not allow origin 'https://admin.example.com'",
            f"[{ts}] [ERROR] [{service}] CORS policy execution failed for preflight request on {ip}:5001",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "CorsService: The policy 'DefaultPolicy' does not allow origin",
            "CORS policy execution failed for preflight request",
            impact_line,
        ], SCEN_COR, RC_COR, ACT_COR, "ASPNET_CORS_POLICY_DISALLOW"),
    _create_template("SEC_COR_09", FAM_COR, "Cloudflare Workers", "JavaScript", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] Cloudflare-Workers: Access to XMLHttpRequest from origin 'https://client.example.com' blocked by Access-Control-Allow-Headers mismatch",
            f"[{ts}] [WARN] [{service}] Header 'x-custom-tenant-id' not allowed by preflight response on {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "blocked by Access-Control-Allow-Headers mismatch",
            "not allowed by preflight response on",
            impact_line,
        ], SCEN_COR, RC_COR, ACT_COR, "CLOUDFLARE_CORS_HEADER_MISMATCH"),
    _create_template("SEC_COR_10", FAM_COR, "Envoy Proxy", "Envoy/C++", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] envoy cors: origin 'https://b2b.example.com' is not permitted by cors filter for route /api/v1/orders",
            f"[{ts}] [ERROR] [{service}] CORS preflight check rejected with 403 Forbidden on ingress {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "envoy cors: origin",
            "is not permitted by cors filter",
            "CORS preflight check rejected with 403 Forbidden",
            impact_line,
        ], SCEN_COR, RC_COR, ACT_COR, "ENVOY_CORS_FILTER_REJECTED"),
]


# =========================================================================
# 6. SEC_SSRF_OR_EGRESS_VIOLATION
# =========================================================================

FAM_SSR = IncidentFamily.SEC_SSRF_OR_EGRESS_VIOLATION

SCEN_SSR = [
    ImpactScenario(
        severity=Severity.P1_CRITICAL,
        impact_line="CRITICAL: SSRF exploit attempting to harvest AWS instance metadata tokens via {service}",
    ),
    ImpactScenario(
        severity=Severity.P2_HIGH,
        impact_line="HIGH ALERT: Unauthorized outbound egress blocked to restricted subnet {ip} by firewall",
    ),
    ImpactScenario(
        severity=Severity.P3_MEDIUM,
        impact_line="NOTICE: Outbound request to private IP rejected by validation hook; safe failure",
    ),
    ImpactScenario(
        severity=Severity.P4_LOW,
        impact_line="LOW: Internal diagnostic probe reached disallowed egress filter; harmlessly dropped",
    ),
]

RC_SSR_TRAIN = {
    "RC_TRAIN_1": "Server-Side Request Forgery (SSRF) attempt trying to access internal cloud metadata endpoint in {service}.",
    "RC_TRAIN_2": "Unauthorized outbound egress request blocked by network firewall policy from {ip}.",
    "RC_TRAIN_3": "Malicious user input supplying loopback or metadata IP in webhook URL parameter in {service}.",
}
ACT_SSR_TRAIN = {
    "ACT_TRAIN_1": "Enforce strict URL destination allowlist and block access to 169.254.169.254 and private CIDRs.",
    "ACT_TRAIN_2": "Deploy IMDSv2 requiring token header on cloud metadata service and inspect suspicious requests.",
    "ACT_TRAIN_3": "Audit input validation on user-supplied webhook URLs in {service} and apply egress network policy.",
}

RC_SSR_VAL = {
    "RC_VAL_1": "Outbound egress connection blocked by security filter due to target IP in forbidden private/metadata range on {ip}.",
}
ACT_SSR_VAL = {
    "ACT_VAL_1": "Verify destination IP allowlist in egress firewall and sanitize target endpoints for {service}.",
}

RC_SSR_TEST = {
    "RC_TEST_1": "Unauthorized outbound connection attempt to internal infrastructure or metadata service blocked on {ip}.",
}
ACT_SSR_TEST = {
    "ACT_TEST_1": "Inspect outbound connection destination, enforce IMDSv2, and verify network policy rules for {service}.",
}

RC_SSR = {**RC_SSR_TRAIN, **RC_SSR_VAL, **RC_SSR_TEST}
ACT_SSR = {**ACT_SSR_TRAIN, **ACT_SSR_VAL, **ACT_SSR_TEST}

TEMPLATES_SSRF = [
    _create_template("SEC_SSR_01", FAM_SSR, "AWS IMDS", "Linux/Proxy", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] security-proxy[{ip}]: SecurityPolicyViolation: Blocked egress request to 169.254.169.254:80 (AWS Metadata Service)",
            f"[{ts}] [WARN] [{service}] SSRF attempt detected in webhook payload URL: 'http://169.254.169.254/latest/meta-data/iam/security-credentials/'",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "SecurityPolicyViolation: Blocked egress request to 169.254.169.254:80",
            "SSRF attempt detected in webhook payload URL",
            impact_line,
        ], SCEN_SSR, RC_SSR, ACT_SSR, "AWS_IMDS_SSRF_BLOCKED"),
    _create_template("SEC_SSR_02", FAM_SSR, "Calico NetworkPolicy", "Linux/Calico", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] calico-felix[{ip}]: Policy 'deny-internal-metadata' dropped packet: SRC={ip} DST=169.254.169.254 PROTO=TCP DPT=80",
            f"[{ts}] [WARN] [{service}] Pod {service}-{hex_id} violated egress network policy",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Policy 'deny-internal-metadata' dropped packet",
            "violated egress network policy",
            impact_line,
        ], SCEN_SSR, RC_SSR, ACT_SSR, "CALICO_EGRESS_METADATA_DROPPED"),
    _create_template("SEC_SSR_03", FAM_SSR, "Python Requests", "Python", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] SecurityException: Destination IP '127.0.0.1' is in restricted loopback range",
            f"[{ts}] [WARN] [{service}] SSRF validation filter blocked request to internal service from host {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "SecurityException: Destination IP '127.0.0.1' is in restricted loopback range",
            "SSRF validation filter blocked request",
            impact_line,
        ], SCEN_SSR, RC_SSR, ACT_SSR, "PYTHON_LOOPBACK_SSRF_FILTERED"),
    _create_template("SEC_SSR_04", FAM_SSR, "Google Cloud Metadata", "Linux", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] gcp-audit: Blocked outbound call to http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token on {ip}",
            f"[{ts}] [WARN] [{service}] Missing required 'Metadata-Flavor: Google' header; unauthorized metadata harvest attempt",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Blocked outbound call to http://metadata.google.internal/computeMetadata/v1/",
            "unauthorized metadata harvest attempt",
            impact_line,
        ], SCEN_SSR, RC_SSR, ACT_SSR, "GCP_METADATA_HARVEST_BLOCKED"),
    _create_template("SEC_SSR_05", FAM_SSR, "Cilium eBPF", "Linux/eBPF", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] cilium-agent[{ip}]: DropNotification: Policy violation: Egress connection to 10.0.0.1:22 dropped by CiliumNetworkPolicy",
            f"[{ts}] [WARN] [{service}] Unauthorized internal port scan detected from {service}-{hex_id}",
            f"[{ts}] [FATAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Policy violation: Egress connection to 10.0.0.1:22 dropped by CiliumNetworkPolicy",
            "Unauthorized internal port scan detected",
            impact_line,
        ], SCEN_SSR, RC_SSR, ACT_SSR, "CILIUM_EGRESS_POLICY_VIOLATION"),
    _create_template("SEC_SSR_06", FAM_SSR, "Java URLConnection", "Java", DatasetSplit.TRAIN,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] java.lang.SecurityException: Access to private network address '192.168.1.1' is disallowed by URLValidator",
            f"[{ts}] [WARN] [{service}] Avatar image download URL resolved to forbidden RFC1918 address on {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "SecurityException: Access to private network address",
            "is disallowed by URLValidator",
            "resolved to forbidden RFC1918 address",
            impact_line,
        ], SCEN_SSR, RC_SSR, ACT_SSR, "JAVA_RFC1918_SSRF_BLOCKED"),
    _create_template("SEC_SSR_07", FAM_SSR, "Squid Proxy", "C/Squid", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] squid[1891]: TCP_DENIED/403 3812 CONNECT 169.254.169.254:443 - HIER_NONE/- text/html",
            f"[{ts}] [WARN] [{service}] Squid proxy blocked unauthorized egress to AWS IMDS from host {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "TCP_DENIED/403",
            "CONNECT 169.254.169.254:443",
            "blocked unauthorized egress to AWS IMDS",
            impact_line,
        ], SCEN_SSR, RC_SSR, ACT_SSR, "SQUID_IMDS_EGRESS_DENIED"),
    _create_template("SEC_SSR_08", FAM_SSR, "Axios SSRF Guard", "Node.js", DatasetSplit.VALIDATION,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ERROR] [{service}] AxiosError: Request forbidden by SSRF Guard: Target host '10.244.0.1' resolves to internal cluster IP",
            f"[{ts}] [WARN] [{service}] Webhook execution cancelled for payload {hex_id} on {ip}",
            f"[{ts}] [ALERT] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "Request forbidden by SSRF Guard: Target host",
            "resolves to internal cluster IP",
            impact_line,
        ], SCEN_SSR, RC_SSR, ACT_SSR, "AXIOS_SSRF_INTERNAL_IP_GUARD"),
    _create_template("SEC_SSR_09", FAM_SSR, "Envoy Proxy", "Envoy/C++", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [WARN] [{service}] envoy egress: [DirectResponse] 403 Forbidden - matched virtual host 'deny-metadata' for request to 169.254.169.254",
            f"[{ts}] [ERROR] [{service}] Outbound call rejected by sidecar proxy on node {ip}",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "403 Forbidden - matched virtual host 'deny-metadata' for request to 169.254.169.254",
            "Outbound call rejected by sidecar proxy",
            impact_line,
        ], SCEN_SSR, RC_SSR, ACT_SSR, "ENVOY_EGRESS_DENY_METADATA"),
    _create_template("SEC_SSR_10", FAM_SSR, "Palo Alto Firewall", "PanOS", DatasetSplit.TEST,
        lambda rng, service, ip, ts, impact_line, hex_id, num: [
            f"[{ts}] [ALERT] [{service}] panos-fw: THREAT: suspicious-dns-tunneling detected from {ip} to external domain {hex_id}.malicious.net",
            f"[{ts}] [FATAL] [{service}] Egress session dropped by perimeter security appliance",
            f"[{ts}] [CRITICAL] [{service}] {impact_line}",
        ],
        lambda service, ip, impact_line, hex_id, num: [
            "panos-fw: THREAT: suspicious-dns-tunneling detected",
            "Egress session dropped by perimeter security appliance",
            impact_line,
        ], SCEN_SSR, RC_SSR, ACT_SSR, "PALOALTO_DNS_TUNNEL_DROPPED"),
]


SECURITY_TEMPLATES: list[LogTemplate] = (
    TEMPLATES_TOKEN +
    TEMPLATES_RBAC +
    TEMPLATES_SECRET_LEAK +
    TEMPLATES_BRUTE_FORCE +
    TEMPLATES_CORS +
    TEMPLATES_SSRF
)

assert len(SECURITY_TEMPLATES) == 60, f"Expected 60 templates in SECURITY, got {len(SECURITY_TEMPLATES)}"
