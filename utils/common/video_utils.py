# /utils/common/video_utils.py

import os
import json
import subprocess
from django.conf import settings
from django.core.files import File
from utils.common.utils import FileUpload, get_hls_output_dir
import logging
from django.core.files.storage import default_storage
from tempfile import NamedTemporaryFile

logger = logging.getLogger(__name__)

def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

def _probe_json(path: str) -> dict:
    # ffprobe JSON (local file path)
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,sample_aspect_ratio,display_aspect_ratio,pix_fmt",
        "-show_entries", "stream_tags=rotate",
        "-of", "json", path
    ]
    out = _run(cmd).stdout.decode("utf-8", "ignore")
    return json.loads(out)

def _even(n: int) -> int:
    return n if n % 2 == 0 else n - 1  # keep even

def _compute_width_for_height(src_w: int, src_h: int, target_h: int) -> int:
    # preserve AR, even width
    w = int(round(src_w * (target_h / float(src_h))))
    return max(2, _even(w))

def convert_video_to_multi_hls(source_path: str, instance, fileupload: FileUpload) -> str:
    temp_input_path = None
    output_dir = None
    master_playlist_storage_path = None

    try:
        # make source local temp file
        if os.path.isabs(source_path):
            rel = os.path.relpath(source_path, settings.MEDIA_ROOT)
        else:
            rel = source_path

        with default_storage.open(rel, 'rb') as source_file:
            with NamedTemporaryFile(delete=False, suffix=os.path.splitext(rel)[1]) as temp_input:
                temp_input.write(source_file.read())
                temp_input.flush()
                temp_input_path = temp_input.name

        # probe original dimensions
        meta = _probe_json(temp_input_path)
        s = (meta.get("streams") or [{}])[0]
        src_w = int(s.get("width") or 0)
        src_h = int(s.get("height") or 0)
        if not src_w or not src_h:
            raise RuntimeError("Cannot probe video width/height")

        # normalize even dims (H.264 requires even)
        src_w_even = _even(src_w)
        src_h_even = _even(src_h)

        # NOTE: if you need to honor rotation tag:
        # rot = int(((s.get("tags") or {}).get("rotate") or 0))
        # Then prepend transpose filter accordingly (90→transpose=1, 270→transpose=2, 180→transpose=1,transpose=1)

        output_dir, relative_dir = get_hls_output_dir(instance, fileupload)
        os.makedirs(output_dir, exist_ok=True)

        master_playlist_local_path = os.path.join(output_dir, "master.m3u8")
        variant_playlists: list[dict] = []

        # --- Rendition plan ---
        # 1) "source" = exact original size (no stretching)
        # 2) Optional ladder (720p/480p) with AR preserved (no pad, no stretch)
        ladder_heights = [720, 480]  # optional; remove if you want only original

        # Build list with dynamic sizes
        renditions = []

        # Source (original)
        renditions.append({
            "label": "source",
            "target_h": src_h_even,
            "target_w": src_w_even,
            "bitrate": "5000000"  # tune or compute by pixels if needed
        })

        # Additional downsized variants (only if original is larger)
        for h in ladder_heights:
            if src_h_even > h:
                renditions.append({
                    "label": f"{h}p",
                    "target_h": h,
                    "target_w": _compute_width_for_height(src_w_even, src_h_even, h),
                    "bitrate": "3000000" if h >= 720 else "1000000",
                })

        # Encode each rendition with AR preserved and SAR=1
        for r in renditions:
            label = r["label"]
            tw = r["target_w"]
            th = r["target_h"]
            br = r["bitrate"]

            subdir = os.path.join(output_dir, label)
            os.makedirs(subdir, exist_ok=True)
            playlist_path = os.path.join(subdir, "playlist.m3u8")

            # Build scale string:
            # - For "source": use exact even dims (no AR change).
            # - For downscales: also exact computed dims (no stretch).
            scale_str = f"scale={tw}:{th}"

            # Base video filter:
            # - setsar=1: normalize pixel aspect
            # - format=yuv420p: wide compatibility
            vfilter = f"{scale_str},setsar=1,format=yuv420p"

            cmd = [
                "ffmpeg", "-y",
                "-noautorotate",                  # ignore rotate metadata (we output final pixels)
                "-i", temp_input_path,
                "-vf", vfilter,                   # keep exact size / AR preserved
                "-metadata:s:v:0", "rotate=0",    # clear rotate tag
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-r", "30",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-ac", "2",
                "-f", "hls",
                "-hls_time", "4",
                "-hls_flags", "independent_segments",
                "-hls_playlist_type", "vod",
                "-hls_segment_filename", os.path.join(subdir, "segment_%03d.ts"),
                playlist_path
            ]

            # run ffmpeg
            proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if proc.returncode != 0:
                logger.warning("FFmpeg error (%s): %s", label, proc.stderr.decode(errors="ignore"))
                proc.check_returncode()

            # Probe one segment to get actual w×h to write accurate RESOLUTION
            # (first segment name is predictable: segment_000.ts)
            seg0 = os.path.join(subdir, "segment_000.ts")
            try:
                seg_meta = _probe_json(seg0)
                ss = (seg_meta.get("streams") or [{}])[0]
                aw = int(ss.get("width") or tw)
                ah = int(ss.get("height") or th)
            except Exception:
                aw, ah = tw, th  # fallback

            variant_playlists.append({
                "label": label,
                "width": aw,
                "height": ah,
                "bandwidth": br,
                "path": os.path.join(label, "playlist.m3u8"),
            })

        # Write master.m3u8 with accurate RESOLUTION
        with open(master_playlist_local_path, "w") as master:
            master.write("#EXTM3U\n#EXT-X-VERSION:3\n")
            for v in variant_playlists:
                master.write(f"#EXT-X-STREAM-INF:BANDWIDTH={v['bandwidth']},RESOLUTION={v['width']}x{v['height']}\n")
                master.write(f"{v['path']}\n")

        # Upload all files to storage
        for root, _, files in os.walk(output_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.join(relative_dir, os.path.relpath(full_path, output_dir))
                with open(full_path, 'rb') as f:
                    default_storage.save(rel_path, File(f))
                if os.path.basename(full_path) == "master.m3u8":
                    master_playlist_storage_path = rel_path

        if not master_playlist_storage_path:
            raise FileNotFoundError("master.m3u8 was not uploaded correctly.")

        return master_playlist_storage_path

    except subprocess.CalledProcessError as e:
        logger.warning(f"⚠️ FFmpeg HLS conversion failed: {e.stderr.decode(errors='ignore').strip()}")
        raise
    finally:
        if temp_input_path and os.path.exists(temp_input_path):
            os.remove(temp_input_path)
        if output_dir and os.path.exists(output_dir):
            import shutil
            shutil.rmtree(output_dir)
