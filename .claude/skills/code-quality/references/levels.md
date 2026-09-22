# Analysis levels: variable → function → class → module → architecture

Work bottom-up. At each level, report only findings that carry real risk (see false-positive control in SKILL.md).

---

## Level 1 — Variables

Evaluate:

* Naming
* Type clarity
* Scope
* Lifetime
* Mutability
* Initialization
* Unused variables
* Shadowing
* Magic values
* Mutable default values
* Nullable / `None` / `null` handling
* Unnecessary state
* Duplicate representations of the same data

Identify variables that increase cognitive load or create hidden bugs. Only report variables that create a *meaningful* problem — a short name in a 3-line closure is not a finding.

---

## Level 2 — Functions / methods

For every important function, evaluate:

### Structural metrics

Calculate or estimate (label which):

* LOC
* Number of parameters
* Number of return paths
* Cyclomatic complexity
* Cognitive complexity
* Nesting depth
* Number of branches
* Number of exceptions
* Number of external dependencies
* Number of side effects

### Responsibility

* What is this function actually responsible for?
* Does it have multiple unrelated responsibilities?
* Does it violate the Single Responsibility Principle?
* Is it doing orchestration and business logic simultaneously?
* Is it performing I/O and computation simultaneously?

### Coupling

Identify dependencies on: database, Redis, APIs, filesystem, cloud storage, external services, other classes, global variables, environment variables.

### Cohesion

Do all operations belong to the same conceptual responsibility?

### Error handling

* Exceptions swallowed
* Overly broad `except` / `catch`
* Missing error handling
* Incorrect error propagation
* Incorrect retry behavior
* Silent failures
* Inconsistent return values

### Side effects

Explicitly enumerate:

```text
Database writes
File writes
Network requests
Cache mutation
Global state mutation
External API calls
Message publishing
Logging
```

---

## Level 3 — Classes

For every significant class, evaluate:

### CK metrics

* **WMC** — Weighted Methods per Class
* **CBO** — Coupling Between Objects
* **RFC** — Response For a Class
* **LCOM** — Lack of Cohesion of Methods
* **DIT** — Depth of Inheritance Tree
* **NOC** — Number of Children

Do not fabricate exact metrics that cannot be derived from the available code. When exact calculation is impossible, say explicitly:

> "Estimated from the visible code."

### Design evaluation

* Single Responsibility Principle
* Open/Closed Principle
* Dependency Inversion
* Encapsulation
* Mutable state
* Constructor complexity
* Inheritance vs composition
* God Object risk
* Anemic domain model
* Service class overgrowth
* Hidden dependencies

---

## Level 4 — Modules / packages

Analyze the dependency structure. Look for:

* High fan-in
* High fan-out
* Circular dependencies
* Layer violations
* Cross-layer coupling
* Utility-module abuse
* Shared mutable state
* Improper dependency direction
* Business logic inside controllers
* Database logic inside API handlers
* Infrastructure leaking into domain logic

Construct a conceptual dependency graph when useful:

```text
API
 ↓
Service
 ↓
Repository
 ↓
Database
```

Then identify violations such as:

```text
API → Database
Domain → HTTP
Domain → Framework
Repository → API
```

...when they violate the intended architecture.

---

## Level 5 — Architecture

**Infer** the apparent architecture from the code — do not assume it. Candidates include: layered, Clean Architecture, Hexagonal, MVC, modular monolith, microservices, event-driven, ETL pipeline, data pipeline.

Then evaluate:

### Dependency direction

Ask: *"Who depends on whom?"* — and does that match the intended direction?

### Boundary violations

* Business logic coupled to framework
* Infrastructure coupled to domain
* Controllers performing business logic
* Services performing persistence directly
* Domain models depending on external APIs
* Circular module dependencies

### Architectural risks

* God modules
* God services
* Shared mutable state
* Distributed monolith
* Over-abstraction
* Under-abstraction
* Premature abstraction
* Excessive inheritance
* Excessive dependency injection
* Excessive utility classes
