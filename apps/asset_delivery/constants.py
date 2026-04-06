# apps/asset_delivery/constants.py

class PlaybackIntent:
    PRELOAD = "preload"
    VIEW = "view"
    RENDER = "render"
    FEED = "feed"
    DETAIL = "detail"
    DOWNLOAD = "download"

    ALL = {
        PRELOAD,
        VIEW,
        RENDER,
        FEED,
        DETAIL,
        DOWNLOAD,
    }


class PlaybackAuthMode:
    COOKIE = "cookie"
    SIGNED_URL = "signed_url"