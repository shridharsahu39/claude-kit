# Upstream sources

What the kit takes from other repositories, pinned, so it can be updated on
purpose. To update one: read the upstream diff since the pinned commit
(`gh api repos/<owner>/<repo>/compare/<pinned>...main`), review any script
before it comes in, update what the kit holds, then the commit and date here.

| Source | Pinned commit (date read) | Licence | What the kit holds | Where |
| --- | --- | --- | --- | --- |
| [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill), `skills/security-audit/` | `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8` (11/11/2026) | MIT | A verbatim copy, without its tests, and the licence. Wrapped by the kit's manual-only skill. | `plugins/sm-kit/skills/cloudflare-security-audit/upstream/` |
| [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills), `skills/karpathy-guidelines/SKILL.md` | `2c606141936f1eeef17fa3043a72095b4765b9c2` (11/11/2026) | MIT per the skill's own frontmatter; the repository has no licence file | The four principles, reworded and shortened; no copied text. | `repo-files/.claude/rules/working.md` |
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable), its own plugin marketplace | tag `skill-v4.8.2` = `035c8f319edd019936525a062fe99e83ca8d12c6` (11/11/2026) | Apache-2.0 | Nothing copied: the shared settings turn its plugin on, pinned to the tag, auto-update off. Its launcher downloads an engine binary from the repository's GitHub releases on first use and refuses one whose SHA-256 doesn't match the pinned `engine-checksums.txt`. | `repo-files/.claude/settings.json` |
| [jeremylongshore/claude-code-plugins-plus-skills](https://github.com/jeremylongshore/claude-code-plugins-plus-skills), `plugins/testing/code-cleanup/agents/circular-dep-untangler.md` | `main` (11/11/2026; not pinned) | Not checked | The approach only: classify a cycle (runtime, type-only, mixed) before fixing it, fix with the smallest change that keeps cohesion, never auto-apply. No copied text. | `plugins/sm-kit/agents/code-quality-reviewer.md`, "Import cycles" |

Updating the Cloudflare copy: replace the files in `upstream/` from the new
commit (skip `*.test.cjs`), check the validators still only read files
(`grep -nE "require\(|child_process|http|net\.|fetch\(|write" upstream/*.cjs`),
and check that the wrapper's notes on output directory, sandbox and agents
still match its `SKILL.md`.

Updating Impeccable: pick the new `skill-v*` tag, read the diff of its
launcher (`.claude/skills/impeccable/scripts/impeccable`) for where it
downloads from and that it still refuses an unverified engine, then change
`ref` in `repo-files/.claude/settings.json` and run `tools/sync.py`.
