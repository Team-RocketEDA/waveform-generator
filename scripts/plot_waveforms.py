#!/usr/bin/env python3
"""Plot ngspice outputs: DAC staircase + filtered waveform, DNL/INL.

Reads results/tran_<mode>.txt (wrdata: time vdac vfilt) and
results/dc_sweep.txt (code voltage). Writes results/waveforms.png and
results/dnl_inl.png. Run with the engine venv python (has matplotlib):
  rocket-engine/.venv/bin/python scripts/plot_waveforms.py [mode]
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def plot_tran(mode):
    d = np.loadtxt(ROOT / f"results/tran_{mode}.txt")
    # wrdata writes each vector with its own scale: t vdac t vfilt
    t, vdac, vfilt = d[:, 0] * 1e6, d[:, 1], d[:, 3]
    fig, ax = plt.subplots(2, 1, figsize=(9, 6), sharex=False)
    ax[0].plot(t, vdac, lw=0.7, label="vdac (staircase)")
    ax[0].plot(t, vfilt, lw=0.9, label="vfilt (RC filtered)")
    ax[0].set(xlabel="time (us)", ylabel="V",
              title=f"{mode}: DAC staircase + RC-filtered output (full)")
    ax[0].legend(fontsize=8)
    m = t <= 1.0
    ax[1].step(t[m], vdac[m], where="post", lw=0.9, label="vdac steps")
    ax[1].plot(t[m], vfilt[m], lw=1.1, label="vfilt")
    ax[1].set(xlabel="time (us, zoom 0-1us)", ylabel="V",
              title="Staircase detail (steps + RC smoothing)")
    ax[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ROOT / "results/waveforms.png", dpi=120)
    print("wrote results/waveforms.png")


def plot_dnl():
    d = np.loadtxt(ROOT / "results/dc_sweep.txt")
    v = d[:, 1]
    n = len(v)
    lsb = (v[-1] - v[0]) / (n - 1)
    dnl = np.diff(v) / lsb - 1
    inl = (v - (v[0] + np.arange(n) * lsb)) / lsb
    fig, ax = plt.subplots(2, 1, figsize=(9, 6))
    ax[0].plot(dnl, lw=0.8)
    ax[0].axhline(1, c="r", ls="--", lw=0.7)
    ax[0].axhline(-1, c="r", ls="--", lw=0.7)
    ax[0].set(ylabel="DNL (LSB)", title=f"DNL (max|.|={np.abs(dnl).max():.3f})")
    ax[1].plot(inl, lw=0.8)
    ax[1].axhline(1, c="r", ls="--", lw=0.7)
    ax[1].axhline(-1, c="r", ls="--", lw=0.7)
    ax[1].set(xlabel="code", ylabel="INL (LSB)",
              title=f"INL (max|.|={np.abs(inl).max():.3f})")
    fig.tight_layout()
    fig.savefig(ROOT / "results/dnl_inl.png", dpi=120)
    print("wrote results/dnl_inl.png")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "sine"
    plot_tran(mode)
    plot_dnl()
