# Version 0.3 verification

## Locally verified

- 141 offline tests on Python 3.10 and 3.14, including previous first-use work.
- Fourteen skill manifests pass the skill-creator validator.
- Wheel and source distribution build successfully. A fresh Python 3.10 environment installs the wheel, installs fourteen skills into both temporary host destinations, repeats installation unchanged, and reports managed ownership.
- All seven packaged examples print and preview from outside the checkout without network access or local settings changes.
- Controlled provider responses exercise all seven CLI selection paths, source evidence, exact original values and prompt-free metrics.
- Published v0.1 unowned files and v0.2 managed seven-skill fixtures upgrade with preserved extras and backups; modified files, name collisions, symlinks, unknown ownership sets and concurrent conflicts are covered by regressions.
- Independent review found a preview/live payload mismatch and incorrect upgrade diagnosis for missing owned files. Both were fixed and rechecked.

## Limits

These checks establish implementation behavior, not semantic Jev accuracy, demand, task completion improvement, speed or savings. No new paid provider or host-helper evaluation was run. Host login and native skill discovery were not tested. Public example inputs are fictional and are not production benchmarks. The existing picker comparison prepares paired captures but does not launch agents or manufacture missing measurements.

Publication and isolated GitHub installation are pending at the time of this local verification record. Deployment for this repository means its GitHub source distribution/release; there is no server application.
