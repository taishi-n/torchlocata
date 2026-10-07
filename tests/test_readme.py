from pathlib import Path

import pytest


@pytest.mark.parametrize("document", ["README.md", "docs/getting-started.md"])
def test_documented_python_example(make_recording, tmp_path, document):
    # Under 1 MiB of synthetic DOUBLE WAV, with one complete documented window.
    make_recording(array="eigenmike", frames=48000, channels=1, sample_rate=48000)
    readme = Path(__file__).parents[1] / document
    code = readme.read_text().split("```python\n", 1)[1].split("```", 1)[0]
    # Substitute only the local corpus path; execute the documented API unchanged.
    code = code.replace('root="~/dataset/LOCATA"', f"root={str(tmp_path)!r}")
    namespace = {}
    exec(compile(code, str(readme), "exec"), namespace)
    assert tuple(namespace["waveforms"].shape) == (1, 1, 48000)
    assert namespace["batch"]["lengths"].tolist() == [48000]
