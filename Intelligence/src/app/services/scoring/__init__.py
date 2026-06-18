"""Scoring subpackage — the four deterministic intelligence engines.

Sanctioned by ``INTELLIGENCE_SPECIFICATION.md`` §16 (the "ask first" approval
required by ``Backend/CLAUDE.md`` §3). Each engine module exposes a **pure
function** over plain dataclasses (no session, no I/O) so the canonical test
vectors (§4.6, §5.4, §6.3, §7.4) are unit-testable to the decimal; a thin
orchestrator in the same module gathers inputs via repositories and persists
snapshots.
"""

from __future__ import annotations
