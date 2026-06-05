"""Cross-platform Client grouping — pure-function resolver + suggester layer.

Downstream sprints (Google-only view filter, Meta-only view filter, combined view
registry) all consume ``resolve_client_accounts`` — no view should read the
``ClientPlatformAccount`` table directly. The resolver is the single choke point
where MCC expansion, tenant scoping, and platform filtering happen.
"""

from __future__ import annotations

from .resolver import (
    ClientAccountBundle,
    MCCExpansion,
    resolve_client_accounts,
    resolve_client_for_external,
)
from .suggester import (
    ClientSuggestion,
    SuggestionAccount,
    normalize_name,
    suggest_clients,
)

__all__ = [
    "ClientAccountBundle",
    "MCCExpansion",
    "resolve_client_accounts",
    "resolve_client_for_external",
    "ClientSuggestion",
    "SuggestionAccount",
    "normalize_name",
    "suggest_clients",
]
