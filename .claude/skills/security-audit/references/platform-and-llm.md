# Platform, operations, and AI

Dependencies · API security · Rate limiting/DoS · Race conditions · Logging · Error handling · LLM security · Docker & infrastructure

---

## Dependency security

Inspect the manifests:

```text
requirements.txt   pyproject.toml   package.json   package-lock.json
poetry.lock        uv.lock          go.mod         Dockerfiles
```

If versions are available, identify known vulnerable dependencies. **Do not claim a CVE without reliable evidence** — if you have not verified it, report the outdated/unpinned dependency as a hygiene finding instead, and say that a CVE scan was not run.

For each confirmed vulnerable dependency provide:

```text
Package
Version
Vulnerability
Severity
Affected component     ← is the vulnerable code path actually used?
Recommended version
```

Also flag: unpinned versions, missing lockfile, dependencies from untrusted sources, and packages installed at container build time from a mutable tag.

---

## API security

Inspect:

```text
Authentication      Authorization        Rate limiting
Input validation    Pagination           Request size limits
Error handling      Mass assignment      Sensitive fields
Object-level authorization
```

Look for excessive data exposure — serializers returning the whole model:

```json
{
  "id": 1,
  "email": "...",
  "password_hash": "...",
  "internal_notes": "...",
  "admin_token": "..."
}
```

Filtering sensitive fields in the frontend is not a control. Check that list/search/export endpoints enforce the same object-level authorization as the detail endpoint, and that pagination bounds are capped server-side.

---

## Rate limiting and DoS

Find endpoints performing expensive operations:

```text
LLM inference     OCR                 PDF processing      Image processing
Database-heavy queries                External API requests
File conversion   Large uploads       Regex processing
```

For each, check:

```text
Request size limit   Timeout           Rate limit
Concurrency limit    Queue limit       Memory limit    CPU limit
```

Pay particular attention to endpoints reachable **unauthenticated** — those are where cost-amplification and resource exhaustion actually bite. Also check for ReDoS in user-supplied or user-matched regexes, and unbounded result sets loaded into memory.

---

## Race conditions

Inspect shared state and concurrent operations:

```text
check → then use          read → modify → write
duplicate job execution   file locking
database race             cache race          TOCTOU
```

Example:

```python
if not exists(order_id):
    create_order(order_id)
```

This is unsafe under concurrent requests without an appropriate database constraint or transaction. Correct fixes are usually a unique constraint, `SELECT ... FOR UPDATE`, an atomic upsert, or an idempotency key — not a wider application-level lock.

Security-relevant instances: balance/quota deduction, coupon or invite redemption, rate-limit counters, one-time token consumption, and privilege changes.

---

## Logging and sensitive data

Check whether logs contain:

```text
Passwords     Tokens        API keys      Authorization headers
Personal data Financial information       Session IDs
Full request bodies
```

Include exception loggers and HTTP client debug logging — those leak headers by default. Consider log destinations too (third-party aggregators inherit the data's sensitivity).

Then check the inverse — are security-relevant events logged at all?

```text
Failed login        Privilege changes    Access denial
Password reset      API key usage        Administrative actions
```

Without these, an incident cannot be investigated.

---

## Error handling

Look for:

```text
Stack traces exposed to users     SQL errors exposed
Internal paths exposed            Credentials exposed
Debug mode enabled                Detailed exception messages
```

Production APIs should not expose internal implementation details unnecessarily. Check the framework's debug flag and its default in production config, and check that error responses do not differ in a way that enables enumeration.

---

## LLM / AI security

If the code uses LLMs, additionally inspect:

```text
Prompt injection            Indirect prompt injection    System prompt leakage
Tool abuse                  Function calling             Excessive agency
Data exfiltration           Unsafe output handling       LLM-generated SQL
LLM-generated code          Sensitive data sent to external models
Cross-user context leakage  Untrusted document content   RAG poisoning
```

Analyze the full flow:

```text
User → Document → LLM → Tool → Database/API
```

**The LLM must NOT be treated as a trusted security boundary.** If LLM output controls:

```text
SQL     shell commands    URLs     file paths
API calls    ERP/Odoo operations   database writes
```

...treat it as untrusted input unless independently validated. Instructions embedded in a retrieved document, an uploaded PDF, or a web page are attacker-controlled input, not content.

Also check: whether tool permissions are scoped per user rather than to a service account with broad rights, whether a human confirmation gates irreversible actions, whether one user's context can leak into another's session or vector store, and what data leaves the perimeter to a third-party model.

---

## Docker / infrastructure security

Inspect:

```text
Dockerfile          docker-compose.yml    Kubernetes manifests
environment variables    ports            volumes
network configuration    container privileges
capabilities        user                  filesystem permissions
```

Look for:

```text
privileged: true             host network
host filesystem mounts       running as root
exposed databases            exposed Redis
hard-coded secrets           unrestricted Docker socket
```

Port bindings matter: `0.0.0.0:5432->5432` publishes the database to every interface, while `127.0.0.1:5432` does not. A mounted `/var/run/docker.sock` is equivalent to host root. Also check for secrets passed as build args (they persist in image layers) and images pinned only to `:latest`.
