# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.checks import register


@register()
def check_generic_foreign_keys(**kwargs):
    from .generic import GenericForeignKey
    from django.db import models

    errors = []
    fields = (obj
        for cls in models.get_models()
        for obj in vars(cls).itervalues()
        if isinstance(obj, GenericForeignKey))
    for field in fields:
        errors.extend(field.check())
    return errors
