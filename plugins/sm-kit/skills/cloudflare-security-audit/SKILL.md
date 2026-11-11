---
name: cloudflare-security-audit
description: A full, independent security audit of a whole repository with Cloudflare's security-audit method — reconnaissance, coverage-led hunting by parallel agents, adversarial validation, schema-checked findings and a report. Manual only; costly. Run only when the owner types /sm-kit:cloudflare-security-audit.
disable-model-invocation: true
argument-hint: "[quick|standard|deep] [paths…]"
---

# Cloudflare security audit (manual only)

A whole-repository vulnerability hunt, separate from the per-change
`security-reviewer` in the checks. It runs many agents; start it only on the
owner's explicit request, never on your own.

The method is Cloudflare's, kept unchanged in
[upstream/SKILL.md](upstream/SKILL.md) with its reference files and
validators (MIT; the pinned commit is in the kit's `UPSTREAM.md`). Read
`upstream/SKILL.md` now and follow its **full audit mode**, with these
settings for this kit:

1. **Before starting, ask the owner once** (skip what the arguments already
   say): the profile (`quick`, `standard` (default), `deep`), the scope (the
   whole repository, paths, or the diff between two refs), and a budget in
   agent runs. State the estimated agent count from its "Cost budget" before
   launching any agent.
2. **Skill directory** is this skill's `upstream/` folder. **Target** is the
   current repository's root. Node.js is needed for the two validators;
   without it, say so and stop before writing a report.
3. **Output directory:** the upstream default,
   `~/security-audit-skill/<repo>/run-<N>`, outside the repository. Never
   inside it, never committed. The findings are confidential.
4. **Agents:** its `research` agent is the `Explore` agent; its `general`
   agent is `general-purpose`. Hunters and verifiers inherit your model. Every
   agent prompt carries the upstream execution-safety block.
5. **Never against anything live:** no deployed site, staging, partner API,
   bank or registrar endpoint, production database or real identity. Source
   and sandboxed local runs only, as upstream says; where a sandbox can't be
   enforced, don't execute the target's code: record it as needing
   validation.
6. **No customer data in any artifact.** Dummy principals and values only
   (`ABCPE1234F`, `9999999999`, `qa+1@example.com`).

When it ends, tell the owner where `REPORT.md` is, the counts by severity,
the needs-validation count, and what the run didn't cover. Each confirmed
finding the owner wants fixed becomes its own change (the `change` skill),
citing the finding's id, not its text.
