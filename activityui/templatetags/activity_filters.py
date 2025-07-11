from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """从字典中获取项目的模板过滤器"""
    if dictionary is None:
        return None
    return dictionary.get(key, '')
