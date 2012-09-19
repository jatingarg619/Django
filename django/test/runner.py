import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django.test.utils import setup_test_environment, teardown_test_environment
from django.utils.importlib import import_module
from django.utils import unittest
from django.utils.unittest.loader import defaultTestLoader


class DjangoTestDiscoverRunner(object):
    """A Django test runner that uses unittest2 test discovery."""
    def __init__(self, verbosity=1, interactive=True, failfast=True, **kwargs):
        self.verbosity = verbosity
        self.interactive = interactive
        self.failfast = failfast

    def setup_test_environment(self, **kwargs):
        setup_test_environment()
        settings.DEBUG = False
        unittest.installHandler()

    def build_suite(self, test_labels, extra_tests=None, **kwargs):
        suite = None
        root = settings.TEST_DISCOVER_ROOT
        pattern = settings.TEST_DISCOVER_PATTERN
        top_level = settings.TEST_DISCOVER_TOP_LEVEL

        if test_labels:
            suite = defaultTestLoader.loadTestsFromNames(test_labels)
            # if single named module has no tests, do discovery within the
            # module itself
            if not suite.countTestCases() and len(test_labels) == 1:
                suite = None
                root = import_module(test_labels[0]).__path__[0]
                top_level = os.path.dirname(root)

        if suite is None:
            suite = defaultTestLoader.discover(root,
                pattern=pattern,
                top_level_dir=top_level,
                )

        if extra_tests:
            for test in extra_tests:
                suite.addTest(test)

        return reorder_suite(suite, (TestCase,))

    def setup_databases(self, **kwargs):
        from django.db import connections, DEFAULT_DB_ALIAS

        # First pass -- work out which databases actually need to be created,
        # and which ones are test mirrors or duplicate entries in DATABASES
        mirrored_aliases = {}
        test_databases = {}
        dependencies = {}
        for alias in connections:
            connection = connections[alias]
            if connection.settings_dict['TEST_MIRROR']:
                # If the database is marked as a test mirror, save
                # the alias.
                mirrored_aliases[alias] = (
                    connection.settings_dict['TEST_MIRROR'])
            else:
                # Store a tuple with DB parameters that uniquely identify it.
                # If we have two aliases with the same values for that tuple,
                # we only need to create the test database once.
                item = test_databases.setdefault(
                    connection.creation.test_db_signature(),
                    (connection.settings_dict['NAME'], set())
                )
                item[1].add(alias)

                if 'TEST_DEPENDENCIES' in connection.settings_dict:
                    dependencies[alias] = (
                        connection.settings_dict['TEST_DEPENDENCIES'])
                else:
                    if alias != DEFAULT_DB_ALIAS:
                        dependencies[alias] = connection.settings_dict.get(
                            'TEST_DEPENDENCIES', [DEFAULT_DB_ALIAS])

        # Second pass -- actually create the databases.
        old_names = []
        mirrors = []

        for signature, (db_name, aliases) in dependency_ordered(
            test_databases.items(), dependencies):
            test_db_name = None
            # Actually create the database for the first connection

            for alias in aliases:
                connection = connections[alias]
                old_names.append((connection, db_name, True))
                if test_db_name is None:
                    test_db_name = connection.creation.create_test_db(
                            self.verbosity, autoclobber=not self.interactive)
                else:
                    connection.settings_dict['NAME'] = test_db_name

        for alias, mirror_alias in mirrored_aliases.items():
            mirrors.append((alias, connections[alias].settings_dict['NAME']))
            connections[alias].settings_dict['NAME'] = (
                connections[mirror_alias].settings_dict['NAME'])

        return old_names, mirrors

    def run_suite(self, suite, **kwargs):
        return unittest.TextTestRunner(
            verbosity=self.verbosity, failfast=self.failfast).run(suite)

    def teardown_databases(self, old_config, **kwargs):
        """
        Destroys all the non-mirror databases.
        """
        old_names, mirrors = old_config
        for connection, old_name, destroy in old_names:
            if destroy:
                connection.creation.destroy_test_db(old_name, self.verbosity)

    def teardown_test_environment(self, **kwargs):
        unittest.removeHandler()
        teardown_test_environment()

    def suite_result(self, suite, result, **kwargs):
        return len(result.failures) + len(result.errors)

    def run_tests(self, test_labels, discovery_root, extra_tests=None, **kwargs):
        """
        Run the unit tests for all the test labels in the provided list.

        Test labels should be dotted Python paths to test modules, test
        classes, or test methods.

        If no test labels are provided, tests will be discovered under the
        filesystem path ``discovery_root``.

        A list of 'extra' tests may also be provided; these tests
        will be added to the test suite.

        Returns the number of tests that failed.
        """
        self.setup_test_environment()
        suite = self.build_suite(test_labels, extra_tests)
        old_config = self.setup_databases()
        result = self.run_suite(suite)
        self.teardown_databases(old_config)
        self.teardown_test_environment()
        return self.suite_result(suite, result)


def dependency_ordered(test_databases, dependencies):
    """
    Reorder test_databases into an order that honors the dependencies
    described in TEST_DEPENDENCIES.
    """
    ordered_test_databases = []
    resolved_databases = set()

    # Maps db signature to dependencies of all it's aliases
    dependencies_map = {}

    # sanity check - no DB can depend on it's own alias
    for sig, (_, aliases) in test_databases:
        all_deps = set()
        for alias in aliases:
            all_deps.update(dependencies.get(alias, []))
        if not all_deps.isdisjoint(aliases):
            raise ImproperlyConfigured(
                "Circular dependency: databases %r depend on each other, "
                "but are aliases." % aliases)
        dependencies_map[sig] = all_deps

    while test_databases:
        changed = False
        deferred = []

        # Try to find a DB that has all it's dependencies met
        for signature, (db_name, aliases) in test_databases:
            if dependencies_map[signature].issubset(resolved_databases):
                resolved_databases.update(aliases)
                ordered_test_databases.append((signature, (db_name, aliases)))
                changed = True
            else:
                deferred.append((signature, (db_name, aliases)))

        if not changed:
            raise ImproperlyConfigured(
                "Circular dependency in TEST_DEPENDENCIES")
        test_databases = deferred
    return ordered_test_databases


def reorder_suite(suite, classes):
    """
    Reorders a test suite by test type.

    `classes` is a sequence of types

    All tests of type classes[0] are placed first, then tests of type
    classes[1], etc. Tests with no match in classes are placed last.
    """
    class_count = len(classes)
    bins = [unittest.TestSuite() for i in range(class_count+1)]
    partition_suite(suite, classes, bins)
    for i in range(class_count):
        bins[0].addTests(bins[i+1])
    return bins[0]


def partition_suite(suite, classes, bins):
    """
    Partitions a test suite by test type.

    classes is a sequence of types
    bins is a sequence of TestSuites, one more than classes

    Tests of type classes[i] are added to bins[i],
    tests with no match found in classes are place in bins[-1]
    """
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            partition_suite(test, classes, bins)
        else:
            for i in range(len(classes)):
                if isinstance(test, classes[i]):
                    bins[i].addTest(test)
                    break
            else:
                bins[-1].addTest(test)
