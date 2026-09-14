"""Typed exceptions raised by the MoMo Bench financial core.

These are internal/programmatic errors (bugs, misuse of the API) — they are
distinct from ordinary *blocked* transactions (insufficient funds, recipient
mismatch, limit violation), which are represented as data via
``TransactionPreview.can_execute=False`` / ``blocking_reason``, not raised as
exceptions, since a blocked transaction is expected benchmark behavior.
"""

from __future__ import annotations


class MoMoWorldError(Exception):
    """Base class for all core-engine errors."""


class UnknownWalletError(MoMoWorldError):
    pass


class UnknownNumberError(MoMoWorldError):
    pass


class UnknownTransactionError(MoMoWorldError):
    pass


class InactiveWalletError(MoMoWorldError):
    pass


class InvalidPreviewError(MoMoWorldError):
    """Raised when commit is attempted against a preview that no longer
    reflects current world state (e.g. stale amount/recipient)."""


class UnknownPolicyError(MoMoWorldError):
    pass


class ScenarioIntegrityError(MoMoWorldError):
    """Raised when a scenario references inconsistent or malformed data."""
