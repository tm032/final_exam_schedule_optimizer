"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

Django custom template tags.
"""

from django import template
register = template.Library()

@register.filter
def access_dict_index(dictionary, key):
    return dictionary[key]

@register.filter
def access_list_index(my_list, key):
    return my_list[key]

@register.filter
def get_range(my_list):
    return range(len(my_list))

@register.filter
def calculate_index(counter, params):
    num_days, loop_index = params
    return counter + (num_days * loop_index)

@register.filter
def times(number):
    return range(number)


@register.filter
def color_for_value(value, max_value):
    """Return a background color based on the value of the cell."""
    if isinstance(value, (int, float)) and max_value > 0:
        opacity = value / max_value
        return f"background-color: rgba(255, 0, 0, {opacity});"
    return "background-color: grey; opacity: 1;"
