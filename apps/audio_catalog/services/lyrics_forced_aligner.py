# apps/audio_catalog/services/lyrics_forced_aligner.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-16.

from __future__ import annotations

import importlib
import math
import os
import subprocess
import tempfile
import threading
import unicodedata
import wave
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from apps.audio_catalog.services.lyrics_alignment import (
    ForcedWordTiming,
    LyricsAlignmentBlock,
)


SAMPLE_RATE = 16_000

DEFAULT_ALIGNMENT_MODEL = "facebook/wav2vec2-base-960h"

VERIFIED_MODEL_LICENSES = {
    "facebook/wav2vec2-base-960h": "apache-2.0",
}

MIN_WORD_DURATION_MS = 20
FINAL_WORD_TAIL_MS = 80


class LyricsForcedAlignerError(RuntimeError):
    pass


class LyricsForcedAlignerDependencyError(LyricsForcedAlignerError):
    pass


@dataclass(frozen=True, slots=True)
class _WordTokenEvidence:
    global_index: int
    text: str
    token_ids: tuple[int, ...]
    token_times_seconds: tuple[float, ...]
    token_confidences: tuple[float, ...]
    blank_after_seconds: float | None


_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}
_MODEL_LOCK = threading.Lock()


def force_align_block(
    *,
    audio_path: str,
    block: LyricsAlignmentBlock,
    model_name: str | None = None,
) -> list[ForcedWordTiming]:
    """
    Force-align one bounded canonical lyrics block.

    CTC token timings are authoritative for word timing.
    Utterance boundaries from determine_utterance_segments()
    are intentionally not used for word timing.
    """

    if not os.path.isfile(audio_path):
        raise LyricsForcedAlignerError(
            "Alignment source audio does not exist."
        )

    if not block.words:
        raise LyricsForcedAlignerError(
            "Alignment block contains no words."
        )

    selected_model = model_name or _configured_model()
    _assert_verified_model(selected_model)

    (
        numpy,
        torch,
        ctc_segmentation,
        auto_model_class,
        auto_processor_class,
    ) = _load_dependencies()

    model, processor = _model_bundle(
        model_name=selected_model,
        torch=torch,
        auto_model_class=auto_model_class,
        auto_processor_class=auto_processor_class,
    )

    wav_path = _render_alignment_window(
        source_path=audio_path,
        start_ms=block.start_ms,
        end_ms=block.end_ms,
    )

    try:
        waveform = _read_pcm16_wav(
            wav_path=wav_path,
            numpy=numpy,
        )

        if waveform.size == 0:
            raise LyricsForcedAlignerError(
                "Alignment audio window is empty."
            )

        log_posteriors = _model_log_posteriors(
            waveform=waveform,
            model=model,
            processor=processor,
            torch=torch,
        )

        if log_posteriors.ndim != 2 or log_posteriors.shape[0] <= 0:
            raise LyricsForcedAlignerError(
                "Alignment model returned invalid log posteriors."
            )

        tokenizer = processor.tokenizer

        token_lists = [
            _tokenize_word(
                word.text,
                tokenizer=tokenizer,
                numpy=numpy,
            )
            for word in block.words
        ]

        config = _segmentation_config(
            tokenizer=tokenizer,
            log_posteriors=log_posteriors,
            waveform_sample_count=waveform.shape[0],
            ctc_segmentation=ctc_segmentation,
        )

        ground_truth, utterance_begin_indices = (
            ctc_segmentation.prepare_token_list(
                config,
                token_lists,
            )
        )

        timings, _, _ = ctc_segmentation.ctc_segmentation(
            config,
            log_posteriors,
            ground_truth,
        )

        evidence = _extract_word_evidence(
            block=block,
            token_lists=token_lists,
            utterance_begin_indices=utterance_begin_indices,
            timings=timings,
            log_posteriors=log_posteriors,
            index_duration_seconds=config.index_duration_in_seconds,
        )

        return _build_word_timings(
            block=block,
            evidence=evidence,
            model_name=selected_model,
        )

    finally:
        try:
            os.unlink(wav_path)
        except FileNotFoundError:
            pass


def _extract_word_evidence(
    *,
    block: LyricsAlignmentBlock,
    token_lists,
    utterance_begin_indices,
    timings,
    log_posteriors,
    index_duration_seconds: float,
) -> list[_WordTokenEvidence]:
    if len(utterance_begin_indices) != len(block.words) + 1:
        raise LyricsForcedAlignerError(
            "CTC utterance boundary count is invalid."
        )

    if index_duration_seconds <= 0:
        raise LyricsForcedAlignerError(
            "CTC alignment index duration is invalid."
        )

    result: list[_WordTokenEvidence] = []

    for word_index, (word, token_ids_array) in enumerate(
        zip(block.words, token_lists)
    ):
        token_ids = tuple(int(value) for value in token_ids_array)

        if not token_ids:
            raise LyricsForcedAlignerError(
                f"Canonical word produced no alignment tokens: {word.text!r}."
            )

        boundary_index = int(utterance_begin_indices[word_index])
        next_boundary_index = int(utterance_begin_indices[word_index + 1])

        first_token_position = boundary_index + 1
        last_token_position = first_token_position + len(token_ids) - 1

        if last_token_position >= next_boundary_index:
            raise LyricsForcedAlignerError(
                f"CTC ground-truth token boundary is invalid for {word.text!r}."
            )

        token_times: list[float] = []
        token_confidences: list[float] = []

        for offset, token_id in enumerate(token_ids):
            ground_truth_position = first_token_position + offset

            try:
                token_time = float(timings[ground_truth_position])
            except (IndexError, TypeError, ValueError) as exc:
                raise LyricsForcedAlignerError(
                    f"CTC token timing is missing for {word.text!r}."
                ) from exc

            if not math.isfinite(token_time):
                raise LyricsForcedAlignerError(
                    f"CTC token timing is non-finite for {word.text!r}."
                )

            frame_index = int(
                round(token_time / index_duration_seconds)
            )

            frame_index = max(
                0,
                min(
                    log_posteriors.shape[0] - 1,
                    frame_index,
                ),
            )

            if token_id < 0 or token_id >= log_posteriors.shape[1]:
                raise LyricsForcedAlignerError(
                    "CTC token ID is outside the model vocabulary."
                )

            log_posterior = float(
                log_posteriors[frame_index, token_id]
            )

            token_times.append(token_time)
            token_confidences.append(
                _posterior_probability(log_posterior)
            )

        blank_after_seconds: float | None = None

        try:
            blank_value = float(timings[next_boundary_index])

            if math.isfinite(blank_value):
                blank_after_seconds = blank_value
        except (IndexError, TypeError, ValueError):
            blank_after_seconds = None

        result.append(
            _WordTokenEvidence(
                global_index=word.global_index,
                text=word.text,
                token_ids=token_ids,
                token_times_seconds=tuple(token_times),
                token_confidences=tuple(token_confidences),
                blank_after_seconds=blank_after_seconds,
            )
        )

    return result


def _build_word_timings(
    *,
    block: LyricsAlignmentBlock,
    evidence: list[_WordTokenEvidence],
    model_name: str,
) -> list[ForcedWordTiming]:
    if len(evidence) != len(block.words):
        raise LyricsForcedAlignerError(
            "CTC evidence word count mismatch."
        )

    frame_half_ms = 10
    raw_starts: list[int] = []

    for item in evidence:
        first_token_seconds = item.token_times_seconds[0]

        start_ms = (
            block.start_ms
            + int(round(first_token_seconds * 1000))
            - frame_half_ms
        )

        raw_starts.append(
            max(
                block.start_ms,
                min(block.end_ms, start_ms),
            )
        )

    results: list[ForcedWordTiming] = []
    previous_end = block.start_ms

    for index, item in enumerate(evidence):
        start_ms = max(
            raw_starts[index],
            previous_end,
        )

        last_token_ms = (
            block.start_ms
            + int(
                round(
                    item.token_times_seconds[-1] * 1000
                )
            )
        )

        blank_after_ms: int | None = None

        if item.blank_after_seconds is not None:
            blank_after_ms = (
                block.start_ms
                + int(
                    round(
                        item.blank_after_seconds * 1000
                    )
                )
            )

        if index + 1 < len(evidence):
            next_start_ms = raw_starts[index + 1]
        else:
            next_start_ms = block.end_ms

        candidate_end = max(
            last_token_ms + FINAL_WORD_TAIL_MS,
            start_ms + MIN_WORD_DURATION_MS,
        )

        if blank_after_ms is not None and blank_after_ms > start_ms:
            candidate_end = max(
                candidate_end,
                blank_after_ms,
            )

        end_ms = min(
            block.end_ms,
            next_start_ms,
            candidate_end,
        )

        if end_ms <= start_ms:
            end_ms = min(
                block.end_ms,
                start_ms + MIN_WORD_DURATION_MS,
            )

        if end_ms <= start_ms:
            raise LyricsForcedAlignerError(
                f"Could not produce a positive word duration for {item.text!r}."
            )

        confidence = (
            sum(item.token_confidences)
            / len(item.token_confidences)
        )

        results.append(
            ForcedWordTiming(
                global_index=item.global_index,
                text=item.text,
                start_ms=start_ms,
                end_ms=end_ms,
                confidence=max(
                    0.0,
                    min(1.0, confidence),
                ),
                provider_metadata={
                    "provider": "ctc_segmentation",
                    "timing_source": "aligned_tokens",
                    "confidence_source": "mean_token_posterior",
                    "model": model_name,
                    "model_license": VERIFIED_MODEL_LICENSES[
                        model_name
                    ],
                    "block_index": block.index,
                    "token_count": len(item.token_ids),
                    "token_confidence_min": min(
                        item.token_confidences
                    ),
                    "token_confidence_max": max(
                        item.token_confidences
                    ),
                },
            )
        )

        previous_end = end_ms

    return results


def _posterior_probability(
    log_posterior: float,
) -> float:
    """
    Convert one CTC log posterior to a bounded probability.
    """

    if not math.isfinite(log_posterior):
        return 0.0

    bounded = min(
        0.0,
        log_posterior,
    )

    probability = math.exp(bounded)

    return max(
        0.0,
        min(
            1.0,
            probability,
        ),
    )


def _load_dependencies():
    """
    Load ML dependencies only inside the dedicated lyrics alignment worker.

    Backend, subtitle, video, and general Celery workers must not require
    these packages merely because they share the TownLIT source tree.
    """

    try:
        numpy = importlib.import_module("numpy")
        torch = importlib.import_module("torch")
        ctc_segmentation = importlib.import_module("ctc_segmentation")
        transformers = importlib.import_module("transformers")
    except ModuleNotFoundError as exc:
        raise LyricsForcedAlignerDependencyError(
            "Lyrics alignment ML dependencies are not installed in this process."
        ) from exc

    try:
        auto_model_class = transformers.AutoModelForCTC
        auto_processor_class = transformers.AutoProcessor
    except AttributeError as exc:
        raise LyricsForcedAlignerDependencyError(
            "Installed Transformers package does not expose the required CTC classes."
        ) from exc

    return (
        numpy,
        torch,
        ctc_segmentation,
        auto_model_class,
        auto_processor_class,
    )

def _configured_model() -> str:
    configured = str(
        getattr(
            settings,
            "LYRICS_ALIGNMENT_MODEL",
            "",
        )
        or os.environ.get(
            "LYRICS_ALIGNMENT_MODEL",
            "",
        )
        or DEFAULT_ALIGNMENT_MODEL
    ).strip()

    return configured or DEFAULT_ALIGNMENT_MODEL


def _assert_verified_model(
    model_name: str,
) -> None:
    if model_name not in VERIFIED_MODEL_LICENSES:
        raise LyricsForcedAlignerError(
            "Lyrics alignment model has not been approved "
            f"for TownLIT licensing: {model_name}."
        )


def _model_bundle(
    *,
    model_name: str,
    torch,
    auto_model_class,
    auto_processor_class,
):
    cached = _MODEL_CACHE.get(model_name)

    if cached is not None:
        return cached

    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get(model_name)

        if cached is not None:
            return cached

        cpu_threads = int(
            os.environ.get(
                "LYRICS_ALIGNMENT_CPU_THREADS",
                "2",
            )
            or "2"
        )

        torch.set_num_threads(
            max(
                1,
                cpu_threads,
            )
        )

        processor = auto_processor_class.from_pretrained(
            model_name
        )

        model = (
            auto_model_class
            .from_pretrained(model_name)
            .to("cpu")
            .eval()
        )

        _MODEL_CACHE[model_name] = (
            model,
            processor,
        )

        return model, processor


def _render_alignment_window(
    *,
    source_path: str,
    start_ms: int,
    end_ms: int,
) -> str:
    if end_ms <= start_ms:
        raise LyricsForcedAlignerError(
            "Alignment audio window is invalid."
        )

    handle = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".wav",
    )

    output_path = handle.name
    handle.close()

    duration_seconds = (
        end_ms - start_ms
    ) / 1000.0

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        source_path,
        "-ss",
        f"{start_ms / 1000.0:.3f}",
        "-t",
        f"{duration_seconds:.3f}",
        "-vn",
        "-map",
        "0:a:0",
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        "-c:a",
        "pcm_s16le",
        "-y",
        output_path,
    ]

    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (
        OSError,
        subprocess.CalledProcessError,
    ) as exc:
        try:
            os.unlink(output_path)
        except FileNotFoundError:
            pass

        stderr = getattr(
            exc,
            "stderr",
            "",
        )

        raise LyricsForcedAlignerError(
            "Could not render lyrics alignment audio. "
            f"{str(stderr or exc)[:500]}"
        ) from exc

    return output_path


def _read_pcm16_wav(
    *,
    wav_path: str,
    numpy,
):
    try:
        with wave.open(
            wav_path,
            "rb",
        ) as audio:
            if audio.getnchannels() != 1:
                raise LyricsForcedAlignerError(
                    "Alignment WAV must be mono."
                )

            if audio.getframerate() != SAMPLE_RATE:
                raise LyricsForcedAlignerError(
                    f"Alignment WAV must use {SAMPLE_RATE} Hz."
                )

            if audio.getsampwidth() != 2:
                raise LyricsForcedAlignerError(
                    "Alignment WAV must be PCM16."
                )

            payload = audio.readframes(
                audio.getnframes()
            )

    except wave.Error as exc:
        raise LyricsForcedAlignerError(
            "Could not read alignment WAV."
        ) from exc

    return (
        numpy.frombuffer(
            payload,
            dtype=numpy.int16,
        )
        .astype(numpy.float32)
        / 32768.0
    )


def _model_log_posteriors(
    *,
    waveform,
    model,
    processor,
    torch,
):
    """
    Return CTC log posterior probabilities.

    ctc-segmentation accumulates log posterior scores in its
    dynamic-programming trellis. Positive softmax probabilities
    must not be passed directly to the segmentation algorithm.
    """

    inputs = processor(
        waveform,
        sampling_rate=SAMPLE_RATE,
        return_tensors="pt",
        padding=False,
    )

    input_values = inputs.input_values.to(
        "cpu"
    )

    with torch.inference_mode():
        logits = model(
            input_values
        ).logits[0]

        log_posteriors = (
            torch.nn.functional
            .log_softmax(
                logits,
                dim=-1,
            )
            .cpu()
            .numpy()
        )

    return log_posteriors


def _tokenize_word(
    word: str,
    *,
    tokenizer,
    numpy,
):
    normalized = _normalize_model_word(
        word
    )

    if not normalized:
        raise LyricsForcedAlignerError(
            "Canonical lyrics word cannot be normalized "
            f"for alignment: {word!r}."
        )

    candidates: list[str] = []

    for candidate in (
        normalized.upper(),
        normalized.lower(),
        normalized,
    ):
        if candidate not in candidates:
            candidates.append(candidate)

    unknown_id = tokenizer.unk_token_id

    for candidate in candidates:
        encoded = tokenizer(
            candidate,
            add_special_tokens=False,
        )

        ids = list(
            encoded["input_ids"]
        )

        if not ids:
            continue

        if (
            unknown_id is not None
            and unknown_id in ids
        ):
            continue

        return numpy.asarray(
            ids,
            dtype=numpy.int64,
        )

    raise LyricsForcedAlignerError(
        "Alignment model cannot represent "
        f"canonical word {word!r}."
    )


def _segmentation_config(
    *,
    tokenizer,
    log_posteriors,
    waveform_sample_count: int,
    ctc_segmentation,
):
    vocabulary = tokenizer.get_vocab()

    if not vocabulary:
        raise LyricsForcedAlignerError(
            "Alignment tokenizer has no vocabulary."
        )

    max_id = max(
        vocabulary.values()
    )

    char_list = [
        ""
        for _ in range(max_id + 1)
    ]

    for token, token_id in vocabulary.items():
        if (
            token_id < 0
            or token_id >= len(char_list)
        ):
            raise LyricsForcedAlignerError(
                "Alignment tokenizer contains an invalid token ID."
            )

        char_list[token_id] = token

    blank_id = tokenizer.pad_token_id

    if blank_id is None:
        blank_id = 0

    config = ctc_segmentation.CtcSegmentationParameters(
        char_list=char_list
    )

    config.blank = int(blank_id)

    config.index_duration = (
        waveform_sample_count
        / log_posteriors.shape[0]
        / SAMPLE_RATE
    )

    # Singing may contain long pauses between canonical phrases.
    config.blank_transition_cost_zero = True

    # Instrumental audio before the first sung word is valid.
    config.preamble_transition_cost_zero = True

    return config


def _normalize_model_word(
    value: str,
) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )

    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )

    normalized = (
        normalized
        .replace("’", "'")
        .replace("‘", "'")
    )

    return "".join(
        character
        for character in normalized
        if character.isalnum()
        or character == "'"
    )