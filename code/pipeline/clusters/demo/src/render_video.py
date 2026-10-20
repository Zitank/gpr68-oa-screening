"""Render the docking demo from the real pocket and smina outputs.

    .venv/bin/python -m clusters.demo.src.render_video

No number in the video is typed by hand. Scores, centres and poses are read
from results/ written by the pocket and docking pipelines.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FFMpegWriter
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

from clusters.docking.src.interpret import discrimination, isomer_resolution, oxygen_distance
from clusters.docking.src.smina import oxygen_xyz
from clusters.pocket.src.annotate import centroid
from clusters.pocket.src.figure import (
    INK,
    PAPER,
    POCKET1_COLOR,
    POCKET2_COLOR,
    TRACE_COLOR,
    _frame,
    ca_trace,
)
from clusters.pocket.src.pdbio import iter_atoms
from clusters.pocket.src.pipeline import DATA, POINTS_PDB, REPO
from clusters.pocket.src.pipeline import RESULTS as POCKET_RESULTS
from clusters.pocket.src.points import read_pockets
from clusters.pocket.src.summary import gs_geometry
from core.errors import ContractViolation

FPS = 30
OUT = REPO / "results" / "demo"
DOCK = REPO / "results" / "docking"
FFMPEG = "/usr/bin/ffmpeg"

ORDER = ("ogerin", "ms48107", "lorazepam", "zinc32547799")
LABELS = {
    "ogerin": "Ogerin",
    "ms48107": "MS48107",
    "lorazepam": "lorazepam",
    "zinc32547799": "ZINC32547799",
}
LIGAND_COLOR = {
    "ogerin": "#E69F00",
    "ms48107": "#CC79A7",
    "lorazepam": "#009E73",
    "zinc32547799": "#56B4E9",
}


def main() -> None:
    scene = _load()
    OUT.mkdir(parents=True, exist_ok=True)
    _scores_chart(scene, OUT / "scores_chart.png")
    shutil.copyfile(POCKET_RESULTS / "topology.png", OUT / "pocket_topology.png")
    mp4 = OUT / "gpr68_docking_demo.mp4"
    n_frames = _write_mp4(scene, mp4)
    _stills(scene)
    duration = n_frames / FPS
    probe = _duration_seconds(mp4)
    print(f"wrote {mp4} frames={n_frames} duration_s={duration:.2f} ffprobe_s={probe:.2f}")


def _load() -> dict:
    scores = _read_scores(DOCK / "scores.csv")
    if len(scores) != 8:
        raise ContractViolation(f"expected 8 score rows, found {len(scores)}")
    pockets = read_pockets(POINTS_PDB.read_text())
    chain = iter_atoms((DATA / "chainR.pdb").read_text())
    full = iter_atoms((REPO / "data" / "structures" / "8Z68.pdb").read_text())
    geometry = gs_geometry(
        pockets,
        [atom for atom in chain if atom.name == "CA"],
        [atom for atom in full if atom.chain == "A"],
        [atom for atom in full if atom.chain in {"A", "B", "G"}],
    )
    ca_xyz, _resseq = ca_trace(chain)
    origin = centroid([atom for atom in chain if atom.name == "CA"])
    axis = geometry["axis_unit_from_chainA_through_chainR"]
    poses = {name: _heavy_pose(DOCK / "runs" / f"{name}_p1" / "out.pdbqt") for name in ORDER}
    oxy_o = oxygen_xyz((DOCK / "runs" / "ogerin_p1" / "out.pdbqt").read_text())
    oxy_z = oxygen_xyz((DOCK / "runs" / "zinc32547799_p1" / "out.pdbqt").read_text())
    return {
        "scores": scores,
        "ca": _frame(ca_xyz, origin, axis),
        "p1": _frame(pockets[1].xyz, origin, axis),
        "p2": _frame(pockets[2].xyz, origin, axis),
        "poses": {name: _frame(list(map(tuple, xyz)), origin, axis) for name, xyz in poses.items()},
        "site": discrimination(scores),
        "isomers": isomer_resolution(scores, oxygen_distance(oxy_o, oxy_z)),
    }


def _read_scores(path: Path) -> list[dict]:
    if not path.is_file():
        raise ContractViolation(f"missing score table: {path}")
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    parsed = []
    for row in rows:
        if row["engine"] != "smina":
            raise ContractViolation(f"score row engine is {row['engine']}, expected smina")
        parsed.append(
            {
                "ligand": row["ligand"],
                "pocket_id": int(row["pocket_id"]),
                "best_score_kcal_mol": float(row["best_score_kcal_mol"]),
                "seconds": float(row["seconds"]),
            }
        )
    return parsed


def _heavy_pose(path: Path) -> np.ndarray:
    if not path.is_file():
        raise ContractViolation(f"missing docked pose: {path}")
    points = []
    for line in path.read_text().splitlines():
        if line.startswith("ENDMDL"):
            break
        if not line.startswith("ATOM") or len(line) < 54:
            continue
        atom_type = line[77:79].strip() if len(line) >= 79 else ""
        if atom_type == "HD":
            continue
        points.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
    if not points:
        raise ContractViolation(f"no heavy atoms in {path}")
    return np.asarray(points, dtype=float)


def _write_mp4(scene: dict, path: Path) -> int:
    if not Path(FFMPEG).is_file():
        raise ContractViolation(f"ffmpeg missing at {FFMPEG}")
    plt.rcParams["animation.ffmpeg_path"] = FFMPEG
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=PAPER)
    writer = FFMpegWriter(fps=FPS, codec="libx264", extra_args=["-pix_fmt", "yuv420p", "-crf", "18"])
    n_frames = 0
    with writer.saving(fig, str(path), dpi=100):
        n_frames += _hold(fig, writer, lambda: _title(fig), 6 * FPS)
        n_frames += _spin(fig, writer, scene, 16 * FPS)
        n_frames += _poses(fig, writer, scene, 4 * FPS)
        n_frames += _bars(fig, writer, scene, 12 * FPS)
        n_frames += _hold(fig, writer, lambda: _close(fig, scene), 10 * FPS)
    plt.close(fig)
    return n_frames


def _hold(fig: plt.Figure, writer: FFMpegWriter, draw, frames: int) -> int:
    draw()
    for _ in range(frames):
        writer.grab_frame()
    return frames


def _spin(fig: plt.Figure, writer: FFMpegWriter, scene: dict, frames: int) -> int:
    fig.clf()
    fig.patch.set_facecolor(PAPER)
    ax = fig.add_subplot(111, projection="3d")
    _receptor(ax, scene)
    ax.set_title("Chain R    pocket 1 away from Gα    pocket 2 off-axis", color=INK, fontsize=20, pad=16)
    for index in range(frames):
        ax.view_init(elev=16, azim=-70 + 360.0 * index / frames)
        writer.grab_frame()
    return frames


def _poses(fig: plt.Figure, writer: FFMpegWriter, scene: dict, frames_each: int) -> int:
    total = 0
    lookup = {(row["ligand"], row["pocket_id"]): row["best_score_kcal_mol"] for row in scene["scores"]}
    for name in ORDER:
        fig.clf()
        fig.patch.set_facecolor(PAPER)
        ax = fig.add_subplot(111, projection="3d")
        _zoom_pocket1(ax, scene, name)
        score = lookup[(name, 1)]
        ax.set_title(
            f"Pocket 1    {LABELS[name]}    {score:.3f} kcal/mol    smina",
            color=INK,
            fontsize=20,
            pad=14,
        )
        for _ in range(frames_each):
            writer.grab_frame()
        total += frames_each
    return total


def _bars(fig: plt.Figure, writer: FFMpegWriter, scene: dict, frames: int) -> int:
    fig.clf()
    fig.patch.set_facecolor(PAPER)
    ax = fig.add_axes((0.10, 0.16, 0.84, 0.70))
    ax.set_facecolor(PAPER)
    lookup = {(row["ligand"], row["pocket_id"]): row["best_score_kcal_mol"] for row in scene["scores"]}
    p1 = [lookup[(name, 1)] for name in ORDER]
    p2 = [lookup[(name, 2)] for name in ORDER]
    x = np.arange(len(ORDER))
    width = 0.36
    bars_1 = ax.bar(x - width / 2, [0] * len(ORDER), width, color=POCKET1_COLOR, label="pocket 1")
    bars_2 = ax.bar(x + width / 2, [0] * len(ORDER), width, color=POCKET2_COLOR, label="pocket 2")
    floor = min(p1 + p2) - 1.0
    ax.set_ylim(floor, 0.4)
    ax.axhline(0.0, color=TRACE_COLOR, linewidth=1)
    ax.set_xticks(x, [LABELS[name] for name in ORDER], fontsize=16)
    ax.set_ylabel("Vina score (kcal/mol)", fontsize=16, color=INK)
    ax.set_title("Eight smina scores    more negative scores lower on the axis", color=INK, fontsize=20)
    ax.legend(frameon=False, fontsize=14)
    ax.tick_params(colors=INK, labelsize=13)
    for index in range(frames):
        grown = (index + 1) / frames
        for bar, target in zip(bars_1, p1, strict=True):
            bar.set_height(target * grown)
        for bar, target in zip(bars_2, p2, strict=True):
            bar.set_height(target * grown)
        writer.grab_frame()
    return frames


def _title(fig: plt.Figure) -> None:
    fig.clf()
    fig.patch.set_facecolor(PAPER)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.08, 0.72, "GPR68", color=INK, fontsize=64, fontweight="bold")
    ax.text(0.08, 0.58, "PDB 8Z68 chain R", color=INK, fontsize=32)
    ax.text(0.08, 0.48, "pH 6.8 cryo-EM", color=INK, fontsize=32)
    ax.text(0.08, 0.30, "Ogerin, MS48107, lorazepam, ZINC32547799", color=INK, fontsize=24)
    ax.text(0.08, 0.20, "pocket 1 and pocket 2    same settings, different centre", color=INK, fontsize=22)
    ax.text(0.08, 0.08, "engine: smina (Vina 1.1.2 scoring)", color=POCKET1_COLOR, fontsize=22)


def _close(fig: plt.Figure, scene: dict) -> None:
    fig.clf()
    fig.patch.set_facecolor(PAPER)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    site = scene["site"]
    isomers = scene["isomers"]
    better = ", ".join(LABELS[name] for name in site["pocket_1_better_than_pocket_2"]) or "none"
    delta = isomers["pocket_1_score_difference"]
    gap = isomers["hydroxymethyl_oxygen_distance_A"]
    lines = [
        (0.78, "What the eight runs show", 36),
        (0.62, f"Pocket 1 scored better for: {better}", 22),
        (0.52, f"Mean pocket1 − pocket2 = {site['mean_delta_p1_minus_p2']:.3f} kcal/mol", 22),
        (0.40, f"Ogerin vs ZINC32547799 pocket 1: {delta:.3f} kcal/mol", 22),
        (0.30, f"Hydroxymethyl oxygens {gap:.2f} Å apart in the receptor frame", 22),
        (0.16, "Pocket 2 is the lipid-facing negative control.", 20),
        (0.08, "engine: smina (Vina scoring); GNINA replay scripts provided", 20),
    ]
    for y, text, size in lines:
        ax.text(0.06, y, text, color=INK, fontsize=size)


def _receptor(ax: plt.Axes, scene: dict) -> None:
    ca = scene["ca"]
    ax.plot(ca[:, 0], ca[:, 1], ca[:, 2], color=TRACE_COLOR, linewidth=1.2)
    _scatter(ax, scene["p1"], POCKET1_COLOR, "pocket 1")
    _scatter(ax, scene["p2"], POCKET2_COLOR, "pocket 2")
    ax.set_xlabel("in-plane x (Å)", color=INK, fontsize=12)
    ax.set_ylabel("in-plane y (Å)", color=INK, fontsize=12)
    ax.set_zlabel("away from Gα (Å)", color=INK, fontsize=12)
    ax.legend(loc="upper left", fontsize=12, frameon=False)
    ax.set_facecolor(PAPER)
    ax.tick_params(colors=INK, labelsize=9)


def _zoom_pocket1(ax: plt.Axes, scene: dict, ligand: str) -> None:
    cloud = scene["p1"]
    pose = scene["poses"][ligand]
    ax.plot(scene["ca"][:, 0], scene["ca"][:, 1], scene["ca"][:, 2], color="#D9D4CC", linewidth=0.8)
    _scatter(ax, cloud, POCKET1_COLOR, "pocket 1")
    ax.scatter(
        pose[:, 0],
        pose[:, 1],
        pose[:, 2],
        s=40,
        c=LIGAND_COLOR[ligand],
        depthshade=False,
        label=LABELS[ligand],
    )
    centre = cloud.mean(axis=0)
    span = 14.0
    ax.set_xlim(centre[0] - span, centre[0] + span)
    ax.set_ylim(centre[1] - span, centre[1] + span)
    ax.set_zlim(centre[2] - span, centre[2] + span)
    ax.view_init(elev=18, azim=-50)
    ax.legend(loc="upper left", fontsize=12, frameon=False)
    ax.set_facecolor(PAPER)
    ax.tick_params(colors=INK, labelsize=9)


def _scatter(ax: plt.Axes, points: np.ndarray, color: str, label: str) -> None:
    ax.scatter(points[:, 0], points[:, 1], points[:, 2], s=22, c=color, depthshade=False, label=label)


def _scores_chart(scene: dict, path: Path) -> None:
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=PAPER)
    _bars_final(fig, scene)
    fig.savefig(path, facecolor=PAPER)
    plt.close(fig)


def _bars_final(fig: plt.Figure, scene: dict) -> None:
    """Draw the finished bar chart used both as a still and as the animation's last look."""
    ax = fig.add_axes((0.10, 0.16, 0.84, 0.70))
    ax.set_facecolor(PAPER)
    lookup = {(row["ligand"], row["pocket_id"]): row["best_score_kcal_mol"] for row in scene["scores"]}
    p1 = [lookup[(name, 1)] for name in ORDER]
    p2 = [lookup[(name, 2)] for name in ORDER]
    x = np.arange(len(ORDER))
    width = 0.36
    ax.bar(x - width / 2, p1, width, color=POCKET1_COLOR, label="pocket 1")
    ax.bar(x + width / 2, p2, width, color=POCKET2_COLOR, label="pocket 2")
    ax.set_ylim(min(p1 + p2) - 1.0, 0.4)
    ax.axhline(0.0, color=TRACE_COLOR, linewidth=1)
    ax.set_xticks(x, [LABELS[name] for name in ORDER], fontsize=16)
    ax.set_ylabel("Vina score (kcal/mol)", fontsize=16, color=INK)
    ax.set_title("Eight smina scores", color=INK, fontsize=20)
    ax.legend(frameon=False, fontsize=14)
    ax.tick_params(colors=INK, labelsize=13)


def _stills(scene: dict) -> None:
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=PAPER)
    _title(fig)
    fig.savefig(OUT / "title.png", facecolor=PAPER)
    fig.clf()
    ax = fig.add_subplot(111, projection="3d")
    _receptor(ax, scene)
    ax.view_init(elev=16, azim=-40)
    ax.set_title("Chain R with pocket 1 and pocket 2", color=INK, fontsize=18)
    fig.savefig(OUT / "rotation_still.png", facecolor=PAPER)
    fig.clf()
    _close(fig, scene)
    fig.savefig(OUT / "closing.png", facecolor=PAPER)
    plt.close(fig)


def _duration_seconds(path: Path) -> float:
    probe = subprocess.run(
        [
            FFMPEG.replace("ffmpeg", "ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        raise ContractViolation(f"ffprobe failed: {probe.stderr.strip()}")
    return float(probe.stdout.strip())


if __name__ == "__main__":
    main()
