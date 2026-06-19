backend/.venv/bin/python docs/ops/skills/adinsights-release-readiness/scripts/run_preflight_skillchain.py \
		--prompt "Content Ops Goal P live Instagram Graph adapter behind disabled beta flag; backend implementation with mocked Graph tests, safe errors, retry and expiry handling, tenant isolation, docs/evidence updates; no production activation" \
		--changed-files-from-git \
		--format markdown
## ADinsights Preflight Skillchain
- Router action: `resolve`
- Scope status: `ESCALATE_ARCH_RISK`
- Contract status: `WARN_POSSIBLE_CONTRACT_CHANGE`
- Release status: `GATE_BLOCK`
- Contract executed: `True`
- Output directory: `/var/folders/4k/xdt2s05j1tl9zpyxhwtt8pk80000gn/T/adinsights-preflight-output-pfdjbkgc`

### Release Blocking Issues
- Scope control gate blocked by architecture-level scope risk.

### Release Warnings
- Contract integrity requires follow-up before release.
- Security/PII gate requires verification due to sensitive signals.
