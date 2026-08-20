# apps/communication/services/block_renderer.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from django.template import Context, Template
from django.utils.html import escape

from apps.communication.constants import EmailBlockType


class EmailBlockRenderer:
    """
    Render admin-created email blocks into email-safe HTML.
    """

    def render(self, blocks, *, context, theme=None):
        html_parts = []

        for block in blocks:
            if not block.is_enabled:
                continue

            data = self._render_value(
                block.data or {},
                context,
            )

            html = self._render_block(
                block.block_type,
                data=data,
                theme=theme,
            )

            if html:
                html_parts.append(html)

        return "\n".join(html_parts)

    def _render_block(self, block_type, *, data, theme):
        renderers = {
            EmailBlockType.HERO: self._hero,
            EmailBlockType.TEXT: self._text,
            EmailBlockType.IMAGE: self._image,
            EmailBlockType.BUTTON: self._button,
            EmailBlockType.QUOTE: self._quote,
            EmailBlockType.CALLOUT: self._callout,
            EmailBlockType.DIVIDER: self._divider,
            EmailBlockType.SPACER: self._spacer,
            EmailBlockType.TWO_COLUMN: self._two_column,
            EmailBlockType.SOCIAL_LINKS: self._social_links,
            EmailBlockType.CUSTOM_HTML: self._custom_html,
        }

        renderer = renderers.get(block_type)

        if not renderer:
            return ""

        return renderer(
            data=data,
            theme=theme,
        )

    def _hero(self, *, data, theme):
        title = escape(data.get("title", ""))
        text = data.get("html") or escape(data.get("text", ""))
        image_url = escape(data.get("image_url", ""))
        button_label = escape(data.get("button_label", ""))
        button_url = escape(data.get("button_url", "#"))
        align = self._align(data.get("align", "center"))

        accent = self._theme_value(
            theme,
            "accent_color",
            "#0F52BA",
        )
        heading = self._theme_value(
            theme,
            "heading_color",
            "#0F52BA",
        )
        button_text = self._theme_value(
            theme,
            "button_text_color",
            "#FFFFFF",
        )

        image_html = ""

        if image_url:
            image_html = (
                f'<img src="{image_url}" alt="" width="100%" '
                'style="display:block;width:100%;max-width:100%;'
                'height:auto;border:0;margin:0 0 24px 0;">'
            )

        button_html = ""

        if button_label:
            button_html = (
                '<div style="margin-top:28px;">'
                f'<a href="{button_url}" '
                f'style="display:inline-block;background:{accent};'
                f'color:{button_text};text-decoration:none;'
                'font-weight:700;padding:13px 24px;'
                'border-radius:8px;">'
                f"{button_label}</a></div>"
            )

        return (
            f'<section style="text-align:{align};padding:8px 0 28px;">'
            f"{image_html}"
            f'<h1 style="margin:0 0 16px;color:{heading};'
            'font-size:30px;line-height:1.25;">'
            f"{title}</h1>"
            '<div style="font-size:17px;line-height:1.7;">'
            f"{text}</div>"
            f"{button_html}"
            "</section>"
        )

    def _text(self, *, data, theme):
        html = data.get("html")

        if html is None:
            html = escape(data.get("text", "")).replace(
                "\n",
                "<br>",
            )

        align = self._align(
            data.get("align", "left")
        )

        return (
            f'<div style="text-align:{align};font-size:16px;'
            'line-height:1.7;margin:0 0 24px;">'
            f"{html}</div>"
        )

    def _image(self, *, data, theme):
        url = escape(data.get("url", ""))
        alt = escape(data.get("alt", ""))
        link_url = escape(data.get("link_url", ""))
        width = self._integer(
            data.get("width", 600),
            default=600,
            minimum=80,
            maximum=720,
        )

        if not url:
            return ""

        image = (
            f'<img src="{url}" alt="{alt}" width="{width}" '
            f'style="display:block;width:100%;max-width:{width}px;'
            'height:auto;border:0;margin:0 auto;">'
        )

        if link_url:
            image = f'<a href="{link_url}">{image}</a>'

        return (
            '<div style="margin:0 0 28px;text-align:center;">'
            f"{image}</div>"
        )

    def _button(self, *, data, theme):
        label = escape(data.get("label", "Learn More"))
        url = escape(data.get("url", "#"))
        align = self._align(
            data.get("align", "center")
        )

        accent = self._theme_value(
            theme,
            "accent_color",
            "#0F52BA",
        )
        button_text = self._theme_value(
            theme,
            "button_text_color",
            "#FFFFFF",
        )

        return (
            f'<div style="text-align:{align};margin:8px 0 28px;">'
            f'<a href="{url}" '
            f'style="display:inline-block;background:{accent};'
            f'color:{button_text};text-decoration:none;'
            'font-weight:700;padding:13px 24px;'
            f'border-radius:{self._radius(theme)}px;">'
            f"{label}</a></div>"
        )

    def _quote(self, *, data, theme):
        quote = data.get("quote") or ""
        attribution = escape(
            data.get("attribution", "")
        )

        accent = self._theme_value(
            theme,
            "accent_color",
            "#0F52BA",
        )

        attribution_html = ""

        if attribution:
            attribution_html = (
                '<div style="margin-top:12px;font-size:14px;'
                'font-weight:700;">'
                f"— {attribution}</div>"
            )

        return (
            f'<div style="border-left:4px solid {accent};'
            'padding:18px 22px;margin:0 0 28px;'
            'font-size:18px;line-height:1.6;font-style:italic;">'
            f"{quote}{attribution_html}</div>"
        )

    def _callout(self, *, data, theme):
        title = escape(data.get("title", ""))
        html = data.get("html") or escape(
            data.get("text", "")
        )

        surface = self._theme_value(
            theme,
            "surface_color",
            "#F9F8F4",
        )

        title_html = ""

        if title:
            title_html = (
                '<div style="font-weight:700;margin-bottom:8px;">'
                f"{title}</div>"
            )

        return (
            f'<div style="background:{surface};padding:20px;'
            f'border-radius:{self._radius(theme)}px;'
            'margin:0 0 28px;line-height:1.6;">'
            f"{title_html}{html}</div>"
        )

    def _divider(self, *, data, theme):
        muted = self._theme_value(
            theme,
            "muted_color",
            "#D8D8D8",
        )

        return (
            f'<div style="border-top:1px solid {muted};'
            'margin:28px 0;"></div>'
        )

    def _spacer(self, *, data, theme):
        height = self._integer(
            data.get("height", 24),
            default=24,
            minimum=4,
            maximum=120,
        )

        return f'<div style="height:{height}px;"></div>'

    def _two_column(self, *, data, theme):
        left = data.get("left_html", "")
        right = data.get("right_html", "")

        return (
            '<table role="presentation" width="100%" cellspacing="0" '
            'cellpadding="0" border="0" style="margin:0 0 28px;">'
            "<tr>"
            '<td width="50%" valign="top" '
            'style="padding:0 10px 0 0;line-height:1.6;">'
            f"{left}</td>"
            '<td width="50%" valign="top" '
            'style="padding:0 0 0 10px;line-height:1.6;">'
            f"{right}</td>"
            "</tr>"
            "</table>"
        )

    def _social_links(self, *, data, theme):
        links = data.get("links") or []
        items = []

        for link in links:
            label = escape(link.get("label", ""))
            url = escape(link.get("url", "#"))

            if not label:
                continue

            items.append(
                f'<a href="{url}" style="margin:0 8px;'
                'text-decoration:none;font-weight:700;">'
                f"{label}</a>"
            )

        if not items:
            return ""

        return (
            '<div style="text-align:center;margin:8px 0 28px;">'
            + "".join(items)
            + "</div>"
        )

    def _custom_html(self, *, data, theme):
        return data.get("html", "")

    def _render_value(self, value, context):
        if isinstance(value, str):
            return Template(value).render(
                Context(context)
            )

        if isinstance(value, list):
            return [
                self._render_value(item, context)
                for item in value
            ]

        if isinstance(value, dict):
            return {
                key: self._render_value(item, context)
                for key, item in value.items()
            }

        return value

    def _theme_value(self, theme, field, default):
        if not theme:
            return default

        return getattr(theme, field, None) or default

    def _radius(self, theme):
        if not theme:
            return 8

        return self._integer(
            theme.border_radius,
            default=8,
            minimum=0,
            maximum=40,
        )

    def _align(self, value):
        if value in {"left", "center", "right"}:
            return value

        return "left"

    def _integer(
        self,
        value,
        *,
        default,
        minimum,
        maximum,
    ):
        try:
            result = int(value)
        except (TypeError, ValueError):
            result = default

        return max(
            minimum,
            min(result, maximum),
        )