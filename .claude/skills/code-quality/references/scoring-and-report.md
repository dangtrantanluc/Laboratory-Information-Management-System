# Scoring, severity, prioritization, and report structure

---

## Scoring system

Score each important component 0–10 on these dimensions:

```text
Correctness    Maintainability   Readability
Complexity     Coupling          Cohesion
Testability    Reliability       Security
Performance    Architecture      Extensibility
```

Scale:

```text
0–2    Critical
3–4    Poor
5–6    Acceptable
7–8    Good
9–10   Excellent
```

**Do not compute a blind average.** Apply critical-risk overrides — for example `Security = 1` can make the overall verdict `CRITICAL` even when every other dimension scores highly. State the override and its reason explicitly.

---

## Severity classification

Every finding carries one of:

### CRITICAL
Can cause security compromise, data loss, severe corruption, or system-wide failure.

### HIGH
Likely to cause major bugs, major reliability problems, severe maintainability problems, or significant performance degradation.

### MEDIUM
Important but localized problem.

### LOW
Minor improvement.

### INFO
Observation or optional improvement.

---

## Prioritization

Produce a prioritized remediation list ordered by:

```text
Impact × Likelihood × Cost
```

Default ordering when in doubt:

1. Security vulnerabilities
2. Correctness bugs
3. Data integrity problems
4. Reliability problems
5. Architectural problems
6. High-complexity / high-coupling code
7. Testing gaps
8. Performance issues
9. Maintainability issues
10. Style issues

---

## Report skeleton

Always produce the following structure. Omit a section only when the audit scope genuinely does not reach it (say so rather than padding).

### Executive summary

```text
Overall Quality
Risk Level
Top 5 Problems
Top 5 Strengths
```

### Quality score

| Dimension       | Score | Evidence |
| --------------- | ----: | -------- |
| Correctness     |  X/10 | ...      |
| Maintainability |  X/10 | ...      |
| Complexity      |  X/10 | ...      |
| Coupling        |  X/10 | ...      |
| Cohesion        |  X/10 | ...      |
| Testability     |  X/10 | ...      |
| Security        |  X/10 | ...      |
| Performance     |  X/10 | ...      |
| Architecture    |  X/10 | ...      |

Every row's evidence cell points at concrete code, not adjectives.

### Critical findings

Only important issues, in the finding format from SKILL.md.

### Variable-level findings

Only variables that create meaningful problems.

### Function-level findings

For each important function:

```text
Function
LOC
Complexity
Dependencies
Risk
Recommendation
```

### Class-level findings

Include CK metrics where derivable; mark estimates as estimates.

### Module-level findings

Dependency direction and coupling.

### Architecture findings

Structural problems, with the inferred architecture stated first.

### Security findings

Ranked by severity.

### Testing findings

Important missing tests, and whether existing tests verify behavior.

### Technical debt

Classified by type.

### Refactoring roadmap

```text
Quick Wins
    ↓
Short Term
    ↓
Medium Term
    ↓
Long Term
```

Each entry names the target files, the expected benefit, and a rough cost.

### What not to change

Code that looks unusual but is justified by its domain — say why, so nobody "fixes" it later.
