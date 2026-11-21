from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_card_ppt.business_card.builder import build_business_card_schema
from business_card_ppt.business_card.export import export_business_card_outputs
from business_card_ppt.business_card.verifier import verify_business_card_outputs
from business_card_ppt.io.writer import ensure_dir, write_json


BUILDER_PARAMS_FROM_NL_PROMPT = ROOT / "prompts" / "glm5_business_card_builder_params_from_nl_prompt.md"


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _extract_json(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _run_glm_json(command: str, prompt_path: Path, payload: str) -> dict[str, Any]:
    prompt = prompt_path.read_text(encoding="utf-8")
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    completed = subprocess.run(
        command,
        input=f"{prompt}\n\n--- INPUT ---\n{payload}\n",
        text=True,
        shell=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"OpenCode/GLM5 command failed: {completed.stderr.strip()}")
    try:
        return _extract_json(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenCode/GLM5 returned non-JSON output: {exc}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run editable business card PPT pipeline.")
    parser.add_argument("--input-request", help="Path to natural-language business card request.")
    parser.add_argument("--output-dir", default=str(ROOT / "outputs" / "business_card_run"))
    parser.add_argument("--glm-command", help="Command that calls GLM5 and returns JSON on stdout.")
    parser.add_argument("--opencode-glm-command", help="Alias for --glm-command.")
    parser.add_argument("--builder-params-json", help="User/model-provided real business_card_builder_params.json.")
    parser.add_argument("--icon-dir", default=str(ROOT / "svg_material"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = ensure_dir(args.output_dir)
    command = args.opencode_glm_command or args.glm_command

    if args.input_request:
        input_path = Path(args.input_request)
        if not input_path.exists():
            raise SystemExit(f"input request not found: {input_path}")
        shutil.copyfile(input_path, output_dir / "input_request.md")

    if not args.builder_params_json:
        if not args.input_request:
            raise SystemExit(
                "missing --input-request and --builder-params-json; stopped at the model-call layer."
            )
        if not command:
            raise SystemExit(
                "missing real business_card_builder_params.json and --glm-command/--opencode-glm-command; "
                "stopped at the model-call layer. Please provide the OpenCode/GLM5 command that reads stdin and writes JSON to stdout."
            )
        request_text = Path(args.input_request).read_text(encoding="utf-8")
        builder_params = _run_glm_json(command, BUILDER_PARAMS_FROM_NL_PROMPT, request_text)
        write_json(output_dir / "business_card_builder_params.json", builder_params)
    else:
        builder_params = _load_json(args.builder_params_json)
        write_json(output_dir / "business_card_builder_params.json", builder_params)

    schema = build_business_card_schema(builder_params, icon_dir=args.icon_dir)
    summary = export_business_card_outputs(schema, output_dir)
    report = verify_business_card_outputs(schema, summary, output_dir, builder_params=builder_params)
    print(json.dumps({"output_dir": str(output_dir), "passed": report["passed"]}, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
