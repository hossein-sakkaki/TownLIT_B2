# /utils/common/video_utils.py
import os
import json
import subprocess
import logging
import time
from tempfile import NamedTemporaryFile

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage

from utils.common.utils import FileUpload, get_hls_output_dir
from apps.media_conversion.services.progress import touch_job

logger = logging.getLogger(__name__)


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
        "stream=width,height,pix_fmt,sample_aspect_ratio,display_aspect_ratio:"
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

    logger.debug("ffprobe raw output for %s: %r", path, out)

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
) -> str:
    """
    Multi-bitrate HLS conversion with TRUE weighted virtual timeline
    + Correct handling for vertical videos (rotation metadata).
    """

    VIDEO_BASE_WEIGHTS = {
        "source": 40,
        "1080p": 30,
        "720p": 20,
        "480p": 10,
    }
    FINALIZE_WEIGHT = 5

    temp_input = None
    output_dir = None

    try:
        # -------------------------------------------------
        # Load source to local temp
        # -------------------------------------------------
        rel = source_path if not os.path.isabs(source_path) else os.path.relpath(
            source_path, settings.MEDIA_ROOT
        )

        with default_storage.open(rel, "rb") as f:
            with NamedTemporaryFile(delete=False, suffix=os.path.splitext(rel)[1]) as tmp:
                tmp.write(f.read())
                tmp.flush()
                temp_input = tmp.name

        # -------------------------------------------------
        # Probe source (including rotation)
        # -------------------------------------------------
        meta = _probe_json(temp_input)
        s0 = (meta.get("streams") or [{}])[0]
        s = s0

        coded_w = _even(int(s.get("width") or 0))
        coded_h = _even(int(s.get("height") or 0))

        try:
            print('----------------------------------------------------------- start logger')
            ssd = s0.get("side_data_list") or []
            tags_rotate = (s0.get("tags") or {}).get("rotate")

            side_rotations = []
            for item in ssd:
                if isinstance(item, dict) and "rotation" in item:
                    side_rotations.append(item.get("rotation"))

            rot_meta, rot_src = _extract_rotation_with_source(meta)

            logger.warning("ROT DEBUG | coded=%sx%s", coded_w, coded_h)
            logger.warning("ROT DEBUG | tags.rotate=%s", tags_rotate)
            logger.warning("ROT DEBUG | side_data_list.len=%s rotations=%s", len(ssd), side_rotations)
            logger.warning("ROT DEBUG | rot_meta=%s rot_src=%s", rot_meta, rot_src)

            disp_w, disp_h = _decide_display_size(meta, coded_w, coded_h)
            logger.warning(
                "ROT DEBUG | DECISION display=%sx%s",
                disp_w,
                disp_h,
            )
            print('----------------------------------------------------------- end logger')

        except Exception:
            logger.exception("ROT DEBUG BLOCK FAILED")



        if not coded_w or not coded_h:
            raise RuntimeError("Invalid source dimensions")

        disp_w, disp_h = _decide_display_size(
            meta,
            coded_w,
            coded_h,
        )

        rot_meta, rot_src = _extract_rotation_with_source(meta)
        total_ms = _probe_duration_ms(temp_input)

        # -------------------------------------------------
        # Rendition plan (SOURCE-FIRST, orientation-safe)
        # -------------------------------------------------
        renditions = []

        # 1️⃣ SOURCE — exact display size (CRITICAL FIX)
        renditions.append({
            "key": "source",
            "width": disp_w,
            "height": disp_h,
            "bitrate": "5000000",
        })

        # 2️⃣ OPTIONAL DOWNSCALES (only if source is larger)
        for h in (1080, 720, 480):
            if disp_h > h:
                renditions.append({
                    "key": f"{h}p",
                    "height": h,
                    "width": _compute_width(disp_w, disp_h, h),
                    "bitrate": "3000000" if h >= 720 else "1000000",
                })


        # -------------------------------------------------
        # Normalize weights so total stays == 100
        # - Keep finalize fixed at 5
        # - Redistribute remaining 95 across present renditions proportionally
        # -------------------------------------------------
        present_keys = [r["key"] for r in renditions]
        base_sum = sum(VIDEO_BASE_WEIGHTS.get(k, 0) for k in present_keys) or 1
        target_sum = 100 - FINALIZE_WEIGHT  # 95

        def _stage_weight(key: str) -> int:
            w = VIDEO_BASE_WEIGHTS.get(key, 0)
            return int(round((w / float(base_sum)) * target_sum))

        # Fix rounding drift (ensure exact sum=95)
        weights = {k: _stage_weight(k) for k in present_keys}
        drift = target_sum - sum(weights.values())
        if drift != 0 and present_keys:
            weights[present_keys[0]] = max(0, weights[present_keys[0]] + drift)

        STAGE_WEIGHTS = {**weights, "finalize": FINALIZE_WEIGHT}

        # -------------------------------------------------
        # Build stage_plan (AUTHORITATIVE)
        # -------------------------------------------------
        stage_plan = [{"key": r["key"], "weight": STAGE_WEIGHTS[r["key"]]} for r in renditions]
        stage_plan.append({"key": "finalize", "weight": STAGE_WEIGHTS["finalize"]})
        total_weight = sum(x["weight"] for x in stage_plan) or 100

        if job:
            touch_job(
                job,
                stage_plan=stage_plan,
                stage_total_weight=total_weight,
                stage_completed_weight=0,
                message="Preparing renditions…",
            )

        # -------------------------------------------------
        # Output dirs
        # -------------------------------------------------
        output_dir, relative_dir = get_hls_output_dir(instance, fileupload)
        os.makedirs(output_dir, exist_ok=True)

        variants = []
        completed_weight = 0


        # -------------------------------------------------
        # Encode each rendition
        # -------------------------------------------------
        for idx, r in enumerate(renditions):
            key = r["key"]
            weight = STAGE_WEIGHTS[key]

            if job:
                touch_job(
                    job,
                    stage=key,
                    stage_index=idx,
                    stage_count=len(stage_plan),
                    stage_weight=weight,
                    stage_completed_weight=completed_weight,
                    stage_progress=0.0,
                    message=f"Encoding {key}…",
                )

            subdir = os.path.join(output_dir, key)
            os.makedirs(subdir, exist_ok=True)

            playlist = os.path.join(subdir, "playlist.m3u8")

            # Build a safe vf chain:
            # - apply rotation (if needed)
            # - scale to target W/H
            # - square pixels + yuv420p for broad device support

            vf = ",".join([
                f"scale={r['width']}:{r['height']}",
                "setsar=1",
                "format=yuv420p",
            ])

            cmd = [
                "ffmpeg", "-y",
                "-hide_banner",
                "-i", temp_input,
                "-vf", vf,
                "-metadata:s:v:0", "rotate=0",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-ac", "2",
                "-f", "hls",
                "-hls_time", "4",
                "-hls_flags", "independent_segments",
                "-hls_playlist_type", "vod",
                "-hls_segment_filename", os.path.join(subdir, "seg_%03d.ts"),
                playlist,
            ]

            # progress output on stderr via -progress pipe:2
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

                    # Keep heartbeat alive (throttled)
                    now_ts = time.time()
                    if job and (now_ts - last_push >= 1.5):
                        last_push = now_ts
                        touch_job(
                            job,
                            stage=key,
                            stage_index=idx,
                            stage_count=len(stage_plan),
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

            # 🔍 probe REAL encoded size (critical for Safari)
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
        # Finalize (5%)
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

        if job:
            touch_job(
                job,
                stage="finalize",
                stage_weight=STAGE_WEIGHTS["finalize"],
                stage_completed_weight=completed_weight,
                stage_progress=1.0,
                message="Finalizing…",
            )

        # -------------------------------------------------
        # Upload to storage
        # -------------------------------------------------
        master_storage_path = None
        for root, _, files in os.walk(output_dir):
            for name in files:
                full = os.path.join(root, name)
                relp = os.path.join(relative_dir, os.path.relpath(full, output_dir))
                with open(full, "rb") as fh:
                    default_storage.save(relp, File(fh))
                if name == "master.m3u8":
                    master_storage_path = relp

        if not master_storage_path:
            raise RuntimeError("master.m3u8 missing")

        return master_storage_path

    finally:
        if temp_input and os.path.exists(temp_input):
            os.remove(temp_input)
        if output_dir and os.path.exists(output_dir):
            import shutil
            shutil.rmtree(output_dir)
