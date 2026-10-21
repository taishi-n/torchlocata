"""LOCATA single-source MUSIC based on MUSIC.m/stft.m; see NOTICE and analysis.md."""

import math
from dataclasses import dataclass
from time import perf_counter

import torch
import torch.nn.functional as functional
from torch import Tensor

from .analysis_types import DOATrack, MusicResult, STFTResult
from .annotations import _clock, _pose_indices
from .geometry import world_to_array
from .types import LocataSample


@dataclass(frozen=True)
class MusicConfig:
    """Explicit reference-baseline parameters; angles in degrees, channels zero-based.

    Defaults match `MUSIC.m`: 30 ms, quarter hop, FFT 1024, 100-frame blocks,
    step 10, strict 800–1400 Hz, c=340 m/s. No source GT is used. See the
    analysis guide for FFT truncation, clock support, and interpolation changes.
    """

    frame_duration_seconds: float = 0.03
    frame_samples: int | None = None
    hop_samples: int | None = None
    fft_size: int = 1024
    frames_per_block: int = 100
    block_step: int = 10
    min_frequency: float = 800
    max_frequency: float = 1400
    sound_speed: float = 340
    channels: tuple[int, ...] | None = None
    azimuth_degrees: tuple[float, ...] = tuple(float(x) for x in range(-180, 181, 5))
    inclination_degrees: tuple[float, ...] = tuple(float(x) for x in range(0, 181, 10))

    def __post_init__(self) -> None:
        for name in (
            "fft_size",
            "frames_per_block",
            "block_step",
            "frame_samples",
            "hop_samples",
        ):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
            ):
                raise ValueError(f"{name} must be a positive integer")
        if (
            not math.isfinite(self.frame_duration_seconds)
            or self.frame_duration_seconds <= 0
        ):
            raise ValueError("frame_duration_seconds must be positive and finite")
        if not 0 <= self.min_frequency < self.max_frequency or not math.isfinite(
            self.max_frequency
        ):
            raise ValueError(
                "frequency limits must be finite, ordered, and nonnegative"
            )
        if not math.isfinite(self.sound_speed) or self.sound_speed <= 0:
            raise ValueError("sound_speed must be positive and finite")
        for grid, lower, upper in (
            (self.azimuth_degrees, -180, 180),
            (self.inclination_degrees, 0, 180),
        ):
            if not grid or any(
                not math.isfinite(v) or not lower <= v <= upper for v in grid
            ):
                raise ValueError("angle grids must be nonempty finite degrees in range")
            if any(b <= a for a, b in zip(grid, grid[1:], strict=False)):
                raise ValueError("angle grids must be strictly increasing")


def music_stft(
    waveform: Tensor,
    sample_rate: int,
    *,
    frame_samples: int,
    hop_samples: int,
    fft_size: int,
) -> STFTResult:
    """Compute reference MATLAB framing and FFT on CPU `[channels, samples]`.

    Returns complex128 `[frames, frequencies, channels]`, frame seconds relative
    to the first input sample, and frequencies in Hz. No amplitude normalization
    is applied. FFT sizes round up to powers of two, including reference window
    truncation when FFT size is shorter than the window.
    """
    for name, value in (
        ("sample_rate", sample_rate),
        ("frame_samples", frame_samples),
        ("hop_samples", hop_samples),
        ("fft_size", fft_size),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if frame_samples < 2 or hop_samples > frame_samples:
        raise ValueError("frame_samples must be >= 2 and hop_samples <= frame_samples")
    if waveform.ndim != 2 or waveform.device.type != "cpu" or not waveform.numel():
        raise ValueError("waveform must be a nonempty CPU [channels, samples] tensor")
    if not waveform.is_floating_point() or not torch.isfinite(waveform).all():
        raise ValueError("waveform must be finite real floating-point audio")
    nfft = 1 << (max(2, fft_size) - 1).bit_length()
    pre = frame_samples - hop_samples
    post = hop_samples - waveform.shape[1] % hop_samples + pre
    padded = functional.pad(waveform.to(torch.float64), (pre, post))
    framed = padded.unfold(1, frame_samples, hop_samples).permute(1, 2, 0)
    window = torch.hamming_window(frame_samples, periodic=False, dtype=torch.float64)
    framed = framed * window[None, :, None]
    padding = max(0, nfft - frame_samples)
    left = (padding + 1) // 2
    if padding:
        framed = functional.pad(framed, (0, 0, left, padding - left))
    spectrum = torch.fft.rfft(framed, n=nfft, dim=1)
    time = (
        torch.arange(len(framed), dtype=torch.float64) * hop_samples - pre + nfft / 2
    ) / sample_rate
    return {
        "spectrum": spectrum,
        "time": time,
        "frequencies": torch.fft.rfftfreq(nfft, 1 / sample_rate, dtype=torch.float64),
    }


def _interpolate_blocks(
    time: Tensor, azimuth: Tensor, inclination: Tensor, query: Tensor
) -> tuple[Tensor, Tensor]:
    az = torch.full_like(query, torch.nan)
    inc = torch.full_like(query, torch.nan)
    if not len(time):
        return az, inc
    for index, target in enumerate(query):
        right = int(torch.searchsorted(time, target))
        if right < len(time) and abs(float(time[right] - target)) <= 1e-12:
            az[index], inc[index] = azimuth[right], inclination[right]
        elif 0 < right < len(time):
            left = right - 1
            if not torch.isfinite(azimuth[left : right + 1]).all():
                continue
            fraction = (target - time[left]) / (time[right] - time[left])
            arc = (
                torch.remainder(azimuth[right] - azimuth[left] + math.pi, 2 * math.pi)
                - math.pi
            )
            az[index] = (
                torch.remainder(azimuth[left] + fraction * arc + math.pi, 2 * math.pi)
                - math.pi
            )
            inc[index] = inclination[left] + fraction * (
                inclination[right] - inclination[left]
            )
    return az, inc


def music_localize(
    sample: LocataSample, *, config: MusicConfig | None = None
) -> MusicResult:
    """Run the reference single-source MUSIC baseline with explicit clock checks.

    Uses waveform and array pose only. Zero-energy/unsupported blocks and
    out-of-range interpolated targets remain NaN. Geometry is nearest-pose
    sampled within its support, never extrapolated. See docs/analysis.md.
    """
    started = perf_counter()
    config = MusicConfig() if config is None else config
    waveform, rate = sample["waveform"], sample["sample_rate"]
    clock = _clock(sample["audio_time"], "audio clock", strict=True)
    if len(clock) != waveform.shape[1] or not len(clock):
        raise ValueError("audio clock must match waveform samples")
    if not torch.allclose(
        clock[1:] - clock[:-1],
        torch.full_like(clock[1:], 1 / rate),
        atol=1e-9,
        rtol=1e-5,
    ):
        raise ValueError("MUSIC requires a uniform audio clock matching sample_rate")
    frame = config.frame_samples or round(config.frame_duration_seconds * rate)
    hop = config.hop_samples or frame // 4
    channels = config.channels
    if channels is None:
        channels = (
            (5, 6, 8)
            if sample["metadata"]["array"] == "dicit"
            else tuple(range(waveform.shape[0]))
        )
    if (
        len(channels) < 2
        or len(set(channels)) != len(channels)
        or any(
            isinstance(c, bool)
            or not isinstance(c, int)
            or not 0 <= c < waveform.shape[0]
            for c in channels
        )
    ):
        raise ValueError(
            "MUSIC channels must select at least two distinct existing channels"
        )
    required = sample["required_time"]
    requested = _clock(required["time"], "required time")
    if (
        required["valid_flag"].dtype != torch.bool
        or required["valid_flag"].shape != requested.shape
    ):
        raise ValueError("valid_flag must match required time")
    query = requested[required["valid_flag"]]
    pose = sample["array_pose"]
    if pose["time_origin"] != sample["time_origin"]:
        raise ValueError("array pose and audio time origins must match")
    indices = _pose_indices(pose, query)
    pose_time = query
    rotations = pose["rotation"][indices]
    microphones = pose["microphone_position"][indices][:, list(channels), :]
    if (
        microphones.shape != (len(query), len(channels), 3)
        or not torch.isfinite(microphones).all()
    ):
        raise ValueError(
            "microphone geometry must be finite and match channels/pose times"
        )
    # Validate proper rotations without deriving anything from source labels.
    world_to_array(
        torch.zeros((len(query), 3)), torch.zeros((len(query), 3)), rotations
    )
    stft = music_stft(
        waveform[list(channels)],
        rate,
        frame_samples=frame,
        hop_samples=hop,
        fft_size=config.fft_size,
    )
    frequencies = stft["frequencies"]
    selected = (frequencies > config.min_frequency) & (
        frequencies < config.max_frequency
    )
    if not selected.any():
        raise ValueError("frequency band contains no FFT bins")
    frequency = frequencies[selected]
    spectra = stft["spectrum"][:, selected, :]
    frame_time = stft["time"] + clock[0]
    starts = list(range(0, len(frame_time), config.block_step))
    stops = [min(start + config.frames_per_block, len(frame_time)) for start in starts]
    block_time = torch.tensor(
        [
            float((frame_time[a] + frame_time[b - 1]) / 2)
            for a, b in zip(starts, stops, strict=True)
        ],
        dtype=torch.float64,
    )
    block_az = torch.full_like(block_time, torch.nan)
    block_inc = torch.full_like(block_time, torch.nan)
    az, inc = torch.meshgrid(
        torch.deg2rad(torch.tensor(config.azimuth_degrees, dtype=torch.float64)),
        torch.deg2rad(torch.tensor(config.inclination_degrees, dtype=torch.float64)),
        indexing="ij",
    )
    az, inc = az.flatten(), inc.flatten()
    directions = torch.stack(
        (-inc.sin() * az.sin(), inc.sin() * az.cos(), inc.cos()), dim=1
    )
    for block_index, (start, stop) in enumerate(zip(starts, stops, strict=True)):
        center = block_time[block_index]
        if not len(pose_time) or center < pose_time[0] or center > pose_time[-1]:
            continue
        nearest = int(torch.argmin(torch.abs(pose_time - center)))
        world_directions = directions @ rotations[nearest].to(torch.float64).T
        differences = microphones[nearest] - microphones[nearest, 0]
        delays = world_directions @ differences.to(torch.float64).T / config.sound_speed
        power = torch.zeros(len(az), dtype=torch.float64)
        any_energy = False
        for f_index, hz in enumerate(frequency):
            data = spectra[start:stop, f_index]
            covariance = data.T @ data.conj()
            if (
                float(covariance.diagonal().real.sum())
                <= torch.finfo(torch.float64).tiny
            ):
                continue
            any_energy = True
            _, vectors = torch.linalg.eigh(covariance)
            noise = vectors[:, :-1]
            steering = torch.exp((2j * math.pi * hz) * delays)
            denominator = (steering.conj() @ noise).abs().square().sum(dim=1)
            power += denominator.clamp_min(torch.finfo(torch.float64).eps).reciprocal()
        if any_energy:
            best = int(torch.argmax(power))
            block_az[block_index] = (
                torch.remainder(az[best] + math.pi, 2 * math.pi) - math.pi
            )
            block_inc[block_index] = inc[best]
    estimated_az, estimated_inc = _interpolate_blocks(
        block_time, block_az, block_inc, query
    )
    track: DOATrack = {
        "id": "music-1",
        "time_origin": sample["time_origin"],
        "time": query.clone(),
        "azimuth": estimated_az,
        "inclination": estimated_inc,
    }
    return {
        "track": track,
        "block_time": block_time,
        "block_azimuth": block_az,
        "block_inclination": block_inc,
        "config": config,
        "elapsed_seconds": perf_counter() - started,
    }
