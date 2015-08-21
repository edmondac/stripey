import re
from django import template
from django.utils.safestring import mark_safe
register = template.Library()


@register.filter(name='highlight')
def highlight(text, filter):
    pattern = re.compile(r"(?P<filter>%s)" % filter, re.IGNORECASE)
    return mark_safe(re.sub(pattern, r"<span class='highlight'>\g<filter></span>", text))
