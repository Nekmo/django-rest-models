# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import logging

from django.apps import apps
from django.core.checks import Error, Tags, register

logger = logging.getLogger(__name__)


def api_struct_check(app_configs, **kwargs):
    from rest_models.backend.compiler import get_resource_path  # NOQA
    from rest_models.router import RestModelRouter  # NOQA

    errors = []

    all_models = []
    if app_configs is None:
        all_models.extend(apps.get_models())
    else:
        for app_config in app_configs:
            all_models.extend(app_config.get_models())
    router = RestModelRouter()
    models = ((router.get_api_connexion(model).cursor(), model)
              for model in all_models if router.is_api_model(model))

    for db, rest_model in models:
        url = get_resource_path(rest_model)
        res = db.options(url)
        if res.status_code != 200:
            errors.append(
                Error(
                    'the remote api does not respond to us. OPTIONS %s/%s => %s' % (db.url, url, res.status_code),
                    hint='check the url for the remote api or the resource_path',
                    obj=rest_model,
                    id='rest_models.E001'
                )
            )
            continue
        options = res.json()
        missings = {
                       'include[]', 'exclude[]', 'filter{}', 'page', 'per_page', 'sort[]'
                   } - set(options.get("features", []))
        if missings:
            errors.append(
                Error(
                    'the remote api does not support the folowing features: %s' % missings,
                    hint='is the api on %s/%s running with dynamic-rest ?' % (db.url, url),
                    obj=rest_model,
                    id='rest_models.E002'
                )
            )
            continue
        for field in rest_model._meta.get_fields():
            if field.is_relation:
                if router.is_api_model(field.related_model):
                    if field.name not in options['properties']:
                        errors.append(
                            Error(
                                'the field %s.%s in not present on the remote serializer' % (
                                    rest_model.__name__, field.name
                                ),
                                obj="%s.%s" % (rest_model.__name__, field.name),
                                hint='check if the serializer on %s/%s has a field "%s"' % (db.url, url, field.name),
                                id='rest_models.E003'
                            )
                        )
            elif field.name not in options['properties']:
                errors.append(
                    Error(
                        'the field %s.%s in not present on the remote serializer' % (rest_model.__name__, field.name),
                        hint='check if the serializer on %s/%s has a field "%s"' % (db.url, url, field.name),
                        id='rest_models.E003'
                    )
                )
    return errors


def register_checks():
    register(api_struct_check, Tags.models)