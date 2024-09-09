from django.core.serializers.base import DeserializationError, DeserializedObject
from django.core.serializers.python import Deserializer
from django.test import SimpleTestCase

from .models import Author


class TestDeserializer(SimpleTestCase):
    def setUp(self):
        self.object_list = [
            {"pk": 1, "model": "serializers.author", "fields": {"name": "Jane"}},
            {"pk": 2, "model": "serializers.author", "fields": {"name": "Joe"}},
        ]
        self.deserializer = Deserializer(self.object_list)
        self.jane = Author(name="Jane", pk=1)
        self.joe = Author(name="Joe", pk=2)

    def test_repr(self):
        deserial_obj = DeserializedObject(obj=self.jane)
        self.assertEqual(
            repr(deserial_obj), "<DeserializedObject: serializers.Author(pk=1)>"
        )

    def test_next_functionality(self):
        first_item = next(self.deserializer)

        self.assertEqual(first_item.object, self.jane)

        second_item = next(self.deserializer)
        self.assertEqual(second_item.object, self.joe)

        with self.assertRaises(StopIteration):
            next(self.deserializer)

    def test_invalid_model_identifier(self):
        invalid_object_list = [
            {"pk": 1, "model": "serializers.author2", "fields": {"name": "Jane"}}
        ]
        self.deserializer = Deserializer(invalid_object_list)
        with self.assertRaises(DeserializationError):
            next(self.deserializer)

        deserializer = Deserializer(object_list=[])
        with self.assertRaises(StopIteration):
            next(deserializer)

    def test_custom_deserializer(self):
        class CustomDeserializer(Deserializer):
            @staticmethod
            def _get_model_from_node(model_identifier):
                return Author

        deserializer = CustomDeserializer(self.object_list)
        result = next(iter(deserializer))
        deserialized_object = result.object
        self.assertEqual(
            self.jane,
            deserialized_object,
        )

    def test_empty_object_list(self):
        deserializer = Deserializer(object_list=[])
        with self.assertRaises(StopIteration):
            next(deserializer)
