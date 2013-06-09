"""
7. The lookup API

This demonstrates features of the database API.
"""

from __future__ import unicode_literals

from django.db import models
from django.utils import six
from django.utils.encoding import python_2_unicode_compatible

from shared_models.models import Author, Book


class Tag(models.Model):
    articles = models.ManyToManyField(Book)
    name = models.CharField(max_length=100)
    class Meta:
        ordering = ('name', )


@python_2_unicode_compatible
class Season(models.Model):
    year = models.PositiveSmallIntegerField()
    gt = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return six.text_type(self.year)


@python_2_unicode_compatible
class Game(models.Model):
    season = models.ForeignKey(Season, related_name='games')
    home = models.CharField(max_length=100)
    away = models.CharField(max_length=100)

    def __str__(self):
        return "%s at %s" % (self.away, self.home)


@python_2_unicode_compatible
class Player(models.Model):
    name = models.CharField(max_length=100)
    games = models.ManyToManyField(Game, related_name='players')

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class RegexTestModel(models.Model):
    name = models.CharField(max_length=100, null=True)
    integer = models.IntegerField(null=True)

    def __str__(self):
        return self.name
