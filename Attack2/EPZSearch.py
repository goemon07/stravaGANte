from Models import Activity
from DataRepresentation import DataRepresentationFactory
from DataRepresentation.DataRepresentation import UTMDataRepresentation

import numpy as np
from sklearn.cluster import KMeans, DBSCAN
from scipy.optimize import minimize

import pandas as pd
import osmnx as ox
import networkx as nx
import contextily as ctx
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from matplotlib.patches import Ellipse

import time
from requests.exceptions import RequestException, ConnectionError
from urllib3.exceptions import ProtocolError
from requests import exceptions as req_exc

from geopy.distance import distance as geopy_distance
from pyproj import Transformer


def is_within_circle(node_x, node_y, center_x, center_y, radius_m):
    dx = (node_x - center_x) * 111320 * np.cos(np.deg2rad(center_y))
    dy = (node_y - center_y) * 111320
    distance = np.sqrt(dx**2 + dy**2)
    return distance <= radius_m


class EPZSearch():

    def __init__(self, activityCluster, data_representation=DataRepresentationFactory.UTMDataRepresentationFactory().create_data_representation()):
        self.DataRepresentation = data_representation
        epz_radius = getattr(activityCluster, 'cloackedRadius', 400)
        self.EndpointsList = self.DataRepresentation.getActivityEndpointList(activityCluster.activityPathList, epz_radius=epz_radius)
        self.center = None
        self.tolatlon = Transformer.from_crs("EPSG:3857", "EPSG:4326")
        self.fromlatlon = Transformer.from_crs("EPSG:4326", "EPSG:3857")

    @staticmethod
    def euclidean_distance(point1, point2):
        if isinstance(point1, list) or isinstance(point1, tuple):
            point1 = type('Point', (), {'x': point1[0], 'y': point1[1]})()
        if isinstance(point2, list) or isinstance(point2, tuple):
            point2 = type('Point', (), {'x': point2[0], 'y': point2[1]})()
        return np.linalg.norm(np.array([point1.x, point1.y]) - np.array([point2.x, point2.y]))

    def fit_circle(self, points):
        if len(points) == 0:
            return (0, 0), 0

        coords = np.array([[point.x, point.y] for point in points])

        def calc_R(xc, yc):
            return np.sqrt((coords[:, 0] - xc)**2 + (coords[:, 1] - yc)**2)

        def f_2(c):
            Ri = calc_R(*c)
            return ((Ri - Ri.mean())**2).sum()

        center_estimate = np.mean(coords, axis=0)
        bounds = [(np.min(coords[:, 0]), np.max(coords[:, 0])),
                  (np.min(coords[:, 1]), np.max(coords[:, 1]))]

        center = minimize(f_2, center_estimate, bounds=bounds, options={'maxiter': 1000})
        center_xy = center.x

        lat_c, lon_c = self.tolatlon.transform(center_xy[0], center_xy[1])
        center_latlon = (lat_c, lon_c)
        point_latlon = []
        for p in points:
            lat_p, lon_p = self.tolatlon.transform(p.x, p.y)
            point_latlon.append((lat_p, lon_p))

        distances = np.array([geopy_distance(center_latlon, pt).meters for pt in point_latlon])
        max_distance = distances.max() if distances.size > 0 else 0.0
        selected_radius = max(200, int(np.ceil(max_distance / 200.0)) * 200)
        return (center_xy[0], center_xy[1]), selected_radius

    def epz_identification(self, tau_converged, tau_disjoint):
        k = 1
        P = self.EndpointsList
        max_iteration = 10
        coords = np.array([[p.x, p.y] for p in P])
        clusters = KMeans(n_clusters=k, random_state=0).fit(coords).labels_
        while True:
            # Track (center, radius) pairs — assignment uses distance to circle edge
            prev_circles = [self.fit_circle([P[i] for i in range(len(P)) if clusters[i] == j]) for j in range(k)]
            for iteration in range(max_iteration):
                new_clusters = np.zeros(len(P), dtype=int)
                for i, point in enumerate(P):
                    # Paper Alg.1: dist(p, C_i) = |dist(p, center_i) - radius_i|
                    distances = [
                        abs(self.euclidean_distance(point, UTMDataRepresentation.UTMEndpoint(*prev_circles[l][0], '', '', 0)) - prev_circles[l][1])
                        for l in range(k)
                    ]
                    new_clusters[i] = int(np.argmin(distances))
                new_circles = [self.fit_circle([P[i] for i in range(len(P)) if new_clusters[i] == j]) for j in range(k)]

                centroid_changes = [
                    self.euclidean_distance(
                        UTMDataRepresentation.UTMEndpoint(*prev_circles[i][0], '', '', 0),
                        UTMDataRepresentation.UTMEndpoint(*new_circles[i][0], '', '', 0)
                    ) for i in range(k)
                ]
                if all(change < tau_converged for change in centroid_changes):
                    break

                clusters = new_clusters
                prev_circles = new_circles
            else:
                print("max iterations without convergence")

            disjoint = True
            for i in range(k):
                center, radius = self.fit_circle([P[j] for j in range(len(P)) if clusters[j] == i])
                # Paper Alg.1: dist(p, C_i) = |dist(p, center) - radius| > tau_disjoint
                if any(
                    abs(self.euclidean_distance(point, UTMDataRepresentation.UTMEndpoint(center[0], center[1], '', '', 0)) - radius) > tau_disjoint
                    for point in [P[j] for j in range(len(P)) if clusters[j] == i]
                ):
                    disjoint = False
                    break

            if disjoint:
                break

            k += 1
            clusters = KMeans(n_clusters=k, random_state=0).fit(coords).labels_

        epz_results = []
        for j in range(k):
            cluster_points = [P[i] for i in range(len(P)) if clusters[i] == j]
            center, radius = self.fit_circle(cluster_points)
            epz_results.append((center, radius, cluster_points))

        return epz_results

    def retriveSensitiveLocationv2(self, epz_circle, realPOI, cloackedCenter, realRadius, cluster_num, tau_snap=10, eps=20, min_samples=1):

        while True:
            try:
                app = self.tolatlon.transform(*epz_circle[0])
                G = ox.graph_from_point(app, int(epz_circle[1]) + 200, network_type='all', simplify=True)
                break
            except (req_exc.ConnectTimeout, ConnectionError, ProtocolError, req_exc.RequestException):
                print(f"Connessione fallita, ritento")
            raise Exception(f"Impossibile connettersi")

        G = ox.truncate.largest_component(G, strongly=True)

        nodeList = []
        endpointNodeDict = {}
        endpointDistanceDict = {}
        for endpoint in self.EndpointsList:
            projected_coords = self.tolatlon.transform(*endpoint.getCoords())
            node, distance = ox.distance.nearest_nodes(G, *projected_coords[::-1], return_dist=True)
            if distance < tau_snap:
                nodeList.append((node, endpoint.distance, endpoint))
                endpointNodeDict[endpoint.getID()] = node
                endpointDistanceDict[endpoint.getID()] = endpoint.distance

        all_nodes = list(G.nodes())

        distances_df = pd.DataFrame(index=[node[2].getID() for node in nodeList], columns=all_nodes)

        for nodeArr in nodeList:
            node = nodeArr[0]
            lengths, paths = nx.single_source_dijkstra(G, source=node, weight='length')
            for target_node, distance in lengths.items():
                distances_df.at[nodeArr[2].getID(), target_node] = distance
        distances_df = distances_df.dropna(axis=1, how='all')

        node_coords = [
            self.fromlatlon.transform(G.nodes[node[0]]['y'], G.nodes[node[0]]['x'])
            for node in nodeList
        ]

        X = np.array(node_coords)
        if len(X) == 0:
            return None

        dbscan = DBSCAN(eps=eps, min_samples=min_samples)
        db = dbscan.fit(X)
        labels = db.labels_
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

        clustered_nodes = pd.DataFrame({
            'node': [node[2].getID() for node in nodeList],
            'distance': [node[1] for node in nodeList],
            'x': X[:, 0],
            'y': X[:, 1],
            'cluster': labels
        })

        max_distance_df = distances_df.max(axis=1).reset_index()
        max_distance_df.columns = ['node', 'max_distance']

        cluster_stats = clustered_nodes.groupby('cluster')['distance'].agg(['mean', 'std']).reset_index()
        cluster_stats.columns = ['cluster', 'mean_distance', 'std_distance']
        cluster_stats['up_threshold'] = cluster_stats['mean_distance'] + 3 * cluster_stats['std_distance']
        cluster_stats['down_threshold'] = cluster_stats['mean_distance'] - 3 * cluster_stats['std_distance']

        cluster_stats = cluster_stats.merge(clustered_nodes, on="cluster")
        cluster_stats = cluster_stats.merge(max_distance_df, on="node")

        cluster_stats['is_outlier'] = (cluster_stats['distance'] < cluster_stats['down_threshold']) | \
                                    (cluster_stats['distance'] > cluster_stats['max_distance'])

        filtered_nodes = cluster_stats[~cluster_stats['is_outlier']]
        nodes_to_keep = filtered_nodes['node'].tolist()
        filtered_distances_df = distances_df.loc[nodes_to_keep]

        positive_differences = filtered_distances_df.copy()
        for node, row in filtered_distances_df.iterrows():
            distance = endpointDistanceDict[node]
            for col in filtered_distances_df.columns:
                diff = row[col] - distance
                positive_differences.at[node, col] = abs(diff)

        column_sums = positive_differences.mean(axis=0).to_frame()
        column_sums.columns = ['distances']
        column_sums['distances'] = column_sums['distances'].astype(float)
        column_sums = column_sums.sort_values(by='distances')

        min_sum = column_sums['distances'].min()
        if column_sums['distances'].isna().all():
            min_node = None
        else:
            min_node = column_sums['distances'].idxmin(skipna=True)

        resultArray = []
        epz_lat, epz_lon = self.tolatlon.transform(*epz_circle[0])
        for index, row in column_sums.iterrows():
            element = dict(G.nodes[index])
            if is_within_circle(element['x'], element['y'], epz_lon, epz_lat, epz_circle[1]):
                element["distances"] = row['distances']
                resultArray.append(element)
                if len(resultArray) >= 5:
                    break

        self.plot_heatmap_clusters_over_osmnx(G, column_sums, resultArray, self.tolatlon.transform(*epz_circle[0]), epz_circle[1], tuple(realPOI), tuple(cloackedCenter), realRadius, cluster_num)

        return resultArray

    def plot_heatmap_clusters_over_osmnx(self, G, column_sums, sensitive_locations, epz_circle, epz_radius, realPOI, cloackedCenter, realRadius, cluster_num):
        column_sums = column_sums.sort_values(by='distances')

        node_x, node_y, node_values = [], [], []
        minValue = column_sums['distances'].min()
        for node, row in column_sums.iterrows():
            value = float(row['distances'])
            if node in G.nodes:
                node_x.append(G.nodes[node]['x'])
                node_y.append(G.nodes[node]['y'])
                node_values.append(value)
            if value > minValue * 2:
                break

        fig, ax = ox.plot_graph(G, show=False, close=False, bgcolor='#f8f8f8',
                                node_color='#cccccc', node_size=4,
                                edge_color='#b0b0b0', edge_linewidth=0.7,
                                figsize=(14, 12))

        if node_values:
            norm = mcolors.Normalize(vmin=min(node_values), vmax=max(node_values))
            sc = ax.scatter(node_x, node_y, c=node_values, cmap=cm.RdYlGn_r, norm=norm,
                            s=55, zorder=8, alpha=0.85, edgecolors='none')
            plt.colorbar(sc, ax=ax, label='Distance score (lower = better candidate)', shrink=0.55, pad=0.01)

        extra_lons, extra_lats = [], []

        if cloackedCenter is not None:
            clat, clon = cloackedCenter
            r_lat = realRadius / 111320.0
            r_lon = realRadius / (111320.0 * np.cos(np.deg2rad(clat)))
            ax.add_patch(Ellipse((clon, clat), 2*r_lon, 2*r_lat,
                                 edgecolor='#2ca02c', fill=False, linewidth=2.5,
                                 linestyle='--', alpha=0.8, zorder=9))
            ax.plot(clon, clat, 'o', color='#2ca02c', markersize=10, zorder=11,
                    label=f'Real EPZ center  (r={realRadius} m)')
            extra_lons.extend([clon - r_lon, clon + r_lon])
            extra_lats.extend([clat - r_lat, clat + r_lat])

        if epz_circle is not None:
            elat, elon = epz_circle
            r_lat = epz_radius / 111320.0
            r_lon = epz_radius / (111320.0 * np.cos(np.deg2rad(elat)))
            ax.add_patch(Ellipse((elon, elat), 2*r_lon, 2*r_lat,
                                 edgecolor='#1f77b4', fill=False, linewidth=2.5,
                                 alpha=0.8, zorder=9))
            ax.plot(elon, elat, 's', color='#1f77b4', markersize=10, zorder=11,
                    label=f'Est. EPZ center  (r={epz_radius} m)')
            extra_lons.extend([elon - r_lon, elon + r_lon])
            extra_lats.extend([elat - r_lat, elat + r_lat])

        if realPOI is not None:
            rlat, rlon = realPOI
            ax.plot(rlon, rlat, '*', color='#d62728', markersize=18, zorder=12, label='Real POI')
            extra_lons.append(rlon)
            extra_lats.append(rlat)

            if epz_circle is not None:
                elat, elon = epz_circle
                dist_est = geopy_distance((rlat, rlon), (elat, elon)).meters
                mid_lon = (rlon + elon) / 2
                mid_lat = (rlat + elat) / 2
                ax.annotate(f'{dist_est:.0f} m', xy=(mid_lon, mid_lat), fontsize=9,
                            color='#1f77b4', ha='center', va='center', fontweight='bold',
                            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='#1f77b4'))

        if sensitive_locations:
            for i, loc in enumerate(sensitive_locations):
                if isinstance(loc, dict):
                    lon, lat = loc.get('x'), loc.get('y')
                elif isinstance(loc, (list, tuple)) and len(loc) == 2:
                    lat, lon = loc
                else:
                    continue
                if lon is not None and lat is not None:
                    label = f'Sensitive locs ({len(sensitive_locations)})' if i == 0 else '_nolegend_'
                    ax.plot(lon, lat, 'D', color='#ff7f0e', markersize=9, zorder=11, label=label)

        node_lons = [G.nodes[n]['x'] for n in G.nodes]
        node_lats = [G.nodes[n]['y'] for n in G.nodes]
        all_lons = node_lons + extra_lons
        all_lats = node_lats + extra_lats
        c_lon = (min(all_lons) + max(all_lons)) / 2
        c_lat = (min(all_lats) + max(all_lats)) / 2
        span = max(max(all_lons) - min(all_lons), max(all_lats) - min(all_lats)) * 1.15
        ax.set_xlim(c_lon - span / 2, c_lon + span / 2)
        ax.set_ylim(c_lat - span / 2, c_lat + span / 2)

        ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, crs='EPSG:4326')

        title_parts = [f'Cluster {cluster_num}']
        if realPOI is not None and epz_circle is not None:
            dist_poi = geopy_distance(realPOI, epz_circle).meters
            title_parts.append(f'Est. EPZ → Real POI: {dist_poi:.0f} m')
        ax.set_title('\n'.join(title_parts), fontsize=13, fontweight='bold', pad=10)
        ax.legend(loc='upper right', fontsize=9, framealpha=0.9, edgecolor='#888888')
        fig.tight_layout()
        plt.show()
