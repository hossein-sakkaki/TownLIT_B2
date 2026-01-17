# apps/media_conversion/services/progress.py
from __future__ import annotations

from typing import Optional, Any
from datetime import timedelta
import re

from django.utils import timezone

from apps.media_conversion.models import MediaConversionJob, MediaJobStatus
from django.contrib.contenttypes.models import ContentType


# -------------------------------------------------
# Helpers
# -------------------------------------------------

# Regex for trailing '(~Xm Ys left)' ---------------
_ETA_SUFFIX_RE = re.compile(r"\s*\(~\s*[^)]*\s*left\)\s*$", re.IGNORECASE)

# Format ETA for UI text --------------------------
def _format_eta(eta_seconds: Optional[int]) -> str:
    """Short human ETA for UI text."""
    if eta_seconds is None or eta_seconds <= 0:
        return ""
    s = int(eta_seconds)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m"

# Remove trailing '(~Xm Ys left)' -----------------
def _strip_eta_suffix(msg: str) -> str:
    """Remove trailing '(~Xm Ys left)' if present to avoid duplication."""
    if not msg:
        return ""
    return _ETA_SUFFIX_RE.sub("", msg).strip()

# Set attr only if field exists -------------------
def _safe_set(obj, field: str, value) -> bool:
    """Set attr only if field exists; return True if set."""
    try:
        if hasattr(obj, field):
            setattr(obj, field, value)
            return True
    except Exception:
        pass
    return False

# Compute weighted progress percent --------------
def _compute_weighted_percent(job: MediaConversionJob) -> Optional[int]:
    """
    Compute weighted progress percent (0..100) if metadata is available.
    """
    try:
        if not job.stage_total_weight or job.stage_total_weight <= 0:
            return None

        completed = job.stage_completed_weight or 0
        weight = job.stage_weight or 0
        frac = job.stage_progress or 0.0

        weighted = (completed + (weight * frac)) / float(job.stage_total_weight)
        return max(0, min(100, int(weighted * 100)))
    except Exception:
        return None

# Sum stage plan weights -------------------------
def _sum_stage_plan_weights(stage_plan: Optional[list[dict]]) -> Optional[int]:
    try:
        if not stage_plan:
            return None
        total = 0
        for x in stage_plan:
            w = int((x or {}).get("weight") or 0)
            total += max(0, w)
        return total if total > 0 else None
    except Exception:
        return None

# Infer stage weight from plan -------------------
def _infer_stage_weight_from_plan(stage_plan: Optional[list[dict]], stage_key: Optional[str]) -> Optional[int]:
    try:
        if not stage_plan or not stage_key:
            return None
        for x in stage_plan:
            if (x or {}).get("key") == stage_key:
                w = int((x or {}).get("weight") or 0)
                return max(0, w)
        return None
    except Exception:
        return None

# Infer completed weight from plan --------------
def _infer_completed_weight_from_plan(stage_plan: Optional[list[dict]], stage_index: Optional[int]) -> Optional[int]:
    """
    Sum weights of stages strictly before current stage_index.
    stage_index is expected to be 0-based.
    """
    try:
        if not stage_plan or stage_index is None:
            return None
        i = int(stage_index)
        if i <= 0:
            return 0
        total = 0
        for x in stage_plan[:i]:
            total += max(0, int((x or {}).get("weight") or 0))
        return total
    except Exception:
        return None

# Clamp to [0..1] -------------------------------
def _clamp01(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    try:
        v = float(x)
    except Exception:
        return None
    if v < 0:
        return 0.0
    if v > 1:
        return 1.0
    return v

# Should allow stage progress 1 ------------------
def _should_allow_stage_progress_one(
    *,
    prev_stage: Optional[str],
    next_stage: Optional[str],
    prev_completed_weight: int,
    next_completed_weight: int,
    next_status: Optional[str],
) -> bool:
    # Allow 1.0 only on real transitions
    if next_status == "done":
        return True
    if prev_stage and next_stage and prev_stage != next_stage:
        return True
    if next_completed_weight > prev_completed_weight:
        return True
    return False


# -------------------------------------------------
# Public API
# -------------------------------------------------

def touch_job(
    job: MediaConversionJob | None,
    *,
    status: Optional[str] = None,
    progress: Optional[int] = None,      # legacy / override
    message: Optional[str] = None,
    error: Optional[str] = None,
    eta_seconds: Optional[int] = None,

    # ---- stage-based (optional) ----
    stage: Optional[str] = None,
    stage_index: Optional[int] = None,
    stage_count: Optional[int] = None,
    stage_weight: Optional[int] = None,
    stage_progress: Optional[float] = None,
    stage_started_at: Optional[Any] = None,

    # ---- weighted timeline (authoritative) ----
    stage_plan: Optional[list[dict]] = None,
    stage_total_weight: Optional[int] = None,
    stage_completed_weight: Optional[int] = None,
) -> None:
    """
    Best-effort heartbeat / progress update.
    Must NEVER raise.
    """
    if not job:
        return

    try:
        now = timezone.now()
        fields: list[str] = []

        # -------------------------------------------------
        # Heartbeat (always)
        # -------------------------------------------------
        job.heartbeat_at = now
        fields.append("heartbeat_at")

        # -------------------------------------------------
        # Status
        # -------------------------------------------------
        if status and job.status != status:
            job.status = status
            fields.append("status")

        # If job is done, force consistent timeline end-state
        # (helps UI + avoids weird partial terminal state)
        if status == "done":
            if _safe_set(job, "stage_progress", 1.0):
                fields.append("stage_progress")

            tw = getattr(job, "stage_total_weight", None)
            if isinstance(tw, (int, float)) and tw:
                if _safe_set(job, "stage_completed_weight", int(tw)):
                    fields.append("stage_completed_weight")

        # -------------------------------------------------
        # Weighted timeline metadata (store plan first so inference works)
        # -------------------------------------------------
        if stage_plan is not None and _safe_set(job, "stage_plan", stage_plan):
            fields.append("stage_plan")

        # If total weight wasn't provided but we have plan, compute it (best-effort)
        if stage_total_weight is None and (stage_plan is not None or getattr(job, "stage_plan", None)):
            computed_total = _sum_stage_plan_weights(getattr(job, "stage_plan", None))
            if computed_total is not None:
                stage_total_weight = computed_total

        if stage_total_weight is not None and _safe_set(job, "stage_total_weight", int(stage_total_weight)):
            fields.append("stage_total_weight")

        # -------------------------------------------------
        # Stage fields (may influence inference)
        # -------------------------------------------------
        prev_stage = getattr(job, "stage", None)
        prev_completed = int(getattr(job, "stage_completed_weight", None) or 0)

        if stage is not None and _safe_set(job, "stage", stage):
            fields.append("stage")
        next_stage = getattr(job, "stage", None)

        if stage_index is not None and _safe_set(job, "stage_index", int(stage_index)):
            fields.append("stage_index")

        if stage_count is not None and _safe_set(job, "stage_count", int(stage_count)):
            fields.append("stage_count")

        # Infer stage_weight from plan if not provided
        if stage_weight is None and (next_stage is not None):
            inferred = _infer_stage_weight_from_plan(getattr(job, "stage_plan", None), next_stage)
            if inferred is not None:
                stage_weight = inferred

        if stage_weight is not None and _safe_set(job, "stage_weight", int(stage_weight)):
            fields.append("stage_weight")

        if stage_started_at is not None and _safe_set(job, "stage_started_at", stage_started_at):
            fields.append("stage_started_at")

        # -------------------------------------------------
        # completed_weight (normalize: monotonic, inferred if missing)
        # -------------------------------------------------
        next_completed = stage_completed_weight

        if next_completed is None and stage_index is not None:
            inferred_cw = _infer_completed_weight_from_plan(getattr(job, "stage_plan", None), stage_index)
            if inferred_cw is not None:
                next_completed = inferred_cw

        if next_completed is None:
            next_completed = int(getattr(job, "stage_completed_weight", None) or 0)

        # ✅ monotonic guard (never go backwards)
        next_completed = max(prev_completed, int(next_completed or 0))

        if _safe_set(job, "stage_completed_weight", int(next_completed)):
            fields.append("stage_completed_weight")

        # -------------------------------------------------
        # stage_progress (CRITICAL FIX: prevent fake 1.0)
        # -------------------------------------------------
        if stage_progress is not None:
            frac = _clamp01(stage_progress)
            if frac is not None:
                # If 1.0 but no real transition happened, cap it
                if frac >= 1.0 and not _should_allow_stage_progress_one(
                    prev_stage=prev_stage,
                    next_stage=next_stage,
                    prev_completed_weight=prev_completed,
                    next_completed_weight=next_completed,
                    next_status=status or getattr(job, "status", None),
                ):
                    frac = 0.999

                if _safe_set(job, "stage_progress", float(frac)):
                    fields.append("stage_progress")

        # -------------------------------------------------
        # Progress (authoritative: weighted → fallback: legacy)
        # -------------------------------------------------
        weighted_percent = _compute_weighted_percent(job)

        if weighted_percent is not None:
            if job.progress != weighted_percent:
                job.progress = weighted_percent
                fields.append("progress")
        elif progress is not None:
            p = max(0, min(100, int(progress)))
            if job.progress != p:
                job.progress = p
                fields.append("progress")

        # -------------------------------------------------
        # Message + ETA (IMPORTANT FIX)
        # -------------------------------------------------
        if message is not None or eta_seconds is not None:
            base = message if message is not None else (job.message or "")
            base = _strip_eta_suffix(base)

            eta_txt = _format_eta(eta_seconds)
            if eta_txt:
                msg = f"{base} (~{eta_txt} left)".strip() if base else f"~{eta_txt} left"
            else:
                msg = base

            if job.message != msg:
                job.message = msg
                fields.append("message")

        # -------------------------------------------------
        # Error
        # -------------------------------------------------
        if error is not None:
            err = (error or "")[:20000]
            if job.error != err:
                job.error = err
                fields.append("error")

        # -------------------------------------------------
        # Persist
        # -------------------------------------------------
        fields.append("updated_at")
        job.save(update_fields=list(dict.fromkeys(fields)))

    except Exception:
        # Must NEVER raise
        pass



# -------------------------------------------------
# Stale-job reaper
# -------------------------------------------------

def auto_fail_stale_jobs(
    *,
    stale_after_seconds: int = 180,
    max_rows: int = 500,
) -> int:
    """
    Mark stuck processing jobs as FAILED when heartbeat is stale.
    """
    try:
        cutoff = timezone.now() - timedelta(seconds=int(stale_after_seconds))

        qs = (
            MediaConversionJob.objects
            .filter(status="processing", heartbeat_at__lt=cutoff)
            .order_by("heartbeat_at")[:max_rows]
        )

        updated = 0
        now = timezone.now()

        for job in qs:
            try:
                fields: list[str] = []

                job.status = "failed"
                fields.append("status")

                job.message = "Auto-failed: stale heartbeat"
                fields.append("message")

                job.error = f"Worker heartbeat stale for > {stale_after_seconds}s."
                fields.append("error")

                if _safe_set(job, "finished_at", now):
                    fields.append("finished_at")

                fields.append("updated_at")
                job.save(update_fields=list(dict.fromkeys(fields)))
                updated += 1
            except Exception:
                continue

        return updated
    except Exception:
        return 0
