"""Helpers for delegation date ranges and display."""

from __future__ import annotations

from datetime import date

from django.utils import timezone

from .models import Delegation


def delegation_is_current(d: Delegation, *, today: date | None = None) -> bool:
    today = today or timezone.now().date()
    if d.start_date and d.start_date > today:
        return False
    if d.end_date and d.end_date < today:
        return False
    return True


def delegation_status_label(d: Delegation, *, today: date | None = None) -> str:
    today = today or timezone.now().date()
    if d.start_date and d.start_date > today:
        return "Scheduled"
    if d.end_date and d.end_date < today:
        return "Ended"
    return "Active"
