# StravaGANte

Reference implementation for the paper *"StravaGANte: A Generative Solution for Endpoint Privacy Zones Disclosure"*.

StravaGANte proposes a GAN-based defense for Strava's Endpoint Privacy Zone (EPZ) mechanism, which hides the start/end of GPS activities near sensitive locations (e.g., a user's home) but has repeatedly been shown vulnerable to inference attacks. Instead of a static, once-per-cluster perimeter, StravaGANte trains a generator against a differentiable surrogate of the inference attack of Hassan et al. (USENIX Security '18) to produce a different EPZ configuration for every activity.

## Notation
- **Activity** — a GPS track plus metadata (distance, endpoints).
- **Endpoint** — the start or end point of an activity's track.
- **EPZ** — the circular Endpoint Privacy Zone around a sensitive location.
- **Cluster** — a set of an athlete's activities that share the same sensitive location / EPZ.

## Approach
StravaGANte adopts a Generator–Discriminator framework:
- The **generator** is conditioned on per-activity features (9 features plus a 16-dimensional noise vector *z*), not on the user's activity history. For each activity it produces a privacy-preserving EPZ configuration: where to center it, how large to make it, and a road-network decoy route disguising how much of the track was actually hidden.
- The **discriminator** plays the adversary: at training time, a differentiable surrogate of the attack of Hassan et al.; at evaluation time, the original, non-differentiable attack itself.

## Evaluation
The generator is evaluated on a synthetic benchmark (1,000 GPS activities across 200 location clusters, five EPZ radii from 200 m to 1,000 m) against two baselines — Strava's current **Static** EPZ and a **Random-per-track** perturbation — and validated on real, consented Strava clusters.

Evaluation uses the attack of Hassan et al. (USENIX Security '18). An attack counts as successful when the inferred location is within τ_e = 22.95 m of the true one, the threshold used by Dhondt et al. (CCS '22). The more recent attack of Dhondt et al. itself was not evaluated.

## Data
`Data/Syntetic/` is kept empty in this repository (only a `.gitkeep` placeholder) because the synthetic dataset (~7 GB of GPX routes) is too large for git. Download the archive from [huggingface.co/datasets/wanaracur/syntetic.gpx](https://huggingface.co/datasets/wanaracur/syntetic.gpx) and extract it into that folder, e.g.:

```
tar --zstd -xf Syntetic_dataset.tar.zst -C Data/
```

so that `Data/Syntetic/<cluster_id>/` ends up populated with the `.gpx` route files as expected by the rest of the pipeline.

## Citation
Orazi, Arazzi, Bresolin, Conti, Nocera. *"StravaGANte: A Generative Solution for Endpoint Privacy Zones Disclosure."* In Proceedings of the 42nd Annual Computer Security Applications Conference ([ACSAC 2026](https://www.acsac.org/)), Los Angeles, CA, USA, December 2026.

Synthetic dataset: [huggingface.co/datasets/wanaracur/syntetic.gpx](https://huggingface.co/datasets/wanaracur/syntetic.gpx)
