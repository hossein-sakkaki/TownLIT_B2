# /utils/common/video_utils.py
import os
import json
import subprocess
import logging
import time
from tempfile import NamedTemporaryFile
from dataclasses import dataclass

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage

from apps.media_conversion.services.video_policy import (
    get_video_rendition_policy_for_instance,
)
from utils.common.utils import FileUpload, get_hls_output_dir
from apps.media_conversion.services.progress import touch_job
from apps.media_conversion.services.video_preview import build_video_preview_mp4

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class VideoConversionResult:
    master_path: str
    width: int | None
    height: int | None
    aspect_ratio: float | None
    duration_ms: int | None
    variants: list[dict]
    preview: dict | None = None
    
# -------------------------------------------------
# Low-level helpers
# -------------------------------------------------

def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def _probe_json(path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "stream=width,height,pix_fmt,"
        "color_range,color_space,color_transfer,color_primaries,"
        "sample_aspect_ratio,display_aspect_ratio:"
        "stream_tags=rotate:"
        "stream_side_data_list",
        "-of", "json",
        path,
    ]
    return json.loads(_run(cmd).stdout.decode("utf-8", "ignore"))





def _probe_duration_ms(path: str) -> int | None:
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=nk=1:nw=1",
                path,
            ],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        sec = float(out)
        return int(sec * 1000) if sec > 0 else None
    except Exception:
        return None


def _even(n: int) -> int:
    return n if n % 2 == 0 else n - 1


def _compute_width(src_w: int, src_h: int, target_h: int) -> int:
    """
    Preserve aspect ratio by computing width from target height.
    Ensures even width for H.264.
    """
    w = int(round(src_w * (target_h / float(src_h))))
    return max(2, _even(w))


def _parse_out_time_ms(line: str) -> int | None:
    if line.startswith("out_time_ms="):
        v = line.split("=", 1)[1].strip()
        return int(v) if v.isdigit() else None

    if line.startswith("out_time="):
        v = line.split("=", 1)[1].strip()
        try:
            h, m, s = v.split(":")
            sec = float(h) * 3600 + float(m) * 60 + float(s)
            return int(sec * 1000)
        except Exception:
            return None

    return None


def _normalize_rotation(rot: int | float | str | None) -> int:
    """
    Normalize rotation to one of {0, 90, 180, 270}.
    Handles -90, 270, floats, strings.
    """
    if rot is None:
        return 0
    try:
        r = int(round(float(rot))) % 360
        candidates = [0, 90, 180, 270]
        return min(candidates, key=lambda x: abs(x - r))
    except Exception:
        return 0


def _extract_rotation_with_source(meta: dict) -> tuple[int, str]:
    """
    Returns (rotation, source)
    source in: "side_data_list.rotation" | "tags.rotate" | "stream.rotation" | "none"
    """
    try:
        s = (meta.get("streams") or [{}])[0]

        # ✅ 1) Prefer Display Matrix rotation (most reliable on iPhone)
        ssd = s.get("side_data_list") or []
        for item in ssd:
            if isinstance(item, dict) and "rotation" in item:
                return _normalize_rotation(item.get("rotation")), "side_data_list.rotation"

        # 2) tags.rotate (less reliable; can be stale)
        tags = s.get("tags") or {}
        if "rotate" in tags:
            return _normalize_rotation(tags.get("rotate")), "tags.rotate"

        # 3) fallback
        if "rotation" in s:
            return _normalize_rotation(s.get("rotation")), "stream.rotation"

    except Exception:
        pass

    return 0, "none"



def _probe_video_size(path: str) -> tuple[int, int]:
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x",
            path,
        ]
    ).decode().strip()

    # ffprobe may return multiple lines → take the first valid one
    for line in out.splitlines():
        if "x" in line:
            try:
                w, h = line.split("x", 1)
                return int(w), int(h)
            except ValueError:
                continue

    raise RuntimeError(f"Could not probe video size from: {path} | output={out!r}")


def _has_side_rotation(meta: dict) -> bool:
    try:
        s0 = (meta.get("streams") or [{}])[0]
        ssd = s0.get("side_data_list") or []
        return any(isinstance(item, dict) and "rotation" in item for item in ssd)
    except Exception:
        return False


def _decide_display_size(meta: dict, coded_w: int, coded_h: int) -> tuple[int, int]:
    rot, _ = _extract_rotation_with_source(meta)
    if rot in (90, 270):
        return coded_h, coded_w
    return coded_w, coded_h


# -------------------------------------------------
# ETA estimator (EMA-smoothed)
# -------------------------------------------------

class _EtaEstimator:
    def __init__(self, total_ms: int | None):
        self.total_ms = total_ms
        self.t0 = time.time()
        self.ema_speed: float | None = None

    def update(self, out_ms: int) -> int | None:
        if not self.total_ms or self.total_ms <= 0:
            return None

        elapsed = max(0.001, time.time() - self.t0)
        inst_speed = out_ms / elapsed

        if self.ema_speed is None:
            self.ema_speed = inst_speed
        else:
            self.ema_speed = (0.2 * inst_speed) + (0.8 * self.ema_speed)

        remaining_ms = max(0, self.total_ms - out_ms)
        return int(remaining_ms / max(1.0, self.ema_speed))


# -------------------------------------------------
# Main pipeline
# -------------------------------------------------
def convert_video_to_multi_hls(
    source_path: str,
    instance,
    fileupload: FileUpload,
    *,
    job=None,
    field_name: str = "video",
) -> VideoConversionResult:
    """
    HLS conversion with policy-based renditions.

    Policy examples:
    - Testimony video: multi HLS
    - Moment/Prayer/PrayerResponse video: single HLS
    """

    policy = get_video_rendition_policy_for_instance(
        instance,
        field_name=field_name,
    )

    PREPARE_WEIGHT = 3
    FINALIZE_WEIGHT = 7
    ENCODE_TOTAL_WEIGHT = 100 - PREPARE_WEIGHT - FINALIZE_WEIGHT

    VIDEO_BASE_WEIGHTS = {
        "source": 40,
        "1080p": 30,
        "720p": 20,
        "480p": 10,
    }

    temp_input = None
    output_dir = None

    try:
        # -------------------------------------------------
        # Prepare local source
        # -------------------------------------------------
        if job:
            touch_job(
                job,
                stage="prepare",
                stage_index=0,
                stage_count=None,
                stage_weight=PREPARE_WEIGHT,
                stage_completed_weight=0,
                stage_progress=0.0,
                message="Preparing video…",
            )

        rel = source_path if not os.path.isabs(source_path) else os.path.relpath(
            source_path,
            settings.MEDIA_ROOT,
        )

        with default_storage.open(rel, "rb") as f:
            with NamedTemporaryFile(delete=False, suffix=os.path.splitext(rel)[1]) as tmp:
                tmp.write(f.read())
                tmp.flush()
                temp_input = tmp.name

        # -------------------------------------------------
        # Probe source metadata
        # -------------------------------------------------
        meta = _probe_json(temp_input)
        s0 = (meta.get("streams") or [{}])[0]
        s = s0

        cp = (s.get("color_primaries") or "").lower()
        ct = (s.get("color_transfer") or "").lower()

        # Real HDR detection.
        is_hdr = (cp == "bt2020") or (ct in ("smpte2084", "arib-std-b67"))

        coded_w = _even(int(s.get("width") or 0))
        coded_h = _even(int(s.get("height") or 0))

        if not coded_w or not coded_h:
            raise RuntimeError("Invalid source dimensions")

        disp_w, disp_h = _decide_display_size(
            meta,
            coded_w,
            coded_h,
        )

        total_ms = _probe_duration_ms(temp_input)

        # -------------------------------------------------
        # Build policy-based rendition plan
        # -------------------------------------------------
        renditions = []
        max_height = max(240, int(policy.max_height or 1080))

        # Main output is always capped for cost/speed safety.
        if disp_h > max_height:
            main_h = max_height
            main_w = _compute_width(disp_w, disp_h, main_h)
        else:
            main_h = disp_h
            main_w = disp_w

        # Always create one main HLS output.
        renditions.append({
            "key": "source",
            "width": main_w,
            "height": main_h,
            "bitrate": "5000000" if main_h >= 1080 else "3000000",
        })

        # Multi mode adds useful lower renditions.
        if policy.mode == "multi":
            for h in (1080, 720, 480):
                if main_h > h:
                    renditions.append({
                        "key": f"{h}p",
                        "height": h,
                        "width": _compute_width(main_w, main_h, h),
                        "bitrate": "3000000" if h >= 720 else "1000000",
                    })

        # -------------------------------------------------
        # Normalize encoding weights
        # -------------------------------------------------
        present_keys = [r["key"] for r in renditions]
        base_sum = sum(VIDEO_BASE_WEIGHTS.get(k, 0) for k in present_keys) or 1

        def _stage_weight(key: str) -> int:
            raw = VIDEO_BASE_WEIGHTS.get(key, 0)
            return int(round((raw / float(base_sum)) * ENCODE_TOTAL_WEIGHT))

        weights = {k: _stage_weight(k) for k in present_keys}

        # Fix rounding drift so encoding sum is exact.
        drift = ENCODE_TOTAL_WEIGHT - sum(weights.values())
        if drift != 0 and present_keys:
            weights[present_keys[0]] = max(0, weights[present_keys[0]] + drift)

        STAGE_WEIGHTS = {
            "prepare": PREPARE_WEIGHT,
            **weights,
            "finalize": FINALIZE_WEIGHT,
        }

        # -------------------------------------------------
        # Authoritative weighted stage plan
        # -------------------------------------------------
        stage_plan = [
            {
                "key": "prepare",
                "label": "Preparing",
                "weight": STAGE_WEIGHTS["prepare"],
            }
        ]

        stage_plan.extend(
            {
                "key": r["key"],
                "label": (
                    "Encoding main quality"
                    if r["key"] == "source"
                    else f"Encoding {r['key']}"
                ),
                "weight": STAGE_WEIGHTS[r["key"]],
            }
            for r in renditions
        )

        stage_plan.append({
            "key": "finalize",
            "label": "Publishing",
            "weight": STAGE_WEIGHTS["finalize"],
        })

        total_weight = sum(x["weight"] for x in stage_plan) or 100
        stage_count = len(stage_plan)

        if job:
            touch_job(
                job,
                stage_plan=stage_plan,
                stage_total_weight=total_weight,
                stage_completed_weight=0,
                stage="prepare",
                stage_index=0,
                stage_count=stage_count,
                stage_weight=STAGE_WEIGHTS["prepare"],
                stage_progress=0.95,
                message="Video prepared…",
            )

        # -------------------------------------------------
        # Output directory
        # -------------------------------------------------
        output_dir, relative_dir = get_hls_output_dir(instance, fileupload)
        os.makedirs(output_dir, exist_ok=True)

        preview_payload = None

        try:
            preview_payload = build_video_preview_mp4(
                local_source_path=temp_input,
                output_key=os.path.join(relative_dir, "preview.mp4"),
                seconds=3.5,
                width=360,
            )
        except Exception:
            logger.warning(
                "Video preview generation skipped",
                exc_info=True,
            )
            
        variants = []
        completed_weight = PREPARE_WEIGHT

        # -------------------------------------------------
        # Encode each rendition
        # -------------------------------------------------
        for idx, r in enumerate(renditions, start=1):
            key = r["key"]

            if key in ("source", "1080p"):
                crf = "18"
            elif key == "720p":
                crf = "19"
            else:
                crf = "20"

            weight = STAGE_WEIGHTS[key]

            if job:
                touch_job(
                    job,
                    stage=key,
                    stage_index=idx,
                    stage_count=stage_count,
                    stage_weight=weight,
                    stage_completed_weight=completed_weight,
                    stage_progress=0.0,
                    message=f"Encoding {key}…",
                )

            subdir = os.path.join(output_dir, key)
            os.makedirs(subdir, exist_ok=True)

            playlist = os.path.join(subdir, "playlist.m3u8")

            # Real HDR mastering metadata.
            has_mastering = any(
                isinstance(sd, dict) and "mastering_display_metadata" in sd
                for sd in (s0.get("side_data_list") or [])
            )

            if is_hdr and has_mastering:
                # Real mastered HDR -> controlled SDR tonemap.
                vf = ",".join([
                    "zscale=transfer=smpte2084:primaries=bt2020:matrix=bt2020nc:range=tv",
                    "zscale=transfer=linear",
                    "tonemap=tonemap=mobius:peak=300:desat=0.15",
                    "zscale=transfer=bt709:primaries=bt709:matrix=bt709:range=tv",
                    f"scale={r['width']}:{r['height']}:flags=lanczos",
                    "setsar=1",
                    "format=yuv420p",
                ])
            else:
                # SDR / mobile HDR -> safe conversion.
                vf = ",".join([
                    f"scale={r['width']}:{r['height']}:flags=lanczos",
                    "setsar=1",
                    "format=yuv420p",
                ])

            cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-i",
                temp_input,

                "-vf",
                vf,
                "-metadata:s:v:0",
                "rotate=0",

                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                crf,
                "-profile:v",
                "high",
                "-level",
                "4.1",
                "-pix_fmt",
                "yuv420p",

                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ac",
                "2",

                "-f",
                "hls",
                "-hls_time",
                "4",
                "-hls_flags",
                "independent_segments",
                "-hls_playlist_type",
                "vod",
                "-hls_segment_filename",
                os.path.join(subdir, "seg_%03d.ts"),
                playlist,
            ]

            proc = subprocess.Popen(
                ["ffmpeg", "-progress", "pipe:2", "-nostats"] + cmd[1:],
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            eta = _EtaEstimator(total_ms)
            last_push = 0.0

            try:
                for line in proc.stderr:
                    if not line:
                        continue

                    out_ms = _parse_out_time_ms(line.strip())

                    now_ts = time.time()
                    if job and (now_ts - last_push >= 1.5):
                        last_push = now_ts
                        touch_job(
                            job,
                            stage=key,
                            stage_index=idx,
                            stage_count=stage_count,
                            stage_weight=weight,
                            stage_completed_weight=completed_weight,
                            message=f"Encoding {key}…",
                        )

                    if out_ms is not None and total_ms:
                        frac = min(1.0, max(0.0, out_ms / float(total_ms)))
                        eta_s = eta.update(out_ms)

                        if job:
                            touch_job(
                                job,
                                stage_progress=frac,
                                eta_seconds=eta_s,
                            )

                rc = proc.wait()
                if rc != 0:
                    raise RuntimeError(f"ffmpeg failed for {key} (exit code {rc})")

            finally:
                if proc.poll() is None:
                    proc.kill()

            completed_weight += weight

            real_w, real_h = _probe_video_size(
                os.path.join(subdir, "seg_000.ts")
            )

            variants.append({
                "key": key,
                "bandwidth": r["bitrate"],
                "path": f"{key}/playlist.m3u8",
                "width": real_w,
                "height": real_h,
            })

        # -------------------------------------------------
        # Build master playlist
        # -------------------------------------------------
        master = os.path.join(output_dir, "master.m3u8")

        with open(master, "w") as f:
            f.write("#EXTM3U\n#EXT-X-VERSION:3\n")
            for v in variants:
                f.write(
                    f"#EXT-X-STREAM-INF:BANDWIDTH={v['bandwidth']},"
                    f"RESOLUTION={v['width']}x{v['height']}\n"
                )
                f.write(f"{v['path']}\n")

        finalize_index = stage_count - 1

        if job:
            touch_job(
                job,
                stage="finalize",
                stage_index=finalize_index,
                stage_count=stage_count,
                stage_weight=STAGE_WEIGHTS["finalize"],
                stage_completed_weight=completed_weight,
                stage_progress=0.0,
                message="Publishing media…",
            )

        # -------------------------------------------------
        # Upload generated HLS files to storage
        # -------------------------------------------------
        upload_files = []

        for root, _, files in os.walk(output_dir):
            for name in files:
                full = os.path.join(root, name)
                relp = os.path.join(
                    relative_dir,
                    os.path.relpath(full, output_dir),
                )
                upload_files.append((full, relp, name))

        total_files = max(1, len(upload_files))
        master_storage_path = None

        for index, (full, relp, name) in enumerate(upload_files, start=1):
            with open(full, "rb") as fh:
                default_storage.save(relp, File(fh))

            if name == "master.m3u8":
                master_storage_path = relp

            if job:
                # Keep final stage below 100 until task marks DONE.
                raw_frac = index / float(total_files)
                safe_frac = min(0.90, raw_frac * 0.90)

                touch_job(
                    job,
                    stage="finalize",
                    stage_index=finalize_index,
                    stage_count=stage_count,
                    stage_weight=STAGE_WEIGHTS["finalize"],
                    stage_completed_weight=completed_weight,
                    stage_progress=safe_frac,
                    message="Publishing media…",
                )

        if not master_storage_path:
            raise RuntimeError("master.m3u8 missing")

        if job:
            # Do not force 100 here. DONE status will make UI show 100.
            touch_job(
                job,
                stage="finalize",
                stage_index=finalize_index,
                stage_count=stage_count,
                stage_weight=STAGE_WEIGHTS["finalize"],
                stage_completed_weight=completed_weight,
                stage_progress=0.95,
                message="Final checks…",
            )

        logger.info(
            "✅ HLS conversion completed policy=%s max_height=%s output=%s",
            policy.mode,
            policy.max_height,
            master_storage_path,
        )

        return VideoConversionResult(
            master_path=master_storage_path,
            width=main_w,
            height=main_h,
            aspect_ratio=(main_w / main_h) if main_w and main_h else None,
            duration_ms=total_ms,
            variants=variants,
            preview=preview_payload,
        )

    finally:
        if temp_input and os.path.exists(temp_input):
            os.remove(temp_input)

        if output_dir and os.path.exists(output_dir):
            import shutil
            shutil.rmtree(output_dir)