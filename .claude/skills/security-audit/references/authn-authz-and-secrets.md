# Identity, access, and secrets

Authentication · Authorization · JWT · Secrets · Cryptography · CSRF · CORS

---

## Authentication

Analyze:

```text
Password storage       Password hashing      Login flow
Session creation       Token generation      JWT handling
Refresh tokens         Password reset        Account enumeration
Brute-force protection Rate limiting         MFA
Logout                 Session invalidation
```

Never store passwords with `MD5`, `SHA1`, plain `SHA256`, or plaintext. Use an algorithm designed for passwords (argon2id, scrypt, bcrypt) with appropriate cost.

Check that password reset tokens are single-use, expiring, and compared in constant time; that login/reset responses do not enable account enumeration; and that logout actually invalidates server-side state.

---

## Authorization

**Do not assume authentication means authorization.** For every sensitive endpoint ask:

```text
Who can call this?
Who owns this resource?
Is ownership checked?
Is role checked?
Is privilege checked?
Can object IDs be changed?
```

Look for IDOR/BOLA:

```text
GET /invoice/123
```

...where the application only checks *"Is the user logged in?"* instead of *"Does this user have permission to access invoice 123?"*

Also check:

* Function-level authorization on admin/privileged routes
* Authorization enforced server-side, not only by hiding UI
* Tenant isolation in multi-tenant queries (is the tenant filter in the query, or applied after fetch?)
* Mass assignment letting a user set `role`, `is_admin`, `owner_id`
* Authorization applied consistently across every route reaching the same resource, including bulk/export/search endpoints

---

## JWT security

Inspect:

```text
Algorithm validation   Signature verification   Key management
Expiration             Issuer                   Audience
Token storage          Refresh token rotation   Revocation
```

Pay special attention to algorithm confusion (`alg: none`, HS256 signed with an RSA public key) and to trusting claims without verification. Never trust a JWT payload field merely because it is present — decode is not verify.

Check that expiry is enforced, that revocation is possible for a compromised token, and where the token is stored client-side.

---

## Secrets detection

Search for:

```text
API keys       Passwords          JWT secrets      Private keys
Cloud credentials  Database credentials  Tokens
Webhook secrets    Encryption keys
```

Examples:

```python
API_KEY = "sk-..."
PASSWORD = "admin123"
SECRET_KEY = "..."
```

Also inspect: `.env`, `docker-compose.yml`, `Dockerfile`, CI/CD configs, config files, logs, and **git history** (a deleted secret is still in the objects).

Recommend: environment variables, a secret manager, credential rotation, least privilege.

**Never expose the discovered secret in the report.** Write:

```text
API key detected in config.py:42
```

...rather than printing the key. Also check for weak defaults that fall back silently (`SECRET_KEY = os.getenv("SECRET_KEY", "dev")`) — those ship to production.

---

## Cryptography

Check for:

```text
Weak hashing              Weak encryption          Hard-coded keys
Predictable randomness    ECB mode                 Improper IV/nonce handling
Certificate verification disabled                  TLS verification disabled
Custom cryptographic algorithms
```

Dangerous examples:

```python
hashlib.md5(password)
```

```python
requests.get(url, verify=False)
```

```python
random.random()     # when cryptographic randomness is required
```

Use `secrets` / `crypto.randomBytes` for tokens, authenticated encryption (AES-GCM, not ECB/unauthenticated CBC), unique IVs per message, and constant-time comparison for secrets and MACs. Flag any hand-rolled cryptographic construction.

---

## CSRF

For **cookie-based** authentication, inspect state-changing requests (`POST` / `PUT` / `PATCH` / `DELETE`):

```text
CSRF tokens        SameSite cookies      Origin validation
Referer validation Authentication architecture
```

Do **not** report CSRF automatically for APIs using appropriately designed bearer-token authentication — the vulnerability requires the browser to attach credentials implicitly.

---

## CORS

Inspect:

```text
Access-Control-Allow-Origin
credentials
wildcards
dynamic origins
```

Flag dangerous combinations — reflecting an arbitrary `Origin` while `Allow-Credentials: true` effectively removes same-origin protection. Also flag `null` origin acceptance and prefix/suffix origin matching (`startswith("https://trusted")` matches `https://trusted.evil.com`).
