"""
Runs the same static/random/gan attack-and-score pipeline as evaluate_stravagante.py,
but against real (consented) Strava clusters instead of the synthetic dataset, reusing
an already-trained generator (no retraining -- this is purely a generalization check).

Each subfolder of --dataset_path must contain a single-entry ActivityClusterList.json
plus an activities/ folder, mirroring the synthetic per-cluster convention.
"""
import argparse
import csv
import os

import torch

from evaluate_stravagante import (
    PureBidirectionalGenerator, apply_obfuscation, run_attack_and_score, device,
    ActivityCluster,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_path", required=True)
    ap.add_argument("--weights_path", required=True)
    ap.add_argument("--tau", type=float, default=22.95)
    ap.add_argument("--csv_path", default="real_results.csv")
    args = ap.parse_args()

    G_eval = PureBidirectionalGenerator().to(device)
    G_eval.load_state_dict(torch.load(args.weights_path, map_location=device))
    G_eval.eval()

    file_exists = os.path.isfile(args.csv_path)
    csv_file = open(args.csv_path, mode="a", newline="")
    csv_writer = csv.writer(csv_file)
    if not file_exists:
        csv_writer.writerow([
            "cluster_name", "radius", "n_activities",
            "static_closest_dist", "static_success",
            "random_closest_dist", "random_success",
            "gan_closest_dist", "gan_success",
        ])

    for folder in sorted(os.listdir(args.dataset_path)):
        cluster_path = os.path.join(args.dataset_path, folder, "ActivityClusterList.json")
        if not os.path.exists(cluster_path):
            continue

        cluster = ActivityCluster.ActivityCluster.initializeActivityClusterFromJson(cluster_path)
        true_home = cluster.center
        r_user = int(cluster.radius) if cluster.radius else 1600
        n_act = len(cluster.activityPathList)
        print(f"\n=== {folder}: {n_act} activities, radius={r_user}m ===")

        apply_obfuscation(cluster_path, mode="static", r_user=r_user)
        best_s, *_ , succ_s, _, _ = run_attack_and_score(cluster_path, true_home, r_user, prefix="[Static]", tau_e=args.tau)

        apply_obfuscation(cluster_path, mode="random_per_track", r_user=r_user)
        best_r, *_, succ_r, _, _ = run_attack_and_score(cluster_path, true_home, r_user, prefix="[Random]", tau_e=args.tau)

        apply_obfuscation(cluster_path, mode="stravagante", G_eval=G_eval, r_user=r_user)
        best_g, *_, succ_g, _, _ = run_attack_and_score(cluster_path, true_home, r_user, prefix="[GAN]", tau_e=args.tau)

        csv_writer.writerow([folder, r_user, n_act, best_s, int(succ_s), best_r, int(succ_r), best_g, int(succ_g)])
        csv_file.flush()
        print(f"   => SUMMARY: Static: {best_s:.1f}m | Random: {best_r:.1f}m | StravaGANte: {best_g:.1f}m")

    csv_file.close()
    print(f"\nDone. Results in {args.csv_path}")


if __name__ == "__main__":
    main()
