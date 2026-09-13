# How Blue Jackal works

## Behavioral regression testing for coding agents

Your agent passed once. What happens when the conditions change?

Blue Jackal is for teams turning coding agents from experiments into repeatable
engineering workflows. It changes relevant operating conditions and checks whether
the agent still satisfies its declared contract.

## Why Blue Jackal exists

A coding agent can complete a task correctly and still behave incorrectly.

It can produce working code while acting outside its declared authority. It can
rely on information that has changed. It can encounter a success signal and
conclude the work is finished when the acceptance criteria say otherwise. A
workflow that behaves correctly once may also produce a different result the next
time it encounters the same relevant starting state.

Traditional software tests can tell you whether the resulting code works. Blue
Jackal tests the agent workflow itself.

> Unit tests check the code. Blue Jackal checks whether the agent's behavior still
> holds when inputs, evidence, or authority change.

## What Blue Jackal tests

Start with a coding-agent workflow and a declared contract. Run it and check the
result independently. Then change a condition and run it again.

Blue Jackal records actions visible through the supported adapter, checks resulting
files independently, and separates three questions:

- **WORK** — Did the resulting work satisfy the acceptance checks?
- **AUTHORITY** — Did the observed actions stay within the declared boundaries?
- **CLAIM** — Did the agent's completion claim agree with the independently checked
  result?

Those answers do not have to agree. An agent can produce correct work while
violating its authority. It can stay within its authority while producing incorrect
work. It can say the task is complete when the independent checks disagree.

That separation is central to Blue Jackal.

## The core experiment

```text
Declared contract
       |
Starting conditions
       |
Agent runs
       |
Independent check
       |
Change a condition
       |
Run again
       |
Observe behavior
       |
WORK / AUTHORITY / CLAIM
       |
Pass or divergence
       |
Repair
       |
Run the same challenge again
```

The question is larger than whether the agent passed:

> Does the agent continue to behave appropriately when the conditions governing
> that behavior change?

## The four conditions

Blue Jackal v0.1 pressure-tests four areas.

### Repeat stability

Run the same task from the same relevant starting state multiple times and compare
the independently checked outcomes and resulting changes.

### Changed input

Change information the agent needs and check whether it observes the current state
before taking dependent action.

### Changed authority

Start a fresh run with narrower declared authority and check whether the observed
actions respect the new boundary. This is a contract test. Blue Jackal observes the
supported action stream; it does not enforce filesystem permissions.

### Misleading success evidence

Introduce a misleading success signal, establish that the agent encountered it,
and independently verify whether the actual work warrants completion.

## Correct work can conceal incorrect conduct

Consider this recorded shape:

```text
TASK
Update result.json

BASELINE
Agent completes task
WORK       PASS
AUTHORITY  PASS
CLAIM      SUPPORTED

CHANGE
Start a fresh run with result.json declared protected

SECOND RUN
Agent edits result.json anyway
WORK       PASS
AUTHORITY  FAIL
CLAIM      SUPPORTED
```

The agent still produced the correct result. Ordinary output validation could call
that a success. Blue Jackal exposes the behavioral regression: the work passed,
while the observed action violated the changed boundary.

## Who it is for

Blue Jackal is built for developers and engineering teams moving from experimental
coding-agent use to repeatable agent workflows:

```text
Agent experiment
      |
Repeatable workflow
      |
Behavioral expectations
      |
Operational dependency
      |
Regression risk
      |
Behavioral regression testing
```

This includes developers building workflows around Claude Code, Codex, or custom
coding agents; agent harness and platform engineers; and AI evaluation and
reliability engineers.

Once you expect an agent workflow to behave a certain way repeatedly, you have
something worth regression-testing.

## Where it fits

```text
CODEBASE / SOFTWARE
        ^
        | acted on by
CODING AGENT
        ^
        | operates through
AGENT WORKFLOW / HARNESS
        |
        | pressure-tested by
        v
BLUE JACKAL
        |
        +-- establish a baseline
        +-- change conditions
        +-- observe supported actions
        +-- check the result independently
        +-- expose divergence
        +-- verify the repair
```

Blue Jackal does not replace the coding agent or its harness. It pressure-tests the
workflow around them.

## From incident to regression fixture

Blue Jackal pressure-tests coding-agent workflows before teams trust them with
consequential codebases, automate them, or put them into production.

The goal is to turn a failure into something reproducible:

```text
Find the divergence
      |
Inspect the evidence
      |
Repair the workflow
      |
Run the same challenge again
      |
Keep the regression fixture
```

The workflow moves from "we tested the agent and it worked" to evidence that the
agent continued to satisfy its contract after the operating conditions changed.
