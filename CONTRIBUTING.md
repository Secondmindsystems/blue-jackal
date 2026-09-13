# Contributing

Start with the offline demo in README.md. Run `python -B -m unittest discover -s tests -v`
from this directory before proposing changes. Include the command, Python version,
operating system, expected result and actual result in bug reports.

Contributions are provided under Apache-2.0, the same license as this project
(inbound equals outbound). Submit only material you have authority to share.
Do not attach credentials, private code, raw prompts, session transcripts or
unreviewed run directories. Review each exported file before sharing it.

Preserve independent acceptance checks and failure fixtures. A test that detects
an intentionally failing agent should pass when the failure is correctly identified.
Do not weaken acceptance criteria or remove completion statements to make a repair pass.
Changes to measurement semantics require explicit new fixtures and documented limits.
