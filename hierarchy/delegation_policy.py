"""Overlap and conflict rules for authority delegations."""

from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError

from .models import Delegation

_FAR_END = date(9999, 12, 31)


def delegation_periods_overlap(
    start_a: date | None,
    end_a: date | None,
    start_b: date | None,
    end_b: date | None,
) -> bool:
    """Inclusive overlap; open end dates count as unbounded forward."""
    if start_a is None or start_b is None:
        return False
    ea = end_a if end_a else _FAR_END
    eb = end_b if end_b else _FAR_END
    return start_a <= eb and start_b <= ea


def validate_delegation_conflicts(instance: Delegation) -> None:
    """
    Enforce:
    - No overlapping delegation with the same delegator and delegatee.
    - No two overlapping *full substitute* delegations for the same delegator
      (different delegatees).
    """
    if not instance.delegator_id or not instance.start_date or not instance.tenant_id:
        return

    qs = Delegation.objects.filter(
        tenant_id=instance.tenant_id,
        delegator_id=instance.delegator_id,
    )
    if instance.pk:
        qs = qs.exclude(pk=instance.pk)

    for other in qs.iterator():
        if not delegation_periods_overlap(
            instance.start_date,
            instance.end_date,
            other.start_date,
            other.end_date,
        ):
            continue

        if instance.delegatee_id and other.delegatee_id == instance.delegatee_id:
            raise ValidationError(
                "This delegator already has a delegation with the same delegatee "
                "for an overlapping period. Adjust dates or edit the existing record."
            )

        if instance.is_full_substitute and other.is_full_substitute:
            raise ValidationError(
                "This delegator already has a full substitute delegation for an "
                "overlapping period. End or change the other delegation, mark one as "
                "not a full substitute, or use non-overlapping dates."
            )
