import pytest
from unittest import mock
from django.core.exceptions import AppRegistryNotReady, ImproperlyConfigured
from collections import Counter, defaultdict
from functools import partial
import sys
import threading
import warnings

from .config import AppConfig
from .registry import Apps

@pytest.fixture
def mock_apps():
    with mock.patch('django.apps.registry.Apps') as mock_apps_class:
        mock_apps_instance = mock_apps_class.return_value
        mock_apps_instance.all_models = defaultdict(dict)
        mock_apps_instance.app_configs = {}
        mock_apps_instance.apps_ready = False
        mock_apps_instance.models_ready = False
        mock_apps_instance.ready = False
        mock_apps_instance.loading = False
        mock_apps_instance._pending_operations = defaultdict(list)
        
        # Mocking methods
        mock_apps_instance.populate = mock.Mock()
        mock_apps_instance.check_apps_ready = mock.Mock()
        mock_apps_instance.check_models_ready = mock.Mock()
        mock_apps_instance.get_app_configs = mock.Mock()
        mock_apps_instance.get_app_config = mock.Mock()
        mock_apps_instance.get_models = mock.Mock()
        mock_apps_instance.get_model = mock.Mock()
        mock_apps_instance.register_model = mock.Mock()
        mock_apps_instance.is_installed = mock.Mock()
        mock_apps_instance.get_containing_app_config = mock.Mock()
        mock_apps_instance.get_registered_model = mock.Mock()
        mock_apps_instance.get_swappable_settings_name = mock.Mock()
        mock_apps_instance.set_available_apps = mock.Mock()
        mock_apps_instance.unset_available_apps = mock.Mock()
        mock_apps_instance.set_installed_apps = mock.Mock()
        mock_apps_instance.unset_installed_apps = mock.Mock()
        mock_apps_instance.clear_cache = mock.Mock()
        mock_apps_instance.lazy_model_operation = mock.Mock()
        mock_apps_instance.do_pending_operations = mock.Mock()

        yield mock_apps_instance

# happy path - __init__ - Test that Apps.__init__ initializes with no installed apps
def test_apps_init_no_installed_apps(mock_apps):
    apps_instance = Apps(installed_apps=None)
    assert apps_instance.all_models == {}
    assert apps_instance.app_configs == {}
    assert not apps_instance.apps_ready
    assert not apps_instance.models_ready
    assert not apps_instance.ready
    assert not apps_instance.loading
    assert apps_instance._pending_operations == defaultdict(list)


# happy path - populate - Test that Apps.populate loads app configurations
def test_apps_populate_loads_configs(mock_apps):
    mock_apps.populate.return_value = None
    apps_instance = Apps(installed_apps=['app1', 'app2'])
    apps_instance.populate(['app1', 'app2'])
    mock_apps.populate.assert_called_once_with(['app1', 'app2'])
    assert apps_instance.apps_ready


# happy path - check_apps_ready - Test that Apps.check_apps_ready does not raise when apps are ready
def test_check_apps_ready_no_exception(mock_apps):
    mock_apps.apps_ready = True
    apps_instance = Apps(installed_apps=[])
    apps_instance.check_apps_ready()
    mock_apps.check_apps_ready.assert_called_once()
    assert mock_apps.apps_ready


# happy path - get_app_configs - Test that Apps.get_app_configs returns all app configs
def test_get_app_configs_returns_configs(mock_apps):
    mock_apps.get_app_configs.return_value = ['app1', 'app2']
    apps_instance = Apps(installed_apps=[])
    result = apps_instance.get_app_configs()
    mock_apps.get_app_configs.assert_called_once()
    assert result == ['app1', 'app2']


# happy path - is_installed - Test that Apps.is_installed returns True for installed app
def test_is_installed_returns_true(mock_apps):
    mock_apps.is_installed.return_value = True
    apps_instance = Apps(installed_apps=[])
    result = apps_instance.is_installed('app1')
    mock_apps.is_installed.assert_called_once_with('app1')
    assert result


# edge case - __init__ - Test that Apps.__init__ raises RuntimeError with no installed_apps
def test_apps_init_runtime_error_no_installed_apps(mock_apps):
    with pytest.raises(RuntimeError):
        Apps(installed_apps=None)


# edge case - populate - Test that Apps.populate raises RuntimeError on reentrant call
def test_apps_populate_runtime_error_reentrant(mock_apps):
    mock_apps.loading = True
    apps_instance = Apps(installed_apps=['app1'])
    with pytest.raises(RuntimeError):
        apps_instance.populate(['app1'])


# edge case - get_app_config - Test that Apps.get_app_config raises LookupError for non-existent app
def test_get_app_config_raises_lookup_error(mock_apps):
    mock_apps.get_app_config.side_effect = LookupError
    apps_instance = Apps(installed_apps=[])
    with pytest.raises(LookupError):
        apps_instance.get_app_config('non_existent_app')


# edge case - is_installed - Test that Apps.is_installed returns False for non-installed app
def test_is_installed_returns_false(mock_apps):
    mock_apps.is_installed.return_value = False
    apps_instance = Apps(installed_apps=[])
    result = apps_instance.is_installed('non_existent_app')
    mock_apps.is_installed.assert_called_once_with('non_existent_app')
    assert not result


# edge case - set_available_apps - Test that Apps.set_available_apps raises ValueError for extra apps
def test_set_available_apps_raises_value_error(mock_apps):
    mock_apps.get_app_configs.return_value = ['app1']
    apps_instance = Apps(installed_apps=[])
    with pytest.raises(ValueError):
        apps_instance.set_available_apps(['extra_app'])


