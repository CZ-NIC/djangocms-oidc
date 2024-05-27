import json

from django.forms.widgets import Textarea


class JsonDataTextarea(Textarea):

    def format_value(self, value):
        """
        Return a value as it should appear when rendered in a template.
        """
        if value == "" or value is None:
            return None
        # Reformat json data with indentation.
        try:
            return json.dumps(json.loads(value), indent=4)
        except json.JSONDecodeError:
            pass
        return value
