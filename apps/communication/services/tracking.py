# apps/communication/services/tracking.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-20.
# Last Update by Hossein Sakkaki on 2026-08-20.


from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

from django.core import signing

from .links import CommunicationURLBuilder


OPEN_SALT = "townlit.communication.open.v1"
CLICK_SALT = "townlit.communication.click.v1"


class EmailTrackingService:
    """
    Build and resolve signed email engagement links.
    """

    def __init__(self):
        self.url_builder = CommunicationURLBuilder()

    def decorate_html(self, *, html, campaign, delivery):
        content = html or ""

        if campaign.track_clicks:
            content = self._rewrite_links(
                content,
                delivery_id=delivery.id,
            )

        if campaign.track_opens:
            content += self._open_pixel(
                delivery_id=delivery.id
            )

        return content

    def resolve_open_token(self, token):
        payload = signing.loads(
            token,
            salt=OPEN_SALT,
        )

        return int(payload["delivery_id"])

    def resolve_click_token(self, token):
        payload = signing.loads(
            token,
            salt=CLICK_SALT,
        )

        delivery_id = int(
            payload["delivery_id"]
        )
        url = payload["url"]

        if not self._is_trackable_url(url):
            raise signing.BadSignature(
                "Unsafe click destination."
            )

        return delivery_id, url

    def build_open_url(self, *, delivery_id):
        token = signing.dumps(
            {
                "delivery_id": delivery_id,
            },
            salt=OPEN_SALT,
            compress=True,
        )

        return self.url_builder.track_open(
            token
        )

    def build_click_url(
        self,
        *,
        delivery_id,
        url,
    ):
        if not self._is_trackable_url(url):
            return url

        token = signing.dumps(
            {
                "delivery_id": delivery_id,
                "url": url,
            },
            salt=CLICK_SALT,
            compress=True,
        )

        return self.url_builder.track_click(
            token
        )

    def _rewrite_links(
        self,
        html,
        *,
        delivery_id,
    ):
        parser = _TrackingLinkParser(
            tracking_service=self,
            delivery_id=delivery_id,
        )

        parser.feed(html)
        parser.close()

        return parser.html

    def _open_pixel(
        self,
        *,
        delivery_id,
    ):
        url = escape(
            self.build_open_url(
                delivery_id=delivery_id
            ),
            quote=True,
        )

        return (
            f'<img src="{url}" width="1" height="1" alt="" '
            'style="display:block;width:1px;height:1px;'
            'border:0;overflow:hidden;" />'
        )

    def _is_trackable_url(self, url):
        if not url:
            return False

        parsed = urlparse(url)

        return parsed.scheme.lower() in {
            "http",
            "https",
        }


class _TrackingLinkParser(HTMLParser):
    def __init__(
        self,
        *,
        tracking_service,
        delivery_id,
    ):
        super().__init__(
            convert_charrefs=False
        )

        self.tracking_service = tracking_service
        self.delivery_id = delivery_id
        self.parts = []

    @property
    def html(self):
        return "".join(
            self.parts
        )

    def handle_starttag(
        self,
        tag,
        attrs,
    ):
        self.parts.append(
            self._build_tag(
                tag,
                attrs,
                closing=False,
            )
        )

    def handle_startendtag(
        self,
        tag,
        attrs,
    ):
        self.parts.append(
            self._build_tag(
                tag,
                attrs,
                closing=True,
            )
        )

    def handle_endtag(
        self,
        tag,
    ):
        self.parts.append(
            f"</{tag}>"
        )

    def handle_data(
        self,
        data,
    ):
        self.parts.append(
            data
        )

    def handle_entityref(
        self,
        name,
    ):
        self.parts.append(
            f"&{name};"
        )

    def handle_charref(
        self,
        name,
    ):
        self.parts.append(
            f"&#{name};"
        )

    def handle_comment(
        self,
        data,
    ):
        self.parts.append(
            f"<!--{data}-->"
        )

    def handle_decl(
        self,
        decl,
    ):
        self.parts.append(
            f"<!{decl}>"
        )

    def handle_pi(
        self,
        data,
    ):
        self.parts.append(
            f"<?{data}>"
        )

    def _build_tag(
        self,
        tag,
        attrs,
        *,
        closing,
    ):
        rendered_attrs = []

        for name, value in attrs:
            if value is None:
                rendered_attrs.append(
                    name
                )
                continue

            if (
                tag.lower() == "a"
                and name.lower() == "href"
            ):
                value = (
                    self.tracking_service
                    .build_click_url(
                        delivery_id=self.delivery_id,
                        url=value,
                    )
                )

            rendered_attrs.append(
                f'{name}="{escape(value, quote=True)}"'
            )

        suffix = " /" if closing else ""

        attributes = (
            " " + " ".join(rendered_attrs)
            if rendered_attrs
            else ""
        )

        return (
            f"<{tag}{attributes}{suffix}>"
        )