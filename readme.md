# StravaGANte

Reference implementation for the paper *"StravaGANte: A Generative Solution for Endpoint Privacy Zones Disclosure"*.

StravaGANte proposes a GAN-based defense for Strava's Endpoint Privacy Zone (EPZ) mechanism, which hides the start/end of GPS activities near sensitive locations (e.g., a user's home) but has repeatedly been shown vulnerable to inference attacks. Instead of a static, once-per-cluster perimeter, StravaGANte trains a generator directly against a real inference attack to produce a different, attack-resilient EPZ configuration for every activity.

## Notation
- **Activity** — a GPS track plus metadata (distance, endpoints).
- **Endpoint** — the start or end point of an activity's track.
- **EPZ** — the circular Endpoint Privacy Zone around a sensitive location.
- **Cluster** — a set of an athlete's activities that share the same sensitive location / EPZ.

## Approach
StravaGANte adopts a Generator–Discriminator framework:
- The **generator** produces, per activity, a privacy-preserving EPZ configuration: where to center it, how large to make it, and a road-network decoy route disguising how much of the track was actually hidden.
- The **discriminator** plays the adversary: at training time, a differentiable surrogate of the real inference attack; at evaluation time, the real, non-differentiable attack itself.

## Evaluation
The generator is evaluated on a synthetic benchmark (1,000 GPS activities across 200 location clusters, five EPZ radii from 200 m to 1,000 m) against two baselines — Strava's current **Static** EPZ and a **Random-per-track** perturbation — and validated on real, consented Strava clusters.
