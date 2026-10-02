# Feature Specification: First-use diagnostics and picker comparison

**Created**: 2026-10-02
**Status**: Implemented and verified locally; real comparative measurements not run
**Input**: Owner approved the proposed first stage: readable doctor, visible skipped skills, reproducible picker comparison.

## User Scenarios & Testing

### User Story 1 - Understand setup (Priority: P1)

A new user can see what is ready, what is missing, and the next setup step without interpreting raw diagnostic fields.

**Independent Test**: Check missing CLI/key/skills and a complete temporary installation without network access.

**Acceptance Scenarios**:
1. Given a missing dependency, checking setup names it and suggests a relevant action without displaying credentials.
2. Given an automation consuming existing diagnostic output, the original structured format remains available and compatible.
3. Given no selected host, setup reports each supported host independently; an unused host does not prevent using the other.

### User Story 2 - Know catalog coverage (Priority: P1)

A user sees when the picker did not consider unreadable or unsupported skills, including when no eligible candidates remain.

**Independent Test**: Use a mixed temporary catalog with valid, excluded, malformed and oversized entries. Check that warnings stay local.

**Acceptance Scenarios**:
1. Given a partially unreadable catalog, preview and selection identify skipped entries without uploading paths or warning contents.
2. Given only invalid entries, the picker falls back with visible coverage information.
3. Given an explicitly excluded skill, its private metadata does not reappear in coverage information.
4. Given a short contextual reply, selection stays local before catalog or profile access.
5. Given long candidate descriptions within accepted input limits, selection splits the set into sendable groups or falls back before sending any request.

### User Story 3 - Compare choices honestly (Priority: P2)

A maintainer can prepare paired tasks and compare recorded ordinary-agent choices with picker choices on an identical public catalog.

**Independent Test**: Prepare tasks and import controlled captured results without launching a model or making network calls.

**Acceptance Scenarios**:
1. Given no captures, preparation reports unmeasured results and hides labels from prompts.
2. Given captures with provenance, comparison separates choice correctness, abstentions, failures, time and tokens.
3. Given duplicates, unknown cases, invalid measurements or mismatched fixtures, comparison rejects the report.
4. Given an existing output file, preparation/comparison does not replace it.

### Edge Cases

- Empty or fully excluded catalogs; files changed between inventory and preparation.
- No API key; host binary absent; installed skills modified by a user.
- English and Russian contextual replies and long descriptions.
- One candidate cannot fit a request; confidence too low in any group.
- Incomplete comparison captures and missing time/token measurements.

## Requirements

### Functional Requirements

- **FR-001**: Diagnostics must provide readable explanations and actionable setup suggestions through an explicit human format.
- **FR-002**: Existing structured consumers must retain the same default diagnostic format.
- **FR-003**: Catalog coverage must remain local, visible in preview, recommendation and fallback, and never become selection context.
- **FR-004**: Follow-up bypass, deadlines, strict choice validation and mandatory host checks must remain intact.
- **FR-005**: Accepted inputs must be grouped by actual transmitted size as well as candidate count.
- **FR-006**: Comparison must require captured results and provenance before claiming measurements, and retain unsuccessful outcomes.
- **FR-007**: Preparation and comparison must never execute selected skills, host helpers or network requests.
- **FR-008**: Documentation must explain first use and the limits of authored choice benchmarks.

### Key Entities

- Setup check: current state, explanation and next action.
- Catalog coverage: eligible count and skipped-entry reasons, local only.
- Comparison case: public task, shared candidates, acceptable choices and contextual status.
- Capture: case identity, method, host/model/source, result and optional measurements.

## Success Criteria

- **SC-001**: Every reported setup problem has a specific next action; no credential values appear.
- **SC-002**: All tested skipped catalog entries are accounted for in user-visible picker output and none in remote input.
- **SC-003**: Paired tasks expose identical candidates and no answer labels.
- **SC-004**: Unmeasured configurations have no fabricated accuracy, time, token or savings figures.
- **SC-005**: All required project checks and meaningful regressions pass without live calls.

## Assumptions

- Live provider usage and publication are separate from this local implementation.
- Comparison fixtures are public authored tasks, not verified real-user production workloads.
- Choosing a skill is distinct from successful execution of the user's task.
- Existing structured output stays the default to preserve integrations.
