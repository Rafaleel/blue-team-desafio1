from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Sequence

for variable in (
    "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(variable, "1")
os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")

import numpy as np
from tokenizers import Tokenizer

_saved_import_stderr = os.dup(2)
_null_import_stderr = os.open(os.devnull, os.O_WRONLY)
try:
    os.dup2(_null_import_stderr, 2)
    import onnxruntime as ort
finally:
    os.dup2(_saved_import_stderr, 2)
    os.close(_null_import_stderr)
    os.close(_saved_import_stderr)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_runtime_artifacts(root: Path, manifest_path: Path) -> None:
    """Confirma que modelo e tokenizer locais são exatamente os artefatos esperados."""

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = [manifest["model"]["runtime_model"], *manifest["tokenizer_files"]]
    for entry in entries:
        path = root / entry["local_path"]
        if not path.is_file() or _sha256(path) != entry["sha256"]:
            raise RuntimeError(f"Artefato local ausente ou inválido: {entry['local_path']}")


@contextmanager
def _silence_native_stderr_during_session_creation():
    """Evita aviso nativo variável de telemetria sem ocultar erros Python."""
    saved_stderr = os.dup(2)
    null_stderr = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(null_stderr, 2)
        yield
    finally:
        os.dup2(saved_stderr, 2)
        os.close(null_stderr)
        os.close(saved_stderr)


class ONNXEmbedder:
    """Executa o encoder local em CPU com opções fixas de concorrência."""

    def __init__(self, model_path: Path, tokenizer_path: Path, runtime: dict, max_tokens: int):
        with _silence_native_stderr_during_session_creation():
            options = ort.SessionOptions()
            options.log_severity_level = 3
            options.intra_op_num_threads = runtime["intra_op_threads"]
            options.inter_op_num_threads = runtime["inter_op_threads"]
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
            self.session = ort.InferenceSession(
                str(model_path), sess_options=options, providers=[runtime["provider"]]
            )
        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self.tokenizer.no_truncation()
        self.tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
        self.max_tokens = max_tokens
        self.quantization_scale = runtime["embedding_quantization_scale"]

    def token_count(self, text: str, *, add_special_tokens: bool = True) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=add_special_tokens).ids)

    def token_ids(self, text: str) -> list[int]:
        return self.tokenizer.encode(text, add_special_tokens=False).ids

    def decode_ids(self, ids: list[int]) -> str:
        return self.tokenizer.decode(ids, skip_special_tokens=True).strip()

    def encode_batch(self, texts: Sequence[str]) -> np.ndarray:
        """Gera embeddings com mean pooling mascarado e normalização L2."""

        if not texts:
            return np.empty((0, 384), dtype=np.float32)
        encodings = self.tokenizer.encode_batch(list(texts), add_special_tokens=True)
        if any(len(encoding.ids) > self.max_tokens for encoding in encodings):
            raise RuntimeError("Segmentador enviou unidade acima do limite do modelo")

        input_ids = np.asarray([item.ids for item in encodings], dtype=np.int64)
        attention_mask = np.asarray([item.attention_mask for item in encodings], dtype=np.int64)
        token_type_ids = np.asarray([item.type_ids for item in encodings], dtype=np.int64)
        output = self.session.run(
            ["last_hidden_state"],
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            },
        )[0]
        # Padding não pode participar da média dos vetores de tokens.
        expanded_mask = attention_mask[..., None].astype(np.float32)
        pooled = (output * expanded_mask).sum(axis=1) / np.clip(
            expanded_mask.sum(axis=1), 1e-9, None
        )
        normalized = pooled / np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None)
        return normalized.astype(np.float32)

    def encode_quantized(self, texts: Sequence[str]) -> np.ndarray:
        """Quantiza embeddings para tornar a pontuação funcional mais estável."""

        embeddings = self.encode_batch(texts)
        return np.rint(embeddings * self.quantization_scale).astype(np.int16)
