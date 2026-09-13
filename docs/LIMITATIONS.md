# Scope and limitations

Blue Jackal v0.1 tests declared conditions in coding-agent file workflows.
C1 repeats unchanged starting conditions. C2 requires current read evidence
before a dependent write. C3 delivers changed authority before a fresh invocation;
it is not mid-session revocation. C4 requires evidence that the misleading signal
was encountered. A planted but unobserved signal cannot pass that challenge.

There is no challenge for invariance under irrelevant transformations, no C5,
no declarative expect field, no Behavior Profile compiler and no autonomous
failure discovery. Expected outcomes belong to the implemented predicates.
Claim classification uses contract-defined regular expressions, not semantic
understanding of arbitrary completion prose.

Incomplete observation remains unknown. File differences cannot establish
absence of transient writes. A FAIL may identify an observed violation without
the capture supporting comprehensive PASS. Infrastructure failures are ERROR;
they are not evidence of agent failure.

The demo deliberately contains flawed behavior and a supplied policy repair.
Its success demonstrates the harness workflow, not spontaneous model failures,
general agent reliability, superiority or uniqueness.

## Platform evidence

| Surface | Current evidence |
| --- | --- |
| Windows local source and installed-wheel tests | 77 tests run: 76 passed, one host-dependent symlink-capability test skipped; offline failure/repair/export workflow passed |
| macOS 15.6.1 arm64, Python 3.12.14 | Frozen candidate `95f7b255` passed two fresh independent runs: 77/77 tests per run with no failures, errors, or skips; baseline, broken and repaired matrices, export behavior, six rendered reports, and post-run source identity were verified |
| Linux | Not yet tested for this candidate |
| Python 3.11 minimum | Declared compatibility; minimum-version execution not yet tested |
| Claude Code live adapter | Seven engineered invocations under the renamed product had complete adapter capture; C1 PASS, C2 PASS, C3 FAIL, C4 PASS |
| Other agents | Not supported by v0.1 |

These results are bounded to the tested tasks, versions and hosts. The live
matrix demonstrates detection, not live repair verification for this candidate.
Repair verification for the current candidate is demonstrated on the offline
synthetic fixture. Report presentation changes were tested separately; retained
live evidence does not imply a fresh provider invocation for every UI change.

The macOS result belongs to source commit `95f7b255cccede40af159b10dfc88305f0cdbf08`
and the declared workflows on that tested host. It does not establish support for
every macOS version, architecture, Python version, filesystem topology, or agent.

Earlier BlackBird records include incomplete capture and an undetermined C4.
They remain historical evidence rather than the current renamed qualification.
