# What a Blue Jackal result establishes

Blue Jackal evaluates developer-declared conditions against a recorded run. The
developer controls the contract and acceptance commands. A PASS answers those
checks for the identified state and observation coverage; it is not a certificate
of security, broad correctness, safe deployment or general agent reliability.

## Independent acceptance

The runner freezes the task contract, seed files, acceptance files, agent command,
verifier runtime and measurement source identity before invoking the agent. Each
execution uses a fresh workspace. The
independent verifier is copied outside that workspace and is checked for changes
before and after evaluation. Verifier changes or verifier-induced workspace
changes make evaluation an ERROR.

Verifier exit codes have a deliberate convention: `0` means acceptance, `1`
means an unmet assertion, and other codes mean evaluation infrastructure error.
Timeouts and unavailable commands are errors. Empty acceptance sets are rejected.
Agent-run tests or statements cannot substitute for these commands.

Acceptance commands are trusted local developer code. They may access resources
with your process's permissions. Blue Jackal is not an OS sandbox and cannot make
hostile same-user code incapable of altering the harness or its records. Use small
disposable fixtures and inspect verifier commands before execution. The supplied
verifier reads JSON; it never imports generated code.

## Observation coverage

The live adapter handles structured Read, Edit and Write attempts and their
reported results. It does not infer file reads from a final diff. C2 and C4 require
returned text-file metadata that identifies the same path and full line range,
an unbounded Read request, and returned content whose UTF-8 SHA-256 matches the
case's initial challenged file. A successful tool status alone is insufficient.
Missing metadata, partial/truncated content or a content mismatch cannot establish
the required read; the condition remains UNDETERMINED. C2 additionally requires
complete direct-tool capture to establish ordering before the first dependent
write attempt.

This is evidence of the adapter's returned content, not an independent
system-call audit. Snapshot comparison identifies net file changes only; it
cannot rule out a temporary write that was later undone.

Unknown tools, malformed streams, unmatched attempts/results, missing terminal
events, process failures and unexplained file changes lower declared coverage.
An observed violation can still establish FAIL when other capture is missing.
No observed violation cannot establish comprehensive compliance when capture is
incomplete. Reports retain UNOBSERVED and challenge UNDETERMINED states.

The scope does not include hidden reads, shell effects, hooks, arbitrary child
processes, network actions or OS-level file activity. Native agent controls can
refuse actions. A denied unauthorized write attempt remains an AUTHORITY failure.
C3 may still pass its narrower condition when there are no completed unauthorized
writes and the agent makes a supported success or failure declaration. Blue Jackal
records relevant evidence; it does not claim to have
prevented the action itself. Do not treat the contract's protected paths as
filesystem access controls.

## Declarations and claims

Only contract-declared anchored lines in the captured final answer are classified.
The default demo recognizes exact `DONE`, `FAILED`, and one explicit extra claim.
Other prose is not understood or fact-checked. A negated line such as `NOT DONE`
does not match the default `DONE` pattern. Define custom patterns conservatively.

Each recognized declaration is checked, so contradictory success and failure
declarations cannot be reduced to whichever one agrees with the result. Missing
final-answer capture or an unavailable work evaluation leaves claim support
UNOBSERVED. A statement of failure can be SUPPORTED when the work fails.

Blue Jackal does not recover chain of thought, internal belief, motivation,
understanding or causal justification. A recorded read before a write is evidence
of that observable ordering, not proof that the agent reconsidered a premise.

## Reset, comparison and identity

Challenge cases recreate frozen relevant starting files and apply only the
declared intervention. Repair verification permits the predeclared policy file
to change while checking task, oracle, seed, agent command, verifier runtime,
measurement source and challenge identities.
Removing a required case, editing acceptance, or suppressing completion language
does not qualify as repair. Complete repair comparison requires all four cases.
C1 requires both outcome agreement and agreement in the set of changed paths,
with accepted work and supported success in every repeat. Content hashes are
also compared, but differing accepted file contents alone do not fail C1.

Inspection verifies the saved record's content hash. Its ID excludes explicitly
volatile metadata, including the recording timestamp. Inspecting a record is not
re-executing the agent; live model execution may differ across fresh runs. Local
hashes do not prove third-party provenance or defend against an actor who can
rewrite both a record and its hashes.

## Local records and exports

Full local records can contain task-derived filenames, verifier command paths,
visible final/assistant text, process errors and other sensitive material. Treat
the run directory as private. Thinking blocks and provider/session metadata are
not retained as the advertised trace, but this does not make other local text
safe to publish.

`blue_jackal export ID` produces a separate typed allowlist derivative with a
manifest. It omits arbitrary text, paths, prompts, visible message bodies and
command data; rejected fields are recorded without echoing their values. The
bundle contains `receipt.json`, `report.html` and `manifest.json`.

This export sacrifices detail deliberately. It cannot reproduce a run by itself
and does not replace the full local evidence. A reviewer must inspect the exact
files before sharing. Pattern scanning cannot certify that arbitrary secrets are
absent, and hashes may disclose equality or allow guesses of low-entropy data.
Blue Jackal has no publication command or automatic upload path.

## Live agent context

The Claude adapter uses installed authenticated tooling. That invocation can
communicate with the provider and may be affected by version, account settings,
native permissions and instructions loaded by the agent. Review these before a
live fixture. Explicit instruction exclusions can be set in the contract; no
claim is made that an empty list suppresses your existing private instructions.

The deterministic demo is offline. A live invocation is neither offline nor a
free-use guarantee. Do not place real credentials or private repository material
in the demo to make it feel realistic.

## Boundaries that remain

There is one live adapter and a constrained direct-file-task contract. This is
not a cross-model benchmark, policy enforcement service, general-purpose agent
recorder, causal debugger, secret scanner or evidence of production readiness.
Engineered demo results do not estimate naturally occurring failure rates.
Any broader claim needs its own appropriate evidence.
