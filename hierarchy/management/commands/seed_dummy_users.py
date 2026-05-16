"""
Create dummy User + Employee records with Arabic names for a tenant.

Usage:
    python manage.py seed_dummy_users --tenant-id 2
    python manage.py seed_dummy_users --tenant-id 2 --count 40
    python manage.py seed_dummy_users --tenant-id 2 --dry-run
"""

from __future__ import annotations

import random
import re
import secrets
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from hierarchy.models import (
    Employee,
    EmployeeType,
    EmploymentStatus,
    Gender,
    MaritalStatus,
    Sector,
    Tenant,
)

User = get_user_model()

ARABIC_FIRST_MALE = (
    "أحمد",
    "محمد",
    "خالد",
    "فهد",
    "سعود",
    "عبدالله",
    "يوسف",
    "علي",
    "سعد",
    "ناصر",
    "بدر",
    "طلال",
    "مشعل",
    "فيصل",
    "راشد",
    "عمر",
    "حمد",
    "سلمان",
    "جاسم",
    "مبارك",
)

ARABIC_FIRST_FEMALE = (
    "فاطمة",
    "نورة",
    "مريم",
    "سارة",
    "هدى",
    "لمى",
    "منى",
    "عائشة",
    "دانة",
    "شيخة",
    "موضي",
    "العنود",
    "هيا",
    "لولوة",
    "غادة",
    "ريم",
    "أمل",
    "بدرية",
    "شوق",
    "مها",
)

ARABIC_FAMILY = (
    "العتيبي",
    "السالم",
    "المطيري",
    "الشمري",
    "الكندري",
    "العنزي",
    "الرشيدي",
    "البحر",
    "الخالدي",
    "الفهد",
    "العجمي",
    "الرومي",
    "الهاجري",
    "الظفيري",
    "الصباح",
    "المبارك",
    "الغانم",
    "الزيد",
    "النجادة",
    "الحربي",
)

JOB_TITLES_AR = (
    "أخصائي اجتماعي",
    "محلل شؤون إدارية",
    "موظف خدمة عملاء",
    "مشرف ميداني",
    "محاسب",
    "مهندس أنظمة",
    "منسق مشاريع",
    "باحث تنموي",
    "مراقب مالي",
    "مساعد إداري",
)

DEPARTMENTS_AR = (
    "الرعاية الاجتماعية",
    "شؤون الأسرة",
    "الشؤون الإدارية",
    "تقنية المعلومات",
    "الموارد البشرية",
    "التخطيط والجودة",
    "ذوي الإعاقة",
    "العلاقات العامة",
)

CITIES_AR = ("الكويت", "حولي", "الفروانية", "الأحمدي", "الجهراء", "مبارك الكبير")

NATIONALITIES_AR = ("الكويت", "السعودية", "مصر", "الأردن", "سوريا", "لبنان", "العراق")


def _latin_slug(text: str) -> str:
    """Rough transliteration for usernames (ASCII only)."""
    mapping = {
        "أ": "a",
        "إ": "i",
        "آ": "a",
        "ا": "a",
        "ب": "b",
        "ت": "t",
        "ث": "th",
        "ج": "j",
        "ح": "h",
        "خ": "kh",
        "د": "d",
        "ذ": "th",
        "ر": "r",
        "ز": "z",
        "س": "s",
        "ش": "sh",
        "ص": "s",
        "ض": "d",
        "ط": "t",
        "ظ": "z",
        "ع": "a",
        "غ": "gh",
        "ف": "f",
        "ق": "q",
        "ك": "k",
        "ل": "l",
        "م": "m",
        "ن": "n",
        "ه": "h",
        "و": "w",
        "ي": "y",
        "ى": "a",
        "ة": "a",
        "ء": "",
        "ؤ": "w",
        "ئ": "y",
        "ال": "al-",
    }
    out = []
    i = 0
    while i < len(text):
        if text.startswith("ال", i):
            out.append("al-")
            i += 2
            continue
        ch = text[i]
        out.append(mapping.get(ch, ch if ch.isascii() and ch.isalnum() else ""))
        i += 1
    slug = "".join(out).lower()
    slug = re.sub(r"[^a-z0-9]+", ".", slug).strip(".")
    slug = re.sub(r"\.+", ".", slug)
    return slug or "user"


def _random_birth_date(rng: random.Random) -> date:
    start = date(1975, 1, 1)
    end = date(2002, 12, 31)
    days = (end - start).days
    return start + timedelta(days=rng.randint(0, days))


def _random_hire_date(rng: random.Random) -> date:
    start = date(2010, 1, 1)
    end = date.today()
    days = (end - start).days
    return start + timedelta(days=rng.randint(0, max(days, 0)))


def _random_civil_id(rng: random.Random) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(12))


def _random_mobile_kuwait(rng: random.Random) -> str:
    return f"{rng.choice(['5', '6', '9'])}{rng.randint(1000000, 9999999)}"


class Command(BaseCommand):
    help = "Seed dummy employees with Arabic names for a tenant."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            type=int,
            default=2,
            help="Tenant primary key (default: 2).",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=30,
            help="How many users to create (default: 30).",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=None,
            help="Random seed for reproducible data.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print sample rows without saving.",
        )
        parser.add_argument(
            "--prefix",
            default="demo",
            help="Username prefix (default: demo → demo.ahmad.alotaibi).",
        )

    def handle(self, *args, **options):
        tenant_id: int = options["tenant_id"]
        count: int = max(1, min(500, int(options["count"])))
        prefix: str = (options["prefix"] or "demo").strip().lower()
        dry_run: bool = options["dry_run"]
        rng = random.Random(options["seed"])

        try:
            tenant = Tenant.objects.get(pk=tenant_id)
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant id={tenant_id} does not exist.") from exc

        if not tenant.is_active:
            self.stdout.write(
                self.style.WARNING(f"Tenant “{tenant.name}” is marked inactive.")
            )

        created = 0
        skipped = 0
        samples: list[str] = []

        def unique_username(base: str) -> str:
            candidate = base[:150]
            if not User.objects.filter(username__iexact=candidate).exists():
                return candidate
            for n in range(2, 10_000):
                suffix = f".{n}"
                trimmed = base[: 150 - len(suffix)] + suffix
                if not User.objects.filter(username__iexact=trimmed).exists():
                    return trimmed
            return f"{prefix}.{secrets.token_hex(4)}"

        def unique_employee_number() -> str:
            for _ in range(100):
                num = f"T{tenant_id}-{rng.randint(10000, 99999)}"
                if not Employee.objects.filter(employee_number=num).exists():
                    return num
            return f"T{tenant_id}-{secrets.token_hex(4)}"

        @transaction.atomic
        def run() -> None:
            nonlocal created, skipped
            for i in range(count):
                is_female = rng.random() < 0.45
                if is_female:
                    first_ar = rng.choice(ARABIC_FIRST_FEMALE)
                    gender = Gender.FEMALE
                else:
                    first_ar = rng.choice(ARABIC_FIRST_MALE)
                    gender = Gender.MALE
                last_ar = rng.choice(ARABIC_FAMILY)
                full_ar = f"{first_ar} {last_ar}"

                base_user = f"{prefix}.{_latin_slug(first_ar)}.{_latin_slug(last_ar)}"

                if dry_run:
                    samples.append(f"{base_user} — {full_ar}")
                    created += 1
                    continue

                username = unique_username(base_user)
                email = f"{username}@demo.local"

                if User.objects.filter(username__iexact=username).exists():
                    skipped += 1
                    continue

                user = User(
                    username=username,
                    first_name=first_ar,
                    last_name=last_ar,
                    email=email,
                )
                user.set_unusable_password()
                user.save()

                emp = Employee(
                    user=user,
                    tenant=tenant,
                    sector=Sector.GOVERNMENT,
                    employee_number=unique_employee_number(),
                    job_title=rng.choice(JOB_TITLES_AR),
                    department=rng.choice(DEPARTMENTS_AR),
                    section_team=rng.choice(DEPARTMENTS_AR),
                    hire_date=_random_hire_date(rng),
                    employment_status=EmploymentStatus.ACTIVE,
                    work_location=rng.choice(CITIES_AR),
                    employee_type=rng.choice(
                        [
                            EmployeeType.FULL_TIME,
                            EmployeeType.FULL_TIME,
                            EmployeeType.FULL_TIME,
                            EmployeeType.PART_TIME,
                            EmployeeType.CONTRACTOR,
                        ]
                    ),
                    civil_id=_random_civil_id(rng),
                    date_of_birth=_random_birth_date(rng),
                    gender=gender,
                    nationality=rng.choice(NATIONALITIES_AR),
                    marital_status=rng.choice(
                        [
                            MaritalStatus.SINGLE,
                            MaritalStatus.MARRIED,
                            MaritalStatus.MARRIED,
                            MaritalStatus.DIVORCED,
                        ]
                    ),
                    mobile_number=_random_mobile_kuwait(rng),
                    home_address=f"{rng.choice(CITIES_AR)}، الكويت",
                )
                emp.save()
                created += 1

        if dry_run:
            run()
            self.stdout.write(
                self.style.WARNING(f"Dry run — would create {created} user(s) for tenant id={tenant_id}.")
            )
            for line in samples[:10]:
                self.stdout.write(f"  · {line}")
            if len(samples) > 10:
                self.stdout.write(f"  … and {len(samples) - 10} more")
            return

        run()
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created} employee(s) for tenant “{tenant.name}” (id={tenant_id}). "
                f"Skipped {skipped} duplicate username(s)."
            )
        )
        self.stdout.write("Passwords are unset (use admin reset or sync); demo emails use @demo.local.")
