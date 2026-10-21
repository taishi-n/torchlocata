import io
import subprocess
import sys

import pytest
from test_analysis import ground_truth, track
from test_music import plane_wave_sample

from locata_torch import evaluate_locata, plot_doa, plot_evaluation, plot_scene


def test_import_does_not_require_plotting_stack():
    code = 'import sys; import locata_torch; assert "matplotlib" not in sys.modules'
    subprocess.run([sys.executable, "-c", code], check=True)


def test_plot_helpers_render_without_display_or_file_writes():
    pytest.importorskip("matplotlib")
    truth = ground_truth()
    tracks = [track([0] * 4)]
    for figure in (
        plot_scene(plane_wave_sample()),
        plot_doa(truth, tracks),
        plot_evaluation(evaluate_locata(truth, tracks)),
    ):
        data = io.BytesIO()
        figure.savefig(data, format="png")
        assert data.getvalue().startswith(b"\x89PNG")
        assert figure.axes
