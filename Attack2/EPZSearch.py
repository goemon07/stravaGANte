from Models import Activity
from DataRepresentation import DataRepresentation, DataRepresentationFactory
from DataRepresentation.DataRepresentation import UTMDataRepresentation

import numpy as np
from sklearn.cluster import KMeans, DBSCAN
from scipy.optimize import minimize
from shapely.geometry import LineString

import pandas as pd
import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
import utm

import requests
from requests.exceptions import ConnectionError, ConnectTimeout
from urllib3.exceptions import ProtocolError
import seaborn as sns
from pyproj import Transformer

import networkx as nx
import pandas as pd
import numpy as np
import time
from sklearn.cluster import DBSCAN
from requests.exceptions import RequestException, ConnectionError
from urllib3.exceptions import ProtocolError
from requests import exceptions as req_exc
import osmnx as ox

from geopy.distance import distance as geopy_distance
import contextily as ctx
from matplotlib.patches import Ellipse

def is_within_circle(node_x, node_y, center_x, center_y, radius_m):
    # Approximate meters to degrees for latitude/longitude
    # For small distances, this is usually sufficient
    dx = (node_x - center_x) * 111320 * np.cos(np.deg2rad(center_y))
    dy = (node_y - center_y) * 111320
    distance = np.sqrt(dx**2 + dy**2)
    return distance <= radius_m
class EPZSearch():

    def __init__(self, activityCluster, data_representation = DataRepresentationFactory.UTMDataRepresentationFactory().create_data_representation()):
        self.DataRepresentation = data_representation
        self.EndpointsList = self.DataRepresentation.getActivityEndpointList(activityCluster.activityPathList)
        #self.zoneLetter = self.EndpointsList[0].zoneLetter
        #self.zoneNumber = self.EndpointsList[0].zoneNumber
        self.center = None
        self.tolatlon= Transformer.from_crs("EPSG:3857", "EPSG:4326")
        self.fromlatlon= Transformer.from_crs("EPSG:4326", "EPSG:3857")

    def printEndpointList(self):
        for endpoint in self.EndpointsList:
            print(endpoint)

    def setTrueCenter(self, center):
        self.center = center

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
        center_xy = center.x  # still in EPSG:3857

        lon_c, lat_c = self.tolatlon.transform(center_xy[0], center_xy[1])
        center_latlon = (lat_c, lon_c)
        point_latlon = []
        for p in points:
            lon_p, lat_p = self.tolatlon.transform(p.x, p.y)
            point_latlon.append((lat_p, lon_p))

        # compute geodesic distances in meters and choose radius as next 200m bucket
        distances = np.array([geopy_distance(center_latlon, pt).meters for pt in point_latlon])
        max_distance = distances.max() if distances.size > 0 else 0.0
        # round up to nearest 200 m (you can change the quantization if you prefer continuous radius)
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
                # Assignment step: distance to current centroids (avoid recomputing fit_circle per point)
                new_clusters = np.zeros(len(P), dtype=int)
                for i, point in enumerate(P):
                    distances = [self.euclidean_distance(point, UTMDataRepresentation.UTMEndpoint(*prev_centroids[l], '', '', 0)) for l in range(k)]
                    new_clusters[i] = int(np.argmin(distances))
                # Update step: recompute centroids based on new assignment
                new_centroids = [self.fit_circle([P[i] for i in range(len(P)) if new_clusters[i] == j])[0] for j in range(k)]
                
                # Check for convergence
                centroid_changes = [self.euclidean_distance(UTMDataRepresentation.UTMEndpoint(*prev_centroids[i], '', '', 0), UTMDataRepresentation.UTMEndpoint(*new_centroids[i], '', '', 0)) for i in range(k)]
                if all(change < tau_converged for change in centroid_changes):
                    break
                
                clusters = new_clusters
                prev_centroids = new_centroids
            else:
                print("max iterations without convergence")
            
            # Check for disjoint EPZs
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
    
    def retriveSensitiveLocationv2(self, epz_circle, realPOI, cloackedCenter, realRadius, cluster_num, tau_snap = 100, eps = 30, min_samples = 1):
    
        # Retrieve the graph
        while True:
            try:
                app = self.tolatlon.transform(*epz_circle[0])
                G = ox.graph_from_point(app, 500, network_type='all', simplify=True)
                break
            except (req_exc.ConnectTimeout, ConnectionError, ProtocolError, req_exc.RequestException):
                print(f"Connessione fallita, ritento")
            raise Exception(f"Impossibile connettersi")

        # Prepare the graph
        G = ox.truncate.largest_component(G, strongly=True)

        # Calculate nearest nodes for each endpoint
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

        # Distance dataframe: rows = endpoint IDs, cols = all graph nodes
        distances_df = pd.DataFrame(index=[node[2].getID() for node in nodeList], columns=all_nodes)

        for nodeArr in nodeList:
            node = nodeArr[0]
            lengths, paths = nx.single_source_dijkstra(G, source=node, weight='length')
            for target_node, distance in lengths.items():
                distances_df.at[nodeArr[2].getID(), target_node] = distance
        distances_df = distances_df.dropna(axis=1, how='all')

        #### Identifying entry gates Y ####
        node_coords = [
            self.fromlatlon.transform(G.nodes[node[0]]['y'], G.nodes[node[0]]['x'])
            for node in nodeList
        ]

        X = np.array(node_coords)
        if len(X) == 0:
            # print('No cords')
            return None

        dbscan = DBSCAN(eps=eps, min_samples=min_samples)
        db = dbscan.fit(X)
        labels = db.labels_
        # print('Labels: ', labels)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        # print(f'            Estimated number of clusters: {n_clusters}')

        clustered_nodes = pd.DataFrame({
            'node': [node[2].getID() for node in nodeList],
            'distance': [node[1] for node in nodeList],
            'x': X[:, 0],
            'y': X[:, 1],
            'cluster': labels
        })

        #### Discarding Outliers ####
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

        #### Debug: Finding node of actual POI ####
        actualPOI = [11.917602, 45.426466]  # lon, lat
        actualPOI_projected = self.fromlatlon.transform(actualPOI[1], actualPOI[0])
        nodePOI, distancePOI = ox.distance.nearest_nodes(G, *actualPOI_projected[::-1], return_dist=True)

        #### Finding the location ####
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
            # Only add if within EPZ circle
            if is_within_circle(element['x'], element['y'], epz_lon, epz_lat, epz_circle[1]):
                resultArray.append(element)

        self.plot_heatmap_clusters_over_osmnx(G, column_sums, resultArray, self.tolatlon.transform(*epz_circle[0]), epz_circle[1], tuple(realPOI), tuple(cloackedCenter), realRadius, cluster_num)

        return resultArray


    def retriveSensitiveLocation(self, epz_circle, realPOI, tau_snap = 50, eps = 30, min_samples = 1):
        
        # Retrieve the graph
        while True:
            try:
                #app = utm.to_latlon(*epz_circle[0], *self.getZoneInfo())
                print("epz circle", epz_circle[0])
                print(self.tolatlon.transform(*epz_circle[0]))
                app = self.tolatlon.transform(*epz_circle[0])
                G = ox.graph_from_point(app, 500, network_type='all') #tau_snap)
                break
            except (ConnectTimeout, ConnectionError, ProtocolError, requests.exceptions.RequestException) as e:
                print(f"Connessione fallita, ritento")
            raise Exception(f"Impossibile connettersi")

        # Prepare the graph
        G = ox.truncate.largest_component(G)

        # enhance graph by chaining
        #G = self.enhance_graph(G)
        
        
        # Calculate nearest nodes for each endpoint
        nodeList = []
        endpointNodeDict = {}
        endpointDistanceDict = {}
        for endpoint in self.EndpointsList:
            #node, distance = ox.distance.nearest_nodes(G, *utm.to_latlon(*endpoint.getCoords())[::-1], return_dist=True)
            node, distance = ox.distance.nearest_nodes(G, *self.tolatlon.transform(*endpoint.getCoords())[::-1], return_dist=True)
            print(node)
            if distance < tau_snap:
                nodeList.append((node, endpoint.distance, endpoint))
                endpointNodeDict[endpoint.getID()] = node
                endpointDistanceDict[endpoint.getID()] = endpoint.distance
        
        
        all_nodes = list(G.nodes())
        

        # Inizializza un DataFrame con indici come i nodi di partenza e colonne come tutti i nodi
        distances_df = pd.DataFrame(index=[node[2].getID() for node in nodeList], columns=all_nodes)

        # Itera attraverso ciascun nodo di partenza per calcolare le distanze minime
        for nodeArr in nodeList:
            node=nodeArr[0]
            # Calcola le distanze del percorso minimo da 'start_node' a tutti gli altri nodi
            lengths, paths = nx.single_source_dijkstra(G, source=node, weight='length')
            # Aggiungi le distanze calcolate alla riga del DataFrame corrispondente al nodo di partenza
            for target_node, distance in lengths.items():
                distances_df.at[nodeArr[2].getID(), target_node] = distance
        distances_df = distances_df.dropna(axis=1, how='all')


     ####         Identifing entry gates Y          ####
        
        node_coords = [utm.from_latlon(G.nodes[node[0]]['y'], G.nodes[node[0]]['x'])[:2] for node in nodeList]

    
        X = np.array(node_coords)
        if len(X) == 0:
            return None
        dbscan = DBSCAN(eps=eps, min_samples = min_samples)
        db = dbscan.fit(X)

        print(f"X: {X}")
        labels = db.labels_

        # Number of clusters in labels, ignoring noise if present (-1 label)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        print(f'Estimated number of clusters: {n_clusters}')

        # Create a DataFrame to view results
        clustered_nodes = pd.DataFrame({'node': [node[2].getID() for node in nodeList], 'distance':[node[1] for node in nodeList], 'x': X[:, 0], 'y': X[:, 1], 'cluster': labels})
        



     ####        Discarding Outliers         ####

        #### Calculating Max for each row ####
        
        max_distance_df = distances_df.max(axis=1).reset_index()
        max_distance_df.columns = ['node', 'max_distance']

        
        #### Calculating deviation in Entry Gates ####
        cluster_stats = clustered_nodes.groupby('cluster')['distance'].agg(['mean', 'std']).reset_index()
        cluster_stats.columns = ['cluster', 'mean_distance', 'std_distance']

        cluster_stats['up_threshold'] = cluster_stats['mean_distance'] + 3 * cluster_stats['std_distance']
        cluster_stats['down_threshold'] = cluster_stats['mean_distance'] - 3 * cluster_stats['std_distance']

        cluster_stats= cluster_stats.merge(clustered_nodes, on="cluster")
        cluster_stats= cluster_stats.merge(max_distance_df, on="node")
        
        
        # Identify points that are outliers
        cluster_stats['is_outlier'] = (cluster_stats['distance'] < cluster_stats['down_threshold']) | (cluster_stats['distance'] > cluster_stats['max_distance'])
        
        # Filter out the outliers
        filtered_nodes = cluster_stats[~cluster_stats['is_outlier']]
        
        # Assume filtered_nodes contains the non-outlier nodes and the initial distances_df matrix
        # filtered_nodes DataFrame should contain at least a 'node' column with the nodes to keep

        # Get the list of nodes that are not outliers
        nodes_to_keep = filtered_nodes['node'].tolist()

        # Filter the distances_df to keep only these nodes
        filtered_distances_df = distances_df.loc[nodes_to_keep]
        


        ## Finding node of actual POI for debugging purposes
        actualPOI = [11.917602, 45.426466]
        nodePOI, distancePOI = ox.distance.nearest_nodes(G, *actualPOI, return_dist=True)
            

            
     ####    Finding the location        ####
        positive_differences = filtered_distances_df.copy()

        for node, row in filtered_distances_df.iterrows():
            distance = endpointDistanceDict[node]
            for col in filtered_distances_df.columns:
                diff = row[col] - distance
                positive_differences.at[node, col] = pow(abs(diff), 2)

        # Sum all rows grouped by columns
        column_sums = positive_differences.mean(axis=0)
        column_sums = column_sums.to_frame()
        column_sums.columns = ['distances']
        column_sums['distances'] = column_sums['distances'].astype(float)
        column_sums = column_sums.sort_values(by='distances')

        # Find the minimum of these column sums
        min_sum = column_sums.min()
        min_node = column_sums.idxmin().loc[column_sums.min().idxmin()]

        resultArray = []
        for index, row in column_sums.head(5).iterrows():
            element = G.nodes[index]
            element["distances"] = row['distances']
            resultArray.append(element)

        # self.plot_heatmap_clusters_over_osmnx(G, column_sums, X, labels)
        self.plot_heatmap_clusters_over_osmnx(G, column_sums, X, labels, self.tolatlon.transform(*epz_circle[0]), tuple(realPOI))
        
        return resultArray

    
    def retriveSensitiveLocationThroughClusters(self, epz_circle, realPOI, tau_snap=50, eps=30, min_samples=1):
        
        # Retrieve the graph
        #G = ox.graph_from_point(utm.to_latlon(*epz_circle[0], *self.getZoneInfo()), tau_snap)
        print("epz circle", epz_circle[0])
        print(self.tolatlon.transform(*epz_circle[0]))
        G = ox.graph_from_point(self.tolatlon.transform(*epz_circle[0]), tau_snap, network_type='all')

        # Prepare the graph
        G = ox.truncate.largest_component(G)

        # enhance graph by chaining
        #G = self.enhance_graph(G)
        
        
        # Calculate nearest nodes for each endpoint
        nodeList = []
        endpointNodeDict = {}
        endpointDistanceDict = {}
        for endpoint in self.EndpointsList:
            #node, distance = ox.distance.nearest_nodes(G, *utm.to_latlon(*endpoint.getCoords())[::-1], return_dist=True)
            node, distance = ox.distance.nearest_nodes(G, *self.tolatlon.transform(*endpoint.getCoords())[::-1], return_dist=True)
            if distance < tau_snap:
                nodeList.append((node, endpoint.distance, endpoint))
                endpointNodeDict[endpoint.getID()] = node
                endpointDistanceDict[endpoint.getID()] = endpoint.distance
        
        
        all_nodes = list(G.nodes())
        
     ####         Identifing entry gates Y          ####
        
        #node_coords = [utm.from_latlon(G.nodes[node[0]]['y'], G.nodes[node[0]]['x'])[:2] for node in nodeList]
        node_coords = [self.fromlatlon.transform(G.nodes[node[0]]['y'], G.nodes[node[0]]['x'])[:2] for node in nodeList]
    
        X = np.array(node_coords)
        if len(X) == 0:
            return None
        dbscan = DBSCAN(eps=eps, min_samples = min_samples)
        db = dbscan.fit(X)

        labels = db.labels_

        # Number of clusters in labels, ignoring noise if present (-1 label)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        print(f'Estimated number of clusters: {n_clusters}')

        # Create a DataFrame to view results
        clustered_nodes = pd.DataFrame({'node': [node[2].getID() for node in nodeList], 'distance':[node[1] for node in nodeList], 'x': X[:, 0], 'y': X[:, 1], 'cluster': labels})
        
        clusters = clustered_nodes.loc[clustered_nodes.groupby('cluster').distance.idxmin()]
        clusters.columns = ['node','distance','x','y','cluster']
        clusters = clusters.reset_index()

        self.clusters = clusters

        # Inizializza un DataFrame con indici come i nodi di partenza e colonne come tutti i nodi
        distances_df = pd.DataFrame(index=clusters['node'], columns=all_nodes)

        # Itera attraverso ciascun nodo di partenza per calcolare le distanze minime
        for index, row in clusters.iterrows():
            node=endpointNodeDict[row['node']]
            # Calcola le distanze del percorso minimo da 'start_node' a tutti gli altri nodi
            lengths, paths = nx.single_source_dijkstra(G, source=node, weight='length')
            # Aggiungi le distanze calcolate alla riga del DataFrame corrispondente al nodo di partenza
            for target_node, distance in lengths.items():
                distances_df.at[row['node'], target_node] = distance
        distances_df = distances_df.dropna(axis=1, how='all')




     ####        Discarding Outliers         ####

        #### Calculating Max for each row ####
        
        max_distance_df = distances_df.max(axis=1).reset_index()
        max_distance_df.columns = ['node', 'max_distance']

        
        #### Calculating deviation in Entry Gates ####
        cluster_stats = clustered_nodes.groupby('cluster')['distance'].agg(['mean', 'std']).reset_index()
        cluster_stats.columns = ['cluster', 'mean_distance', 'std_distance']

        cluster_stats['up_threshold'] = cluster_stats['mean_distance'] + 3 * cluster_stats['std_distance']
        cluster_stats['down_threshold'] = cluster_stats['mean_distance'] - 3 * cluster_stats['std_distance']

        cluster_stats= cluster_stats.merge(clustered_nodes, on="cluster")
        cluster_stats= cluster_stats.merge(max_distance_df, on="node")
        
        
        # Identify points that are outliers
        cluster_stats['is_outlier'] = (cluster_stats['distance'] < cluster_stats['down_threshold']) | (cluster_stats['distance'] > cluster_stats['max_distance'])
        
        # Filter out the outliers
        filtered_nodes = cluster_stats[~cluster_stats['is_outlier']]
        
        # Assume filtered_nodes contains the non-outlier nodes and the initial distances_df matrix
        # filtered_nodes DataFrame should contain at least a 'node' column with the nodes to keep

        # Get the list of nodes that are not outliers
        nodes_to_keep = filtered_nodes['node'].tolist()

        # Filter the distances_df to keep only these nodes
        filtered_distances_df = distances_df.loc[nodes_to_keep]
        


        ## Finding node of actual POI for debugging purposes
        actualPOI = [11.917602, 45.426466]
        nodePOI, distancePOI = ox.distance.nearest_nodes(G, *actualPOI, return_dist=True)
            

            
     ####    Finding the location        ####
        positive_differences = filtered_distances_df.copy()

        for node, row in filtered_distances_df.iterrows():
            distance = endpointDistanceDict[node]
            for col in filtered_distances_df.columns:
                diff = row[col] - distance
                positive_differences.at[node, col] = abs(diff)


        # Sum all rows grouped by columns
        column_sums = positive_differences.sum(axis=0)
        column_sums = column_sums.to_frame()
        column_sums.columns = ['distances']
        column_sums['distances'] = column_sums['distances'].astype(float)
        column_sums = column_sums.sort_values(by='distances')

        # Find the minimum of these column sums
        min_sum = column_sums.min()
        min_node = column_sums.idxmin().loc[column_sums.min().idxmin()]
        
        resultArray = []
        for index, row in column_sums.head(5).iterrows():
            element = G.nodes[index]
            element["distances"] = row['distances']
            resultArray.append(element)

        # self.plot_heatmap_clusters_over_osmnx(G, column_sums, X, labels)
        self.plot_heatmap_clusters_over_osmnx(G, column_sums, X, labels, self.tolatlon.transform(*epz_circle[0]), tuple(realPOI))
        
        return resultArray
    
    def enhance_graph(self, G, max_distance=50):
        new_G = G.copy()
        for u, v, data in G.edges(data=True):
            length = data['length']
            if length > max_distance:
                # Calculate the number of segments
                num_segments = int(np.ceil(length / max_distance))

                # Get coordinates of the original nodes
                x1, y1 = G.nodes[u]['x'], G.nodes[u]['y']
                x2, y2 = G.nodes[v]['x'], G.nodes[v]['y']

                # Calculate the segment length
                segment_length = length / num_segments

                # Calculate the coordinates of intermediate nodes
                x_coords = np.linspace(x1, x2, num_segments + 1)
                y_coords = np.linspace(y1, y2, num_segments + 1)

                # Add the intermediate nodes and edges
                previous_node = u
                for i in range(1, len(x_coords) - 1):
                    new_node = max(new_G.nodes) + 1
                    new_G.add_node(new_node, x=x_coords[i], y=y_coords[i])

                    # Add edge from previous node to the new node
                    new_G.add_edge(previous_node, new_node, length=segment_length)
                    previous_node = new_node

                # Add the final edge from the last intermediate node to the original end node
                new_G.add_edge(previous_node, v, length=segment_length)
            else:
                # Add the original edge if no segmentation is needed
                new_G.add_edge(u, v, length=length)

        return new_G

    def plot_heatmap_over_osmnx(self, G, column_sums):
        column_sums = column_sums.sort_values(by='distances')

        # Step 2: Extract node coordinates
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

        # Step 3: Plot the OSMnx graph
        fig, ax = ox.plot_graph(G, show=True, close=True)
        
        # Step 4: Create a scatter plot
        scatter = ax.scatter(node_x, node_y, c=node_values, cmap='plasma', s=100, alpha=0.75, edgecolor='k', zorder=5)
        plt.colorbar(scatter, ax=ax, label='Sum of Positive Differences')
        
        plt.title('Heatmap of Sum of Positive Differences Over Street Grid')
        plt.show()

    def plot_heatmap_clusters_over_osmnx(self, G, column_sums, sensitive_locations, epz_circle, epz_radius, realPOI, cloackedCenter, realRadius, cluster_num):
        column_sums = column_sums.sort_values(by='distances')

        # Step 2: Extract node coordinates
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

        # Step 3: Plot the OSMnx graph on a real map (with basemap)
        fig, ax = ox.plot_graph(G, show=False, close=False, bgcolor='w', node_color='gray', edge_color='gray', edge_linewidth=0.8)

        # Plot sensitive locations as red dots
        sensitive_plotted = False
        if sensitive_locations is not None:
            for loc in sensitive_locations:
                # If loc is a dict-like node, get its coordinates
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

        # Transform node coordinates to lat/lon for basemap
        # Get all node coordinates in EPSG:4326
        node_lons = [G.nodes[n]['x'] for n in G.nodes]
        node_lats = [G.nodes[n]['y'] for n in G.nodes]

        # Plot the realPOI as a green dot
        extra_lons = []
        extra_lats = []
        if cloackedCenter is not None:
            cloackedCenter_lat, cloackedCenter_lon = cloackedCenter
            ax.plot(cloackedCenter_lon, cloackedCenter_lat, 'go', markersize=8, alpha=0.8, label=f'Cloacked r={realRadius}m', zorder=10)
            # Convert radius in meters to degrees for latitude and longitude
            radius_deg_lat = realRadius / 111320.0
            radius_deg_lon = realRadius / (111320.0 * np.cos(np.deg2rad(cloackedCenter_lat)))
            # Use an ellipse to represent the circle correctly
            ellipse = Ellipse((cloackedCenter_lon, cloackedCenter_lat), 2*radius_deg_lon, 2*radius_deg_lat, edgecolor='green', fill=False, linewidth=2, alpha=0.5, zorder=9)
            ax.add_patch(ellipse)
            extra_lons.extend([cloackedCenter_lon - radius_deg_lon, cloackedCenter_lon + radius_deg_lon])
            extra_lats.extend([cloackedCenter_lat - radius_deg_lat, cloackedCenter_lat + radius_deg_lat])

        if realPOI is not None:
            realPOI_lat, realPOI_lon = realPOI
            ax.plot(realPOI_lon, realPOI_lat, 'ro', markersize=8, alpha=0.8, label=f'RealPOI', zorder=10)

        # Plot the EPZ center as a blue dot
        if epz_circle is not None:
            epz_lat, epz_lon = epz_circle
            ax.plot(epz_lon, epz_lat, 'bo', markersize=8, alpha=0.8, label=f'EPZ r={epz_radius}m', zorder=10)
            # Convert radius in meters to degrees for latitude and longitude
            radius_deg_lat = epz_radius / 111320.0
            radius_deg_lon = epz_radius / (111320.0 * np.cos(np.deg2rad(epz_lat)))
            # Use an ellipse to represent the circle correc
            ellipse = Ellipse((epz_lon, epz_lat), 2*radius_deg_lon, 2*radius_deg_lat, edgecolor='blue', fill=False, linewidth=2, alpha=0.5, zorder=9)
            ax.add_patch(ellipse)
            extra_lons.extend([epz_lon - radius_deg_lon, epz_lon + radius_deg_lon])
            extra_lats.extend([epz_lat - radius_deg_lat, epz_lat + radius_deg_lat])

        # Set extent for basemap, including extra points
        all_lons = node_lons + extra_lons
        all_lats = node_lats + extra_lats

        # Calculate min/max for both axes
        min_lon, max_lon = min(all_lons), max(all_lons)
        min_lat, max_lat = min(all_lats), max(all_lats)

        # Find the center and the largest span
        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2
        span = max(max_lon - min_lon, max_lat - min_lat)

        # Expand both axes equally from the center
        ax.set_xlim(center_lon - span / 2, center_lon + span / 2)
        ax.set_ylim(center_lat - span / 2, center_lat + span / 2)
        ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, crs='EPSG:4326')  # omit zoom for auto

        # Add legend only if at least one is present
        if realPOI is not None or epz_circle is not None:
            ax.legend(title=f"ACTIVITY {cluster_num}", title_fontproperties={'weight': 'bold'})
        fig.show()
