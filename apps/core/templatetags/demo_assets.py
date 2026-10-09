from django import template

from apps.core.demo_assets import demo_image

register = template.Library()


@register.simple_tag
def demo_asset(kind, code, variant="thumb"):
    return demo_image(kind, code, variant)
