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
        title = data.get("title") or ""

        text = (
            data.get("html")
            or escape(
                data.get("text", "")
            )
        )

        image_url = escape(
            data.get("image_url", "")
        )

        image_alt = escape(
            data.get("image_alt", "")
        )

        image_link_url = escape(
            data.get(
                "image_link_url",
                "",
            )
        )

        image_width = self._integer(
            data.get(
                "image_width",
                320,
            ),
            default=320,
            minimum=80,
            maximum=700,
        )

        button_label = escape(
            data.get(
                "button_label",
                "",
            )
        )

        button_url = escape(
            data.get(
                "button_url",
                "#",
            )
        )

        align = self._align(
            data.get(
                "align",
                "center",
            )
        )

        heading = self._theme_value(
            theme,
            "heading_color",
            "#0F52BA",
        )

        image_html = ""

        if image_url:
            image = (
                f'<img src="{image_url}" '
                f'alt="{image_alt}" '
                f'width="{image_width}" '
                f'style="display:inline-block;'
                f'width:{image_width}px;'
                'max-width:100%;'
                'height:auto;'
                'border:0;'
                'outline:none;'
                'text-decoration:none;">'
            )

            if image_link_url:
                image = (
                    f'<a href="{image_link_url}" '
                    'style="display:inline-block;'
                    'max-width:100%;'
                    'text-decoration:none;">'
                    f"{image}"
                    "</a>"
                )

            image_html = (
                f'<div style="text-align:{align};'
                'margin:0 0 24px;">'
                f"{image}"
                "</div>"
            )

        title_html = ""

        if title:
            title_html = (
                f'<div style="margin:0 0 16px;'
                f'color:{heading};'
                'font-size:30px;'
                'line-height:1.25;">'
                f"{title}"
                "</div>"
            )

        button_html = ""

        if button_label:
            button_html = self._render_button(
                label=button_label,
                url=button_url,
                align=align,
                theme=theme,
                margin="22px 0 0",
            )

        return (
            f'<section style="text-align:{align};'
            'padding:8px 0 28px;">'
            f"{image_html}"
            f"{title_html}"
            '<div style="font-size:17px;'
            'line-height:1.7;">'
            f"{text}"
            "</div>"
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
        url = escape(
            data.get(
                "url",
                "",
            )
        )

        alt = escape(
            data.get(
                "alt",
                "",
            )
        )

        link_url = escape(
            data.get(
                "link_url",
                "",
            )
        )

        width = self._integer(
            data.get(
                "width",
                320,
            ),
            default=320,
            minimum=80,
            maximum=700,
        )

        align = self._align(
            data.get(
                "align",
                "center",
            )
        )

        if not url:
            return ""

        image = (
            f'<img src="{url}" '
            f'alt="{alt}" '
            f'width="{width}" '
            f'style="display:inline-block;'
            f'width:{width}px;'
            'max-width:100%;'
            'height:auto;'
            'border:0;'
            'outline:none;'
            'text-decoration:none;">'
        )

        if link_url:
            image = (
                f'<a href="{link_url}" '
                'style="display:inline-block;'
                'max-width:100%;'
                'text-decoration:none;">'
                f"{image}"
                "</a>"
            )

        return (
            f'<div style="margin:0 0 28px;'
            f'text-align:{align};">'
            f"{image}"
            "</div>"
        )

    def _button(self, *, data, theme):
        label = escape(data.get("label", "Learn More"))
        url = escape(data.get("url", "#"))
        align = self._align(
            data.get("align", "center")
        )

        return self._render_button(
            label=label,
            url=url,
            align=align,
            theme=theme,
            margin="6px 0 24px",
        )

    def _render_button(
        self,
        *,
        label,
        url,
        align,
        theme,
        margin,
    ):
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
            f'<div style="text-align:{align};margin:{margin};">'
            f'<a href="{url}" '
            'style="display:inline-block;'
            'box-sizing:border-box;'
            f'background-color:{accent};'
            f'color:{button_text};'
            'text-decoration:none;'
            'font-family:Arial,Helvetica,sans-serif;'
            'font-size:14px;'
            'line-height:18px;'
            'font-weight:600;'
            'padding:9px 48px;'
            'border-radius:14px;'
            f'border:1px solid {accent};'
            '-webkit-text-size-adjust:none;">'
            f"{label}</a>"
            "</div>"
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
        title = data.get("title") or ""
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
                '<div style="margin-bottom:8px;">'
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