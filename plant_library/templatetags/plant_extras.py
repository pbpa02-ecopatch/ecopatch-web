from django import template

register = template.Library()


@register.filter
def selected_label(field):
    """Text of the option that is currently picked, for the custom dropdown."""
    value = field.value()
    for option_value, option_label in field.field.choices:
        if str(option_value) == str(value):
            return option_label
    return ''


@register.filter
def select_options(field):
    """Every real choice; the empty first entry becomes a placeholder instead."""
    return [(value, label) for value, label in field.field.choices if value != '']
