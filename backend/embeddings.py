"""Pretrained audio embeddings (CLAP, trained on ~630k audio-text pairs).

Each song -> 3 ten-second clips (at 20% / 50% / 80%) -> CLAP audio embedding -> mean -> L2-normalise.

Two interchangeable inference backends produce the same vectors, tried in this order:
1. torch + transformers (dev machines): fp32 model from the HF cache.
2. onnxruntime + models/clap_audio_int8.onnx (desktop build): int8-quantised export of the same
   network, so the packaged app keeps CLAP recommendations without shipping torch (~2 GB).

The mel front-end for the ONNX backend is numpy-only (clap_mel.py) and reproduces
ClapFeatureExtractor (truncation="rand_trunc", padding="repeatpad", slaney filters) exactly.
"""
import importlib.util
import os
import sys
from pathlib import Path

import numpy as np

EMBED_MODEL = "laion/clap-htsat-unfused"   # same id for both backends: the vectors are compatible
EMBED_DIM = 512
SR = 48000
CLIP_SEC = 10
N_CLIPS = 3
_MAX_SAMPLES = 480000                      # max_length_s * sampling_rate
_state = {}

BACKEND_DIR = Path(__file__).resolve().parent


def model_file():
    """Path of the bundled ONNX model, or None. PyInstaller datas land beside the bundled modules."""
    bases = [BACKEND_DIR]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bases.insert(0, Path(meipass))
    for base in bases:
        p = base / "models" / "clap_audio_int8.onnx"
        if p.is_file():
            return p
    return None


def torch_backend_available():
    return all(importlib.util.find_spec(m) is not None for m in ("torch", "transformers"))


def onnx_backend_available():
    return importlib.util.find_spec("onnxruntime") is not None and model_file() is not None


def available():
    return torch_backend_available() or onnx_backend_available()


def _clips(y):
    n = CLIP_SEC * SR
    if len(y) <= n:
        return [y]
    starts = [int(f * (len(y) - n)) for f in np.linspace(0.2, 0.8, N_CLIPS)]
    return [y[s:s + n] for s in starts]


# ------------------------------------------------------------- backend 1: torch + transformers
def _load():
    if not _state.get("torch"):
        import torch
        from transformers import ClapModel, ClapProcessor
        torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
        _state["torch"] = torch
        _state["model"] = ClapModel.from_pretrained(EMBED_MODEL).eval()
        _state["fe"] = ClapProcessor.from_pretrained(EMBED_MODEL).feature_extractor
    return _state


def _as_tensor(st, out):
    """Works across transformers versions: older ones return a tensor, newer ones a model-output
    object whose pooler_output holds the features (projected to 512 dims, or pre-projection)."""
    model = st["model"]
    if hasattr(out, "pooler_output"):
        out = out.pooler_output
    if out.shape[-1] != model.config.projection_dim:
        out = model.audio_projection(out)
    return st["torch"].nn.functional.normalize(out, dim=-1)


# ------------------------------------------------------------- backend 2: onnxruntime (numpy mel)
def _load_ort():
    if not _state.get("ort"):
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = max(1, (os.cpu_count() or 2) - 1)
        _state["ort"] = ort.InferenceSession(model_file(), sess_options=so,
                                             providers=["CPUExecutionProvider"])
        _state["ort_in"] = _state["ort"].get_inputs()[0].name
    return _state


def _np_mel(waveform):
    """Exactly ClapFeatureExtractor(truncation='rand_trunc', padding='repeatpad') for one clip."""
    import clap_mel

    if waveform.shape[0] < _MAX_SAMPLES:          # repeatpad: repeat, then zero-pad to 10 s
        n_repeat = int(_MAX_SAMPLES / waveform.shape[0])
        waveform = np.tile(waveform, n_repeat)
        waveform = np.pad(waveform, (0, _MAX_SAMPLES - waveform.shape[0]), mode="constant")
    elif waveform.shape[0] > _MAX_SAMPLES:        # our clips are always <= 10 s; deterministic crop
        waveform = waveform[:_MAX_SAMPLES]

    filters = clap_mel.mel_filter_bank(
        num_frequency_bins=513, num_mel_filters=64,
        min_frequency=50.0, max_frequency=14000.0, sampling_rate=SR,
        norm="slaney", mel_scale="slaney",
    )
    mel = clap_mel.spectrogram(
        waveform.astype(np.float32),
        clap_mel.window_function(1024, "hann"),
        frame_length=1024, hop_length=480, power=2.0,
        mel_filters=filters, log_mel="dB",
    )
    return mel.T[None, :].astype(np.float32)      # [batch=1, frames, 64] — channel dim is added at the session call


def _onnx_embed_clip(waveform):
    st = _load_ort()
    features = _np_mel(waveform)[:, None]   # [1, 1, frames, 64]: batch, channel, frames, mel bins
    out = st["ort"].run(None, {st["ort_in"]: features})[0][0]
    v = np.asarray(out, dtype=np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


# ------------------------------------------------------------- unified entry point
def embed(path):
    """Returns a unit-length float32 vector of size EMBED_DIM, or None on failure."""
    try:
        import librosa
        y, _ = librosa.load(path, sr=SR, mono=True, dtype=np.float32)
        if len(y) < SR:  # under 1 second: not worth embedding
            return None
        if torch_backend_available():
            st = _load()
            inputs = st["fe"](_clips(y), sampling_rate=SR, return_tensors="pt")
            with st["torch"].no_grad():
                feats = _as_tensor(st, st["model"].get_audio_features(**inputs))
            v = feats.mean(dim=0).cpu().numpy().astype(np.float32)
            return v / (np.linalg.norm(v) + 1e-9)
        if onnx_backend_available():
            clips = _clips(y)
            vs = [_onnx_embed_clip(c) for c in clips]
            v = np.mean(vs, axis=0).astype(np.float32)
            return v / (np.linalg.norm(v) + 1e-9)
        print("ℹ️ No embedding backend: install torch+transformers or bundle models/clap_audio_int8.onnx")
        return None
    except Exception as e:
        print(f"⚠️ Could not embed {os.path.basename(path)}: {e}")
        return None
