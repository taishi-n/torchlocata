# I/O and DataLoader

## Recording discovery and errors

Dataset construction reads directory names, array WAV headers, and the existence
of mandatory files. It does not load waveform payloads or sample timestamp
tables. Existing WAV files determine the recording index; ZIP archives, results,
and MATLAB code are outside it.

An existing selected array directory without its array WAV is excluded and
reported in `missing_audio` with `MissingAudioWarning`. The reader does not assume
every recording has every array, or fabricate warnings for absent directories.

| Condition | Result |
| --- | --- |
| Missing array WAV in an existing array directory | Warning and exclusion from the index |
| Invalid header or missing mandatory file for an existing WAV | `LocataError` during construction |
| Corrupt TXT rows, invalid values, or mismatched row counts | `LocataError` on first relevant access |
| Missing optional annotation | `None`, independently of split |
| Malformed optional file that is read | `LocataError`, including path and cause |

Mandatory files are the array WAV, its audio timestamp TXT, array-position TXT,
and `required_time.txt`. Available source files are handled independently. Source
WAV and clock content validation is deferred when source audio is disabled and
no source VAD needs that clock. Existing malformed data is never silently dropped
or reported as an absent annotation.

## Partial reads and bounded worker caches

Windows seek within the WAV and read only the requested frames using SoundFile.
The reader never loads a whole recording merely to slice a window.

Audio timestamps and VAD are streamed and validated in full on first access in
each worker. The reader records file offsets every 4096 rows, then reads near the
requested interval. It preserves the actual clock values, including nonuniform
sampling, without replacing them with an unverified uniform approximation.
Smaller pose and required-time tables are read per item and cropped by time.

Each worker has an LRU limit of `cache_size=16` indexed files and
`cache_bytes=16777216` estimated index bytes by default. An index exceeding the
limit is used for the current access without being cached. Eviction, or setting
either limit to zero, causes full validation to run again on subsequent access.
Temporary indexing memory and returned samples are separate from this cache
budget.

The dataset retains no open file handles. Pickling and process changes reset the
cache. It writes no disk cache or index under the corpus. Input files must remain
unchanged during the lifetime of a dataset instance.

## Collation

`collate_locata(samples)` accepts a nonempty batch with the same array, sample
rate, channel count, and waveform dtype. Mixed batches raise a clear `ValueError`.

| Batch field | Representation |
| --- | --- |
| `waveform` | `[B, C, T_max]`, padded with zeros on the right |
| `lengths` | `[B]`, int64, original waveform lengths |
| `audio_mask` | `[B, T_max]`, bool, true only for original audio frames |
| `sample_rate` | One common `int` in Hz |
| `audio_time`, `time_origin` | Lists with one original entry per sample |
| `required_time`, `array_pose` | Lists of original typed annotations |
| `sources`, `metadata` | Lists retaining each sample's source mapping and identity |

`audio_mask=False` describes padding only. It does not describe silence, source
activity, or `valid_flag`. Annotation lengths and source counts may vary; the
collator does not interpolate, pad ground truth, or create dense labels.

Datasets return CPU tensors. Transfer waveforms explicitly, for example
`batch["waveform"].to(device)`, after loading a batch.

## Multiple workers and samplers

Both dataset views and the top-level collate function are pickle-compatible.
They support standard `Subset`, `SequentialSampler`, `RandomSampler`, and
`DataLoader` shuffle.

Use `multiprocessing_context="spawn"` for multiple workers, and place loader
creation and iteration behind a main guard:

```python
from locata_torch import LocataDataset, collate_locata
from torch.utils.data import DataLoader


def main():
    dataset = LocataDataset(root="/path/to/LOCATA", arrays=("eigenmike",))
    windows = dataset.windows(num_samples=48000, hop_samples=24000)
    loader = DataLoader(
        windows,
        batch_size=4,
        shuffle=True,
        num_workers=2,
        multiprocessing_context="spawn",
        collate_fn=collate_locata,
    )
    batch = next(iter(loader))
    print(batch["waveform"].shape)


if __name__ == "__main__":
    main()
```

An executable example is available at `examples/read_locata.py` in the repository.
Worker-zero and explicit-spawn checks are recorded in [validation](validation.md).
See the [PyTorch DataLoader documentation](https://docs.pytorch.org/docs/2.9/data.html)
for the upstream multiprocessing contract.
