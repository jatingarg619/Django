from unittest import skip

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS


def no_backend(test_func, backend):
    "Use this decorator to disable test on specified backend."
    if settings.DATABASES[DEFAULT_DB_ALIAS]['ENGINE'].rsplit('.')[-1] == backend:
        @skip("This test is skipped on '%s' backend" % backend)
        def inner():
            pass
        return inner
    else:
        return test_func


# Decorators to disable entire test functions for specific
# spatial backends.
def no_oracle(func):
    return no_backend(func, 'oracle')


# Shortcut booleans to omit only portions of tests.
_default_db = settings.DATABASES[DEFAULT_DB_ALIAS]['ENGINE'].rsplit('.')[-1]
oracle = _default_db == 'oracle'
postgis = _default_db == 'postgis'
mysql = _default_db == 'mysql'
spatialite = _default_db == 'spatialite'

# MySQL spatial indices can't handle NULL geometries.
gisfield_may_be_null = not mysql
