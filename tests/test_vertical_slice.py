from pathlib import Path
from unittest.mock import patch

from lirox.execution.vertical_slice import VerticalSliceRequest, execute_vertical_slice


def test_vertical_slice_generates_and_runs_python(tmp_path):
    with patch("lirox.utils.llm.generate_response", return_value="print('hello from slice')"):
        result = execute_vertical_slice(
            VerticalSliceRequest(
                language="python",
                description="print hello",
                output_dir=str(tmp_path),
                document_format="none",
                train_learning=False,
            )
        )

    assert result.ok
    assert result.code.ok
    assert result.run is not None
    assert result.run.success
    assert "hello from slice" in result.run.output
    assert Path(result.artifact_path).exists()

