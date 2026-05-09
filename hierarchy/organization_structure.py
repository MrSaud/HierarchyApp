"""Tenant organizational units + positions tree for UI overview."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from django.db.models import Prefetch
from django.utils import timezone

from .models import OrganizationalUnit, Position, PositionAssignment, Tenant


def assignment_is_current(a: PositionAssignment, *, today: date | None = None) -> bool:
    today = today or timezone.now().date()
    if a.start_date and a.start_date > today:
        return False
    if a.end_date and a.end_date < today:
        return False
    return True


@dataclass
class OrgUnitBranch:
    unit: OrganizationalUnit
    children: list[OrgUnitBranch] = field(default_factory=list)
    positions: list[Position] = field(default_factory=list)


def partition_assignments_for_positions(
    positions: list[Position],
    *,
    today: date | None = None,
) -> None:
    """Attach ``org_current_assignments`` and ``org_past_assignments`` lists on each position."""
    today = today or timezone.now().date()
    for p in positions:
        assignments = list(p.assignments.all())
        cur = [a for a in assignments if assignment_is_current(a, today=today)]
        cur.sort(key=lambda x: (-bool(x.is_primary), x.pk))
        past = [a for a in assignments if not assignment_is_current(a, today=today)]
        past.sort(key=lambda x: (x.end_date or x.start_date or today, x.pk), reverse=True)
        p.org_current_assignments = cur
        p.org_past_assignments = past


def load_positions_with_assignments(tenant: Tenant) -> list[Position]:
    qs = (
        Position.objects.filter(tenant=tenant)
        .select_related("organizational_unit")
        .prefetch_related(
            Prefetch(
                "assignments",
                queryset=PositionAssignment.objects.select_related(
                    "employee__user",
                ).order_by("-is_primary", "-start_date", "pk"),
            ),
        )
        .order_by("sort_order", "title")
    )
    positions = list(qs)
    partition_assignments_for_positions(positions)
    return positions


def build_org_structure_branches(tenant: Tenant) -> tuple[list[OrgUnitBranch], list[Position]]:
    """
    Nested organizational units with positions; positions without a unit are returned separately.
    """
    units = list(
        OrganizationalUnit.objects.filter(tenant=tenant).order_by("sort_order", "name"),
    )
    unit_ids = {u.pk for u in units}
    positions = load_positions_with_assignments(tenant)

    children_map: defaultdict[int, list[OrganizationalUnit]] = defaultdict(list)
    for u in units:
        if u.parent_id and u.parent_id in unit_ids:
            children_map[u.parent_id].append(u)

    for lst in children_map.values():
        lst.sort(key=lambda x: (x.sort_order, x.name))

    positions_by_unit: defaultdict[int, list[Position]] = defaultdict(list)
    loose: list[Position] = []
    for p in positions:
        ou = p.organizational_unit_id
        if ou and ou in unit_ids:
            positions_by_unit[ou].append(p)
        else:
            loose.append(p)

    roots = [
        u for u in units if u.parent_id is None or u.parent_id not in unit_ids
    ]
    roots.sort(key=lambda x: (x.sort_order, x.name))

    def branch(u: OrganizationalUnit) -> OrgUnitBranch:
        kids = [branch(x) for x in children_map.get(u.pk, [])]
        pos = positions_by_unit.get(u.pk, [])
        return OrgUnitBranch(unit=u, children=kids, positions=pos)

    return [branch(u) for u in roots], loose


def count_structure_stats(tenant: Tenant) -> dict[str, int]:
    return {
        "units": OrganizationalUnit.objects.filter(tenant=tenant).count(),
        "positions": Position.objects.filter(tenant=tenant).count(),
        "assignments": PositionAssignment.objects.filter(position__tenant=tenant).count(),
    }
