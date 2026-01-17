# utils/mixins/media_autoconvert.py
from __future__ import annotations
from typing import Dict, Iterable, Tuple
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class MediaAutoConvertMixin:
    """
    Drop-in mixin to:
      - Track original filenames
      - Detect RAW media changes (ignore converter outputs like .m3u8/.mp3/.jpg)
      - Flip <is_converted> to False only on RAW change or create
      - Enqueue conversion AFTER COMMIT via your existing MediaConversionMixin

    Requirements:
      - Model must define `media_conversion_config` (like you already do)
      - Optional flag field name (defaults to "is_converted")
      - Your other mixin (MediaConversionMixin) must define convert_uploaded_media_async()

    Usage:
      class MyModel(MediaAutoConvertMixin, MediaConversionMixin, SlugMixin, models.Model):
          ...
    """

    # You can override these in subclasses if needed
    MEDIA_FLAG_FIELD = "is_converted"

    # Final-exts per kind; can be overridden per-model
    MEDIA_FINAL_EXTS: Dict[str, Iterable[str]] = {
        "video": (".m3u8",),              # HLS master/variants
        "audio": (".mp3",),               # final for your pipeline
        "image": (".jpg", ".jpeg", ".png")# image finals after conversion
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # keep MRO intact
        # snapshot original names once loaded
        self._media_orig_names = self._collect_current_media_names()

    # ---------- helpers ----------
    def _get_flag_value(self) -> bool:
        fld = self.MEDIA_FLAG_FIELD
        return bool(getattr(self, fld, False))

    def _set_flag_value(self, val: bool) -> None:
        fld = self.MEDIA_FLAG_FIELD
        if hasattr(self, fld):
            setattr(self, fld, bool(val))

    def _iter_media_fields(self) -> Iterable[Tuple[str, str]]:
        """
        Yields (field_name, kind) from media_conversion_config.
        Expected kinds: "video" | "audio" | "image".
        """
        cfg = getattr(self, "media_conversion_config", {}) or {}
        for fname, meta in cfg.items():
            # meta could be dict or FileUpload (legacy) — we only need kind
            if isinstance(meta, dict):
                kind = meta.get("kind")
            else:
                # try to infer from field_name as fallback
                n = fname.lower()
                if n in ("audio", "voice", "sound"):
                    kind = "audio"
                elif n in ("video", "movie", "clip"):
                    kind = "video"
                else:
                    kind = "image"
            if kind in ("video", "audio", "image"):
                yield fname, kind

    def _collect_current_media_names(self) -> Dict[str, str | None]:
        names: Dict[str, str | None] = {}
        for fname, _ in self._iter_media_fields():
            val = getattr(self, fname, None)
            names[fname] = getattr(val, "name", None)
        return names

    def _is_final_name(self, kind: str, name: str | None) -> bool:
        if not name:
            return False
        exts = tuple(ext.lower() for ext in self.MEDIA_FINAL_EXTS.get(kind, ()))
        return str(name).lower().endswith(exts) if exts else False

    def _raw_media_changed(self) -> bool:
        """
        True if any configured media field changed AND new name is not a final artifact.
        """
        cur = self._collect_current_media_names()
        orig = getattr(self, "_media_orig_names", {}) or {}
        for fname, kind in self._iter_media_fields():
            old = (orig.get(fname) or None)
            new = (cur.get(fname) or None)
            if new != old and not self._is_final_name(kind, new):
                return True
        return False

    
    # -----------------------------------------------
    # Optional hooks
    # -----------------------------------------------
    def media_autoconvert_enabled(self) -> bool:
        """
        Models can override per-instance.
        Default: enabled.
        """
        return True

    def after_autoconvert_save(self, *, is_new: bool, raw_changed: bool) -> None:
        """
        Optional post-save hook (runs after DB save, before on_commit enqueue).
        Default: no-op.
        """
        return


    # -----------------------------------------------
    # MRO
    # -----------------------------------------------
    def save(self, *args, **kwargs):
        is_new = getattr(self, "_state", None) and self._state.adding or kwargs.get("force_insert", False)

        hook = getattr(self, "before_autoconvert_save", None)
        if callable(hook):
            try:
                hook()
            except Exception:
                pass

        # ✅ If autoconvert disabled for this instance, do normal save and exit
        if not self.media_autoconvert_enabled():
            super().save(*args, **kwargs)
            self._media_orig_names = self._collect_current_media_names()
            try:
                self.after_autoconvert_save(is_new=is_new, raw_changed=False)
            except Exception:
                pass
            return
    
        # mark not-converted only for create OR RAW change
        raw_changed = self._raw_media_changed()
        if is_new or raw_changed:
            self._set_flag_value(False)

        # continue the MRO (SlugMixin, Model.save, etc.)
        super().save(*args, **kwargs)

        # refresh snapshot
        self._media_orig_names = self._collect_current_media_names()

        # schedule conversion only if needed
        should_convert = (is_new or raw_changed) and not self._get_flag_value()
        if not should_convert:
            return

        logger.info(
            "🧾 will convert after commit: id=%s new=%s raw_changed=%s",
            getattr(self, "pk", None), is_new, raw_changed
        )

        def _after_commit():
            try:
                # If already flipped true somehow, skip.
                if self._get_flag_value():
                    return
                # Delegate to your existing mixin method (must exist)
                if hasattr(self, "convert_uploaded_media_async"):
                    self.convert_uploaded_media_async()
                else:
                    logger.warning("convert_uploaded_media_async() not found on %s", self.__class__.__name__)
            except Exception as e:
                logger.exception("❌ Failed to enqueue conversion for %s[%s]: %s",
                                 self.__class__.__name__, getattr(self, "pk", None), e)

        # Works inside/outside atomic; outside will run immediately.
        transaction.on_commit(_after_commit)
