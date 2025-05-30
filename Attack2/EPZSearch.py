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

class EPZSearch():

    def __init__(self, activityCluster, data_representation = DataRepresentationFactory.UTMDataRepresentationFactory().create_data_representation()):
        self.DataRepresentation = data_representation
        self.EndpointsList = self.DataRepresentation.initActivityEndpointList(activityCluster)
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
        #return np.linalg.norm(np.array([point1.easting, point1.northing]) - np.array([point2.easting, point2.northing]))
        return np.linalg.norm(np.array([point1.x, point1.y]) - np.array([point2.x, point2.y]))

    @staticmethod
    def fit_circle(points):
        if len(points) == 0:
            return (0, 0), 0
        
        #coords = np.array([[point.easting, point.northing] for point in points])
        coords = np.array([[point.x, point.y] for point in points])
        
        def calc_R(xc, yc):
            return np.sqrt((coords[:, 0] - xc)**2 + (coords[:, 1] - yc)**2)
        
        def f_2(c):
            Ri = calc_R(*c)
            return ((Ri - Ri.mean())**2).sum()
            
        center_estimate = np.mean(coords, axis=0)
        # Adding constraints and bounds
        bounds = [(np.min(coords[:, 0]), np.max(coords[:, 0])), (np.min(coords[:, 1]), np.max(coords[:, 1]))]
    
        center = minimize(f_2, center_estimate, bounds=bounds, options={'maxiter': 10})
        center = center.x
        Ri = calc_R(*center)
        radius = Ri.mean()
        return (center[0], center[1]), radius

    def epz_identification(self, tau_converged, tau_disjoint):
        k = 1
        P = self.EndpointsList
        print(self.EndpointsList)
        max_iteration = 10
        #coords = np.array([[p.easting, p.northing] for p in P])
        coords = np.array([[p.x, p.y] for p in P])
        clusters = KMeans(n_clusters=k, random_state=0).fit(coords).labels_
        while True:
            prev_centroids = [self.fit_circle([P[i] for i in range(len(P)) if clusters[i] == j])[0] for j in range(k)]
            for iteration in range(max_iteration):
                # Assignment step
                new_clusters = np.zeros(len(P), dtype=int)
                for i, point in enumerate(P):
                    #distances = [self.euclidean_distance(point, UTMDataRepresentation.UTMEndpoint(*self.fit_circle([P[j] for j in range(len(P)) if clusters[j] == l])[0], 0, 'A', '', '', 0)) for l in range(k)]
                    distances = [self.euclidean_distance(point, UTMDataRepresentation.UTMEndpoint(*self.fit_circle([P[j] for j in range(len(P)) if clusters[j] == l])[0], '', '', 0)) for l in range(k)]
                    new_clusters[i] = np.argmin(distances)
                
                # Update step
                new_centroids = [self.fit_circle([P[i] for i in range(len(P)) if new_clusters[i] == j])[0] for j in range(k)]
                
                # Check for convergence
                #centroid_changes = [self.euclidean_distance(UTMDataRepresentation.UTMEndpoint(*prev_centroids[i], 0, 'A', '', '', 0), UTMDataRepresentation.UTMEndpoint(*new_centroids[i], 0, 'A', '', '', 0)) for i in range(k)]
                centroid_changes = [self.euclidean_distance(UTMDataRepresentation.UTMEndpoint(*prev_centroids[i], '', '', 0), UTMDataRepresentation.UTMEndpoint(*new_centroids[i], '', '', 0)) for i in range(k)]
                # print(tau_converged, centroid_changes)
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
                #if any(self.euclidean_distance(point, UTMDataRepresentation.UTMEndpoint(center[0], center[1], 0, 'A', '', '', 0)) > tau_disjoint for point in [P[j] for j in range(len(P)) if clusters[j] == i]):
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


    def retriveSensitiveLocation(self, epz_circle, tau_snap = 50, eps = 30, min_samples = 1):
        
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

        self.plot_heatmap_clusters_over_osmnx(G, column_sums, X, labels)
        
        return resultArray
    
    def retriveSensitiveLocationThroughClusters(self, epz_circle, tau_snap = 500, eps = 30, min_samples = 1):
        
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

        self.plot_heatmap_clusters_over_osmnx(G, column_sums, X, labels)
        
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

    def plot_heatmap_clusters_over_osmnx(self, G, column_sums, X, labels):
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

        
        # Plot the clusters

        unique_labels = set(labels)
        colors = [plt.cm.Spectral(each) for each in np.linspace(0, 1, len(unique_labels))]

        for k, col in zip(unique_labels, colors):
            if k == -1:
                # Black used for noise.
                col = [0, 0, 0, 1]

            class_member_mask = (labels == k)

            xy = X[class_member_mask]
            latlon = []
            for coords in xy:
                #latlon.append(utm.to_latlon(*coords, *self.getZoneInfo()))
                latlon.append(self.tolatlon.transform(*coords))
            latlon = np.array(latlon)  # Convert to NumPy array
            plt.plot(latlon[:, 0], latlon[:, 1], 'o', markerfacecolor=tuple(col),
                    markeredgecolor='k', markersize=15, alpha=0.3)
        
        # Step 4: Create a scatter plot
        scatter = ax.scatter(node_x, node_y, c=node_values, cmap='plasma', s=100, alpha=0.75, edgecolor='k', zorder=5)
        plt.colorbar(scatter, ax=ax, label='Sum of Positive Differences')
        
        if self.center is not None:
            print('center', self.center)
            plt.plot(self.center[1], self.center[0], 'ro', markersize=18, alpha=0.6)
            
        plt.title('Heatmap of Sum of Positive Differences Over Street Grid')
        plt.show()


    def plotClusters(self, X, labels):
        # Plot the clusters

        unique_labels = set(labels)
        colors = [plt.cm.Spectral(each) for each in np.linspace(0, 1, len(unique_labels))]

        for k, col in zip(unique_labels, colors):
            if k == -1:
                # Black used for noise.
                col = [0, 0, 0, 1]

            class_member_mask = (labels == k)

            xy = X[class_member_mask]
            latlon = []
            for coords in xy:
                #latlon.append(utm.to_latlon(*coords, *self.getZoneInfo()))
                latlon.append(self.tolatlon.transform(*coords))
            latlon = np.array(latlon)
            plt.plot(latlon[:, 0], latlon[:, 1], 'o', markerfacecolor=tuple(col),
                    markeredgecolor='k', markersize=14)
        
        plt.title(f'Estimated number of clusters: {len(set(labels)) - (1 if -1 in labels else 0)}')
        plt.show()

    def getZoneInfo(self):
        return [self.zoneNumber, self.zoneLetter]