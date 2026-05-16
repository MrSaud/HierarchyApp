"""
Seed organizational units for Kuwait Ministry of Social Affairs (Arabic names).

Usage:
    python manage.py seed_mosa_kuwait_units
    python manage.py seed_mosa_kuwait_units --tenant-slug mosa
    python manage.py seed_mosa_kuwait_units --create-tenant
    python manage.py seed_mosa_kuwait_units --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import OrgUnitType, OrganizationalUnit, Tenant

# Hierarchical OU tree: name (Arabic), code, unit_type, sort_order, children.
MOSSA_KUWAIT_UNITS: list[dict] = [
    {
        "code": "MIN",
        "name": "مكتب وزير الشؤون الاجتماعية",
        "unit_type": OrgUnitType.MINISTER,
        "sort_order": 10,
        "children": [
            {
                "code": "MIN-SEC",
                "name": "الأمانة العامة لمعالي الوزير",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 10,
            },
            {
                "code": "MIN-ADV",
                "name": "مكتب المستشارين",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 20,
            },
            {
                "code": "MIN-INQ",
                "name": "مكتب الشكاوى والمتابعة",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 30,
            },
        ],
    },
    {
        "code": "US",
        "name": "وكيل الوزارة",
        "unit_type": OrgUnitType.DEPUTY_DG,
        "sort_order": 20,
        "children": [
            {
                "code": "US-ADM",
                "name": "الإدارة العامة للشؤون الإدارية والمالية",
                "unit_type": OrgUnitType.GENERAL_ADMIN,
                "sort_order": 10,
                "children": [
                    {
                        "code": "US-ADM-FIN",
                        "name": "إدارة الشؤون المالية",
                        "unit_type": OrgUnitType.DEPARTMENT,
                        "sort_order": 10,
                    },
                    {
                        "code": "US-ADM-PRC",
                        "name": "إدارة المشتريات والمخازن",
                        "unit_type": OrgUnitType.DEPARTMENT,
                        "sort_order": 20,
                    },
                    {
                        "code": "US-ADM-SVC",
                        "name": "إدارة الخدمات الإدارية",
                        "unit_type": OrgUnitType.DEPARTMENT,
                        "sort_order": 30,
                    },
                ],
            },
            {
                "code": "US-HR",
                "name": "الإدارة العامة للموارد البشرية",
                "unit_type": OrgUnitType.GENERAL_ADMIN,
                "sort_order": 20,
                "children": [
                    {
                        "code": "US-HR-REC",
                        "name": "إدارة التوظيف والتدريب",
                        "unit_type": OrgUnitType.DEPARTMENT,
                        "sort_order": 10,
                    },
                    {
                        "code": "US-HR-PAY",
                        "name": "إدارة شؤون الموظفين",
                        "unit_type": OrgUnitType.DEPARTMENT,
                        "sort_order": 20,
                    },
                ],
            },
            {
                "code": "US-IT",
                "name": "الإدارة العامة لتقنية المعلومات",
                "unit_type": OrgUnitType.GENERAL_ADMIN,
                "sort_order": 30,
                "children": [
                    {
                        "code": "US-IT-SYS",
                        "name": "إدارة الأنظمة والبنية التحتية",
                        "unit_type": OrgUnitType.DEPARTMENT,
                        "sort_order": 10,
                    },
                    {
                        "code": "US-IT-APP",
                        "name": "إدارة التطبيقات والخدمات الرقمية",
                        "unit_type": OrgUnitType.DEPARTMENT,
                        "sort_order": 20,
                    },
                ],
            },
            {
                "code": "US-LEG",
                "name": "الإدارة العامة للشؤون القانونية",
                "unit_type": OrgUnitType.GENERAL_ADMIN,
                "sort_order": 40,
            },
        ],
    },
    {
        "code": "SOC",
        "name": "قطاع الرعاية الاجتماعية",
        "unit_type": OrgUnitType.SECTOR,
        "sort_order": 30,
        "children": [
            {
                "code": "SOC-SVC",
                "name": "إدارة الخدمات الاجتماعية",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 10,
            },
            {
                "code": "SOC-CTR",
                "name": "إدارة مراكز الرعاية الاجتماعية",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 20,
            },
            {
                "code": "SOC-AID",
                "name": "إدارة المساعدات والدعم الاجتماعي",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 30,
            },
            {
                "code": "SOC-FLD",
                "name": "إدارة الرعاية الميدانية",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 40,
            },
        ],
    },
    {
        "code": "FAM",
        "name": "قطاع شؤون الأسرة",
        "unit_type": OrgUnitType.SECTOR,
        "sort_order": 40,
        "children": [
            {
                "code": "FAM-PRT",
                "name": "إدارة حماية الأسرة",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 10,
            },
            {
                "code": "FAM-CHD",
                "name": "إدارة شؤون الطفولة",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 20,
            },
            {
                "code": "FAM-CNS",
                "name": "إدارة الإرشاد الأسري",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 30,
            },
            {
                "code": "FAM-SHL",
                "name": "إدارة دور الرعاية الأسرية",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 40,
            },
        ],
    },
    {
        "code": "DIS",
        "name": "قطاع شؤون ذوي الإعاقة",
        "unit_type": OrgUnitType.SECTOR,
        "sort_order": 50,
        "children": [
            {
                "code": "DIS-SVC",
                "name": "إدارة خدمات ذوي الإعاقة",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 10,
            },
            {
                "code": "DIS-REH",
                "name": "إدارة التأهيل والدمج",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 20,
            },
            {
                "code": "DIS-CTR",
                "name": "إدارة مراكز الرعاية النهارية",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 30,
            },
        ],
    },
    {
        "code": "PLN",
        "name": "قطاع التخطيط والمتابعة والجودة",
        "unit_type": OrgUnitType.SECTOR,
        "sort_order": 60,
        "children": [
            {
                "code": "PLN-STR",
                "name": "إدارة التخطيط الاستراتيجي",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 10,
            },
            {
                "code": "PLN-MON",
                "name": "إدارة المتابعة والتقييم",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 20,
            },
            {
                "code": "PLN-QA",
                "name": "إدارة الجودة ومؤشرات الأداء",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 30,
            },
        ],
    },
    {
        "code": "INT",
        "name": "قطاع العلاقات العامة والتعاون الدولي",
        "unit_type": OrgUnitType.SECTOR,
        "sort_order": 70,
        "children": [
            {
                "code": "INT-MED",
                "name": "إدارة الإعلام والعلاقات العامة",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 10,
            },
            {
                "code": "INT-ICO",
                "name": "إدارة التعاون الدولي",
                "unit_type": OrgUnitType.DEPARTMENT,
                "sort_order": 20,
            },
        ],
    },
    {
        "code": "REG",
        "name": "المديريات الإقليمية",
        "unit_type": OrgUnitType.REGIONAL_DIRECTORATE,
        "sort_order": 80,
        "children": [
            {
                "code": "REG-CAP",
                "name": "مديرية العاصمة",
                "unit_type": OrgUnitType.REGIONAL_DIRECTORATE,
                "sort_order": 10,
            },
            {
                "code": "REG-HAW",
                "name": "مديرية محافظة حولي",
                "unit_type": OrgUnitType.REGIONAL_DIRECTORATE,
                "sort_order": 20,
            },
            {
                "code": "REG-FAR",
                "name": "مديرية محافظة الفروانية",
                "unit_type": OrgUnitType.REGIONAL_DIRECTORATE,
                "sort_order": 30,
            },
            {
                "code": "REG-AHM",
                "name": "مديرية محافظة الأحمدي",
                "unit_type": OrgUnitType.REGIONAL_DIRECTORATE,
                "sort_order": 40,
            },
            {
                "code": "REG-JAH",
                "name": "مديرية محافظة الجهراء",
                "unit_type": OrgUnitType.REGIONAL_DIRECTORATE,
                "sort_order": 50,
            },
            {
                "code": "REG-MUB",
                "name": "مديرية محافظة مبارك الكبير",
                "unit_type": OrgUnitType.REGIONAL_DIRECTORATE,
                "sort_order": 60,
            },
        ],
    },
]

DEFAULT_TENANT_SLUG = "mosa-kuwait"
DEFAULT_TENANT_NAME = "وزارة الشؤون الاجتماعية — الكويت"


def _create_unit_tree(
    tenant: Tenant,
    nodes: list[dict],
    *,
    parent: OrganizationalUnit | None = None,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Return (created_count, skipped_existing_count)."""
    created = 0
    skipped = 0

    for node in nodes:
        code = (node.get("code") or "").strip()
        name = (node.get("name") or "").strip()
        unit_type = (node.get("unit_type") or OrgUnitType.DEPARTMENT).strip()
        sort_order = int(node.get("sort_order") or 0)
        children = node.get("children") or []

        if not name:
            continue

        existing = None
        if code:
            existing = OrganizationalUnit.objects.filter(
                tenant=tenant,
                code=code,
            ).first()
        if existing is None:
            existing = OrganizationalUnit.objects.filter(
                tenant=tenant,
                parent=parent,
                name=name,
            ).first()

        if existing:
            unit = existing
            skipped += 1
            if not dry_run:
                updates = []
                if unit_type and existing.unit_type != unit_type:
                    existing.unit_type = unit_type
                    updates.append("unit_type")
                if sort_order != existing.sort_order:
                    existing.sort_order = sort_order
                    updates.append("sort_order")
                if updates:
                    existing.save(update_fields=updates)
        elif dry_run:
            unit = OrganizationalUnit(
                tenant=tenant,
                parent=parent,
                name=name,
                code=code,
                unit_type=unit_type,
                sort_order=sort_order,
            )
            created += 1
        else:
            unit = OrganizationalUnit.objects.create(
                tenant=tenant,
                parent=parent,
                name=name,
                code=code,
                unit_type=unit_type,
                sort_order=sort_order,
            )
            created += 1

        sub_created, sub_skipped = _create_unit_tree(
            tenant,
            children,
            parent=unit,
            dry_run=dry_run,
        )
        created += sub_created
        skipped += sub_skipped

    return created, skipped


class Command(BaseCommand):
    help = "Seed Arabic organizational units for Kuwait Ministry of Social Affairs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-slug",
            default=DEFAULT_TENANT_SLUG,
            help=f"Tenant slug (default: {DEFAULT_TENANT_SLUG}).",
        )
        parser.add_argument(
            "--tenant-name",
            default=DEFAULT_TENANT_NAME,
            help="Display name when --create-tenant is used.",
        )
        parser.add_argument(
            "--create-tenant",
            action="store_true",
            help="Create the tenant if it does not exist.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without writing to the database.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        slug = (options["tenant_slug"] or DEFAULT_TENANT_SLUG).strip()
        dry_run = options["dry_run"]

        tenant = Tenant.objects.filter(slug=slug).first()
        if tenant is None:
            if options["create_tenant"]:
                if dry_run:
                    self.stdout.write(f"Would create tenant slug={slug!r}")
                    tenant = Tenant(slug=slug, name=options["tenant_name"])
                else:
                    tenant = Tenant.objects.create(
                        slug=slug,
                        name=options["tenant_name"],
                        is_active=True,
                    )
                    self.stdout.write(self.style.SUCCESS(f"Created tenant {tenant.name}"))
            else:
                self.stderr.write(
                    self.style.ERROR(
                        f"No tenant with slug {slug!r}. Use --create-tenant or create it first."
                    )
                )
                return

        created, skipped = _create_unit_tree(
            tenant,
            MOSSA_KUWAIT_UNITS,
            dry_run=dry_run,
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: would create {created} units; "
                    f"{skipped} already existed (matched by code or parent+name)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. Created {created} units; "
                    f"{skipped} already existed (matched by code or parent+name)."
                )
            )
