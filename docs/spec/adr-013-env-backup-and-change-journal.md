# ADR-013: Environment Backup & Change Journal — Mandatory Pre-Change Guard

## Status

Accepted

## Context

On 2026-08-19 an "orphan cleanup" (based on a DLL built from an **unmerged local
branch**) deleted 13 live plugin steps + 11 plugintypes in DEV. Recovery had **no
authoritative record to consult**:

- The solution ZIP covers only components **inside** the solution — the deleted
  steps were org-level registrations (outside `new_plugin930`), invisible to any
  solution export.
- No journal existed: no "when / who / what / why / on what basis" for any past
  environment write.
- The only recovery source was the source code's own registration doc-comments —
  reconstruction was possible but purely by luck of code hygiene.

Requirement (user, verbatim intent): for complex tasks, back the environment's
solutions up **before** any change; record every change 如实 (as-it-happened,
completely); backup path `workspace/docs/env_backup/{解决方案名称}.zip`; the rule
must live **in the engine** so any agent discovers it.

Two options were considered:

| Option | Mechanism | Trade-off |
|--------|-----------|-----------|
| A. Documentation-only rule | Write the guard rule into CLAUDE.md / skills | Zero code, but relies on every agent reading and obeying prose — the incident itself proves prose alone is insufficient |
| B. Engine-first guard (chosen) | `env_guard` component + `pp env-guard` CLI + guard rule pinned in all discovery layers (CLAUDE.md ×2, skills ×2, ADR) | Small engine surface; the capability is callable, testable, and self-documenting; adoption is seeded by wiring it into existing deploy scripts |

## Decision

1. **Component** — `framework_power/components/env_guard.py`:
   - `backup_solution(client, solution, ws)` — export solution ZIP to
     `workspace/docs/env_backup/{name}.zip`; an existing file **rotates** to
     `{name}.{UTC}.zip` (history is never lost; the canonical path always holds
     the freshest export).
   - `snapshot_plugin_registrations(client, ws)` — org-level plugin registration
     JSON snapshot: assemblies → plugintypes → steps (stage/mode/filtering
     attributes) → step images. This is the **solution-ZIP blind spot**: org-level
     registrations (outside any solution) never appear in solution exports —
     exactly what made the 08-19 deletion unrecoverable from backups.
     System assemblies (`Microsoft.*` / `System.*`) are skipped by default —
     live-pinned: the org has thousands of system steps; a full walk with one
     image query per step times out. Images are fetched via chunked OR-filter
     bulk queries (`get_step_images_bulk`, ≤15 ids per request — 292 custom
     steps ≈ 20 requests, not 292). `include_system=True` opts in explicitly.
   - `append_change(ws, env, actor, intent, changes, backups, basis)` —
     append-only journal `docs/env_backup/CHANGELOG.md`. Every entry: UTC time,
     env, actor, intent, change list, backup files, basis (script/ADR/ticket).
     Corrections are **new entries**, never edits.
   - `read_journal(ws, last=N)` / `list_backups(ws)` — recovery-time queries.
     **Recovery always starts by reading the journal.**

2. **CLI** — `pp env-guard` command group:
   - `pp env-guard backup <solution>… [--env] [--note] [--no-plugin-snapshot]` —
     backup solution ZIP(s) + plugin snapshot, journaled in one atomic entry;
   - `pp env-guard snapshot [--assemblies a,b]` — standalone snapshot;
   - `pp env-guard log [--last N] [--json]` — read the journal;
   - `pp env-guard show` — inventory of the backup dir.
   Requires a workspace (backups land under `docs/env_backup/`).

3. **Discovery layers** (the rule must be findable by any agent):
   - Root `CLAUDE.md` — mandatory-guard paragraph in the safety section;
   - `framework_power/CLAUDE.md` — component table + new §9.10;
   - `.claude/skills/dv-plugin-python/skill.md` + `dv-solution-python/skill.md` —
     pre-change backup step in both entry-point skills;
   - This ADR (context + contract).

4. **Adoption seed** — `ninebot-project/plugins/RollingForecast/deploy.py` and
   `restore_misdeleted_steps.py` call `env_guard.backup_solution` +
   `snapshot_plugin_registrations` + `append_change` before any write, proving
   the pattern for future scripts.

## Consequences

- **Positive**: every environment write from now on has (a) a restorable ZIP of
  affected solutions, (b) a full org-level plugin registration snapshot (covers
  org-level registrations), (c) a truthful append-only audit trail. The exact
  08-19 failure mode (deletion with nothing to consult) is structurally closed.
- **Negative**: solution export takes ~30s per solution (online export API);
  snapshots add ~8 requests per 100 custom steps. Acceptable for pre-change
  overhead; `--no-plugin-snapshot` provides an escape hatch.
- **Rotation disk cost**: history is kept forever by design. At ~1.5 MB per
  `new_plugin930` export this is negligible; large solutions should prune
  rotated history manually when disk matters.
- **Org-level non-plugin writes** (tables, optionsets, webresources) rely on the
  solution ZIP only when they are inside the backed-up solution — out-of-solution
  org-level writes of those types remain unjournaled unless the calling script
  adds a journal entry. The CLI `log` subcommand accepts any script's entry.
