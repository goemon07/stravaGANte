import os
import shutil  
import sys

# ── 1. SELF-HEALING BYTECODE PURGE (MUST BE FIRST) ──
# Recursively scans and purges corrupted __pycache__ and .pyc files 
# inside both the project directory and the virtual environment (.venv)
print("🧹 Scanning and purging corrupted Python bytecode...")
for folder_to_clean in ['.', '.venv']:
    if os.path.exists(folder_to_clean):
        for root, dirs, files in os.walk(folder_to_clean):
            for dir_name in dirs:
                if dir_name == "__pycache__":
                    try:
                        shutil.rmtree(os.path.join(root, dir_name))
                    except Exception:
                        pass
            for file_name in files:
                if file_name.endswith('.pyc'):
                    try:
                        os.remove(os.path.join(root, file_name))
                    except Exception:
                        pass
print("✨ Caches cleared. Recompiling clean bytecode...")

import importlib  
import json
import math
import random
import csv
import argparse

# ── 1. EXPLICIT SHAPELY CUDA WORKAROUND (MUST BE FIRST) ──
# Force-import all of shapely and disable speedups at the absolute top 
# to prevent GEOS / CUDA malloc segment collisions in memory.
try:
    import shapely
    import shapely.geometry
    import shapely.speedups
    if shapely.speedups.is_available():
        shapely.speedups.disable()
except Exception:
    pass

# ── 2. GEOSPATIAL IMPORTS (SECOND) ──
import osmnx as ox
import networkx as nx
from pyproj import Transformer
from geopy.distance import distance as geopy_distance

# ── 3. HEAVY ML FRAMEWORKS (THIRD) ──
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np

# Headless plotting for background script safety
import matplotlib
matplotlib.use('Agg')


# Project imports
from Models import ActivityCluster, Activity
from Attack2 import EPZSearch as EPZSearch2
from DataRepresentation import DataRepresentationFactory

# Clear corrupted __pycache__ folders
for root, dirs, files in os.walk('.'):
    for dir_name in dirs:
        if dir_name == "__pycache__":
            shutil.rmtree(os.path.join(root, dir_name))

# Force-reload the attack module from disk to clear the corrupted memory
if 'Attack2.EPZSearch' in sys.modules:
    importlib.reload(sys.modules['Attack2.EPZSearch'])
    EPZSearch2 = sys.modules['Attack2.EPZSearch']
    print("🧹 Active memory cleared! Attack library restored.")

# ── 1. SILENCE THE PLOTTER FOR FAST METRICS ──
def silent_plot(self, *args, **kwargs):
    pass
EPZSearch2.EPZSearch.plot_heatmap_clusters_over_osmnx = silent_plot

# ── 2. GLOBAL TRANSFORMERS & DEVICE ──
fromlatlon = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
tolatlon = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
#device = torch.device("cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu"))
device = "cpu"
print(f"🚀 Active device: {device}")

# ── 3. DATASET HELPER FUNCTIONS ──
def fast_distance(pt1, pt2):
    lat1, lon1 = pt1
    lat2, lon2 = pt2
    cos_lat = math.cos(math.radians(lat1))
    dx = (lon2 - lon1) * 111320.0 * cos_lat
    dy = (lat2 - lat1) * 111320.0
    return math.sqrt(dx**2 + dy**2)

def calculate_bearing(pt1, pt2):
    lat1, lon1 = np.radians(pt1[0]), np.radians(pt1[1])
    lat2, lon2 = np.radians(pt2[0]), np.radians(pt2[1])
    d_lon = lon2 - lon1
    y = np.sin(d_lon) * np.cos(lat2)
    x = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(d_lon)
    return np.degrees(np.arctan2(y, x)) % 360

class DynamicStravaGANDataset(Dataset):
    def __init__(self, clusters):
        self.data = []
        radii_to_train = [200, 400, 600, 800, 1000, 1600]
        
        for cluster_path in clusters:
            cluster = ActivityCluster.ActivityCluster.initializeActivityClusterFromJson(cluster_path)
            if not cluster: continue
            
            true_home_lat, true_home_lon = cluster.center[0], cluster.center[1]
            home_x, home_y = fromlatlon.transform(true_home_lon, true_home_lat)
            
            for act_path in cluster.activityPathList:
                act = Activity.Activity.initActivityFromPath(act_path)
                try: coords = act.decodePolyline()
                except: continue
                
                dists_to_home = [fast_distance(pt, cluster.center) for pt in coords]
                
                for r_user in radii_to_train:
                    start_hidden = [coords[i] for i, d in enumerate(dists_to_home) if d < r_user]
                    if len(start_hidden) < 2: continue
                    start_entry = coords[len(start_hidden)]
                    
                    start_dist = sum(fast_distance(start_hidden[i], start_hidden[i+1]) for i in range(len(start_hidden)-1))
                    start_bearing = calculate_bearing(start_hidden[-1], start_entry)
                    
                    end_hidden = [coords[i] for i, d in reversed(list(enumerate(dists_to_home))) if d < r_user]
                    if len(end_hidden) < 2: continue
                    end_entry = coords[-(len(end_hidden) + 1)]
                    
                    end_dist = sum(fast_distance(end_hidden[i], end_hidden[i+1]) for i in range(len(end_hidden)-1))
                    end_bearing = calculate_bearing(end_hidden[-1], end_entry)
                    
                    entry_start_x, entry_start_y = fromlatlon.transform(start_entry[1], start_entry[0])
                    entry_end_x, entry_end_y = fromlatlon.transform(end_entry[1], end_entry[0])
                    
                    self.data.append({
                        'home_x': home_x, 'home_y': home_y,
                        'rel_start_x': entry_start_x - home_x, 'rel_start_y': entry_start_y - home_y,
                        'start_dist': start_dist, 'start_bearing': start_bearing,
                        'rel_end_x': entry_end_x - home_x, 'rel_end_y': entry_end_y - home_y,
                        'end_dist': end_dist, 'end_bearing': end_bearing,
                        'r_user': r_user
                    })
                
    def __len__(self):
        return len(self.data)
        
    def __getitem__(self, idx):
        row = self.data[idx]
        g_features = torch.tensor([
            row['rel_start_x'] / 1000.0, row['rel_start_y'] / 1000.0, row['start_dist'] / 1000.0,
            row['rel_end_x'] / 1000.0, row['rel_end_y'] / 1000.0, row['end_dist'] / 1000.0,
            row['start_bearing'] / 360.0, row['end_bearing'] / 360.0, row['r_user'] / 1000.0
        ], dtype=torch.float32)
        
        abs_home = torch.tensor([row['home_x'] / 1000.0, row['home_y'] / 1000.0], dtype=torch.float32)
        return g_features, abs_home

# ── 4. NEURAL NETWORK ARCHITECTURE (PURE MODEL) ──
class PureBidirectionalGenerator(nn.Module):
    def __init__(self, feature_dim=9, noise_dim=16):
        super(PureBidirectionalGenerator, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(feature_dim + noise_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 5) 
        )
        self.sigmoid = nn.Sigmoid()

    def forward(self, features, z):
        x = torch.cat([features, z], dim=1)
        out = self.net(x)
        
        r_user_m = features[:, 8:9] * 1000.0
        
        dX = torch.tanh(out[:, 0:1]) * (r_user_m * 0.45)  
        dY = torch.tanh(out[:, 1:2]) * (r_user_m * 0.45)  
        dR = self.sigmoid(out[:, 2:3]) * (r_user_m * 0.40) 
        
        # Decoys: Capped to leave at least a tiny bit of real track
        start_ratio = 0.05 + (self.sigmoid(out[:, 3:4]) * 0.80)
        end_ratio = 0.05 + (self.sigmoid(out[:, 4:5]) * 0.80)
        
        return dX, dY, dR, start_ratio, end_ratio

class SurrogateDiscriminator(nn.Module):
    def __init__(self, input_dim=6):
        super(SurrogateDiscriminator, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 2)
        )
    def forward(self, fake_start_X, fake_start_Y, fake_start_dist, fake_end_X, fake_end_Y, fake_end_dist):
        x = torch.stack([fake_start_X, fake_start_Y, fake_start_dist, fake_end_X, fake_end_Y, fake_end_dist], dim=1)
        return self.net(x)

# ── 5. STABLE TRAINING ROUTINE (LOCAL ANCHOR + TRUE METERS) ──
def train_stravagante(train_clusters, weights_path, num_epochs=150):
    print(f"⚙️ Model not found at '{weights_path}'. Commencing automated training...")
    dataset = DynamicStravaGANDataset(train_clusters)
    dataloader = DataLoader(dataset, batch_size=32, shuffle=True)
    
    G = PureBidirectionalGenerator().to(device)
    D = SurrogateDiscriminator().to(device)
    
    opt_G = optim.Adam(G.parameters(), lr=0.001)
    opt_D = optim.Adam(D.parameters(), lr=0.001)
    criterion = nn.L1Loss()
    
    lambda_usability = 0.05 * 100.0  
    lambda_geometry  = 0.5 * 100.0
    
    print(f"🚀 Starting Pure GAN Training on {device}...")
    for epoch in range(num_epochs):
        epoch_d_loss, epoch_g_loss, epoch_error = 0.0, 0.0, 0.0
        
        for batch_features, _ in dataloader:
            batch_size = batch_features.size(0)
            batch_features = batch_features.to(device)
            
            # Local Random Anchor
            anchor = (torch.rand(batch_size, 2, device=device) * 2.0) - 1.0 
            anchor_x, anchor_y = anchor[:, 0], anchor[:, 1]
            
            rel_start_x, rel_start_y = batch_features[:, 0], batch_features[:, 1]
            start_dist = batch_features[:, 2]
            rel_end_x, rel_end_y = batch_features[:, 3], batch_features[:, 4]
            end_dist = batch_features[:, 5]
            
            z = torch.randn(batch_size, 16, device=device)
            
            norm_start = torch.sqrt(rel_start_x**2 + rel_start_y**2 + 1e-8)
            dir_start_x, dir_start_y = rel_start_x / norm_start, rel_start_y / norm_start
            norm_end = torch.sqrt(rel_end_x**2 + rel_end_y**2 + 1e-8)
            dir_end_x, dir_end_y = rel_end_x / norm_end, rel_end_y / norm_end
            
            # 1. TRAIN DISCRIMINATOR
            opt_D.zero_grad()
            with torch.no_grad():
                dX, dY, dR, start_ratio, end_ratio = G(batch_features, z)
                dX_sq, dY_sq, dR_sq = dX.squeeze(1)/1000.0, dY.squeeze(1)/1000.0, dR.squeeze(1)/1000.0
                start_ratio_sq, end_ratio_sq = start_ratio.squeeze(1), end_ratio.squeeze(1)
                
                mod_start_dist = torch.clamp(start_dist + dR_sq + (dX_sq * dir_start_x + dY_sq * dir_start_y), min=0.01)
                mod_end_dist = torch.clamp(end_dist + dR_sq + (dX_sq * dir_end_x + dY_sq * dir_end_y), min=0.01)
                
                fake_start_len = mod_start_dist * start_ratio_sq
                fake_start_dist = mod_start_dist - fake_start_len
                fake_end_len = mod_end_dist * end_ratio_sq
                fake_end_dist = mod_end_dist - fake_end_len
                
                fake_start_X = anchor_x + rel_start_x + (dir_start_x * fake_start_len)
                fake_start_Y = anchor_y + rel_start_y + (dir_start_y * fake_start_len)
                fake_end_X = anchor_x + rel_end_x + (dir_end_x * fake_end_len)
                fake_end_Y = anchor_y + rel_end_y + (dir_end_y * fake_end_len)
                
            pred_home = D(fake_start_X, fake_start_Y, fake_start_dist, fake_end_X, fake_end_Y, fake_end_dist)
            loss_D = criterion(pred_home * 1000.0, anchor * 1000.0)
            loss_D.backward()
            opt_D.step()
            
            # 2. TRAIN GENERATOR
            opt_G.zero_grad()
            dX, dY, dR, start_ratio, end_ratio = G(batch_features, z)
            dX_sq, dY_sq, dR_sq = dX.squeeze(1)/1000.0, dY.squeeze(1)/1000.0, dR.squeeze(1)/1000.0
            start_ratio_sq, end_ratio_sq = start_ratio.squeeze(1), end_ratio.squeeze(1)
            
            mod_start_dist = torch.clamp(start_dist + dR_sq + (dX_sq * dir_start_x + dY_sq * dir_start_y), min=0.01)
            mod_end_dist = torch.clamp(end_dist + dR_sq + (dX_sq * dir_end_x + dY_sq * dir_end_y), min=0.01)
            
            fake_start_len = mod_start_dist * start_ratio_sq
            fake_start_dist = mod_start_dist - fake_start_len
            fake_end_len = mod_end_dist * end_ratio_sq
            fake_end_dist = mod_end_dist - fake_end_len
            
            fake_start_X = anchor_x + rel_start_x + (dir_start_x * fake_start_len)
            fake_start_Y = anchor_y + rel_start_y + (dir_start_y * fake_start_len)
            fake_end_X = anchor_x + rel_end_x + (dir_end_x * fake_end_len)
            fake_end_Y = anchor_y + rel_end_y + (dir_end_y * fake_end_len)
            
            pred_home = D(fake_start_X, fake_start_Y, fake_start_dist, fake_end_X, fake_end_Y, fake_end_dist)
            adv_loss = -criterion(pred_home * 1000.0, anchor * 1000.0)
            
            usability_loss = lambda_usability * torch.mean(start_ratio_sq**2 + end_ratio_sq**2)
            # Geometry penalty: constants stay exactly 0.150/0.100 km (unchanged from the
            # original) for r_user<=1000m, matching every previously-validated result at
            # 200-1000m byte-for-byte. Only above 1000m -- outside the original training
            # range, where a fixed absolute-metre penalty becomes disproportionately harsh --
            # do the constants scale up proportionally with r_user, clamped so they never
            # shrink below their original value.
            r_user_km = batch_features[:, 8]
            c1_km = torch.clamp(0.150 * r_user_km, min=0.150)
            c2_km = torch.clamp(0.100 * r_user_km, min=0.100)
            geom_loss = lambda_geometry * torch.mean((dX_sq/c1_km)**2 + (dY_sq/c1_km)**2 + (dR_sq/c2_km)**2)
            
            loss_G = adv_loss + usability_loss + geom_loss
            loss_G.backward()
            opt_G.step()
            
            epoch_d_loss += loss_D.item()
            epoch_g_loss += loss_G.item()
            with torch.no_grad():
                epoch_error += torch.mean(torch.sqrt(torch.sum(((pred_home - anchor) * 1000.0)**2, dim=1))).cpu().item()

        if (epoch + 1) % 15 == 0:
            print(f"   Epoch [{epoch+1}/{num_epochs}] | D Loss: {epoch_d_loss/len(dataloader):.1f} | G Loss: {epoch_g_loss/len(dataloader):.1f} | Attacker Error: {epoch_error/len(dataloader):.1f}m")

    torch.save(G.state_dict(), weights_path)
    print(f"💾 Training Complete! Saved weights to '{weights_path}'.\n")


# ── 6. GEOMETRY & ROUTING HELPERS ──
def generate_fake_osm_decoy_directed(entry_pt, fake_path_len, G_cluster, true_home):
    if fake_path_len <= 1.0: return [], 0.0
    try:
        start_node = ox.distance.nearest_nodes(G_cluster, entry_pt[1], entry_pt[0])
        dy = entry_pt[0] - true_home[0]
        dx = entry_pt[1] - true_home[1]
        angle = np.arctan2(dy, dx)
        
        target_lat = entry_pt[0] + (fake_path_len / 111320.0) * np.sin(angle)
        target_lon = entry_pt[1] + (fake_path_len / (111320.0 * np.cos(np.deg2rad(entry_pt[0])))) * np.cos(angle)
        
        target_node = ox.distance.nearest_nodes(G_cluster, target_lon, target_lat)
        path_nodes = nx.shortest_path(G_cluster, start_node, target_node, weight='length')
        
        path_coords = []
        actual_len = 0.0
        for i in range(len(path_nodes)):
            node = path_nodes[i]
            path_coords.append((G_cluster.nodes[node]['y'], G_cluster.nodes[node]['x']))
            if i > 0:
                edge_data = G_cluster.get_edge_data(path_nodes[i-1], node)
                actual_len += edge_data[0].get('length', 20) if isinstance(edge_data, list) else edge_data.get('length', 20)
                
        return path_coords[::-1], actual_len
    except Exception:
        dx_lat = (fake_path_len / 111320.0) * np.sin(angle)
        dx_lon = (fake_path_len / (111320.0 * np.cos(np.deg2rad(entry_pt[0])))) * np.cos(angle)
        return [(entry_pt[0] + dx_lat, entry_pt[1] + dx_lon), entry_pt], fake_path_len

# Native Static baseline implementation
def fullDisguiseOfActivityCluster(activityClusterPath, r_user):
    activityCluster = ActivityCluster.ActivityCluster.initializeActivityClusterFromJson(activityClusterPath)
    geocentricData = DataRepresentationFactory.GeocentricDataRepresentationFactory().create_data_representation()
    sphericalData = DataRepresentationFactory.SphericalDataRepresentationFactory().create_data_representation()
    dataRep = DataRepresentationFactory.UTMDataRepresentationFactory().create_data_representation()
    
    try:
        cloackedCenter = dataRep.generateCloackedCenter(activityCluster.center, r_user)
    except AttributeError:
        # Custom dynamic geometric offset
        import math, random
        angle = random.uniform(0, 2 * math.pi)
        r_shift = random.uniform(0, r_user * 0.7)
        dx_lat = (r_shift / 111320.0) * math.sin(angle)
        dx_lon = (r_shift / (111320.0 * math.cos(math.radians(activityCluster.center[0])))) * math.cos(angle)
        cloackedCenter = [activityCluster.center[0] + dx_lat, activityCluster.center[1] + dx_lon]
    
    # Force write to JSON so EPZSearch can retrieve the exact static variables
    with open(activityClusterPath, 'r+') as jsonFile:
        jsonData = json.load(jsonFile)
        for entry in jsonData["ActivityClusterList"]:
            if entry["id"] == activityCluster.id:
                entry["cloackedCenter"] = cloackedCenter
                entry["cloackedRadius"] = r_user
        jsonFile.seek(0)
        json.dump(jsonData, jsonFile, indent=4)
        jsonFile.truncate()

    for activityPath in activityCluster.activityPathList:
        activity = Activity.Activity.initActivityFromPath(activityPath)
        activity.completeDisguiseActivityInCluster(
            activityCluster.center, r_user,
            cloackedCenter, sphericalData, geocentricData)
    return activityCluster

def apply_obfuscation(activityClusterPath, mode, G_eval=None, r_user=600):
    activityCluster = ActivityCluster.ActivityCluster.initializeActivityClusterFromJson(activityClusterPath)
    true_home = activityCluster.center
    
    # FIXED: Replaced 'transformer' typo with 'fromlatlon'
    home_x, home_y = fromlatlon.transform(true_home[1], true_home[0])
    
    if mode == 'static':
        fullDisguiseOfActivityCluster(activityClusterPath, r_user)
        return None

    G_cluster = None
    if mode == 'stravagante':
        try:
            G_cluster = ox.graph_from_point(true_home, dist=r_user + 1500, network_type='all', simplify=True)
        except: pass
    
    all_epzs = []
    for activityPath in activityCluster.activityPathList:
        activity = Activity.Activity.initActivityFromPath(activityPath)
        try: coordsList = activity.decodePolyline()
        except: continue
        
        start_hidden = [pt for pt in coordsList if geopy_distance(pt, true_home).meters < r_user]
        end_hidden = [pt for pt in coordsList[::-1] if geopy_distance(pt, true_home).meters < r_user]
        if len(start_hidden) < 2 or len(end_hidden) < 2: continue
        
        real_start_dist = sum(geopy_distance(start_hidden[i], start_hidden[i+1]).meters for i in range(len(start_hidden)-1))
        real_end_dist = sum(geopy_distance(end_hidden[i], end_hidden[i+1]).meters for i in range(len(end_hidden)-1))
        
        # Safe Initialization of loop fuzzing variables to prevent NameError scope leaks
        fuzz_start = 0.0
        fuzz_end = 0.0
        
        if mode == 'random_per_track':
            dX = random.uniform(-r_user * 0.45, r_user * 0.45)
            dY = random.uniform(-r_user * 0.45, r_user * 0.45)
            dR = random.uniform(0, r_user * 0.40)
            start_ratio, end_ratio = 0.0, 0.0 
            
        elif mode == 'stravagante':
            start_entry = coordsList[len(start_hidden)]
            end_entry = coordsList[-(len(end_hidden) + 1)]
            
            # FIXED: Replaced 'transformer' typo with 'fromlatlon'
            entry_start_x, entry_start_y = fromlatlon.transform(start_entry[1], start_entry[0])
            entry_end_x, entry_end_y = fromlatlon.transform(end_entry[1], end_entry[0])
            
            feat_tensor = torch.tensor([[(entry_start_x - home_x)/1000.0, (entry_start_y - home_y)/1000.0, real_start_dist/1000.0,
                                         (entry_end_x - home_x)/1000.0, (entry_end_y - home_y)/1000.0, real_end_dist/1000.0,
                                         0.0, 0.0, r_user/1000.0]], dtype=torch.float32, device=device)
            z = torch.randn(1, 16, device=device)
            with torch.no_grad():
                dX, dY, dR, start_ratio, end_ratio = G_eval(feat_tensor, z)
                dX, dY, dR, start_ratio, end_ratio = dX.cpu().item(), dY.cpu().item(), dR.cpu().item(), start_ratio.cpu().item(), end_ratio.cpu().item()
            
            fuzz_start = random.uniform(-15.0, 15.0)
            fuzz_end = random.uniform(-15.0, 15.0)

        cloacked_x, cloacked_y = home_x + dX, home_y + dY
        cloacked_lon, cloacked_lat = tolatlon.transform(cloacked_x, cloacked_y)
        cloackedCenter = [cloacked_lat, cloacked_lon]
        cloackedRadius = r_user + dR
        all_epzs.append((cloackedCenter, cloackedRadius))
        
        trimmed_coords = [pt for pt in coordsList if geopy_distance(pt, cloackedCenter).meters >= cloackedRadius]
        if len(trimmed_coords) < 3: continue
        
        if start_ratio > 0:
            start_fake_coords, start_actual = generate_fake_osm_decoy_directed(trimmed_coords[0], real_start_dist * start_ratio, G_cluster, true_home)
            end_fake_coords, end_actual = generate_fake_osm_decoy_directed(trimmed_coords[-1], real_end_dist * end_ratio, G_cluster, true_home)
        else:
            start_fake_coords, start_actual, end_fake_coords, end_actual = [], 0.0, [], 0.0
            
        new_coords = start_fake_coords + trimmed_coords + end_fake_coords[::-1]
        
        with open(activityClusterPath, 'r+') as jsonFile:
            jsonData = json.load(jsonFile)
            for entry in jsonData["ActivityClusterList"]:
                if entry["id"] == activityCluster.id:
                    entry["cloackedCenter"] = cloackedCenter
                    entry["cloackedRadius"] = cloackedRadius
            jsonFile.seek(0)
            json.dump(jsonData, jsonFile, indent=4)
            jsonFile.truncate()
        
        activity.maps["EPZ"] = activity.encodePolyline(new_coords)
        activity.maps["EPZ_start_distance"] = max(0.0, (real_start_dist - start_actual) + fuzz_start)
        activity.maps["EPZ_end_distance"] = max(0.0, (real_end_dist - end_actual) + fuzz_end)
        activity.updateActivityJson("map", activity.maps)
        
    return all_epzs


def run_attack_and_score(cluster_path, true_home, r_user, prefix, tau_e=22.95):
    activityCluster = ActivityCluster.ActivityCluster.initializeActivityClusterFromJson(cluster_path)
    try:
        with open(cluster_path, 'r', encoding="utf-8") as f:
            raw_data = json.load(f)["ActivityClusterList"][0]
        c_rad = raw_data.get('cloackedRadius')
        activityCluster.cloackedCenter = raw_data.get('cloackedCenter') or true_home
        activityCluster.cloackedRadius = c_rad if c_rad is not None else r_user
    except Exception:
        activityCluster.cloackedCenter = true_home
        activityCluster.cloackedRadius = r_user
        
    epzSearch = EPZSearch2.EPZSearch(activityCluster, data_representation=DataRepresentationFactory.UTMDataRepresentationFactory().create_data_representation())
    
    possible_locs = []
    est_center_dist = 9999
    est_radius = 9999
    try:
        epz_circles = epzSearch.epz_identification(10, 1600)
        if epz_circles:
            # Reconstruct estimated EPZ attributes
            center, radius, _ = epz_circles[0]
            est_lon, est_lat = tolatlon.transform(center[0], center[1])
            est_center_dist = geopy_distance((est_lat, est_lon), tuple(true_home)).meters
            est_radius = radius
            
            for c in epz_circles:
                # ── GEOGRAPHIC MATCHING FIX ──
                # Pass tau_snap = 100m to safely snap the off-road static crop coordinates back onto OSMnx streets
                locs = epzSearch.retriveSensitiveLocationv2(
                    c, activityCluster.center, activityCluster.cloackedCenter, 
                    activityCluster.cloackedRadius, cluster_num="X", tau_snap=100.0
                )
                if locs: possible_locs += locs
    except Exception as e:
        print(f"      [!] Attack crashed/failed: {e}")
        
    best_dist, best_lat, best_lon = 9999, None, None
    if possible_locs:
        best_loc = min(possible_locs, key=lambda l: geopy_distance((l['y'], l['x']), tuple(true_home)).meters)
        best_dist = geopy_distance((best_loc['y'], best_loc['x']), tuple(true_home)).meters
        best_lat, best_lon = best_loc['y'], best_loc['x']
        print(f"      {prefix} Closest Sensitive Loc: ({best_lat:.6f}, {best_lon:.6f}) | Dist: {best_dist:.1f} m")
        print(f"      {prefix} Est. EPZ Center Offset: {est_center_dist:.1f} m | Est. Radius: {est_radius:.1f} m")
    else:
        print(f"      {prefix} No sensitive locations found by attacker.")
        if est_center_dist != 9999:
            print(f"      {prefix} Est. EPZ Center Offset: {est_center_dist:.1f} m | Est. Radius: {est_radius:.1f} m")
        
    success = best_dist <= tau_e
    return best_dist, est_center_dist, est_radius, success, best_lat, best_lon

# ── 7. MAIN EXECUTION ──
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate StravaGANte across multiple configurations.")
    parser.add_argument("--radii", nargs="+", type=int, default=[600, 800], help="List of r_user radii to test")
    parser.add_argument("--tau", type=float, default=22.95, help="Success threshold in meters")
    parser.add_argument("--dataset_path", type=str, default="Data/Syntetic", help="Path to synthetic clusters")
    parser.add_argument("--weights_path", type=str, default="StravaGANte_Generator.pth", help="Path to trained GAN weights")
    parser.add_argument("--epochs", type=int, default=150, help="Number of epochs if training is required")
    parser.add_argument("--csv_path", type=str, default="detailed_results.csv", help="CSV log for additional analysis")
    args = parser.parse_args()

    existing_clusters = []
    for folder in os.listdir(args.dataset_path)[:1000]:
        cluster_file = os.path.join(args.dataset_path, folder, "ActivityClusterList.json")
        if os.path.exists(cluster_file):
            existing_clusters.append(cluster_file)

    random.seed(42)
    random.shuffle(existing_clusters)
    split_idx = int(len(existing_clusters) * 0.8)
    train_clusters = existing_clusters[:split_idx]
    test_clusters = existing_clusters[split_idx:]
    
    if not os.path.exists(args.weights_path):
        train_stravagante(train_clusters, args.weights_path, num_epochs=args.epochs)
        
    G_eval = PureBidirectionalGenerator().to(device)
    G_eval.load_state_dict(torch.load(args.weights_path, map_location=device))
    G_eval.eval()

    # Setup CSV Writer with complete structural metrics (Coordinates & Distances)
    file_exists = os.path.isfile(args.csv_path)
    
    # ── RESUME CHECK CONDITION ──
    # Check what (radius, cluster_id) configurations are already recorded in the CSV to bypass them
    completed_configs = {}
    if file_exists:
        try:
            with open(args.csv_path, mode='r', newline='', encoding="utf-8") as f:
                csv_reader = csv.reader(f)
                header = next(csv_reader, None)
                if header:
                    for row in csv_reader:
                        if len(row) >= 14:
                            try:
                                r_val = int(row[0])
                                c_val = str(row[1])
                                succ_s = bool(int(row[7]))
                                succ_r = bool(int(row[13]))
                                succ_g = bool(int(row[19]))
                                completed_configs[(r_val, c_val)] = (succ_s, succ_r, succ_g)
                            except (ValueError, IndexError):
                                continue
            print(f"📖 Found {len(completed_configs)} previously evaluated configurations in '{args.csv_path}'. Running in resume mode.")
        except Exception as e:
            print(f"⚠️ Warning: Could not read existing CSV file to determine resume state: {e}")

    csv_file = open(args.csv_path, mode='a', newline='')
    csv_writer = csv.writer(csv_file)
    if not file_exists:
        csv_writer.writerow([
            "radius", "cluster_id", 
            "static_closest_dist", "static_est_epz_center_dist", "static_est_epz_radius", "static_lat", "static_lon", "static_success", 
            "random_closest_dist", "random_est_epz_center_dist", "random_est_epz_radius", "random_lat", "random_lon", "random_success", 
            "gan_closest_dist", "gan_est_epz_center_dist", "gan_est_epz_radius", "gan_lat", "gan_lon", "gan_success"
        ])

    print(f"🚀 Starting evaluation on {len(test_clusters)} unseen test clusters.")
    final_results = {}
    
    for r_user in args.radii:
        print(f"\n{'='*60}\n📡 CONFIGURATION: Radius = {r_user}m\n{'='*60}")
        
        config_stats = {'static': [], 'random': [], 'gan': []}
        
        for cluster in test_clusters:
            cluster_num = os.path.basename(os.path.dirname(cluster))
            
            # Check if this configuration was already processed
            if (r_user, cluster_num) in completed_configs:
                print(f"\n   [Cluster {cluster_num}] already evaluated for {r_user}m. Skipping (Restored from log)...")
                succ_s, succ_r, succ_g = completed_configs[(r_user, cluster_num)]
                config_stats['static'].append(succ_s)
                config_stats['random'].append(succ_r)
                config_stats['gan'].append(succ_g)
                continue

            true_home = ActivityCluster.ActivityCluster.initializeActivityClusterFromJson(cluster).center
            print(f"\n   [Cluster {cluster_num}]")
            
            # 1. Static Baseline
            apply_obfuscation(cluster, mode='static', r_user=r_user)
            best_s, est_c_s, est_r_s, succ_s, lat_s, lon_s = run_attack_and_score(cluster, true_home, r_user, prefix="[Static]", tau_e=args.tau)
            config_stats['static'].append(succ_s)
            
            # 2. Random Baseline
            apply_obfuscation(cluster, mode='random_per_track', r_user=r_user)
            best_r, est_c_r, est_r_r, succ_r, lat_r, lon_r = run_attack_and_score(cluster, true_home, r_user, prefix="[Random]", tau_e=args.tau)
            config_stats['random'].append(succ_r)
            
            # 3. StravaGANte
            apply_obfuscation(cluster, mode='stravagante', G_eval=G_eval, r_user=r_user)
            best_g, est_c_g, est_r_g, succ_g, lat_g, lon_g = run_attack_and_score(cluster, true_home, r_user, prefix="[GAN]", tau_e=args.tau)
            config_stats['gan'].append(succ_g)
            
            # Append detailed metrics (Distances + Coordinates + Circle Estimations) to CSV for plotting
            csv_writer.writerow([
                r_user, cluster_num, 
                best_s, est_c_s, est_r_s, lat_s, lon_s, int(succ_s), 
                best_r, est_c_r, est_r_r, lat_r, lon_r, int(succ_r), 
                best_g, est_c_g, est_r_g, lat_g, lon_g, int(succ_g)
            ])
            csv_file.flush() 
            
            def fmt(d): return f"{d:.1f}m" if d != 9999 else "N/A"
            print(f"   => SUMMARY: Static: {fmt(best_s):>8} | Random: {fmt(best_r):>8} | StravaGANte: {fmt(best_g):>8}")

        n_test = len(test_clusters)
        final_results[r_user] = {
            'Static': sum(config_stats['static']) / max(n_test, 1),
            'Random': sum(config_stats['random']) / max(n_test, 1),
            'StravaGANte': sum(config_stats['gan']) / max(n_test, 1)
        }
        
        print(f"\n📊 RESULTS FOR RADIUS {r_user}m:")
        print(f"   Static Success:      {sum(config_stats['static'])}/{n_test} ({final_results[r_user]['Static']:.1%})")
        print(f"   Random Success:      {sum(config_stats['random'])}/{n_test} ({final_results[r_user]['Random']:.1%})")
        print(f"   StravaGANte Success: {sum(config_stats['gan'])}/{n_test} ({final_results[r_user]['StravaGANte']:.1%})")

    csv_file.close()
    
    with open("results_summary.json", "w") as f:
        json.dump(final_results, f, indent=4)
        
    print("\n✅ All experiments complete. Results saved to 'results_summary.json'.")