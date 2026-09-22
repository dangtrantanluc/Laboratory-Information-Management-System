# Cross-cutting analysis

Duplication · Testing · Security · Performance · Reliability · Technical debt

---

## Code duplication

Detect:

* Exact duplication
* Structural duplication
* Copy-pasted business rules
* Repeated validation
* Repeated API handling
* Repeated database queries
* Repeated transformation logic

For every duplication, decide whether abstraction is *actually* justified. Do **not** recommend abstraction merely because two snippets look similar. Weigh:

```text
Duplication
vs
Coupling introduced by abstraction
```

Prefer the option with lower long-term complexity. Two similar-looking snippets that change for different reasons should stay separate.

---

## Testing

Evaluate: unit tests, integration tests, end-to-end tests, mock usage, test isolation, branch coverage, edge cases, error cases, regression tests.

If coverage data exists, analyze line / branch / function coverage. Never assume `90% coverage = high quality`. Evaluate whether the tests actually verify behavior.

Look for:

* Tests that only test implementation details
* Excessive mocking
* Missing failure-path tests
* Missing boundary tests
* Missing concurrency tests
* Missing idempotency tests
* Missing security tests

If no execution data is available, say so rather than estimating coverage numbers.

---

## Security

Perform a static security review. Look for:

* Hard-coded secrets, API keys, passwords
* SQL injection
* Command injection
* Path traversal
* Unsafe deserialization
* SSRF
* Authentication bypass
* Authorization flaws
* Insecure file handling
* Weak cryptography
* Sensitive information in logs
* Improper error disclosure
* Unsafe subprocess execution
* Dependency vulnerabilities, if dependency data is available

Security issues are prioritized above style issues. Rank by severity: `CRITICAL / HIGH / MEDIUM / LOW / INFO`.

---

## Performance

Look for:

* N+1 queries
* Unnecessary database calls
* Repeated network requests
* Blocking I/O
* Sequential operations that could be parallel
* Excessive serialization
* Memory-heavy operations
* Large object copies
* Inefficient loops
* Missing caching
* Incorrect caching
* Cache stampede
* Excessive LLM / API calls
* Unbounded concurrency
* Thread-pool exhaustion

Do not optimize without evidence. Clearly distinguish:

```text
Confirmed performance problem
Potential performance risk
Optimization opportunity
```

---

## Reliability

Evaluate: retry behavior, timeout handling, idempotency, transaction boundaries, partial failures, race conditions, concurrency, resource cleanup, connection management, graceful degradation, failure recovery.

Pay particular attention to every boundary with an external system:

```text
Database
Redis
HTTP APIs
LLM APIs
Object storage
Message queues
```

---

## Technical debt

Identify: TODOs, FIXMEs, workarounds, hard-coded values, dead code, legacy interfaces, temporary hacks, duplicate business rules, missing abstractions, overly complex functions, overly complex modules.

Classify each item:

```text
Structural
Architectural
Testing
Documentation
Security
Performance
Operational
```
