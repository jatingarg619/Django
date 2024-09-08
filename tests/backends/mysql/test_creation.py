import subprocess
import unittest
from io import StringIO
from unittest import mock

from django.db import DatabaseError, connection
from django.db.backends.base.creation import BaseDatabaseCreation
from django.db.backends.mysql.creation import DatabaseCreation
from django.test import SimpleTestCase


@unittest.skipUnless(connection.vendor == "mysql", "MySQL tests")
class DatabaseCreationTests(SimpleTestCase):
    def _execute_raise_database_exists(self, cursor, parameters, keepdb=False):
        raise DatabaseError(
            1007, "Can't create database '%s'; database exists" % parameters["dbname"]
        )

    def _execute_raise_access_denied(self, cursor, parameters, keepdb=False):
        raise DatabaseError(1044, "Access denied for user")

    def patch_test_db_creation(self, execute_create_test_db):
        return mock.patch.object(
            BaseDatabaseCreation, "_execute_create_test_db", execute_create_test_db
        )

    @mock.patch("sys.stdout", new_callable=StringIO)
    @mock.patch("sys.stderr", new_callable=StringIO)
    def test_create_test_db_database_exists(self, *mocked_objects):
        # Simulate test database creation raising "database exists"
        creation = DatabaseCreation(connection)
        with self.patch_test_db_creation(self._execute_raise_database_exists):
            with mock.patch("builtins.input", return_value="no"):
                with self.assertRaises(SystemExit):
                    # SystemExit is raised if the user answers "no" to the
                    # prompt asking if it's okay to delete the test database.
                    creation._create_test_db(
                        verbosity=0, autoclobber=False, keepdb=False
                    )
            # "Database exists" shouldn't appear when keepdb is on
            creation._create_test_db(verbosity=0, autoclobber=False, keepdb=True)

    @mock.patch("sys.stdout", new_callable=StringIO)
    @mock.patch("sys.stderr", new_callable=StringIO)
    def test_create_test_db_unexpected_error(self, *mocked_objects):
        # Simulate test database creation raising unexpected error
        creation = DatabaseCreation(connection)
        with self.patch_test_db_creation(self._execute_raise_access_denied):
            with self.assertRaises(SystemExit):
                creation._create_test_db(verbosity=0, autoclobber=False, keepdb=False)

    def test_clone_test_db_database_exists(self):
        creation = DatabaseCreation(connection)
        with self.patch_test_db_creation(self._execute_raise_database_exists):
            with mock.patch.object(DatabaseCreation, "_clone_db") as _clone_db:
                creation._clone_test_db("suffix", verbosity=0, keepdb=True)
                _clone_db.assert_not_called()

    @mock.patch("subprocess.Popen")
    def test_clone_test_db_unexpected_error(self, mocked_popen):
        creation = DatabaseCreation(connection)
        mocked_proc = mock.Mock()
        mocked_proc.communicate.return_value = (b"stdout", b"stderr")
        mocked_popen.return_value.__enter__.return_value = mocked_proc

        with self.assertRaises(SystemExit):
            creation._clone_db("source_db", "target_db")

    @mock.patch("subprocess.Popen")
    def test_clone_test_db_options_ordering(self, mocked_popen):
        creation = DatabaseCreation(connection)
        try:
            saved_settings = connection.settings_dict
            connection.settings_dict = {
                "NAME": "source_db",
                "USER": "",
                "PASSWORD": "",
                "PORT": "",
                "HOST": "",
                "ENGINE": "django.db.backends.mysql",
                "OPTIONS": {
                    "read_default_file": "my.cnf",
                },
            }
            mock_proc = mock.Mock()
            mock_proc.communicate.return_value = (b"", b"")
            mock_proc.returncode = 0
            mocked_popen.return_value.__enter__.return_value = mock_proc

            creation._clone_db("source_db", "target_db")
            mocked_popen.assert_has_calls(
                [
                    mock.call(
                        [
                            "mysqldump",
                            "--defaults-file=my.cnf",
                            "--routines",
                            "--events",
                            "source_db",
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=None,
                    ),
                    mock.call().__enter__(),
                    mock.call(
                        [
                            "mysql",
                            "--defaults-file=my.cnf",
                            "target_db",
                        ],
                        stdin=mock.ANY,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=None,
                    ),
                    mock.call().__enter__(),
                    mock.call().__enter__().stdout.close(),
                    mock.call().__enter__().communicate(),
                    mock.call().__enter__().stderr.read(),
                    mock.call().__enter__().stderr.read().decode(),
                    mock.call().__exit__(None, None, None),
                    mock.call().__exit__(None, None, None),
                ]
            )
        finally:
            connection.settings_dict = saved_settings
