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

        center = minimize(f_2, center_estimate, bounds=bounds, options={'maxiter': 10})
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
            prev_centroids = [self.fit_circle([P[i] for i in range(len(P)) if clusters[i] == j])[0] for j in range(k)]
            for iteration in range(max_iteration):
                new_clusters = np.zeros(len(P), dtype=int)
                for i, point in enumerate(P):
                    distances = [self.euclidean_distance(point, UTMDataRepresentation.UTMEndpoint(*prev_centroids[l], '', '', 0)) for l in range(k)]
                    new_clusters[i] = int(np.argmin(distances))
                new_centroids = [self.fit_circle([P[i] for i in range(len(P)) if new_clusters[i] == j])[0] for j in range(k)]

                centroid_changes = [self.euclidean_distance(UTMDataRepresentation.UTMEndpoint(*prev_centroids[i], '', '', 0), UTMDataRepresentation.UTMEndpoint(*new_centroids[i], '', '', 0)) for i in range(k)]
                if all(change < tau_converged for change in centroid_changes):
                    break

                clusters = new_clusters
                prev_centroids = new_centroids
            else:
                print("max iterations without convergence")

            disjoint = True
            for i in range(k):
                center, radius = self.fit_circle([P[j] for j in range(len(P)) if clusters[j] == i])
                if any(self.euclidean_distance(point, UTMDataRepresentation.UTMEndpoint(center[0], center[1], '', '', 0)) > tau_disjoint for point in [P[j] for j in range(len(P)) if clusters[j] == i]):
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

    def retriveSensitiveLocationv2(self, epz_circle, realPOI, cloackedCenter, realRadius, cluster_num, tau_snap=100, eps=30, min_samples=1):

        while True:
            try:
                app = self.tolatlon.transform(*epz_circle[0])
                G = ox.graph_from_point(app, 500, network_type='all', simplify=True)
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
                positive_differences.at[node, col] = pow(abs(diff), 2)

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
        for index, row in column_sums.head(5).iterrows():
            element = G.nodes[index]
            element["distances"] = row['distances']
            if is_within_circle(element['x'], element['y'], epz_lon, epz_lat, epz_circle[1]):
                resultArray.append(element)

        self.plot_heatmap_clusters_over_osmnx(G, column_sums, resultArray, self.tolatlon.transform(*epz_circle[0]), epz_circle[1], tuple(realPOI), tuple(cloackedCenter), realRadius, cluster_num)

        return resultArray

    def plot_heatmap_clusters_over_osmnx(self, G, column_sums, sensitive_locations, epz_circle, epz_radius, realPOI, cloackedCenter, realRadius, cluster_num):
        column_sums = column_sums.sort_values(by='distances')

        node_x = []
        node_y = []
        node_values = []

        minValue = column_sums['distances'].min()
        for node, value in column_sums.iterrows():
            value = value['distances']
            if node in G.nodes:
                x, y = G.nodes[node]['x'], G.nodes[node]['y']
                node_x.append(x)
                node_y.append(y)
                node_values.append(value)
            if value > minValue*2:
                break

        fig, ax = ox.plot_graph(G, show=False, close=False, bgcolor='w', node_color='gray', edge_color='gray', edge_linewidth=0.8)

        sensitive_plotted = False
        if sensitive_locations is not None:
            for loc in sensitive_locations:
                if isinstance(loc, dict):
                    lon = loc.get('x', None)
                    lat = loc.get('y', None)
                elif isinstance(loc, (list, tuple)) and len(loc) == 2:
                    lat, lon = loc
                else:
                    continue
                if lon is not None and lat is not None and not sensitive_plotted:
                    ax.plot(lon, lat, 'yo', markersize=6, alpha=1.0, label=f'Sensitive Locs ({len(sensitive_locations)})', zorder=10)
                    sensitive_plotted = True
                else:
                    ax.plot(lon, lat, 'yo', markersize=6, alpha=1.0, zorder=10)

        node_lons = [G.nodes[n]['x'] for n in G.nodes]
        node_lats = [G.nodes[n]['y'] for n in G.nodes]

        extra_lons = []
        extra_lats = []
        if cloackedCenter is not None:
            cloackedCenter_lat, cloackedCenter_lon = cloackedCenter
            ax.plot(cloackedCenter_lon, cloackedCenter_lat, 'go', markersize=8, alpha=0.8, label=f'Cloacked r={realRadius}m', zorder=10)
            radius_deg_lat = realRadius / 111320.0
            radius_deg_lon = realRadius / (111320.0 * np.cos(np.deg2rad(cloackedCenter_lat)))
            ellipse = Ellipse((cloackedCenter_lon, cloackedCenter_lat), 2*radius_deg_lon, 2*radius_deg_lat, edgecolor='green', fill=False, linewidth=2, alpha=0.5, zorder=9)
            ax.add_patch(ellipse)
            extra_lons.extend([cloackedCenter_lon - radius_deg_lon, cloackedCenter_lon + radius_deg_lon])
            extra_lats.extend([cloackedCenter_lat - radius_deg_lat, cloackedCenter_lat + radius_deg_lat])

        if realPOI is not None:
            realPOI_lat, realPOI_lon = realPOI
            ax.plot(realPOI_lon, realPOI_lat, 'ro', markersize=8, alpha=0.8, label=f'RealPOI', zorder=10)

        if epz_circle is not None:
            epz_lat, epz_lon = epz_circle
            ax.plot(epz_lon, epz_lat, 'bo', markersize=8, alpha=0.8, label=f'EPZ r={epz_radius}m', zorder=10)
            radius_deg_lat = epz_radius / 111320.0
            radius_deg_lon = epz_radius / (111320.0 * np.cos(np.deg2rad(epz_lat)))
            ellipse = Ellipse((epz_lon, epz_lat), 2*radius_deg_lon, 2*radius_deg_lat, edgecolor='blue', fill=False, linewidth=2, alpha=0.5, zorder=9)
            ax.add_patch(ellipse)
            extra_lons.extend([epz_lon - radius_deg_lon, epz_lon + radius_deg_lon])
            extra_lats.extend([epz_lat - radius_deg_lat, epz_lat + radius_deg_lat])

        all_lons = node_lons + extra_lons
        all_lats = node_lats + extra_lats

        min_lon, max_lon = min(all_lons), max(all_lons)
        min_lat, max_lat = min(all_lats), max(all_lats)

        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2
        span = max(max_lon - min_lon, max_lat - min_lat)

        ax.set_xlim(center_lon - span / 2, center_lon + span / 2)
        ax.set_ylim(center_lat - span / 2, center_lat + span / 2)
        ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, crs='EPSG:4326')

        if realPOI is not None or epz_circle is not None:
            ax.legend(title=f"ACTIVITY {cluster_num}", title_fontproperties={'weight': 'bold'})
        fig.show()
