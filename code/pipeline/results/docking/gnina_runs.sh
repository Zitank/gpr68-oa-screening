#!/usr/bin/env bash
# GNINA replay of the eight GPR68 runs. NOT executed by the smina pipeline.
# Binary: https://github.com/gnina/gnina/releases/download/v1.3.3/gnina.cuda12.8.static
# CNN scoring is the only addition relative to the smina commands.
# Receptor pH 6.8 (OpenBabel). Seed 1.
set -euo pipefail
cd "$(dirname "$0")"
RECEPTOR=${RECEPTOR:-receptor_pH6.8.pdbqt}
mkdir -p gnina_out

./gnina -r $RECEPTOR -l lorazepam.pdbqt --center_x 145.67 --center_y 128.56 --center_z 99.49 --size_x 24.00 --size_y 24.00 --size_z 24.00 --exhaustiveness 16 --num_modes 9 --energy_range 3.00 --seed 1 --cpu 1 --cnn_scoring rescore -o gnina_out/lorazepam_p1.sdf

./gnina -r $RECEPTOR -l lorazepam.pdbqt --center_x 129.32 --center_y 131.62 --center_z 117.61 --size_x 24.00 --size_y 24.00 --size_z 24.00 --exhaustiveness 16 --num_modes 9 --energy_range 3.00 --seed 1 --cpu 1 --cnn_scoring rescore -o gnina_out/lorazepam_p2.sdf

./gnina -r $RECEPTOR -l ms48107.pdbqt --center_x 145.67 --center_y 128.56 --center_z 99.49 --size_x 24.00 --size_y 24.00 --size_z 24.00 --exhaustiveness 16 --num_modes 9 --energy_range 3.00 --seed 1 --cpu 1 --cnn_scoring rescore -o gnina_out/ms48107_p1.sdf

./gnina -r $RECEPTOR -l ms48107.pdbqt --center_x 129.32 --center_y 131.62 --center_z 117.61 --size_x 24.00 --size_y 24.00 --size_z 24.00 --exhaustiveness 16 --num_modes 9 --energy_range 3.00 --seed 1 --cpu 1 --cnn_scoring rescore -o gnina_out/ms48107_p2.sdf

./gnina -r $RECEPTOR -l ogerin.pdbqt --center_x 145.67 --center_y 128.56 --center_z 99.49 --size_x 24.00 --size_y 24.00 --size_z 24.00 --exhaustiveness 16 --num_modes 9 --energy_range 3.00 --seed 1 --cpu 1 --cnn_scoring rescore -o gnina_out/ogerin_p1.sdf

./gnina -r $RECEPTOR -l ogerin.pdbqt --center_x 129.32 --center_y 131.62 --center_z 117.61 --size_x 24.00 --size_y 24.00 --size_z 24.00 --exhaustiveness 16 --num_modes 9 --energy_range 3.00 --seed 1 --cpu 1 --cnn_scoring rescore -o gnina_out/ogerin_p2.sdf

./gnina -r $RECEPTOR -l zinc32547799.pdbqt --center_x 145.67 --center_y 128.56 --center_z 99.49 --size_x 24.00 --size_y 24.00 --size_z 24.00 --exhaustiveness 16 --num_modes 9 --energy_range 3.00 --seed 1 --cpu 1 --cnn_scoring rescore -o gnina_out/zinc32547799_p1.sdf

./gnina -r $RECEPTOR -l zinc32547799.pdbqt --center_x 129.32 --center_y 131.62 --center_z 117.61 --size_x 24.00 --size_y 24.00 --size_z 24.00 --exhaustiveness 16 --num_modes 9 --energy_range 3.00 --seed 1 --cpu 1 --cnn_scoring rescore -o gnina_out/zinc32547799_p2.sdf
