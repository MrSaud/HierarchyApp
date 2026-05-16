"""
Generic ORM audit: create / update / delete on all hierarchy models (+ auth User),
M2M changes on hierarchy instances, without logging AuditLog rows (avoids recursion).
"""

from __future__ import annotations

import logging

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .audit_store import record_audit
from .models import AuditLog

logger = logging.getLogger(__name__)


def _skip_raw(kwargs) -> bool:
    return bool(kwargs.get("raw"))


def _actor_bits() -> str:
    from .audit_context import get_audit_actor, get_audit_ip

    uid, uname = get_audit_actor()
    ip = get_audit_ip()
    return "actor_uid=%s actor=%s ip=%s" % (uid, uname, ip)


def _brief_instance(instance: models.Model) -> str:
    try:
        s = str(instance)
    except Exception:
        s = ""
    s = (s or "").replace("\n", " ").strip()
    if len(s) > 160:
        s = s[:157] + "..."
    return s


def _details(sender, instance: models.Model, *, extra: str = "") -> str:
    label = sender._meta.label_lower
    bits = _actor_bits()
    brief = _brief_instance(instance)
    tail = (" " + extra) if extra else ""
    return '%s model=%s pk=%s repr="%s"%s' % (bits, label, instance.pk, brief, tail)


def _generic_post_save(sender, instance, created, **kwargs):
    if _skip_raw(kwargs):
        return
    if sender is AuditLog:
        return
    verb = "create" if created else "update"
    action = "%s_%s" % (sender._meta.model_name, verb)
    try:
        record_audit(action, _details(sender, instance))
    except Exception:
        logger.exception("audit post_save failed model=%s", sender._meta.label)


def _generic_post_delete(sender, instance, **kwargs):
    if sender is AuditLog:
        return
    action = "%s_delete" % sender._meta.model_name
    try:
        record_audit(action, _details(sender, instance))
    except Exception:
        logger.exception("audit post_delete failed model=%s", sender._meta.label)


def _connect_model(model: type[models.Model]) -> None:
    if model is AuditLog:
        return
    if model._meta.proxy:
        return
    post_save.connect(_generic_post_save, sender=model, dispatch_uid="audit_generic_save_%s" % model._meta.label)
    post_delete.connect(_generic_post_delete, sender=model, dispatch_uid="audit_generic_delete_%s" % model._meta.label)


def connect_generic_orm_audit() -> None:
    """Wire post_save/post_delete for all concrete hierarchy models (+ User)."""
    cfg = apps.get_app_config("hierarchy")
    for model in cfg.get_models():
        if not model._meta.managed:
            continue
        if model._meta.auto_created:
            continue
        _connect_model(model)

    User = get_user_model()
    if User is not None and User._meta.managed:
        post_save.connect(_generic_post_save, sender=User, dispatch_uid="audit_generic_save_auth_user")
        post_delete.connect(_generic_post_delete, sender=User, dispatch_uid="audit_generic_delete_auth_user")


@receiver(m2m_changed, dispatch_uid="audit_generic_m2m_changed")
def audit_m2m_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    """Log M2M mutations on hierarchy models (sender is the through model)."""
    if not instance or not hasattr(instance, "_meta"):
        return
    if instance._meta.app_label != "hierarchy":
        return
    if isinstance(instance, AuditLog):
        return
    if action not in ("post_add", "post_remove", "post_clear", "pre_clear"):
        return
    rel = getattr(sender, "_meta", None)
    through_label = rel.label if rel else str(sender)
    pks = sorted(pk_set) if pk_set else []
    if len(pks) > 40:
        pks = pks[:40] + ["…"]
    details = "%s m2m_through=%s action=%s reverse=%s related_model=%s pk_set=%s instance=%s pk=%s" % (
        _actor_bits(),
        through_label,
        action,
        reverse,
        getattr(model, "__name__", str(model)),
        pks,
        instance._meta.label_lower,
        instance.pk,
    )
    try:
        record_audit("m2m_changed", details)
    except Exception:
        logger.exception("audit m2m_changed failed")
