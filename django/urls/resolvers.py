"""
This module converts requested URLs to callback view functions.

RegexURLResolver is the main class here. Its resolve() method takes a URL (as
a string) and returns a ResolverMatch object which provides access to all
attributes of the resolved URL match.
"""
from __future__ import unicode_literals

from functools import update_wrapper
from types import ModuleType

from django.utils.decorators import available_attrs
from django.utils.functional import cached_property

from .exceptions import Resolver404
from .utils import get_lookup_string


class ResolverMatch(object):
    def __init__(self, endpoint, args, kwargs, app_names=None, namespaces=None):
        self.endpoint = endpoint
        self.args = args
        self.kwargs = kwargs
        self.app_names = app_names or []
        self.namespaces = namespaces or []

    @cached_property
    def func(self):
        return self.endpoint.func

    @cached_property
    def callback(self):
        return getattr(self.endpoint, 'callback', self.func)

    @cached_property
    def url_name(self):
        return getattr(self.endpoint, 'url_name', None)

    @cached_property
    def _func_path(self):
        if hasattr(self.endpoint, 'lookup_str'):
            return self.endpoint.lookup_str

        return get_lookup_string(self.func)

    @cached_property
    def app_name(self):
        """
        Return the fully qualified application namespace.
        """
        return ':'.join(self.app_names)

    @cached_property
    def namespace(self):
        """
        Return the fully qualified instance namespace.
        """
        return ':'.join(self.namespaces)

    @cached_property
    def view_name(self):
        """
        Return the fully qualified view name, consisting of the instance
        namespace and the view's name.
        """
        view_name = self.url_name or self._func_path
        return ':'.join(self.namespaces + [view_name])

    def __getitem__(self, index):
        return (self.callback, self.args, self.kwargs)[index]

    def __repr__(self):
        return "ResolverMatch(func=%s, args=%s, kwargs=%s, url_name=%s, app_names=%s, namespaces=%s)" % (
            self._func_path, self.args, self.kwargs, self.url_name,
            self.app_names, self.namespaces,
        )

    @classmethod
    def from_submatch(cls, submatch, args, kwargs, app_name=None, namespace=None):
        """
        Create a new ResolverMatch, carrying over any properties from
        submatch. Does not carry over args if there are any kwargs.
        """
        if kwargs or submatch.kwargs:
            args = submatch.args
            kwargs.update(submatch.kwargs)
        else:
            args += submatch.args
        app_names = ([app_name] if app_name else []) + submatch.app_names
        namespaces = ([namespace] if namespace else []) + submatch.namespaces
        return cls(submatch.endpoint, args, kwargs, app_names, namespaces)


class BaseResolver(object):
    def __init__(self, urlpattern, decorators=None):
        self.constraints = list(urlpattern.constraints)
        self.kwargs = urlpattern.target.kwargs.copy()
        self.decorators = list(decorators or [])
        self.decorators.extend(urlpattern.target.decorators)

    def resolve(self, path, request):
        raise NotImplementedError("Subclasses of 'BaseResolver' must implement the 'resolve' method.")

    def match(self, path, request):
        args, kwargs = (), {}
        for constraint in self.constraints:
            path, new_args, new_kwargs = constraint.match(path, request)
            args += new_args
            kwargs.update(new_kwargs)
        kwargs.update(self.kwargs)
        return path, args, kwargs


class Resolver(BaseResolver):
    def __init__(self, urlpattern, *args, **kwargs):
        super(Resolver, self).__init__(urlpattern, *args, **kwargs)
        self.urlconf = urlpattern.target
        self.namespace = urlpattern.target.namespace
        self.app_name = urlpattern.target.app_name

    def __repr__(self):
        urlconf_name = self.urlconf.urlconf_name
        if isinstance(urlconf_name, (list, tuple)) and len(urlconf_name):
            urlconf_repr = '<%s list>' % self.resolvers[0].__class__.__name__
        elif isinstance(urlconf_name, ModuleType):
            urlconf_repr = repr(urlconf_name.__name__)
        else:
            urlconf_repr = repr(urlconf_name)
        return "<%s %s%s>" % (
            self.__class__.__name__, urlconf_repr,
            ("[app_name='%s']" % self.app_name) if self.app_name else '',
        )

    @cached_property
    def resolvers(self):
        return [
            urlpattern.as_resolver(decorators=self.decorators)
            for urlpattern in self.urlconf.urlpatterns
        ]

    def resolve(self, path, request=None):
        new_path, args, kwargs = self.match(path, request)

        tried = []
        for resolver in self.resolvers:
            try:
                for match in resolver.resolve(new_path, request):
                    yield ResolverMatch.from_submatch(match, args, kwargs, self.app_name, self.namespace)
                tried.append([resolver])
            except Resolver404 as e:
                if e.tried:
                    tried.extend([resolver] + t for t in e.tried)
                else:
                    tried.append([resolver])
        raise Resolver404({'path': new_path, 'tried': tried})


class ResolverEndpoint(BaseResolver):
    def __init__(self, urlpattern, *args, **kwargs):
        super(ResolverEndpoint, self).__init__(urlpattern, *args, **kwargs)
        self.func = urlpattern.target.view
        self.lookup_str = urlpattern.target.lookup_str
        self.url_name = urlpattern.target.url_name

    def __repr__(self):
        return "<%s '%s'%s>" % (
            self.__class__.__name__, self.lookup_str,
            (" [name='%s']" % self.url_name) if self.url_name else '',
        )

    @cached_property
    def callback(self):
        if not self.decorators:
            return self.func
        callback = self.func
        for decorator in reversed(self.decorators):
            callback = decorator(callback)
        update_wrapper(callback, self.func, assigned=available_attrs(self.func))
        return callback

    def resolve(self, path, request=None):
        new_path, args, kwargs = self.match(path, request)
        yield ResolverMatch(self, args, kwargs)
