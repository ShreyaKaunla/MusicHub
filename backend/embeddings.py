"""Pretrained audio embeddings (CLAP, trained on ~630k audio-text pairs).

Heavy deps (torch, transformers) are imported lazily and ONLY used offline when building the
library. The hosted server never imports this file: it just reads the stored vectors.

Each song -> 3 ten-second clips (at 20% / 50% / 80%) -> CLAP audio embedding -> mean -> L2-normalise.
"""
import os
import numpy as np

EMBED_MODEL = "laion/clap-htsat-unfused"
EMBED_DIM = 512
SR = 48000
CLIP_SEC = 10
N_CLIPS = 3
_state = {}


def _load():
    if not _state:
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


def _clips(y):
    n = CLIP_SEC * SR
    if len(y) <= n:
        return [y]
    starts = [int(f * (len(y) - n)) for f in np.linspace(0.2, 0.8, N_CLIPS)]
    return [y[s:s + n] for s in starts]


def embed(path):
    """Returns a unit-length float32 vector of size EMBED_DIM, or None on failure."""
    try:
        import librosa
        st = _load()
        y, _ = librosa.load(path, sr=SR, mono=True, dtype=np.float32)
        if len(y) < SR:  # under 1 second: not worth embedding
            return None
        inputs = st["fe"](_clips(y), sampling_rate=SR, return_tensors="pt")
        with st["torch"].no_grad():
            feats = _as_tensor(st, st["model"].get_audio_features(**inputs))
        v = feats.mean(dim=0).cpu().numpy().astype(np.float32)
        return v / (np.linalg.norm(v) + 1e-9)
    except Exception as e:
        print(f"⚠️ Could not embed {os.path.basename(path)}: {e}")
        return None
