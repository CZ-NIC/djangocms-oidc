from django.test import SimpleTestCase

from djangocms_oidc.widgets import JsonDataTextarea


class JsonDataTextareaTest(SimpleTestCase):

    def setUp(self):
        self.widget = JsonDataTextarea()

    def test_none(self):
        self.assertIsNone(self.widget.format_value(None))

    def test_empty_string(self):
        self.assertIsNone(self.widget.format_value(""))

    def test_valid_json(self):
        response = self.widget.format_value('{"data": 42}')
        self.assertJSONEqual(response, {"data": 42})

    def test_invalid_json(self):
        data = '{data": 42}'
        self.assertEqual(self.widget.format_value(data), data)
        data = '{"data": 42'
        self.assertEqual(self.widget.format_value(data), data)
        data = '{"data": 42{'
        self.assertEqual(self.widget.format_value(data), data)
        data = '{"data": 42}}'
        self.assertEqual(self.widget.format_value(data), data)
        data = '{"data" 42}'
        self.assertEqual(self.widget.format_value(data), data)
        data = '{"data": 42} {"end": "test"}'
        self.assertEqual(self.widget.format_value(data), data)
