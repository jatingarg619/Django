from __future__ import unicode_literals

from django.conf.global_settings import PASSWORD_HASHERS as default_hashers
from django.contrib.auth.hashers import (is_password_usable, 
    check_password, make_password, PBKDF2PasswordHasher, load_hashers,
    PBKDF2SHA1PasswordHasher, BCryptPasswordHasher, get_hasher, identify_hasher,
    UNUSABLE_PASSWORD)
from django.utils import unittest
from django.utils.unittest import skipUnless


try:
    import crypt
except ImportError:
    crypt = None

try:
    import bcrypt
except ImportError:
    bcrypt = None


class TestUtilsHashPass(unittest.TestCase):

    def setUp(self):
        load_hashers(password_hashers=default_hashers)

    def test_simple(self):
        encoded = make_password('letmein')
        self.assertTrue(encoded.startswith('pbkdf2_sha256$'))
        self.assertTrue(is_password_usable(encoded))
        self.assertTrue(check_password('letmein', encoded))
        self.assertFalse(check_password('letmeinz', encoded))

    def test_pkbdf2(self):
        encoded = make_password('letmein', 'seasalt', 'pbkdf2_sha256')
        self.assertEqual(encoded, 
'pbkdf2_sha256$10000$seasalt$FQCNpiZpTb0zub+HBsH6TOwyRxJ19FwvjbweatNmK/Y=')
        self.assertTrue(is_password_usable(encoded))
        self.assertTrue(check_password('letmein', encoded))
        self.assertFalse(check_password('letmeinz', encoded))
        self.assertEqual(identify_hasher(encoded).algorithm, "pbkdf2_sha256")

    def test_sha1(self):
        encoded = make_password('letmein', 'seasalt', 'sha1')
        self.assertEqual(encoded, 
'sha1$seasalt$fec3530984afba6bade3347b7140d1a7da7da8c7')
        self.assertTrue(is_password_usable(encoded))
        self.assertTrue(check_password('letmein', encoded))
        self.assertFalse(check_password('letmeinz', encoded))
        self.assertEqual(identify_hasher(encoded).algorithm, "sha1")

    def test_md5(self):
        encoded = make_password('letmein', 'seasalt', 'md5')
        self.assertEqual(encoded, 
                         'md5$seasalt$f5531bef9f3687d0ccf0f617f0e25573')
        self.assertTrue(is_password_usable(encoded))
        self.assertTrue(check_password('letmein', encoded))
        self.assertFalse(check_password('letmeinz', encoded))
        self.assertEqual(identify_hasher(encoded).algorithm, "md5")

    def test_unsalted_md5(self):
        encoded = make_password('letmein', 'seasalt', 'unsalted_md5')
        self.assertEqual(encoded, '0d107d09f5bbe40cade3de5c71e9e9b7')
        self.assertTrue(is_password_usable(encoded))
        self.assertTrue(check_password('letmein', encoded))
        self.assertFalse(check_password('letmeinz', encoded))
        self.assertEqual(identify_hasher(encoded).algorithm, "unsalted_md5")

    @skipUnless(crypt, "no crypt module to generate password.")
    def test_crypt(self):
        encoded = make_password('letmein', 'ab', 'crypt')
        self.assertEqual(encoded, 'crypt$$abN/qM.L/H8EQ')
        self.assertTrue(is_password_usable(encoded))
        self.assertTrue(check_password('letmein', encoded))
        self.assertFalse(check_password('letmeinz', encoded))
        self.assertEqual(identify_hasher(encoded).algorithm, "crypt")

    @skipUnless(bcrypt, "py-bcrypt not installed")
    def test_bcrypt(self):
        encoded = make_password('letmein', hasher='bcrypt')
        self.assertTrue(is_password_usable(encoded))
        self.assertTrue(encoded.startswith('bcrypt$'))
        self.assertTrue(check_password('letmein', encoded))
        self.assertFalse(check_password('letmeinz', encoded))
        self.assertEqual(identify_hasher(encoded).algorithm, "bcrypt")

    def test_unusable(self):
        encoded = make_password(None)
        self.assertFalse(is_password_usable(encoded))
        self.assertFalse(check_password(None, encoded))
        self.assertFalse(check_password(UNUSABLE_PASSWORD, encoded))
        self.assertFalse(check_password('', encoded))
        self.assertFalse(check_password('letmein', encoded))
        self.assertFalse(check_password('letmeinz', encoded))
        self.assertRaises(ValueError, identify_hasher, encoded)

    def test_bad_algorithm(self):
        def doit():
            make_password('letmein', hasher='lolcat')
        self.assertRaises(ValueError, doit)
        self.assertRaises(ValueError, identify_hasher, "lolcat$salt$hash")

    def test_bad_encoded(self):
        self.assertFalse(is_password_usable('letmein_badencoded'))
        self.assertFalse(is_password_usable(''))

    def test_low_level_pkbdf2(self):
        hasher = PBKDF2PasswordHasher()
        encoded = hasher.encode('letmein', 'seasalt')
        self.assertEqual(encoded, 
'pbkdf2_sha256$10000$seasalt$FQCNpiZpTb0zub+HBsH6TOwyRxJ19FwvjbweatNmK/Y=')
        self.assertTrue(hasher.verify('letmein', encoded))

    def test_low_level_pbkdf2_sha1(self):
        hasher = PBKDF2SHA1PasswordHasher()
        encoded = hasher.encode('letmein', 'seasalt')
        self.assertEqual(encoded, 
'pbkdf2_sha1$10000$seasalt$91JiNKgwADC8j2j86Ije/cc4vfQ=')
        self.assertTrue(hasher.verify('letmein', encoded))

    def test_pbkdf2_is_current_returns_false_if_iterations_differs(self):
        hasher = PBKDF2PasswordHasher()
        hasher.iterations = 1000
        encoded = hasher.encode('letmein', 'seasalt')
        hasher.iterations = 2000
        self.assertFalse(hasher.is_current(encoded))

    @skipUnless(bcrypt, "py-bcrypt not installed")
    def test_bcrypt_is_current_returns_false_if_work_factor_differs(self):
        hasher = BCryptPasswordHasher()
        hasher.rounds = 2
        encoded = hasher.encode('letmein', hasher.salt())
        hasher.rounds = 3
        self.assertFalse(hasher.is_current(encoded))

    def test_check_password_setter_called_when_is_current_false(self):
        class ExceptionSetterCalled(Exception):
            pass
        def setter(password):
            raise ExceptionSetterCalled
        raw_password = 'letmein'
        hasher = PBKDF2PasswordHasher()
        # We're going to hash with an iteration of 1. In check_password() below,
        # it is going to instantiate a new Hasher with the iterations value from 
        # settings or default of 10000, which will make is_current() False.
        # Is there a better way to guarantee is_current() is false?
        hasher.iterations = 1
        encoded = make_password(raw_password, hasher=hasher)
        self.assertRaises(ExceptionSetterCalled,
            check_password, *(raw_password, encoded), **{ 'setter': setter })

    def test_check_password_setter_not_called_when_is_current_true(self):
        class ExceptionSetterCalled(Exception):
            pass
        def setter(password):
            raise ExceptionSetterCalled
        raw_password = 'letmein'
        hasher = PBKDF2PasswordHasher()
        encoded = make_password(raw_password, hasher=hasher)
        self.assertTrue(check_password(raw_password, encoded, setter))

    def test_upgrade(self):
        self.assertEqual('pbkdf2_sha256', get_hasher('default').algorithm)
        for algo in ('sha1', 'md5'):
            encoded = make_password('letmein', hasher=algo)
            state = {'upgraded': False}
            def setter(password):
                state['upgraded'] = True
            self.assertTrue(check_password('letmein', encoded, setter))
            self.assertTrue(state['upgraded'])

    def test_no_upgrade(self):
        encoded = make_password('letmein')
        state = {'upgraded': False}
        def setter():
            state['upgraded'] = True
        self.assertFalse(check_password('WRONG', encoded, setter))
        self.assertFalse(state['upgraded'])

    def test_no_upgrade_on_incorrect_pass(self):
        self.assertEqual('pbkdf2_sha256', get_hasher('default').algorithm)
        for algo in ('sha1', 'md5'):
            encoded = make_password('letmein', hasher=algo)
            state = {'upgraded': False}
            def setter():
                state['upgraded'] = True
            self.assertFalse(check_password('WRONG', encoded, setter))
            self.assertFalse(state['upgraded'])
