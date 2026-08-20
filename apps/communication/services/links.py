# apps/communication/services/links.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-20.
# Last Update by Hossein Sakkaki on 2026-08-20.


from urllib.parse import urljoin

from django.conf import settings
from django.urls import reverse


class CommunicationURLBuilder:
    """
    Build canonical absolute Communication URLs.

    Route paths always come from Django's URL resolver instead of
    hard-coded application prefixes.
    """

    def unsubscribe(self, token):
        return self._absolute(
            reverse(
                "communication:email-unsubscribe",
                kwargs={"token": token},
            )
        )

    def resubscribe(self, token):
        return self._absolute(
            reverse(
                "communication:email-resubscribe",
                kwargs={"token": token},
            )
        )

    def external_unsubscribe(self, token):
        return self._absolute(
            reverse(
                "communication:external-email-unsubscribe",
                kwargs={"token": token},
            )
        )

    def track_open(self, token):
        return self._absolute(
            reverse(
                "communication:email-track-open",
                kwargs={"token": token},
            )
        )

    def track_click(self, token):
        return self._absolute(
            reverse(
                "communication:email-track-click",
                kwargs={"token": token},
            )
        )

    def _absolute(self, path):
        base_url = settings.SITE_URL.rstrip("/") + "/"

        return urljoin(
            base_url,
            path.lstrip("/"),
        )