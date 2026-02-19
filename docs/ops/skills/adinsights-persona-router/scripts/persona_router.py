#!/usr/bin/env python3
"""Router v2 for ADinsights persona selection and decision-packet generation."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit("Missing dependency: pyyaml. Install with `pip install pyyaml`.") from exc


SOURCE_WEIGHTS = {
    "explicit_stream": 0.90,
    "folder_path": 0.80,
    "domain_keyword": 0.60,
}
SOURCE_RANK = {
    "explicit_persona_name": 0,
    "explicit_stream": 1,
    "folder_path": 2,
    "domain_keyword": 3,
}
CONFLICT_PENALTY = 0.20
CROSS_STREAM_PENALTY = 0.15
MAX_SUPPORT_BONUS = 0.20
SUPPORT_BONUS_STEP = 0.10
SCHEMA_VERSION = "2.1.0"

CONTRACT_HINT_KEYWORDS = (
    "contract",
    "breaking change",
    "serializer",
    "openapi",
    "schema",
    "response field",
    "request field",
    "dbt model",
    "snapshot",
    "integration-data-contract-matrix",
    "api-contract-changelog",
)

CONTRACT_HINT_PATH_PATTERNS = (
    r"docs/project/api-contract-changelog\.md",
    r"docs/project/integration-data-contract-matrix\.md",
    r"backend/.*/serializers\.py",
    r"backend/.*/views\.py",
    r"backend/.*/urls\.py",
    r"backend/.*/schema.*\.py",
    r"dbt/models/.*\.(sql|yml)",
    r"dbt/snapshots/.*\.(sql|yml)",
    r"^infrastructure/airbyte/.*",
    r"^integrations/.*",
)

RELEASE_INTENT_KEYWORDS = (
    "release",
    "go-live",
    "go live",
    "deploy",
    "production readiness",
    "release checklist",
    "readiness gate",
    "ship to prod",
)


def default_repo_root() -> Path:
    # /repo/docs/ops/skills/adinsights-persona-router/scripts/persona_router.py
    return Path(__file__).resolve().parents[5]


def default_catalog_path() -> Path:
    return (
        default_repo_root()
        / "docs"
        / "ops"
        / "skills"
        / "adinsights-persona-router"
        / "references"
        / "persona-catalog.yaml"
    )


def default_contract_signal_patterns_path() -> Path:
    return (
        default_repo_root()
        / "docs"
        / "ops"
        / "skills"
        / "adinsights-contract-guard"
        / "references"
        / "contract-signal-patterns.yaml"
    )


def load_contract_signal_patterns(path: Path) -> tuple[list[str], list[str]]:
    fallback_paths = [str(p) for p in CONTRACT_HINT_PATH_PATTERNS]
    fallback_keywords = [str(keyword) for keyword in CONTRACT_HINT_KEYWORDS]
    if not path.exists():
        return fallback_keywords, fallback_paths

    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        return fallback_keywords, fallback_paths

    keywords = data.get("keywords")
    paths = data.get("path_patterns")
    if not isinstance(keywords, list) or not isinstance(paths, list):
        return fallback_keywords, fallback_paths

    keyword_list = [str(keyword).strip().lower() for keyword in keywords if str(keyword).strip()]
    path_list = [str(pattern) for pattern in paths if str(pattern).strip()]
    if not keyword_list or not path_list:
        return fallback_keywords, fallback_paths

    return keyword_list, path_list


def load_catalog(catalog_path: Path) -> dict[str, Any]:
    data = yaml.safe_load(catalog_path.read_text()) or {}
    personas = data.get("personas")
    streams = data.get("streams")
    if not isinstance(personas, list) or not isinstance(streams, dict):
        raise ValueError("Catalog must contain `personas` list and `streams` map.")

    by_id: dict[str, dict[str, Any]] = {}
    name_or_alias_to_id: dict[str, str] = {}

    for persona in personas:
        persona_id = str(persona["id"])
        by_id[persona_id] = persona

        name = str(persona["name"]).strip().lower()
        name_or_alias_to_id[name] = persona_id
        for alias in persona.get("aliases", []):
            alias_key = str(alias).strip().lower()
            if alias_key:
                name_or_alias_to_id[alias_key] = persona_id

    confidence_policy = data.get("confidence_policy", {})
    auto_resolve_min = float(confidence_policy.get("auto_resolve_min", 0.75))
    clarify_min = float(confidence_policy.get("clarify_min", 0.55))

    stream_order = sorted(streams.keys())

    return {
        "raw": data,
        "personas_by_id": by_id,
        "persona_lookup": name_or_alias_to_id,
        "streams": streams,
        "stream_order": stream_order,
        "auto_resolve_min": auto_resolve_min,
        "clarify_min": clarify_min,
    }


def persona_to_stream_map(streams: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for stream_id, stream_info in streams.items():
        out[str(stream_info.get("primary"))] = stream_id
        out[str(stream_info.get("backup"))] = stream_id
    return out


def extract_prompt_paths(prompt: str) -> list[str]:
    pattern = r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]*)+/?"
    return sorted({match.group(0) for match in re.finditer(pattern, prompt)})


def discover_changed_files_from_git(repo_root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []

    changed: list[str] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.rstrip("\n")
        if not line:
            continue
        path_part = line[3:] if len(line) > 3 else ""
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1]
        path_part = path_part.strip()
        if path_part:
            changed.append(path_part)
    return changed


def find_explicit_persona_id(prompt: str, persona_lookup: dict[str, str]) -> str | None:
    lower = prompt.lower()
    # Match longer aliases first so "integration lead" beats "lead"-like aliases.
    for key in sorted(persona_lookup.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(key)}\b", lower):
            return persona_lookup[key]
    return None


def find_explicit_stream_ids(prompt: str, stream_order: list[str]) -> list[str]:
    lower = prompt.lower()
    found: set[str] = set()

    for match in re.finditer(r"\b(?:stream|workstream)\s*([1-7])\b", lower):
        found.add(f"S{match.group(1)}")

    for match in re.finditer(r"\bs([1-7])(?:-[a-z0-9]+)?\b", lower):
        found.add(f"S{match.group(1)}")

    return [sid for sid in stream_order if sid in found]


def stream_matches_for_paths(paths: list[str], streams: dict[str, Any], stream_order: list[str]) -> dict[str, list[str]]:
    lower_paths = [p.lower() for p in paths]
    matched: dict[str, list[str]] = {sid: [] for sid in stream_order}

    for sid in stream_order:
        folder_hints = [str(h).lower() for h in streams[sid].get("folder_hints", [])]
        for hint in folder_hints:
            if any(hint in p for p in lower_paths):
                matched[sid].append(hint)

    return {sid: hints for sid, hints in matched.items() if hints}


def stream_matches_for_keywords(prompt: str, streams: dict[str, Any], stream_order: list[str]) -> dict[str, list[str]]:
    lower = prompt.lower()
    matched: dict[str, list[str]] = {sid: [] for sid in stream_order}

    for sid in stream_order:
        for kw in streams[sid].get("keywords", []):
            kw_s = str(kw).strip().lower()
            if not kw_s:
                continue
            if re.search(rf"\b{re.escape(kw_s)}\b", lower):
                matched[sid].append(kw_s)

    return {sid: kws for sid, kws in matched.items() if kws}


def merge_unique(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return out


def packet_evidence_item(evidence_type: str, value: str, strength: float, source: str) -> dict[str, Any]:
    return {
        "type": evidence_type,
        "value": value,
        "strength": round(max(0.0, min(1.0, strength)), 4),
        "source": source,
    }


def detect_contract_sensitivity(
    prompt: str,
    paths: list[str],
    contract_keywords: list[str],
    contract_path_patterns: list[str],
) -> tuple[bool, list[str]]:
    lower_prompt = prompt.lower()
    reasons: list[str] = []

    for keyword in contract_keywords:
        if keyword in lower_prompt:
            reasons.append(f"Prompt contains contract keyword '{keyword}'.")

    for path in paths:
        for pattern in contract_path_patterns:
            if re.search(pattern, path, flags=re.IGNORECASE):
                reasons.append(f"Path '{path}' matched contract pattern '{pattern}'.")

    deduped_reasons = merge_unique(reasons)
    return bool(deduped_reasons), deduped_reasons


def detect_release_intent(prompt: str) -> tuple[bool, str | None]:
    lower_prompt = prompt.lower()
    for keyword in RELEASE_INTENT_KEYWORDS:
        if keyword in lower_prompt:
            return True, keyword
    return False, None


def build_evidence(
    explicit_persona_id: str | None,
    explicit_stream_ids: list[str],
    folder_stream_matches: dict[str, list[str]],
    keyword_stream_matches: dict[str, list[str]],
    explicit_paths: list[str],
    changed_files: list[str],
    prompt_paths: list[str],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []

    if explicit_persona_id:
        evidence.append(
            packet_evidence_item(
                evidence_type="explicit_persona_name",
                value=explicit_persona_id,
                strength=1.00,
                source="prompt",
            )
        )

    for stream_id in explicit_stream_ids:
        evidence.append(
            packet_evidence_item(
                evidence_type="explicit_stream",
                value=stream_id,
                strength=SOURCE_WEIGHTS["explicit_stream"],
                source="prompt",
            )
        )

    for stream_id, hints in folder_stream_matches.items():
        for hint in hints:
            evidence.append(
                packet_evidence_item(
                    evidence_type="folder_path",
                    value=f"{stream_id}:{hint}",
                    strength=SOURCE_WEIGHTS["folder_path"],
                    source="paths",
                )
            )

    for stream_id, keywords in keyword_stream_matches.items():
        for keyword in keywords:
            evidence.append(
                packet_evidence_item(
                    evidence_type="domain_keyword",
                    value=f"{stream_id}:{keyword}",
                    strength=SOURCE_WEIGHTS["domain_keyword"],
                    source="prompt",
                )
            )

    for path in explicit_paths:
        evidence.append(
            packet_evidence_item(
                evidence_type="explicit_path",
                value=path,
                strength=0.75,
                source="explicit_paths",
            )
        )
    for path in changed_files:
        evidence.append(
            packet_evidence_item(
                evidence_type="changed_file",
                value=path,
                strength=0.70,
                source="changed_files",
            )
        )
    for path in prompt_paths:
        evidence.append(
            packet_evidence_item(
                evidence_type="prompt_path",
                value=path,
                strength=0.65,
                source="prompt_paths",
            )
        )

    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in evidence:
        key = (str(item["type"]), str(item["value"]), str(item["source"]))
        if key not in seen:
            deduped.append(item)
            seen.add(key)

    return deduped


def make_stream_candidate(
    stream_id: str,
    sources: list[str],
    explicit_stream_ids: list[str],
    explicit_persona_stream: str | None,
    cross_stream: bool,
) -> dict[str, Any]:
    base = max(SOURCE_WEIGHTS[s] for s in sources)
    support_bonus = min(MAX_SUPPORT_BONUS, SUPPORT_BONUS_STEP * (len(set(sources)) - 1))

    conflict_count = 0
    for sid in explicit_stream_ids:
        if sid != stream_id:
            conflict_count += 1
    if explicit_persona_stream and explicit_persona_stream != stream_id:
        conflict_count += 1

    score = base + support_bonus - (CONFLICT_PENALTY * conflict_count)
    if cross_stream:
        score -= CROSS_STREAM_PENALTY

    score = max(0.0, min(1.0, score))

    # Pick best source rank for deterministic tie-breaking.
    source_rank = min(SOURCE_RANK[s] for s in set(sources))
    resolved_by = min(set(sources), key=lambda s: SOURCE_RANK[s])

    return {
        "kind": "stream",
        "stream_id": stream_id,
        "sources": sorted(set(sources), key=lambda s: SOURCE_RANK[s]),
        "resolved_by": resolved_by,
        "source_rank": source_rank,
        "base": round(base, 4),
        "support_bonus": round(support_bonus, 4),
        "conflict_count": conflict_count,
        "score": round(score, 4),
    }


def make_persona_candidate(
    persona_id: str,
    inferred_stream: str | None,
    strong_stream_ids: list[str],
    cross_stream: bool,
) -> dict[str, Any]:
    base = 1.0
    conflict_count = 0

    if inferred_stream:
        for sid in strong_stream_ids:
            if sid != inferred_stream:
                conflict_count += 1

    score = base - (CONFLICT_PENALTY * conflict_count)
    if cross_stream:
        score -= CROSS_STREAM_PENALTY
    score = max(0.0, min(1.0, score))

    return {
        "kind": "persona",
        "persona_id": persona_id,
        "stream_id": inferred_stream,
        "sources": ["explicit_persona_name"],
        "resolved_by": "explicit_persona_name",
        "source_rank": SOURCE_RANK["explicit_persona_name"],
        "base": base,
        "support_bonus": 0.0,
        "conflict_count": conflict_count,
        "score": round(score, 4),
    }


def select_best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None

    return sorted(
        candidates,
        key=lambda c: (-c["score"], c["source_rank"], c.get("stream_id", ""), c.get("persona_id", "")),
    )[0]


def choose_report_template(mode: str, cross_stream: bool, prompt: str) -> str:
    if cross_stream:
        return "C"
    lower = prompt.lower()
    if re.search(r"\b(phase\s*0|backlog|workstream review|kpi|dod)\b", lower):
        return "A"
    if mode == "preflight":
        return "B"
    return "B"


def persona_summary(persona: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": persona["id"],
        "name": persona["name"],
        "role": persona["role"],
    }


def build_escalation_decision(cross_stream: bool, conflict: bool, confidence: float) -> dict[str, Any]:
    reviewers: list[str] = []
    reasons: list[str] = []

    if cross_stream:
        reviewers.extend(["Raj", "Mira"])
        reasons.append("Multiple streams detected in routing evidence.")

    if conflict and confidence < 0.75:
        reasons.append("Conflicting strong signals reduced routing confidence.")

    return {
        "advisory_only": True,
        "required_reviewers": merge_unique(reviewers),
        "reason": " ".join(reasons) if reasons else "No escalation required by router signals.",
    }


def build_clarifying_question(conflict: bool, cross_stream: bool, touched_streams: list[str]) -> str:
    if cross_stream and touched_streams:
        return (
            "Your request maps to multiple streams "
            f"({', '.join(touched_streams)}). Which single stream should lead this pass?"
        )
    if conflict:
        return (
            "I detected conflicting persona and scope signals. "
            "Should I prioritize the named persona or the detected folder/stream scope?"
        )
    return (
        "I could not confidently map this request to a persona. "
        "Please provide a stream ID (for example S1-S7), persona name, or concrete folder path."
    )


def collect_required_artifacts(
    selected_stream: str | None,
    touched_streams: list[str],
    streams: dict[str, Any],
    personas_by_id: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    stream_ids = touched_streams[:] if touched_streams else ([selected_stream] if selected_stream else [])

    tests: list[str] = []
    docs: list[str] = []

    for sid in stream_ids:
        info = streams.get(sid)
        if not info:
            continue
        for pid_key in ("primary", "backup"):
            pid = info.get(pid_key)
            if pid in personas_by_id:
                tests.extend(str(t) for t in personas_by_id[pid].get("required_tests", []))
                docs.extend(str(d) for d in personas_by_id[pid].get("primary_docs", []))

    docs.extend([
        "AGENTS.md",
        "docs/workstreams.md",
        "docs/ops/escalation-rules.md",
    ])

    return merge_unique(tests), merge_unique(docs)


def build_decision_packet(
    prompt: str,
    mode: str,
    explicit_paths: list[str],
    changed_files: list[str],
    use_git_changed_files: bool,
    catalog_path: Path,
) -> dict[str, Any]:
    catalog = load_catalog(catalog_path)
    streams = catalog["streams"]
    personas_by_id = catalog["personas_by_id"]
    stream_order = catalog["stream_order"]
    persona_lookup = catalog["persona_lookup"]
    persona_stream_lookup = persona_to_stream_map(streams)
    auto_resolve_min = catalog["auto_resolve_min"]
    clarify_min = catalog["clarify_min"]

    prompt_paths = extract_prompt_paths(prompt)
    all_paths = merge_unique(explicit_paths + changed_files + prompt_paths)
    contract_keywords, contract_path_patterns = load_contract_signal_patterns(
        default_contract_signal_patterns_path()
    )
    contract_sensitive, contract_reasons = detect_contract_sensitivity(
        prompt,
        all_paths,
        contract_keywords=contract_keywords,
        contract_path_patterns=contract_path_patterns,
    )
    release_requested, release_keyword = detect_release_intent(prompt)

    explicit_persona_id = find_explicit_persona_id(prompt, persona_lookup)
    explicit_stream_ids = find_explicit_stream_ids(prompt, stream_order)
    folder_stream_matches = stream_matches_for_paths(all_paths, streams, stream_order)
    folder_stream_ids = sorted(folder_stream_matches.keys(), key=lambda sid: stream_order.index(sid))
    keyword_stream_matches = stream_matches_for_keywords(prompt, streams, stream_order)
    keyword_stream_ids = sorted(keyword_stream_matches.keys(), key=lambda sid: stream_order.index(sid))
    evidence = build_evidence(
        explicit_persona_id=explicit_persona_id,
        explicit_stream_ids=explicit_stream_ids,
        folder_stream_matches=folder_stream_matches,
        keyword_stream_matches=keyword_stream_matches,
        explicit_paths=explicit_paths,
        changed_files=changed_files,
        prompt_paths=prompt_paths,
    )

    explicit_persona_stream = None
    if explicit_persona_id:
        explicit_persona_stream = persona_stream_lookup.get(explicit_persona_id)

    strong_stream_ids = merge_unique(explicit_stream_ids + folder_stream_ids)

    touched_streams = merge_unique(
        ([explicit_persona_stream] if explicit_persona_stream else [])
        + explicit_stream_ids
        + folder_stream_ids
        + keyword_stream_ids
    )
    touched_streams = [sid for sid in touched_streams if sid]
    cross_stream = len(touched_streams) > 1

    stream_sources: dict[str, list[str]] = {}
    for sid in explicit_stream_ids:
        stream_sources.setdefault(sid, []).append("explicit_stream")
    for sid in folder_stream_ids:
        stream_sources.setdefault(sid, []).append("folder_path")
    for sid in keyword_stream_ids:
        stream_sources.setdefault(sid, []).append("domain_keyword")

    candidates: list[dict[str, Any]] = []

    if explicit_persona_id:
        candidates.append(
            make_persona_candidate(
                explicit_persona_id,
                explicit_persona_stream,
                strong_stream_ids,
                cross_stream,
            )
        )

    for sid in stream_order:
        sources = stream_sources.get(sid)
        if not sources:
            continue
        candidates.append(
            make_stream_candidate(
                sid,
                sources,
                explicit_stream_ids,
                explicit_persona_stream,
                cross_stream,
            )
        )

    selected = select_best_candidate(candidates)

    if selected is None:
        conflict_flags = {
            "conflict": False,
            "cross_stream": False,
            "strong_conflict_count": 0,
        }
        downstream = {
            "invoke_scope_gatekeeper": True,
            "invoke_contract_guard": contract_sensitive,
            "invoke_release_readiness": release_requested,
        }
        decision_trace = (
            "no_candidates; "
            "reason=no_persona_or_stream_signals; "
            f"contract_sensitive={contract_sensitive}; "
            f"release_requested={release_requested}; "
            "action=clarify"
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "input_prompt": prompt,
            "resolved_by": "ask_user_for_clarification",
            "action": "clarify",
            "confidence": 0.0,
            "selected_persona": None,
            "backup_persona": None,
            "conflict_flags": conflict_flags,
            "touched_streams": [],
            "required_tests": [],
            "docs_to_open": ["AGENTS.md", "docs/workstreams.md"],
            "escalation_decision": {
                "advisory_only": True,
                "required_reviewers": [],
                "reason": "No routing signals were detected.",
            },
            "recommended_report_template": choose_report_template(mode, False, prompt),
            "clarifying_question": build_clarifying_question(False, False, []),
            "downstream_recommendations": downstream,
            "invoke_scope_gatekeeper": downstream["invoke_scope_gatekeeper"],
            "evidence": evidence,
            "decision_trace": decision_trace,
            "rationale": [
                "No persona aliases, stream IDs, folder hints, or keyword hints matched.",
                "Request requires clarification before routing.",
            ],
            "signals": {
                "explicit_persona_id": None,
                "explicit_stream_ids": [],
                "folder_stream_ids": [],
                "keyword_stream_ids": [],
                "explicit_paths": explicit_paths,
                "changed_files": changed_files,
                "prompt_paths": prompt_paths,
                "used_git_changed_files": use_git_changed_files,
                "contract_sensitive": contract_sensitive,
                "contract_reasons": contract_reasons,
                "release_requested": release_requested,
                "release_keyword": release_keyword,
            },
        }

    selected_score = float(selected["score"])
    conflict_count = int(selected["conflict_count"])
    conflict = conflict_count > 0

    should_clarify = False
    if selected_score < clarify_min:
        should_clarify = True
    elif selected_score < auto_resolve_min and (conflict or cross_stream):
        # Keep cross-stream prompts actionable when score is at threshold.
        should_clarify = True

    # Exception: if we only have stream/path evidence and score hits the boundary,
    # resolve with escalation instead of forcing clarification.
    if should_clarify and not conflict and cross_stream and selected_score >= auto_resolve_min:
        should_clarify = False

    selected_persona: dict[str, Any] | None = None
    backup_persona: dict[str, Any] | None = None
    selected_stream: str | None = selected.get("stream_id")

    if selected["kind"] == "persona":
        selected_persona = personas_by_id[selected["persona_id"]]
        if not selected_stream:
            selected_stream = persona_stream_lookup.get(selected["persona_id"])
        if selected_stream and selected_stream in streams:
            backup_id = streams[selected_stream].get("backup")
            if backup_id in personas_by_id:
                backup_persona = personas_by_id[backup_id]
    else:
        if selected_stream and selected_stream in streams:
            primary_id = streams[selected_stream].get("primary")
            backup_id = streams[selected_stream].get("backup")
            selected_persona = personas_by_id.get(primary_id)
            backup_persona = personas_by_id.get(backup_id)

    required_tests, docs_to_open = collect_required_artifacts(
        selected_stream,
        touched_streams,
        streams,
        personas_by_id,
    )

    escalation_decision = build_escalation_decision(cross_stream, conflict, selected_score)

    action = "clarify" if should_clarify else "resolve"
    clarifying_question = (
        build_clarifying_question(conflict, cross_stream, touched_streams)
        if action == "clarify"
        else None
    )

    invoke_scope_gatekeeper = cross_stream or selected_score < auto_resolve_min
    downstream_recommendations = {
        "invoke_scope_gatekeeper": invoke_scope_gatekeeper,
        "invoke_contract_guard": contract_sensitive,
        "invoke_release_readiness": release_requested,
    }

    rationale = [
        f"Selected via {selected['resolved_by']} with score {selected_score:.2f}.",
        f"Strong streams: {', '.join(strong_stream_ids) if strong_stream_ids else 'none'}.",
        f"Touched streams: {', '.join(touched_streams) if touched_streams else 'none'}.",
    ]
    if conflict:
        rationale.append(f"Detected {conflict_count} strong conflict(s).")
    if cross_stream:
        rationale.append("Cross-stream signal detected; advisory escalation prepared.")
    if contract_sensitive and contract_reasons:
        rationale.append("Contract-sensitive indicators detected; contract guard recommended.")
    if release_requested and release_keyword:
        rationale.append(f"Release intent detected from keyword '{release_keyword}'.")

    conflict_flags = {
        "conflict": conflict,
        "cross_stream": cross_stream,
        "strong_conflict_count": conflict_count,
    }
    winner = selected.get("persona_id") or selected.get("stream_id") or "none"
    decision_trace = (
        f"winner={winner}; "
        f"resolved_by={selected['resolved_by']}; "
        f"score={selected_score:.4f}; "
        f"conflicts={conflict_count}; "
        f"cross_stream={cross_stream}; "
        f"action={action}; "
        f"contract_sensitive={contract_sensitive}; "
        f"release_requested={release_requested}"
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "input_prompt": prompt,
        "resolved_by": selected["resolved_by"],
        "action": action,
        "confidence": round(selected_score, 4),
        "selected_persona": persona_summary(selected_persona) if selected_persona else None,
        "backup_persona": persona_summary(backup_persona) if backup_persona else None,
        "conflict_flags": conflict_flags,
        "touched_streams": touched_streams,
        "required_tests": required_tests,
        "docs_to_open": docs_to_open,
        "escalation_decision": escalation_decision,
        "recommended_report_template": choose_report_template(mode, cross_stream, prompt),
        "clarifying_question": clarifying_question,
        "downstream_recommendations": downstream_recommendations,
        "invoke_scope_gatekeeper": downstream_recommendations["invoke_scope_gatekeeper"],
        "evidence": evidence,
        "decision_trace": decision_trace,
        "rationale": rationale,
        "signals": {
            "explicit_persona_id": explicit_persona_id,
            "explicit_stream_ids": explicit_stream_ids,
            "folder_stream_ids": folder_stream_ids,
            "keyword_stream_ids": keyword_stream_ids,
            "explicit_paths": explicit_paths,
            "changed_files": changed_files,
            "prompt_paths": prompt_paths,
            "used_git_changed_files": use_git_changed_files,
            "folder_matches": folder_stream_matches,
            "keyword_matches": keyword_stream_matches,
            "contract_sensitive": contract_sensitive,
            "contract_reasons": contract_reasons,
            "release_requested": release_requested,
            "release_keyword": release_keyword,
        },
    }


def decision_packet_to_markdown(packet: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("## Persona Router Decision Packet")
    lines.append(f"- Schema version: `{packet.get('schema_version', 'unknown')}`")
    lines.append(f"- Action: `{packet['action']}`")
    lines.append(f"- Resolved by: `{packet['resolved_by']}`")
    lines.append(f"- Confidence: `{packet['confidence']}`")
    downstream = packet.get("downstream_recommendations", {})
    lines.append(f"- Invoke scope gatekeeper: `{downstream.get('invoke_scope_gatekeeper')}`")
    lines.append(f"- Invoke contract guard: `{downstream.get('invoke_contract_guard')}`")
    lines.append(f"- Invoke release readiness: `{downstream.get('invoke_release_readiness')}`")

    selected = packet.get("selected_persona")
    backup = packet.get("backup_persona")

    if selected:
        lines.append(f"- Selected persona: `{selected['name']}` ({selected['id']})")
    else:
        lines.append("- Selected persona: `None`")

    if backup:
        lines.append(f"- Backup persona: `{backup['name']}` ({backup['id']})")
    else:
        lines.append("- Backup persona: `None`")

    lines.append(f"- Touched streams: `{', '.join(packet.get('touched_streams', [])) or 'none'}`")

    cf = packet.get("conflict_flags", {})
    lines.append(
        "- Conflict flags: "
        f"`conflict={cf.get('conflict')}`, "
        f"`cross_stream={cf.get('cross_stream')}`, "
        f"`strong_conflict_count={cf.get('strong_conflict_count')}`"
    )

    lines.append("\n### Required Tests")
    tests = packet.get("required_tests", [])
    if tests:
        lines.extend([f"- `{cmd}`" for cmd in tests])
    else:
        lines.append("- None")

    lines.append("\n### Docs To Open")
    docs = packet.get("docs_to_open", [])
    if docs:
        lines.extend([f"- `{doc}`" for doc in docs])
    else:
        lines.append("- None")

    lines.append("\n### Escalation")
    esc = packet.get("escalation_decision", {})
    reviewers = esc.get("required_reviewers", [])
    lines.append(f"- Advisory-only: `{esc.get('advisory_only')}`")
    lines.append(f"- Required reviewers: `{', '.join(reviewers) or 'none'}`")
    lines.append(f"- Reason: {esc.get('reason', 'n/a')}")

    lines.append("\n### Recommended Template")
    lines.append(f"- `{packet.get('recommended_report_template')}`")

    lines.append("\n### Decision Trace")
    lines.append(f"- {packet.get('decision_trace', 'n/a')}")

    lines.append("\n### Evidence")
    evidence = packet.get("evidence", [])
    if evidence:
        for item in evidence:
            lines.append(
                "- "
                f"`{item.get('type')}` "
                f"`{item.get('value')}` "
                f"(strength={item.get('strength')}, source={item.get('source')})"
            )
    else:
        lines.append("- None")

    question = packet.get("clarifying_question")
    if question:
        lines.append("\n### Clarifying Question")
        lines.append(f"- {question}")

    lines.append("\n### Rationale")
    lines.extend([f"- {item}" for item in packet.get("rationale", [])])

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ADinsights persona router v2")
    parser.add_argument("--prompt", required=True, help="Prompt text to route.")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--mode", choices=["resolve", "preflight"], default="resolve")
    parser.add_argument("--path", action="append", default=[], help="Explicit path hint (repeatable).")
    parser.add_argument("--changed-file", action="append", default=[], help="Changed file path hint (repeatable).")
    parser.add_argument(
        "--changed-files-from-git",
        action="store_true",
        help="Include changed files discovered via `git status --porcelain`.",
    )
    parser.add_argument("--catalog", type=Path, default=default_catalog_path())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = default_repo_root()

    changed_files = list(args.changed_file)
    if args.changed_files_from_git:
        changed_files.extend(discover_changed_files_from_git(repo_root))

    packet = build_decision_packet(
        prompt=args.prompt,
        mode=args.mode,
        explicit_paths=list(args.path),
        changed_files=merge_unique(changed_files),
        use_git_changed_files=args.changed_files_from_git,
        catalog_path=args.catalog,
    )

    if args.format == "markdown":
        print(decision_packet_to_markdown(packet))
    else:
        print(json.dumps(packet, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
