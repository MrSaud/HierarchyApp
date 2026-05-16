#!/usr/bin/env python3
"""Merge extra Arabic msgstr into locale/ar/LC_MESSAGES/django.po (requires polib)."""
import polib
from pathlib import Path

PO_PATH = Path(__file__).resolve().parents[1] / "locale" / "ar" / "LC_MESSAGES" / "django.po"

NEW = {
    "Tenant:": "المستأجر:",
    "drag employees onto a position or use Assign / Remove. Multiple people can share a position.": "اسحب الموظفين إلى منصب أو استخدم تعيين/إزالة. يمكن لعدة أشخاص مشاركة منصب واحد.",
    "Drag employees onto a selected position to create assignments.": "اسحب الموظفين إلى منصب محدد لإنشاء التعيينات.",
    "Superusers: pick": "المستخدمون الفائقون: اختر",
    "in the app bar. Tenant staff: uses your employee tenant automatically.": "في شريط التطبيق. موظفو المستأجر: يُستخدم مستأجر موظفك تلقائيًا.",
    "No positions yet.": "لا توجد مناصب بعد.",
    "first.": "أولاً.",
    "Click a position to select it as the drop target.": "انقر منصبًا لتحديده كهدف الإسقاط.",
    "Position list": "قائمة المناصب",
    "Inactive": "غير نشط",
    "Filter": "تصفية",
    "Name or username…": "الاسم أو اسم المستخدم…",
    "Available employees — drag from here or drop here to unassign": "الموظفون المتاحون — اسحب من هنا أو أفلت هنا لإلغاء التعيين",
    "Select a position to see who can be assigned.": "اختر منصبًا لمعرفة من يمكن تعيينه.",
    "Assigned to": "معيّن إلى",
    "New assignments are primary roles": "التعيينات الجديدة هي أدوار أساسية",
    "Only one primary assignment is kept per person; marking a new one as primary clears primary on their other positions.": "يُحتفظ بتعيين أساسي واحد فقط لكل شخص؛ عند تعيين تعيين جديد كأساسي يُلغى الأساسي على مناصبهم الأخرى.",
    "Assigned employees — drop here to assign": "الموظفون المعيّنون — أفلت هنا للتعيين",
    "Select a position on the left, then drag employees here.": "اختر منصبًا على اليسار، ثم اسحب الموظفين إلى هنا.",
    "Full name": "الاسم الكامل",
    "CSV file": "ملف CSV",
    "Generate passwords (omit password column)": "توليد كلمات مرور (تجاهل عمود كلمة المرور)",
    "Tenant Hierarchy": "التسلسل الهرمي للمستأجر",
    "by": "بواسطة",
}

po = polib.pofile(str(PO_PATH))
for entry in po:
    if entry.msgid in NEW:
        entry.msgstr = NEW[entry.msgid]
po.save(str(PO_PATH))
print("merged", len(NEW), "entries")
