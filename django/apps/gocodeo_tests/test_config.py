import pytest
from unittest import mock
from django.core.exceptions import ImproperlyConfigured
from django.utils.functional import cached_property
from django.utils.module_loading import import_string, module_has_submodule
from importlib import import_module
import inspect
import os

from django.apps.config import AppConfig

@pytest.fixture
def app_config_mock():
    with mock.patch('django.apps.config.import_module') as mock_import_module, \
         mock.patch('django.apps.config.module_has_submodule') as mock_module_has_submodule, \
         mock.patch('django.apps.config.inspect.getmembers') as mock_getmembers, \
         mock.patch('django.apps.config.os.path.dirname') as mock_path_dirname, \
         mock.patch('django.apps.config.cached_property') as mock_cached_property, \
         mock.patch('django.apps.config.ImproperlyConfigured') as mock_improperly_configured:
        
        # Mocking import_module to return a mock module
        mock_module = mock.Mock()
        mock_import_module.return_value = mock_module
        
        # Mocking module_has_submodule to return True
        mock_module_has_submodule.return_value = True
        
        # Mocking getmembers to return an empty list
        mock_getmembers.return_value = []
        
        # Mocking path.dirname to return a mock path
        mock_path_dirname.return_value = '/mock/path/to/app'
        
        # Mocking cached_property to return the property itself
        mock_cached_property.side_effect = lambda f: f
        
        # Mocking ImproperlyConfigured exception
        mock_improperly_configured.side_effect = ImproperlyConfigured
        
        yield {
            'mock_import_module': mock_import_module,
            'mock_module_has_submodule': mock_module_has_submodule,
            'mock_getmembers': mock_getmembers,
            'mock_path_dirname': mock_path_dirname,
            'mock_cached_property': mock_cached_property,
            'mock_improperly_configured': mock_improperly_configured,
            'app_config': AppConfig('django.contrib.admin', mock_module)
        }

# happy path - __init__ - Test that AppConfig initializes with valid app_name and app_module.
def test_init_valid(app_config_mock):
    app_config = app_config_mock['app_config']
    assert app_config.name == 'django.contrib.admin'
    assert app_config.label == 'admin'
    assert app_config.verbose_name == 'Admin'
    assert app_config.path == '/mock/path/to/app'


# happy path - __repr__ - Test that __repr__ returns the correct string representation of AppConfig.
def test_repr(app_config_mock):
    app_config = app_config_mock['app_config']
    assert repr(app_config) == '<AppConfig: admin>'


# happy path - default_auto_field - Test that default_auto_field returns the DEFAULT_AUTO_FIELD setting.
def test_default_auto_field(app_config_mock, settings):
    settings.DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
    app_config = app_config_mock['app_config']
    assert app_config.default_auto_field == 'django.db.models.BigAutoField'


# happy path - _is_default_auto_field_overridden - Test that _is_default_auto_field_overridden detects overridden default_auto_field.
def test_is_default_auto_field_overridden(app_config_mock):
    class CustomAppConfig(AppConfig):
        default_auto_field = 'django.db.models.SmallAutoField'
    custom_app_config = CustomAppConfig('custom', app_config_mock['mock_import_module'].return_value)
    assert custom_app_config._is_default_auto_field_overridden


# happy path - _path_from_module - Test that _path_from_module returns correct path for a valid module.
def test_path_from_module_valid(app_config_mock):
    app_config = app_config_mock['app_config']
    path = app_config._path_from_module(app_config.module)
    assert path == '/mock/path/to/app'


# happy path - create - Test that create method returns an AppConfig instance for a valid entry.
def test_create_valid_entry(app_config_mock):
    mock_import_module = app_config_mock['mock_import_module']
    app_config = AppConfig.create('django.contrib.admin')
    assert isinstance(app_config, AppConfig)
    assert app_config.name == 'django.contrib.admin'


# edge case - __init__ - Test that __init__ raises ImproperlyConfigured for invalid app_name.
def test_init_invalid_app_name(app_config_mock):
    with pytest.raises(ImproperlyConfigured) as excinfo:
        AppConfig('invalid app name', app_config_mock['mock_import_module'].return_value)
    assert "The app label 'name' is not a valid Python identifier." in str(excinfo.value)


# edge case - _path_from_module - Test that _path_from_module raises ImproperlyConfigured for module with multiple paths.
def test_path_from_module_multiple_paths(app_config_mock):
    mock_module = app_config_mock['mock_import_module'].return_value
    mock_module.__path__ = ['/path/one', '/path/two']
    app_config = app_config_mock['app_config']
    with pytest.raises(ImproperlyConfigured) as excinfo:
        app_config._path_from_module(mock_module)
    assert "The app module '<module>' has multiple filesystem locations" in str(excinfo.value)


# edge case - create - Test that create raises ImproperlyConfigured for non-AppConfig subclass entry.
def test_create_non_appconfig_subclass(app_config_mock):
    with pytest.raises(ImproperlyConfigured) as excinfo:
        AppConfig.create('non_appconfig_class')
    assert "'non_appconfig_class' isn't a subclass of AppConfig." in str(excinfo.value)


# edge case - get_model - Test that get_model raises LookupError for non-existent model_name.
def test_get_model_non_existent(app_config_mock):
    app_config = app_config_mock['app_config']
    app_config.models = {}
    with pytest.raises(LookupError) as excinfo:
        app_config.get_model('NonExistentModel')
    assert "App 'admin' doesn't have a 'NonExistentModel' model." in str(excinfo.value)


# edge case - import_models - Test that import_models handles apps without models module gracefully.
def test_import_models_no_models_module(app_config_mock):
    app_config = app_config_mock['app_config']
    app_config.models_module = None
    app_config.import_models()
    assert app_config.models_module is None


