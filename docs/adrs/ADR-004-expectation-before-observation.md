# ADR-004: Compile Expected Treatment Before Response Observation

**Status:** Accepted  
**Decision:** Compile an immutable expectation record from the approved case, policy, and rubric before provider execution.

## Rationale

A single end-to-end judge can redefine policy after seeing the response. Separating expectation from observation makes regrading explainable and prevents a grader from becoming an unreviewed policy engine.

## Consequences

Case, policy, rubric, and compiler versions become score-affecting inputs. A changed expectation requires a new record and trend decision.
