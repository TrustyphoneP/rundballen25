from django import template

register = template.Library()

@register.filter
def dict_key(d, key):
    """{{ my_dict|dict_key:'some_key' }}"""
    return d.get(key, [])

@register.filter
def get_item(d, key):
    """{{ my_dict|get_item:key }} – key kann eine Variable sein"""
    return d.get(key, 0)
