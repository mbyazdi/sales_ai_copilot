"""Presentation aliases only; stored catalog values remain authoritative."""
import re

from django import template

register = template.Library()


@register.filter
def unit_label(value):
    return "عدد" if value == "PCS" else value


@register.filter
def package_label(value):
    return re.sub(r"(?<![\w])PCS(?![\w])", "عدد", str(value or ""))
