"""Name-match suggester for auto-grouping unclaimed platform accounts into Clients.

Algorithm
---------
1. Walk every platform account source (Google Ads mappings, analytics.AdAccount
   for Meta ads, MetaPage for pages) and exclude any already linked via
   ``ClientPlatformAccount``.
2. Normalize each name (lowercase, strip common legal/brand suffixes, collapse
   punctuation) and derive a token set.
3. Group candidates by normalized name AND by token Jaccard similarity ≥ 0.7.
4. For each group, propose either attaching to an existing Client with a
   matching name, or creating a new Client.

Complexity: O(N²) pairwise for N accounts — fine for the dozens-to-low-hundreds
scale this sees. If an agency ever has >1k unlinked accounts we can switch to
a token-indexed approach.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from integrations.models import (
    Client,
    ClientPlatformAccount,
    GoogleAdsAccountMapping,
    MetaPage,
)

# These stop-suffixes get stripped before comparison — "Bank of Jamaica Limited"
# and "Bank of Jamaica" should match. Order matters (longest first).
_SUFFIX_PATTERNS = [
    r"\bcompany limited\b",
    r"\bcompany ltd\b",
    r"\bcorporation\b",
    r"\blimited\b",
    r"\bincorporated\b",
    r"\bholdings\b",
    r"\bgroup\b",
    r"\binc\.?\b",
    r"\bltd\.?\b",
    r"\bllc\b",
    r"\bco\.?\b",
    r"\bplc\b",
]
_PAREN_CONTENT = re.compile(r"\([^)]*\)")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_MULTISPACE = re.compile(r"\s+")


def normalize_name(raw: Optional[str]) -> str:
    """Lowercase, strip parentheticals + common suffixes + punctuation."""

    if not raw:
        return ""
    s = raw.lower()
    s = _PAREN_CONTENT.sub(" ", s)
    for pattern in _SUFFIX_PATTERNS:
        s = re.sub(pattern, " ", s)
    s = _NON_ALNUM.sub(" ", s)
    s = _MULTISPACE.sub(" ", s).strip()
    return s


def _tokens(normalized: str) -> frozenset[str]:
    return frozenset(t for t in normalized.split(" ") if t)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


@dataclass(frozen=True)
class SuggestionAccount:
    platform: str
    external_id: str
    display_name: str


@dataclass
class ClientSuggestion:
    """One proposed grouping. ``existing_client_id`` is set when the suggester
    believes the unclaimed accounts should attach to an existing Client rather
    than create a new one."""

    proposed_name: str
    normalized_name: str
    unclaimed_accounts: list[SuggestionAccount] = field(default_factory=list)
    existing_client_id: Optional[str] = None
    confidence: float = 0.0

    def platforms(self) -> frozenset[str]:
        return frozenset(a.platform for a in self.unclaimed_accounts)


def _collect_unclaimed(tenant_id: str) -> list[SuggestionAccount]:
    linked_keys: set[tuple[str, str]] = set(
        ClientPlatformAccount.all_objects.filter(tenant_id=tenant_id).values_list(
            "platform", "external_id"
        )
    )

    out: list[SuggestionAccount] = []

    for row in GoogleAdsAccountMapping.all_objects.filter(
        tenant_id=tenant_id, is_manager=False
    ).values("customer_id", "customer_name"):
        key = (ClientPlatformAccount.PLATFORM_GOOGLE_ADS, row["customer_id"])
        if key in linked_keys:
            continue
        out.append(
            SuggestionAccount(
                platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
                external_id=row["customer_id"],
                display_name=row["customer_name"] or "",
            )
        )

    # Meta ad accounts — names live on analytics.AdAccount. Import lazily so
    # this module stays importable without the analytics app loaded.
    try:
        from analytics.models import AdAccount  # noqa: WPS433 - lazy import

        for row in AdAccount.all_objects.filter(tenant_id=tenant_id).values(
            "external_id", "name"
        ):
            key = (ClientPlatformAccount.PLATFORM_META_ADS, row["external_id"])
            if key in linked_keys:
                continue
            out.append(
                SuggestionAccount(
                    platform=ClientPlatformAccount.PLATFORM_META_ADS,
                    external_id=row["external_id"],
                    display_name=row["name"] or "",
                )
            )
    except Exception:  # pragma: no cover - analytics app optional in some envs
        pass

    for row in MetaPage.all_objects.filter(tenant_id=tenant_id).values(
        "page_id", "name"
    ):
        key = (ClientPlatformAccount.PLATFORM_META_PAGE, row["page_id"])
        if key in linked_keys:
            continue
        out.append(
            SuggestionAccount(
                platform=ClientPlatformAccount.PLATFORM_META_PAGE,
                external_id=row["page_id"],
                display_name=row["name"] or "",
            )
        )

    return out


def _group_by_similarity(
    candidates: list[SuggestionAccount], *, threshold: float
) -> list[list[SuggestionAccount]]:
    """Greedy agglomerative grouping by token Jaccard ≥ threshold."""

    tokenized = [(c, _tokens(normalize_name(c.display_name))) for c in candidates]
    used = [False] * len(tokenized)
    groups: list[list[SuggestionAccount]] = []

    for i, (acct_i, toks_i) in enumerate(tokenized):
        if used[i] or not toks_i:
            continue
        used[i] = True
        group = [acct_i]
        for j in range(i + 1, len(tokenized)):
            if used[j]:
                continue
            acct_j, toks_j = tokenized[j]
            if not toks_j:
                continue
            # Same platform + same external_id would already be dedup'd by
            # collect; we skip same-platform matches so a group always
            # represents a CROSS-platform grouping opportunity.
            if acct_j.platform == acct_i.platform and acct_j.external_id == acct_i.external_id:
                continue
            if _jaccard(toks_i, toks_j) >= threshold:
                used[j] = True
                group.append(acct_j)
        # Only return groups that represent a real grouping signal: either
        # multiple unclaimed accounts across platforms, OR a single account
        # whose name matches an existing Client (handled in suggest_clients).
        groups.append(group)

    # Orphans (no tokens) — still surface them individually so user can attach.
    for i, (acct, toks) in enumerate(tokenized):
        if not toks and not used[i]:
            used[i] = True
            groups.append([acct])
    return groups


def _match_score(a: frozenset[str], b: frozenset[str]) -> float:
    """Best-of Jaccard plus directional containment.

    Containment handles the acronym case: a Client named "JDIC" (one token)
    should match an account named "JDIC Jamaica Deposit Insurance" — their
    Jaccard is 1/4 but the JDIC token is fully contained in the account, so
    the containment score is 1.0.
    """

    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    jaccard = inter / len(a | b)
    containment_a = inter / len(a)
    containment_b = inter / len(b)
    return max(jaccard, containment_a, containment_b)


def _match_existing_client(
    tenant_id: str, tokens: frozenset[str], *, threshold: float
) -> tuple[Optional[str], Optional[str], float]:
    """Return (client_id, client_name, confidence) for the best existing match."""

    best: tuple[Optional[str], Optional[str], float] = (None, None, 0.0)
    for client in Client.all_objects.filter(tenant_id=tenant_id).values(
        "id", "name"
    ):
        client_tokens = _tokens(normalize_name(client["name"]))
        if not client_tokens:
            continue
        score = _match_score(tokens, client_tokens)
        if score >= threshold and score > best[2]:
            best = (str(client["id"]), client["name"], score)
    return best


def suggest_clients(
    tenant_id: str, *, threshold: float = 0.7
) -> list[ClientSuggestion]:
    """Return a list of proposed Client groupings for a tenant.

    Each suggestion either:
    - proposes creating a new Client (``existing_client_id is None``) when
      multiple unclaimed accounts across platforms share a similar name, OR
    - proposes attaching an unclaimed account to an existing Client when its
      name matches an existing ``Client.name``.

    Results are sorted by confidence descending, then by account count.
    """

    candidates = _collect_unclaimed(tenant_id)
    if not candidates:
        return []

    groups = _group_by_similarity(candidates, threshold=threshold)
    suggestions: list[ClientSuggestion] = []

    for group in groups:
        # Representative name: longest display_name wins (most specific).
        rep = max(group, key=lambda a: len(a.display_name or ""))
        normalized = normalize_name(rep.display_name)
        tokens = _tokens(normalized)
        if not tokens:
            # No tokens means we can't match anything; only surface if group
            # has multiple members (still useful to manually link).
            if len(group) <= 1:
                continue

        existing_id, existing_name, existing_score = _match_existing_client(
            tenant_id, tokens, threshold=threshold
        )

        platforms_in_group = frozenset(a.platform for a in group)

        # Don't emit a suggestion unless there's a real signal: cross-platform
        # group, multi-account group, or a confident existing-client match.
        has_cross_platform = len(platforms_in_group) > 1
        has_multiple = len(group) > 1
        has_existing_match = existing_id is not None

        if not (has_cross_platform or has_multiple or has_existing_match):
            continue

        if existing_id is not None:
            confidence = max(existing_score, 0.8 if has_cross_platform else existing_score)
            proposed = existing_name or rep.display_name
        else:
            # Confidence for a new grouping — boost when cross-platform.
            confidence = 0.9 if has_cross_platform else 0.75
            proposed = rep.display_name

        suggestions.append(
            ClientSuggestion(
                proposed_name=proposed,
                normalized_name=normalized,
                unclaimed_accounts=list(group),
                existing_client_id=existing_id,
                confidence=round(confidence, 3),
            )
        )

    suggestions.sort(
        key=lambda s: (s.confidence, len(s.unclaimed_accounts)), reverse=True
    )
    return suggestions
