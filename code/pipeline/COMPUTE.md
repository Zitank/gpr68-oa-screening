# COMPUTE.md

Runs = conditions × parameter values × seeds × datasets.
If the total does not fit, reduce the grid or the seeds in the prereg, not silently.

## Dev machine

| Field | Value |
| --- | --- |
| CPU | Intel N100 |
| Cores | 4 |
| RAM | 15 GiB (~4 GiB free) |
| GPU | none (Intel UHD integrated only; no discrete GPU) |
| OS | Arch Linux, kernel 7.1.9-arch1-2 |

## GPU (fill before any GPU sweep)

| Field | Value |
| --- | --- |
| GPU type | — |
| GPU count | — |
| CUDA | — |

GNINA CNN scoring is blocked on this machine. This was checked and is settled: the only GNINA v1.3.3 artifact is a CUDA 12.8 binary, the container image is 22.5 GB and CUDA-built, and no conda package exists. There is no CPU build. Docking in this sprint uses smina (D-1). GNINA command files are shipped so the same runs can be replayed where a GPU exists. Do not fill this table with a guessed device.

## Budget (from the pilot; fill in the prereg)

Not filled. Seconds per ligand come from the eight-run pilot after those runs are logged. They are not known yet, and they are not estimated here. The only logged run is the ligand harvest (`m1-ligand-harvest`), `duration_s` 41.709 on the ledger. That is not a docking time.

| Field | Value |
| --- | --- |
| Hours per run | |
| Total hours | |
| Cost or queue time | |
| conditions | |
| parameter values | |
| seeds | |
| datasets | |
| total runs | |
