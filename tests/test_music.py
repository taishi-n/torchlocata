import math

import numpy as np
import pytest
import torch

from locata_torch import MusicConfig, music_localize, music_stft


def scalar_stft(x, rate, window, hop, fft):
    """Separate NumPy transcription of the reference's framing equations."""
    nfft = 2 ** math.ceil(math.log2(fft))
    pre = window - hop
    post = hop - len(x) % hop + pre
    padded = np.pad(x, ((pre, post), (0, 0)))
    result, times = [], []
    for start in range(0, len(padded) - window + 1, hop):
        block = padded[start : start + window] * np.hamming(window)[:, None]
        pad = max(0, nfft - window)
        left = (pad + 1) // 2
        block = np.pad(block, ((left, pad - left), (0, 0)))
        result.append(np.fft.rfft(block, n=nfft, axis=0))
        times.append((start - pre + nfft / 2) / rate)
    return np.stack(result), np.array(times)


@pytest.mark.parametrize("window,hop,fft", [(8, 2, 16), (12, 3, 8), (8, 4, 9)])
def test_stft_matches_independent_matlab_equations(window, hop, fft):
    data = np.random.default_rng(11).normal(size=(31, 3))
    expected, times = scalar_stft(data, 8000, window, hop, fft)
    actual = music_stft(
        torch.tensor(data.T), 8000, frame_samples=window, hop_samples=hop, fft_size=fft
    )
    np.testing.assert_allclose(actual["spectrum"].numpy(), expected, atol=1e-12)
    np.testing.assert_allclose(actual["time"].numpy(), times, atol=1e-12)
    assert actual["spectrum"].dtype == torch.complex128


def plane_wave_sample(*, silent=False, offset=0.0):
    rate, length = 8000, 1024
    mics = torch.tensor(
        [[0.0, 0, 0], [0.03, 0, 0], [0, 0.04, 0], [0, 0, 0.05]], dtype=torch.float64
    )
    time = torch.arange(length, dtype=torch.float64) / rate
    waveform = torch.cos(2 * math.pi * 1000 * (time[None, :] + mics[:, 1:2] / 340))
    if silent:
        waveform.zero_()
    pose_time = torch.linspace(0, (length - 1) / rate, 17, dtype=torch.float64) + offset
    return {
        "waveform": waveform,
        "sample_rate": rate,
        "audio_time": time + offset,
        "time_origin": (2017, 1, 25, 0, 0, 0.0),
        "required_time": {
            "time": pose_time,
            "valid_flag": torch.ones(17, dtype=torch.bool),
        },
        "array_pose": {
            "time": pose_time,
            "time_origin": (2017, 1, 25, 0, 0, 0.0),
            "position": torch.zeros(17, 3, dtype=torch.float64),
            "rotation": torch.eye(3, dtype=torch.float64).expand(17, 3, 3),
            "ref_vec": torch.tensor([[0.0, 1, 0]] * 17, dtype=torch.float64),
            "microphone_position": mics.expand(17, 4, 3),
        },
        "sources": {},  # Localization must work without source GT or VAD.
        "metadata": {"array": "dummy", "start_frame": round(offset * rate)},
    }


def config(**kwargs):
    return MusicConfig(
        frame_samples=64,
        hop_samples=16,
        fft_size=64,
        frames_per_block=8,
        block_step=4,
        min_frequency=700,
        max_frequency=1500,
        azimuth_degrees=(-90.0, 0.0, 90.0),
        inclination_degrees=(30.0, 90.0, 150.0),
        **kwargs,
    )


def test_music_plane_wave_silence_and_window_origin():
    sample = plane_wave_sample()
    result = music_localize(sample, config=config())
    finite = torch.isfinite(result["block_azimuth"])
    assert finite.sum() >= 5
    torch.testing.assert_close(
        result["block_azimuth"][finite],
        torch.zeros_like(result["block_azimuth"][finite]),
    )
    torch.testing.assert_close(
        result["block_inclination"][finite],
        torch.full_like(result["block_inclination"][finite], math.pi / 2),
    )
    shifted = music_localize(plane_wave_sample(offset=2), config=config())
    torch.testing.assert_close(shifted["block_time"], result["block_time"] + 2)
    torch.testing.assert_close(
        shifted["track"]["azimuth"], result["track"]["azimuth"], equal_nan=True
    )
    silent = music_localize(plane_wave_sample(silent=True), config=config())
    assert torch.isnan(silent["track"]["azimuth"]).all()


def test_music_block_peaks_match_scalar_numpy_reference():
    sample = plane_wave_sample()
    result = music_localize(sample, config=config())
    x, t = scalar_stft(sample["waveform"].T.numpy(), 8000, 64, 16, 64)
    frequencies = np.fft.rfftfreq(64, 1 / 8000)
    selected = (frequencies > 700) & (frequencies < 1500)
    mics = sample["array_pose"]["microphone_position"][0].numpy()
    candidates = [(a, i) for a in (-90.0, 0.0, 90.0) for i in (30.0, 90.0, 150.0)]
    checked = 0
    for index, start in enumerate(range(0, len(x), 4)):
        stop = min(start + 8, len(x))
        center = (t[start] + t[stop - 1]) / 2
        if not 0 <= center <= sample["array_pose"]["time"][-1]:
            continue
        power = []
        for az, inc in candidates:
            a, e = np.deg2rad([az, inc])
            direction = np.array(
                [-np.sin(e) * np.sin(a), np.sin(e) * np.cos(a), np.cos(e)]
            )
            value = 0
            for fi in np.flatnonzero(selected):
                block = x[start:stop, fi, :]
                _, vectors = np.linalg.eigh(block.T @ block.conj())
                noise = vectors[:, :-1]
                steering = np.exp(
                    2j * np.pi * frequencies[fi] * (mics - mics[0]) @ direction / 340
                )
                value += 1 / max(
                    float(np.linalg.norm(noise.conj().T @ steering) ** 2),
                    np.finfo(float).eps,
                )
            power.append(value)
        az, inc = candidates[int(np.argmax(power))]
        assert result["block_azimuth"][index].item() == pytest.approx(math.radians(az))
        assert result["block_inclination"][index].item() == pytest.approx(
            math.radians(inc)
        )
        checked += 1
    assert checked > 5


def test_music_rejects_clock_gap_channels_and_missing_frequency_bins():
    sample = plane_wave_sample()
    sample["audio_time"][100:] += 0.001
    with pytest.raises(ValueError, match="clock|uniform"):
        music_localize(sample, config=config())
    with pytest.raises(ValueError, match="channel"):
        music_localize(plane_wave_sample(), config=config(channels=(7,)))
    with pytest.raises(ValueError, match="frequency"):
        MusicConfig(min_frequency=1500, max_frequency=1000)


def test_music_rotated_array_and_translation():
    sample = plane_wave_sample()
    sample["array_pose"]["rotation"] = torch.tensor(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]], dtype=torch.float64
    ).expand(17, 3, 3)
    sample["array_pose"]["microphone_position"] = sample["array_pose"][
        "microphone_position"
    ] + torch.tensor([10.0, 20.0, 30.0])
    result = music_localize(sample, config=config())
    finite = torch.isfinite(result["block_azimuth"])
    assert finite.sum() > 5
    torch.testing.assert_close(
        result["block_azimuth"][finite],
        torch.full_like(result["block_azimuth"][finite], -math.pi / 2),
    )


def test_estimate_interpolation_wrap_gaps_and_outside_support():
    from locata_torch.music import _interpolate_blocks

    times = torch.tensor([0.0, 1.0, 2.0, 3.0], dtype=torch.float64)
    angles = torch.deg2rad(
        torch.tensor([179.0, -179.0, math.nan, 0.0], dtype=torch.float64)
    )
    az, inc = _interpolate_blocks(
        times,
        angles,
        torch.ones(4, dtype=torch.float64),
        torch.tensor([-0.1, 0.5, 1.5, 2.5, 3.0, 3.1], dtype=torch.float64),
    )
    assert az[1].item() == pytest.approx(-math.pi)
    assert torch.isnan(az[[0, 2, 3, 5]]).all()
    assert az[4] == 0
    assert inc[1] == 1
