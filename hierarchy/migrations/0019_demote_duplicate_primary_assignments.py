# Generated manually — enforce at most one primary assignment per employee in existing data.

from django.db import migrations
from django.db.models import Count


def demote_duplicate_primaries(apps, schema_editor):
    PositionAssignment = apps.get_model("hierarchy", "PositionAssignment")
    dup = (
        PositionAssignment.objects.filter(is_primary=True)
        .values("employee_id")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
    )
    for row in dup:
        eid = row["employee_id"]
        if eid is None:
            continue
        qs = PositionAssignment.objects.filter(employee_id=eid, is_primary=True).order_by(
            "-start_date",
            "-pk",
        )
        keep = qs.first()
        if keep is None:
            continue
        PositionAssignment.objects.filter(employee_id=eid, is_primary=True).exclude(
            pk=keep.pk,
        ).update(is_primary=False)


class Migration(migrations.Migration):

    dependencies = [
        ("hierarchy", "0018_delegation_templates"),
    ]

    operations = [
        migrations.RunPython(demote_duplicate_primaries, migrations.RunPython.noop),
    ]
