"""Organizational unit type taxonomy and parent/child rules (tenant catalog)."""

from __future__ import annotations

from django.core.exceptions import ValidationError

from .models import OrgUnitType, OrgUnitTypeDefinition, OrganizationalUnit, Tenant
from .org_unit_type_defaults import DEFAULT_ORG_UNIT_TYPE_ROWS


def ensure_default_org_unit_types(tenant: Tenant) -> int:
    """Create missing default type rows for a tenant. Returns number created."""
    created = 0
    for slug, label, rank, allows_root, sort_order in DEFAULT_ORG_UNIT_TYPE_ROWS:
        _obj, was_created = OrgUnitTypeDefinition.objects.get_or_create(
            tenant=tenant,
            slug=slug,
            defaults={
                "label": label,
                "rank": rank,
                "allows_root": allows_root,
                "sort_order": sort_order,
            },
        )
        if was_created:
            created += 1
    return created


def definitions_for_tenant(tenant_id: int):
    return OrgUnitTypeDefinition.objects.filter(tenant_id=tenant_id).order_by(
        "sort_order",
        "rank",
        "label",
    )


def definition_map_for_tenant(tenant_id: int) -> dict[str, OrgUnitTypeDefinition]:
    return {d.slug: d for d in definitions_for_tenant(tenant_id)}


def unit_type_choices_for_tenant(tenant_id: int) -> list[tuple[str, str]]:
    return [(d.slug, d.label) for d in definitions_for_tenant(tenant_id)]


def resolve_unit_type_label(tenant_id: int | None, slug: str) -> str:
    if not slug:
        return ""
    if tenant_id is None:
        return slug.replace("_", " ").title()
    defn = definition_map_for_tenant(tenant_id).get(slug)
    return defn.label if defn is not None else slug.replace("_", " ").title()


def org_unit_type_rank(tenant_id: int | None, unit_type: str) -> int:
    if tenant_id is None:
        return 99
    defn = definition_map_for_tenant(tenant_id).get(unit_type or "")
    return defn.rank if defn is not None else 99


def root_unit_type_slugs(tenant_id: int | None) -> frozenset[str]:
    if tenant_id is None:
        return frozenset({OrgUnitType.MINISTER, OrgUnitType.DEPUTY_DG})
    return frozenset(
        d.slug for d in definitions_for_tenant(tenant_id) if d.allows_root
    )


def validate_unit_type_slug(tenant_id: int | None, slug: str) -> None:
    if tenant_id is None or not slug:
        return
    if slug not in definition_map_for_tenant(tenant_id):
        raise ValidationError(
            {
                "unit_type": (
                    "Unknown unit type for this tenant. "
                    "Add it under Organization → Unit types."
                ),
            }
        )


def validate_org_unit_parent_type(
    unit: OrganizationalUnit,
    parent: OrganizationalUnit | None,
) -> None:
    """Parent must be higher in the hierarchy (lower rank number)."""
    tenant_id = unit.tenant_id
    roots = root_unit_type_slugs(tenant_id)

    if parent is None:
        if unit.unit_type and unit.unit_type not in roots:
            raise ValidationError(
                {
                    "parent": (
                        "This unit type must have a parent. "
                        "Only types marked “May be top-level” can exist at the root."
                    ),
                }
            )
        return

    if parent.tenant_id != unit.tenant_id:
        raise ValidationError({"parent": "Parent must belong to the same tenant."})

    child_rank = org_unit_type_rank(tenant_id, unit.unit_type or OrgUnitType.DEPARTMENT)
    parent_rank = org_unit_type_rank(tenant_id, parent.unit_type or OrgUnitType.DEPARTMENT)
    if parent_rank >= child_rank:
        parent_label = parent.get_unit_type_display()
        child_label = unit.get_unit_type_display()
        raise ValidationError(
            {
                "parent": (
                    f"A {child_label} cannot report to a {parent_label}. "
                    "Choose a higher-level parent."
                ),
            }
        )


def unit_type_in_use(tenant_id: int, slug: str) -> bool:
    return OrganizationalUnit.objects.filter(
        tenant_id=tenant_id,
        unit_type=slug,
    ).exists()
