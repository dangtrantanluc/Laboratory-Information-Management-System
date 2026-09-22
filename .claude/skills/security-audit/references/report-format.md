# Severity, report structure, and remediation

---

## Severity

```text
CRITICAL   HIGH   MEDIUM   LOW   INFO
```

Severity weighs:

```text
Impact                    Exploitability          Authentication requirement
Privileges required       Attack complexity       Data sensitivity
Blast radius
```

**Do not assign severity based only on the existence of a dangerous API.** `eval()` over a hard-coded constant is not a finding; `eval()` over a request body is `CRITICAL`. An unauthenticated endpoint outranks the same flaw behind an admin login.

Pair severity with the confidence label (`CONFIRMED` / `LIKELY` / `POTENTIAL`) — they are independent axes, and a reader needs both to triage.

---

## Report skeleton

### 1. Executive summary

```text
Security Risk:
CRITICAL / HIGH / MEDIUM / LOW

Critical Findings:  X
High Findings:      X
Medium Findings:    X
Low Findings:       X
```

State the scope reviewed and, explicitly, what was **not** reviewed.

### 2. Attack surface

The main externally controllable inputs, and which require authentication.

### 3. Critical findings

Only the most serious issues, in the full finding format.

### 4. High findings

Detailed findings, full format.

### 5. Medium / low findings

Concise — location, problem, fix.

### 6. Authentication & authorization

Analyzed separately, because these fail systemically rather than per-line.

### 7. Input & injection security

```text
SQL    Command    Path    SSRF    XSS    Serialization
```

### 8. Secrets & cryptography

Locations only, never values. Note which secrets need rotation.

### 9. API security

### 10. Infrastructure security

### 11. LLM security

Only when applicable.

### 12. Dependency security

Only when dependency information is available. State whether a CVE scan was actually run.

### 13. Security architecture

Systemic weaknesses — patterns that will keep producing vulnerabilities (e.g. authorization enforced ad hoc in each handler instead of centrally, validation applied after canonicalization, secrets read with insecure fallbacks).

### 14. Remediation roadmap

```text
Immediate  →  Short Term  →  Medium Term  →  Long Term
```

`Immediate` means rotate the credential and block the exploitable path — today, not next sprint.

### 15. Top 5

Close with the answer to the final question:

```text
1. [CRITICAL] ...
2. [HIGH]     ...
3. [HIGH]     ...
4. [MEDIUM]   ...
5. [MEDIUM]   ...
```

---

## Security gates

Any of these fails the audit regardless of overall code quality:

```text
Confirmed credential exposure
Critical injection vulnerability
Authentication bypass
Authorization bypass
Remote code execution
Critical data exposure
Unsafe arbitrary code execution
Critical dependency vulnerability
```

Never let a high quality score hide a critical security issue — say plainly that the gate failed.
