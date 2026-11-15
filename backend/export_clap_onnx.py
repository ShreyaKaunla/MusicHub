"""Export the CLAP audio encoder to ONNX (int8-quantised) and verify it matches the torch model.

Run on a machine with torch + transformers (the dev environment):
    python export_clap_onnx.py            # fp32 export + int8 quantisation + parity report
    python export_clap_onnx.py --fp32     # keep the unquantised model

Writes backend/models/clap_audio_int8.onnx (and/or clap_audio_fp32.onnx). The int8 model is what
the packaged desktop app uses (embeddings.py picks it up automatically), keeping CLAP recommendations
without shipping torch.
"""
import sys
import time
from pathlib import Path

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import librosa  # noqa: E402
import clap_mel  # noqa: E402
from embeddings import EMBED_MODEL, SR, _clips  # noqa: E402

OUT_DIR = BACKEND_DIR / "models"
CHECK_SONGS = 5  # real songs from the local library used for the parity check


def find_test_songs():
    import sqlite3
    from config import DB_PATH
    c = sqlite3.connect(DB_PATH)
    try:
        rows = c.execute("SELECT file_path FROM tracks WHERE embedding IS NOT NULL LIMIT ?", (CHECK_SONGS,)).fetchall()
    finally:
        c.close()
    return [r[0] for r in rows]


def slaney_filters():
    return clap_mel.mel_filter_bank(
        num_frequency_bins=513, num_mel_filters=64,
        min_frequency=50.0, max_frequency=14000.0, sampling_rate=SR,
        norm="slaney", mel_scale="slaney",
    )


def numpy_mel(waveform):
    """Mirror of ClapFeatureExtractor(rand_trunc, repeatpad) for a single clip."""
    max_len = 480000
    w = waveform
    if w.shape[0] < max_len:
        w = np.tile(w, int(max_len / w.shape[0]))
        w = np.pad(w, (0, max_len - w.shape[0]), mode="constant")
    elif w.shape[0] > max_len:
        w = w[:max_len]
    mel = clap_mel.spectrogram(
        w.astype(np.float32), clap_mel.window_function(1024, "hann"),
        frame_length=1024, hop_length=480, power=2.0,
        mel_filters=slaney_filters(), log_mel="dB",
    )
    return mel.T[None, :].astype(np.float32)


def main():
    import torch
    from transformers import ClapModel, ClapProcessor

    print(f"Loading {EMBED_MODEL} …")
    model = ClapModel.from_pretrained(EMBED_MODEL).eval()
    fe = ClapProcessor.from_pretrained(EMBED_MODEL).feature_extractor

    # ---- 1. build the exportable wrapper --------------------------------------------
    class AudioEmbedder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.audio_model = model.audio_model
            self.audio_projection = model.audio_projection

        def forward(self, input_features):
            pooled = self.audio_model(input_features=input_features).pooler_output
            emb = self.audio_projection(pooled)
            return torch.nn.functional.normalize(emb, dim=-1)

    wrapper = AudioEmbedder().eval()

    # ---- 2. mel parity: torch feature extractor vs our numpy version ------------------
    songs = find_test_songs()
    if not songs:
        sys.exit("No embedded songs in the database — scan a library first.")
    y, _ = librosa.load(songs[0], sr=SR, mono=True, dtype=np.float32)
    clip = _clips(y)[0]
    ref = fe(clip, sampling_rate=SR, return_tensors="np")["input_features"]  # [batch, 1, frames, 64]
    mine = numpy_mel(clip)[:, None]                                          # [1, 1, frames, 64]
    diff = float(np.abs(ref.astype(np.float32) - mine).max())
    print(f"mel shape torch={ref.shape} numpy={mine.shape}  max|Δ|={diff:.5f}")
    if ref.shape != mine.shape or diff > 0.05:
        sys.exit("❌ numpy mel does not match the torch feature extractor — aborting.")

    # ---- 3. export fp32 ONNX ----------------------------------------------------------
    import torch.onnx as _t  # noqa: F401
    OUT_DIR.mkdir(exist_ok=True)
    fp32_path = OUT_DIR / "clap_audio_fp32.onnx"
    print(f"Exporting fp32 ONNX → {fp32_path.name} …")
    t0 = time.time()
    example = torch.from_numpy(mine)          # [1, 1, frames, 64]: batch, channel, frames, mel bins
    torch.onnx.export(
        wrapper, (example,), str(fp32_path),
        input_names=["input_features"], output_names=["embedding"],
        opset_version=17, do_constant_folding=True,
        dynamo=False,   # legacy TorchScript exporter: no onnxscript needed, and our input shape is fixed
    )
    print(f"  exported in {time.time() - t0:.0f}s, {fp32_path.stat().st_size / 1e6:.0f} MB")

    # ---- 4. int8 dynamic quantisation -------------------------------------------------
    int8_path = OUT_DIR / "clap_audio_int8.onnx"
    if "--fp32" in sys.argv:
        print("Skipping int8 quantisation (--fp32).")
    else:
        from onnxruntime.quantization import QuantType, quantize_dynamic
        print("Quantising to int8 …")
        t0 = time.time()
        quantize_dynamic(str(fp32_path), str(int8_path), weight_type=QuantType.QInt8)
        print(f"  quantised in {time.time() - t0:.0f}s, {int8_path.stat().st_size / 1e6:.0f} MB")

    # ---- 5. parity on real songs ------------------------------------------------------
    import onnxruntime as ort

    def make_session(path):
        so = ort.SessionOptions()
        return ort.InferenceSession(str(path), sess_options=so, providers=["CPUExecutionProvider"])

    sessions = {"fp32": make_session(fp32_path)}
    if int8_path.exists():
        sessions["int8"] = make_session(int8_path)

    def torch_embed(clip):
        with torch.no_grad():
            out = wrapper(torch.from_numpy(numpy_mel(clip))[:, None])[0].numpy()
        return out / (np.linalg.norm(out) + 1e-9)

    def ort_embed(sess, clip):
        v = sess.run(None, {"input_features": numpy_mel(clip)[:, None]})[0][0].astype(np.float32)
        return v / (np.linalg.norm(v) + 1e-9)

    print(f"\nParity check on {len(songs)} real songs (cosine similarity vs torch):")
    worst = {k: 1.0 for k in sessions}
    for path in songs:
        audio, _ = librosa.load(path, sr=SR, mono=True, dtype=np.float32)
        if len(audio) < SR:
            continue
        ref_vec = torch_embed(_clips(audio)[0])
        for name, sess in sessions.items():
            sim = float(np.dot(ref_vec, ort_embed(sess, _clips(audio)[0])))
            worst[name] = min(worst[name], sim)
            print(f"  {Path(path).name[:44]:44s} {name}: cos = {sim:.4f}")
    print(f"\nworst-case cosine: {worst}")
    print("✅ Parity verified — safe to bundle." if all(v > 0.995 for v in worst.values()) else "⚠️ Check parity above.")


if __name__ == "__main__":
    main()
