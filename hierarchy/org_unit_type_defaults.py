"""Default organizational unit type catalog (seeded per tenant)."""

from __future__ import annotations

from .models import OrgUnitType

# slug, label, rank, allows_root, sort_order
DEFAULT_ORG_UNIT_TYPE_ROWS: tuple[tuple[str, str, int, bool, int], ...] = (
    (OrgUnitType.MINISTER, "Minister (DG)", 0, True, 0),
    (OrgUnitType.DEPUTY_DG, "Deputy DG", 10, True, 10),
    (OrgUnitType.SECTOR, "Sector (Program)", 20, False, 20),
    (OrgUnitType.REGIONAL_DIRECTORATE, "Regional directorate", 20, False, 25),
    (OrgUnitType.GENERAL_ADMIN, "General administration", 30, False, 30),
    (OrgUnitType.DEPARTMENT, "Department", 40, False, 40),
    (OrgUnitType.CONTROLLER, "Controller", 45, False, 45),
    (OrgUnitType.SECTION, "Section", 50, False, 50),
)
