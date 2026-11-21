from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_stops_without_json_or_glm_command(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "run_business_card_pipeline.py"),
            "--output-dir",
            str(tmp_path / "no_model"),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "stopped at the model-call layer" in completed.stderr


def test_pipeline_stops_without_input_request_or_builder_params(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "run_business_card_pipeline.py"),
            "--glm-command",
            f'"{sys.executable}" -c "print({{}})"',
            "--output-dir",
            str(tmp_path / "no_input"),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "missing --input-request" in completed.stderr
    assert "stopped at the model-call layer" in completed.stderr


def test_pipeline_runs_with_user_provided_builder_params_json(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "run_business_card_pipeline.py"),
            "--builder-params-json",
            str(ROOT / "tests" / "fixtures" / "sample_business_card_builder_params.json"),
            "--output-dir",
            str(tmp_path / "with_json"),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "with_json" / "business_card.pptx").exists()
    assert (tmp_path / "with_json" / "verification_report.json").exists()


def test_pipeline_uses_single_fake_glm_call_from_input_request(tmp_path):
    input_request = tmp_path / "input_request.md"
    input_request.write_text("姓名：李雷\n公司：未来科技\n电话：186-0000-0000\n", encoding="utf-8")
    call_count = tmp_path / "glm_call_count.txt"
    fake_glm = tmp_path / "fake_glm.py"
    builder_params = {
        "name": "李雷",
        "company": "未来科技",
        "phone": "186-0000-0000",
        "layout_style": "minimal_corner",
        "style": {"accent_color": "#008577", "background_color": "#FFFFFF", "text_color": "#111111"},
        "uncertainties": [],
    }
    fake_glm.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import json, sys",
                f"count_path = Path({str(call_count)!r})",
                "count = int(count_path.read_text(encoding='utf-8')) if count_path.exists() else 0",
                "count_path.write_text(str(count + 1), encoding='utf-8')",
                "prompt = sys.stdin.read()",
                "assert 'business_card_builder_params.json' in prompt",
                "assert 'education' not in json.dumps(" + repr(builder_params) + ", ensure_ascii=False)",
                f"print(json.dumps({builder_params!r}, ensure_ascii=False))",
            ]
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "run_business_card_pipeline.py"),
            "--input-request",
            str(input_request),
            "--glm-command",
            f'"{sys.executable}" "{fake_glm}"',
            "--output-dir",
            str(tmp_path / "with_glm"),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert call_count.read_text(encoding="utf-8") == "1"
    written_params = json.loads((tmp_path / "with_glm" / "business_card_builder_params.json").read_text(encoding="utf-8"))
    assert written_params["name"] == "李雷"
    assert (tmp_path / "with_glm" / "business_card.schema.json").exists()

