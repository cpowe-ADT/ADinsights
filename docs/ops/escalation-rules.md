# Escalation Rules for AI Sessions (v0.1)

Purpose: when to stop and request human review.

## Escalate to Raj (Integration)

- Any change that touches more than one top-level folder.
- Any change that alters API contracts used by another stream.

## Escalate to Mira (Architecture)

- Cross-cutting refactors or performance changes.
- Altering core stack choices or replacing frameworks.

## Escalate to Stream Owner

- When unsure about domain-specific logic or data contracts.
