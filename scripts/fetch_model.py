"""Baixa e prepara os artefatos locais descritos em models/MANIFEST.json."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from importlib import metadata
from pathlib import Path

from huggingface_hub import hf_hub_download
from onnxruntime.quantization import QuantType, quantize_dynamic


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "models" / "MANIFEST.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path: Path, expected: str) -> bool:
    return path.is_file() and sha256(path) == expected


def require_build_versions(expected: dict[str, str]) -> None:
    current_python = ".".join(map(str, sys.version_info[:3]))
    if current_python != expected["python"]:
        raise RuntimeError(
            f"Python incompatível: esperado {expected['python']}, atual {current_python}"
        )
    for package in ("numpy", "onnx", "onnxruntime", "tokenizers"):
        current = metadata.version(package)
        if current != expected[package]:
            raise RuntimeError(
                f"Dependência incompatível: {package} esperado={expected[package]} atual={current}"
            )


def download_file(repo_id: str, revision: str, entry: dict[str, str]) -> Path:
    destination = ROOT / entry["local_path"]
    if verify(destination, entry["sha256"]):
        return destination

    cached = Path(
        hf_hub_download(
            repo_id=repo_id,
            filename=entry["hub_path"],
            revision=revision,
        )
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    shutil.copyfile(cached, temporary)
    if sha256(temporary) != entry["sha256"]:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Hash inválido para {entry['hub_path']}")
    os.replace(temporary, destination)
    return destination


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    require_build_versions(manifest["build_versions"])
    model = manifest["model"]

    source_path = download_file(
        model["repo_id"], model["revision"], model["source_model"]
    )
    for entry in manifest["tokenizer_files"]:
        download_file(model["repo_id"], model["revision"], entry)

    runtime_entry = model["runtime_model"]
    runtime_path = ROOT / runtime_entry["local_path"]
    if not verify(runtime_path, runtime_entry["sha256"]):
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = runtime_path.with_suffix(".onnx.part")
        temporary.unlink(missing_ok=True)
        quantize_dynamic(source_path, temporary, weight_type=QuantType.QInt8)
        if sha256(temporary) != runtime_entry["sha256"]:
            actual = sha256(temporary)
            temporary.unlink(missing_ok=True)
            raise RuntimeError(
                f"Quantização não reproduzível: esperado={runtime_entry['sha256']} atual={actual}"
            )
        os.replace(temporary, runtime_path)

    print("Artefatos locais verificados com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
