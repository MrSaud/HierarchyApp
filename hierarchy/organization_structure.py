"""Tenant organizational units + positions tree for UI overview."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from django.db.models import Prefetch
from django.utils import timezone

from .models import Employee, OrganizationalUnit, Position, PositionAssignment, Tenant


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

    @property
    def has_body(self) -> bool:
        return bool(self.positions or self.children)


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


def flatten_org_units_for_search(tenant: Tenant) -> list[dict[str, object]]:
    """Flat list of units with breadcrumb path for the structure page search picker."""
    units = list(
        OrganizationalUnit.objects.filter(tenant=tenant).order_by(
            "sort_order",
            "name",
        ),
    )
    by_id = {u.pk: u for u in units}

    def depth(u: OrganizationalUnit) -> int:
        d = 0
        pid = u.parent_id
        seen: set[int] = set()
        while pid and pid in by_id and pid not in seen:
            seen.add(pid)
            d += 1
            pid = by_id[pid].parent_id
        return d

    def path(u: OrganizationalUnit) -> str:
        parts = [u.name]
        pid = u.parent_id
        seen: set[int] = set()
        while pid and pid in by_id and pid not in seen:
            seen.add(pid)
            parts.insert(0, by_id[pid].name)
            pid = by_id[pid].parent_id
        return " › ".join(parts)

    return [
        {
            "id": u.pk,
            "name": u.name,
            "code": u.code or "",
            "unit_type": u.unit_type,
            "unit_type_label": u.get_unit_type_display(),
            "path": path(u),
            "depth": depth(u),
        }
        for u in units
    ]


def chief_position_and_holder(ou: OrganizationalUnit) -> tuple[Position | None, Employee | None]:
    """
    Canonical “boss slot” for an organizational unit: the **first** active position
    by ``sort_order``, ``pk`` under that unit. Returns that position and its **primary-first**
    current assignee (if any).

    Put the managerial role first among positions under each unit (lowest ``sort_order``)
    so “reports to” resolves correctly.
    """
    positions = list(
        Position.objects.filter(
            tenant_id=ou.tenant_id,
            organizational_unit_id=ou.pk,
            is_active=True,
        )
        .prefetch_related(
            Prefetch(
                "assignments",
                queryset=PositionAssignment.objects.select_related("employee__user").order_by(
                    "-is_primary",
                    "-start_date",
                    "pk",
                ),
            ),
        )
        .order_by("sort_order", "pk"),
    )
    partition_assignments_for_positions(positions)
    if not positions:
        return None, None
    chief_pos = positions[0]
    cur = getattr(chief_pos, "org_current_assignments", None) or []
    if not cur:
        return chief_pos, None
    return chief_pos, cur[0].employee


def primary_org_unit_from_assignments(employee) -> OrganizationalUnit | None:
    """
    Org unit from **primary-first** current assignment whose position has an OU
    (matches employee profile “primary unit” intent).
    """
    candidates: list[tuple[bool, int, OrganizationalUnit]] = []
    for a in employee.position_assignments.all():
        if not assignment_is_current(a):
            continue
        pos = a.position
        if pos is None or pos.organizational_unit_id is None:
            continue
        ou = pos.organizational_unit
        assert ou is not None
        candidates.append((bool(a.is_primary), a.pk, ou))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], -x[1]))
    return candidates[0][2]


def count_structure_stats(tenant: Tenant) -> dict[str, int]:
    return {
        "units": OrganizationalUnit.objects.filter(tenant=tenant).count(),
        "positions": Position.objects.filter(tenant=tenant).count(),
        "assignments": PositionAssignment.objects.filter(position__tenant=tenant).count(),
    }


def employee_display_label(employee) -> str:
    """Human-readable label for drag-and-drop and API payloads."""
    name = employee.user.get_full_name().strip()
    if name:
        return f"{name} ({employee.user.username})"
    return employee.user.username


def build_position_groups_for_board(tenant: Tenant) -> list[dict]:
    """Positions grouped by organizational unit for the assignment board sidebar."""
    positions = list(
        Position.objects.filter(tenant=tenant)
        .select_related("organizational_unit")
        .order_by("organizational_unit_id", "sort_order", "title"),
    )
    by_ou: dict[int, dict] = {}
    loose: list[Position] = []
    for p in positions:
        ou = p.organizational_unit
        if ou is not None:
            if ou.pk not in by_ou:
                by_ou[ou.pk] = {"ou_name": ou.name, "positions": []}
            by_ou[ou.pk]["positions"].append(p)
        else:
            loose.append(p)
    groups = sorted(by_ou.values(), key=lambda g: g["ou_name"].lower())
    if loose:
        groups.append({"ou_name": "No unit", "positions": loose})
    return groups
