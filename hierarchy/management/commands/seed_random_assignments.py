"""
Randomly assign employees to positions for a tenant.

Usage:
    python manage.py seed_random_assignments --tenant-id 2
    python manage.py seed_random_assignments --tenant-id 2 --replace
    python manage.py seed_random_assignments --tenant-id 2 --create-positions
    python manage.py seed_random_assignments --tenant-id 2 --dry-run
"""

from __future__ import annotations

import random
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from hierarchy.models import Employee, OrganizationalUnit, Position, PositionAssignment, Tenant

POSITION_TITLES = (
    "مدير قسم",
    "رئيس شعبة",
    "أخصائي أول",
    "أخصائي",
    "مساعد إداري",
    "منسق",
    "محلل",
    "مشرف",
    "موظف خدمات",
    "كاتب",
)


def _is_current(assignment: PositionAssignment, *, today: date) -> bool:
    if assignment.start_date and assignment.start_date > today:
        return False
    if assignment.end_date and assignment.end_date < today:
        return False
    return True


class Command(BaseCommand):
    help = "Randomly assign tenant employees to positions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            type=int,
            default=2,
            help="Tenant primary key (default: 2).",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=None,
            help="Random seed for reproducible assignments.",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Remove existing assignments for this tenant before assigning.",
        )
        parser.add_argument(
            "--create-positions",
            action="store_true",
            help="Create sample positions from org units when none exist.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would happen without saving.",
        )

    def handle(self, *args, **options):
        tenant_id: int = options["tenant_id"]
        dry_run: bool = options["dry_run"]
        replace: bool = options["replace"]
        create_positions: bool = options["create_positions"]
        rng = random.Random(options["seed"])
        today = timezone.now().date()

        try:
            tenant = Tenant.objects.get(pk=tenant_id)
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant id={tenant_id} does not exist.") from exc

        employees = list(
            Employee.objects.filter(tenant=tenant)
            .select_related("user")
            .order_by("pk"),
        )
        if not employees:
            raise CommandError(
                f"No employees for tenant “{tenant.name}” (id={tenant_id}). "
                "Run seed_dummy_users first."
            )

        positions = list(
            Position.objects.filter(tenant=tenant, is_active=True).order_by("pk"),
        )
        if not positions and create_positions:
            positions = self._create_sample_positions(tenant, rng, dry_run=dry_run)
        if not positions:
            raise CommandError(
                f"No active positions for tenant id={tenant_id}. "
                "Create positions in Organization → Positions, or pass --create-positions."
            )

        if dry_run:
            self._report_dry_run(
                tenant,
                employees,
                positions,
                replace=replace,
                rng=rng,
                today=today,
            )
            return

        created, skipped, removed = self._run_assignments(
            tenant,
            employees,
            positions,
            replace=replace,
            rng=rng,
            today=today,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Tenant “{tenant.name}” (id={tenant_id}): "
                f"created {created} assignment(s), skipped {skipped}, removed {removed}."
            )
        )

    def _create_sample_positions(
        self,
        tenant: Tenant,
        rng: random.Random,
        *,
        dry_run: bool,
    ) -> list[Position]:
        units = list(
            OrganizationalUnit.objects.filter(tenant=tenant).order_by("sort_order", "name"),
        )
        if not units:
            raise CommandError(
                f"No organizational units for tenant id={tenant.pk}. "
                "Run seed_mosa_kuwait_units or create units first."
            )

        positions: list[Position] = []
        for i, unit in enumerate(units):
            title = f"{rng.choice(POSITION_TITLES)} — {unit.name}"
            code = f"P{unit.pk:04d}"
            if dry_run:
                self.stdout.write(f"  would create position: {title}")
                positions.append(
                    Position(pk=-(i + 1), tenant=tenant, title=title, organizational_unit=unit),
                )
                continue
            pos, _ = Position.objects.get_or_create(
                tenant=tenant,
                organizational_unit=unit,
                code=code,
                defaults={
                    "title": title[:200],
                    "sort_order": unit.sort_order,
                    "is_active": True,
                },
            )
            positions.append(pos)

        if not dry_run:
            self.stdout.write(
                self.style.WARNING(f"Created/found {len(positions)} position(s) from org units.")
            )
        return positions

    def _current_assignment_filter(self, today: date) -> Q:
        return (
            Q(start_date__isnull=True) | Q(start_date__lte=today)
        ) & (Q(end_date__isnull=True) | Q(end_date__gte=today))

    def _employees_without_current(
        self,
        tenant: Tenant,
        employees: list[Employee],
        today: date,
    ) -> list[Employee]:
        assigned_ids = set(
            PositionAssignment.objects.filter(
                employee__tenant=tenant,
            )
            .filter(self._current_assignment_filter(today))
            .values_list("employee_id", flat=True)
        )
        return [e for e in employees if e.pk not in assigned_ids]

    @transaction.atomic
    def _run_assignments(
        self,
        tenant: Tenant,
        employees: list[Employee],
        positions: list[Position],
        *,
        replace: bool,
        rng: random.Random,
        today: date,
    ) -> tuple[int, int, int]:
        removed = 0
        if replace:
            qs = PositionAssignment.objects.filter(position__tenant=tenant)
            removed, _ = qs.delete()

        pool = self._employees_without_current(tenant, employees, today)
        if not pool and not replace:
            pool = list(employees)

        created = 0
        skipped = 0
        shuffled_positions = list(positions)
        rng.shuffle(shuffled_positions)

        for employee in pool:
            position = rng.choice(shuffled_positions)
            if position.pk is not None and position.pk < 0:
                skipped += 1
                continue

            exists = PositionAssignment.objects.filter(
                position=position,
                employee=employee,
            ).filter(self._current_assignment_filter(today)).exists()
            if exists:
                skipped += 1
                continue

            assignment = PositionAssignment(
                position=position,
                employee=employee,
                is_primary=True,
                start_date=today,
            )
            assignment.full_clean()
            assignment.save()
            created += 1

        return created, skipped, removed

    def _report_dry_run(
        self,
        tenant: Tenant,
        employees: list[Employee],
        positions: list[Position],
        *,
        replace: bool,
        rng: random.Random,
        today: date,
    ) -> None:
        pool = self._employees_without_current(tenant, employees, today)
        if not pool:
            pool = employees
        self.stdout.write(
            self.style.WARNING(
                f"Dry run — tenant “{tenant.name}”: "
                f"{len(pool)} employee(s) → {len(positions)} position(s)"
                f"{' (replace existing)' if replace else ''}."
            )
        )
        sample = pool[:8]
        for emp in sample:
            pos = rng.choice(positions)
            name = emp.user.get_full_name().strip() or emp.user.username
            pos_title = getattr(pos, "title", str(pos))
            self.stdout.write(f"  · {name} → {pos_title}")
        if len(pool) > 8:
            self.stdout.write(f"  … and {len(pool) - 8} more")
