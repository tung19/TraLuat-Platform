# Claude for Legal — Update Check vs Baseline (DELTA)

> Checked: 2026-11-05. Scope: find anything NEW in Anthropic's open-source "Claude for Legal"
> (`github.com/anthropics/claude-for-legal`) and in legal-tech press since the team's baseline snapshot,
> for folding into the W6 (contract Review/Draft) workflow spec.
> Method: live GitHub API (commits, tree, marketplace.json, tags, releases) + web search of press.

## Bottom line

**No material new capability since the baseline.** The repo today is structurally identical to what the
team already documented: 12 first-party plugins + 1 partner (cocounsel-legal) = 13, the same 5
managed-agent cookbooks, all plugins still at `1.0.0`. No new plugins, skills, cookbooks, connectors,
slash-command families, or versioned releases. The only post-launch activity is bug-fixes to deploy
scripts, CLA/governance plumbing, marketplace `displayName` cosmetics, and one prose/wording refresh.
Nothing needs to be folded into W6 as "new."

## 1. Live repo state (verified)

- Repo: `github.com/anthropics/claude-for-legal`, **Apache-2.0**, 2026 copyright. ~9.9k stars, ~1.9k forks.
- **38 commits on `main`. Latest commit: 2026-07-23** ("Update plugin content (#104)").
- **No tags. No GitHub releases.** All plugin `plugin.json` still `1.0.0` ("Bump all plugins to 1.0.0 for public launch", 2026-05-11). No `CHANGELOG`.
- **Plugins = 13, unchanged** (12 first-party in `marketplace.json` + `cocounsel-legal` under `external_plugins/`):
  commercial-legal, privacy-legal, product-legal, corporate-legal, employment-legal, regulatory-legal,
  ai-governance-legal, litigation-legal, ip-legal, law-student, legal-clinic, legal-builder-hub (+ cocounsel-legal).
  → **Count now vs baseline 12: still 12 first-party. No new practice area.**
- **Managed-agent cookbooks = 5, unchanged**: diligence-grid, docket-watcher, launch-radar, reg-monitor, renewal-watcher.
- **Skills = 151 SKILL.md files** across the plugins (full inventory below). All the baseline-named skills
  are present (review, vendor-agreement-review, nda-review, saas-msa-review, tabular-review,
  cold-start-interview, dsar-response, launch-review). The larger count just reflects that the baseline's
  "incl." list was not exhaustive — these are **launch-era skills, not post-baseline additions**.

### Commit timeline since launch (nothing substantive)
- 2026-05-11/12 — Initial commit, launch-morning fixes, add cocounsel-legal, remove Lexis refs (partner request).
- 2026-05-15..22 — post-merge cleanup; `displayName` added to marketplace entries; remove unused references; cookbook attribution stamp.
- 2026-05-16..29 — deploy-script fixes (mktemp on Linux; handoff regex truncation); add CLA.md + CLA workflow.
- 2026-06-17 — CLA workflow robustness merges.
- **2026-07-23 (#104, latest)** — "Update plugin content": **markdown prose + YAML comment wording only**.
  Files touched: law-student CLAUDE.md + 6 study skills, legal-clinic memo/research-start, reg-monitor
  README + feed-reader.yaml, regulatory-legal cold-start-interview. No new files; no logic.

## 2. Press / announcements scan

- Launch confirmed **2026-05-12**: 12 practice-area plugins, 20+ MCP connectors, open-sourced same day.
  Built on Claude Opus 4.7. (This is the baseline, not new.)
- Pre-launch precursor: a Feb 2026 Cowork legal plugin + existing Microsoft 365 (Word/Outlook/Excel/PowerPoint)
  integration — i.e. "Claude for Word" in the baseline is part of the M365 story, already known.
- **No credible post-launch "v2", new-practice-area, or new-connector announcement found.** No Anthropic
  primary-source update after May. No Artificial Lawyer piece surfaced in results.
- **Unverified claim to flag:** one low-quality blog mentioned a "June 3, 2026 release adding jurisdiction
  support and litigation-side features." **Not corroborated** — the repo commit log has nothing on/around
  that date (jumps June 17 CLA → July 23 prose), no release, no jurisdiction-support commit. Treat as
  **likely fabricated / not real.** Do not fold in.

## 3. DELTA vs baseline

| Area | Baseline | Now (2026-11-05) | New? |
|---|---|---|---|
| First-party plugins | 12 | 12 | No |
| Partner plugins | 1 (cocounsel-legal) | 1 | No |
| Managed-agent cookbooks | 5 | 5 | No |
| Skills (named) | subset listed | all present, 151 total files | No (launch-era) |
| Versions | 1.0.0 launch | still 1.0.0, no tags/releases | No |
| Connectors | ~20 | ~20, unchanged | No |
| Claude for Word / M365 | ~Apr 2026 beta | unchanged | No |
| "Claude for Legal v2" / new practice area | — | none found | No |

**Net: zero verified-new items to fold into W6.** Forkability is unchanged: Apache-2.0, fully forkable
(same as baseline). W6 mapping is therefore unchanged — the W6-relevant refs remain
`commercial-legal/skills/{vendor-agreement-review, nda-review, review, saas-msa-review}`,
`corporate-legal/skills/tabular-review`, and `managed-agent-cookbooks/diligence-grid`. No new asset
displaces or augments those.

## Full skill inventory (reference, launch-era — NOT new)
151 SKILL.md across 13 plugins. Highlights by W6 relevance:
- commercial-legal: review, vendor-agreement-review, nda-review, saas-msa-review, review-proposals,
  amendment-history, escalation-flagger, renewal-tracker, stakeholder-summary, matter-workspace,
  cold-start-interview, customize.
- corporate-legal: tabular-review, diligence-issue-extraction, material-contract-schedule, closing-checklist,
  board-minutes, written-consent, entity-compliance, deal-team-summary, integration-management, ai-tool-handoff.
- privacy-legal: dpa-review, dsar-response, pia-generation, reg-gap-analysis, policy-monitor, use-case-triage.
- product-legal: launch-review, feature-risk-assessment, is-this-a-problem, marketing-claims-review.
- (Other plugins — employment, litigation, ip, ai-governance, regulatory, law-student, legal-clinic,
  legal-builder-hub, cocounsel-legal — unchanged from launch; see repo tree.)

## Sources
- Repo (live): https://github.com/anthropics/claude-for-legal — commits, tree, marketplace.json, tags(none), releases(none), PR #104.
- Bloomberg Law: https://news.bloomberglaw.com/litigation/anthropic-expands-push-into-legal-industry-with-new-ai-tools
- LawSites / terms.law review: https://www.terms.law/services/ai-implementation/claude-for-legal-review/
- Pulse.bot legaltech coverage: https://www.pulse.bot/legaltech/news/anthropic-rolls-out-claude-for-legal-with-20-connectors-and-12-practice-plugins-d1d77930-89b4-48e1-a171-436ceabde09f/
- (Unverified "June 3 jurisdiction" claim, treat as false): secondary blog only, no primary source, not in commit log.
