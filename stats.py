import datetime
import random, time
from Models import ActivityCluster, Point
from Attack1 import EPZSearch
from Attack2 import EPZSearch as epzsearch2
from DataRepresentation import DataRepresentationFactory
from Utility import ApplicationInfo
from matplotlib import pyplot as plt
import utm

import os

import ast
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, DBSCAN

def main():
    #testFirstAttack()
    calculateStats()
    calculateStats2nd()
    #retriveStatsNoMultiReading()
    #retriveStatsSecondAttack()


def retriveStats():
    initializeApplication("Strava")

    fileName = "Data/Stats/Stats"+datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")+".csv"
    n_epochs = 10
    test_data = []
    radiusSet = appInfo.EPZRadiusesList

    activityClusters = []
    activityClusters.append(ActivityCluster.ActivityCluster.initializeActivityClusterFromJson("Data/Strava/39260108/ActivityClusterList.json", 2))
    activityClusters.append(ActivityCluster.ActivityCluster.initializeActivityClusterFromJson("Data/Strava/39260108/ActivityClusterList.json", 3))
    
    attackType = "EPZ" ####To Check
    global dataRepresentation
    dataRepresentation = DataRepresentationFactory.SphericalDataRepresentationFactory().create_data_representation(attackType)

    results = []

    for activityCluster in activityClusters:
        activityList = dataRepresentation.getPolylineList(activityCluster.activityPathList)
        for radius in radiusSet:
            n_epochs = random.randint(8,18)
            for epoch in range(n_epochs):
                preprocessingStart = time.time() #### 
                randomCenter = dataRepresentation.generateCloackedCenter(activityCluster.center, radius)
                
                randomActivityList = random_batch(activityList)
                numberActivity = len(randomActivityList)
                randomActivityEndpoints = disguiseActivityBatch(randomActivityList[:10], randomCenter, radius)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
                
                epzsa = EPZSearch.EPZSearch(dataRepresentation, randomActivityEndpoints, appInfo, attackType)
                processingStart = time.time()   #####
                preprocessingTime = processingStart-preprocessingStart
                possibleEPZs = epzsa.attack()
                processingEnd = time.time()
                normalProcessingTime = processingEnd-processingStart
                
                listEPZ = sorted(list(possibleEPZs), key= lambda x: -possibleEPZs[x])
                
                possibleEPZCenters = []
                possibleEPZFrequencies = []
                for possibleEPZ in listEPZ[:min(3, len(listEPZ))]:
                        possibleEPZCenters.append(possibleEPZ.center)
                        possibleEPZFrequencies.append(possibleEPZs[possibleEPZ])
                
                results.append({"n": epoch, "radius": radius,"numberActivity":numberActivity, "center": activityCluster.center, "randomCenter": randomCenter, "centerShift": dataRepresentation.distance(randomCenter, activityCluster.center),
                                "endpoints": [x.center for x in randomActivityEndpoints], "EPZs": possibleEPZCenters, "EPZsFreq": possibleEPZFrequencies,
                                "distance": [dataRepresentation.distance(randomCenter, x) for x in possibleEPZCenters],
                                "preprocessingTime": preprocessingTime, "normalProcessingTime": normalProcessingTime})
                print(f"radius: {radius}, epoch:{epoch}")
                df = pd.DataFrame(results)
                #df.to_csv(fileName, encoding="utf-8", index=False)
    return df
    

def calculateStats():
    for filename in os.listdir("Data/Stats/"):
        if ".csv" not in filename or "Stats2n" in filename:
            continue
        print(filename)
        df = pd.read_csv("Data/Stats/"+filename)
        df['distance'] = df['distance'].apply(str_to_array)
        df['endpoints'] = df['endpoints'].apply(str_to_array)
        columns = ['radius','distance','endpoints']
        if "numberActivity" in df:
            columns.append('numberActivity')
        if "distanceClusters" in df:
            df['distanceClusters'] = df['distanceClusters'].apply(str_to_array)
            columns.extend(['distanceClusters', 'endpointsClusters'])
            Clusters = True
        else:
            Clusters = False

        results = []
        distanceThreshold = 35
        for radius in df["radius"].unique():
            subDf = df[df["radius"] == radius][columns].reset_index()
            subDf.columns = ['index',*columns]
            firstRight = 0 
            secondRight = 0
            secondsCount = 0
            thirdRight = 0
            thirdsCount = 0
            notFound = 0
            endpoints= 0
            firstRightClusters = 0 
            secondRightClusters = 0
            secondsCountClusters = 0
            thirdRightClusters = 0
            thirdsCountClusters = 0
            notFoundClusters = 0
            endpointsClusters = 0
            activityCount = 0
            for index, row in subDf.iterrows():
                if "numberActivity" in row:
                    activityCount += row["numberActivity"]
                endpoints+=len(row['endpoints'])
                lendist = len(row['distance'])
                if lendist > 0 and row['distance'][0]<distanceThreshold:
                    firstRight+=1
                elif lendist > 1 and row['distance'][1] < distanceThreshold:
                    secondRight+=1
                    secondsCount+=1
                elif lendist > 2 and row['distance'][2] < distanceThreshold:
                    secondsCount+=1
                    thirdRight+=1
                    thirdsCount+=1
                elif lendist > 2:
                    secondsCount+=1
                    thirdsCount+=1
                elif lendist == 0:
                    notFound +=1
                if Clusters:
                    endpointsClusters += int(row['endpointsClusters'][-3])
                    lendistClusters = len(row['distanceClusters'])
                    if lendistClusters > 0 and row['distanceClusters'][0]<distanceThreshold:
                        firstRightClusters+=1
                    elif lendistClusters > 1 and row['distanceClusters'][1] < distanceThreshold:
                        secondRightClusters+=1
                        secondsCountClusters+=1
                    elif lendistClusters > 2 and row['distanceClusters'][2] < distanceThreshold:
                        secondsCountClusters+=1
                        thirdRightClusters+=1
                        thirdsCountClusters+=1
                    elif lendistClusters > 2:
                        secondsCountClusters+=1
                        thirdsCountClusters+=1
                    elif lendistClusters == 0:
                        notFoundClusters +=1
            if Clusters:
                results.append({'radius':radius, 'right/tot_n°': f"{firstRight+secondRight+thirdRight}/{len(subDf)}", "avarage Activities": activityCount/len(subDf), 'avarage endpoints': endpoints/len(subDf), 
                            'firstRight':firstRight, 'correctNessRation':firstRight/len(subDf)*100, 
                            'secondRight':secondRight, 'secondRightRatio':secondRight/secondsCount*100 if secondsCount != 0 else 0,
                            'thirdRight':thirdRight, 'thirdRightRatio':thirdRight/thirdsCount*100  if thirdsCount != 0 else 0,
                            'notFound' : notFound, 'right/tot_clust':f"{firstRightClusters+secondRightClusters+thirdRightClusters}/{len(subDf)}", "Clusters average":endpointsClusters/len(subDf),
                            'firstRightClusters':firstRightClusters, 'correctNessRation':firstRightClusters/len(subDf)*100, 
                            'secondRightClusters':secondRightClusters, 'secondRightRatio':secondRightClusters/secondsCountClusters*100 if secondsCountClusters != 0 else 0,
                            'thirdRightClusters':thirdRightClusters, 'thirdRightRatio':thirdRightClusters/thirdsCountClusters*100  if thirdsCountClusters != 0 else 0,
                            'notFoundClusters' : notFoundClusters})
            else:
                results.append({'radius':radius, 'right/tot_n°': f"{firstRight+secondRight+thirdRight}/{len(subDf)}", "avarage Activities": activityCount/len(subDf), 'avarage endpoints': endpoints/len(subDf), 
                            'firstRight':firstRight, 'correctNessRation':firstRight/len(subDf)*100, 
                            'secondRight':secondRight, 'secondRightRatio':secondRight/secondsCount*100 if secondsCount != 0 else 0,
                            'thirdRight':thirdRight, 'thirdRightRatio':thirdRight/thirdsCount*100  if thirdsCount != 0 else 0,
                            'notFound' : notFound})
        for result in results:
            print(result)


def calculateStats2nd():
    for filename in os.listdir("Data/Stats/"):
        if ".csv" not in filename or "Stats2n" not in filename:
            continue
        print(filename)
        df = pd.read_csv("Data/Stats/"+filename)
        df['distance'] = df['distance'].apply(str_to_array)
        df['endpoints'] = df['endpoints'].apply(str_to_array)
        if "distanceClusters" in df:
            df['distanceClusters'] = df['distanceClusters'].apply(str_to_array)
            Clusters = True
        else:
            Clusters = False
        results = []
        distanceThreshold = 50
        for radius in df["radius"].unique():
            if Clusters:
                subDf = df[df["radius"] == radius][['radius','distance','endpoints','distanceClusters', 'endpointsClusters']].reset_index()
                subDf.columns = ['index','radius','distance','endpoints','distanceClusters', 'endpointsClusters']
            else:
                subDf = df[df["radius"] == radius][['radius','distance','endpoints']].reset_index()
                subDf.columns = ['index','radius','distance','endpoints']
            firstRight = 0 
            secondRight = 0
            secondsCount = 0
            thirdRight = 0
            thirdsCount = 0
            notFound = 0
            endpoints= 0
            firstRightClusters = 0 
            secondRightClusters = 0
            secondsCountClusters = 0
            thirdRightClusters = 0
            thirdsCountClusters = 0
            notFoundClusters = 0
            endpointsClusters = 0
            for index, row in subDf.iterrows():
                endpoints+=len(row['endpoints'])
                lendist = len(row['distance'])
                if lendist > 0 and row['distance'][0]<distanceThreshold:
                    firstRight+=1
                elif lendist > 1 and row['distance'][1] < distanceThreshold:
                    secondRight+=1
                    secondsCount+=1
                elif lendist > 2 and row['distance'][2] < distanceThreshold:
                    secondsCount+=1
                    thirdRight+=1
                    thirdsCount+=1
                elif lendist > 2:
                    secondsCount+=1
                    thirdsCount+=1
                elif lendist == 0:
                    notFound +=1
                if Clusters:
                    endpointsClusters += int(row['endpointsClusters'][-3])
                    lendistClusters = len(row['distanceClusters'])
                    if lendistClusters > 0 and row['distanceClusters'][0]<distanceThreshold:
                        firstRightClusters+=1
                    elif lendistClusters > 1 and row['distanceClusters'][1] < distanceThreshold:
                        secondRightClusters+=1
                        secondsCountClusters+=1
                    elif lendistClusters > 2 and row['distanceClusters'][2] < distanceThreshold:
                        secondsCountClusters+=1
                        thirdRightClusters+=1
                        thirdsCountClusters+=1
                    elif lendistClusters > 2:
                        secondsCountClusters+=1
                        thirdsCountClusters+=1
                    elif lendistClusters == 0:
                        notFoundClusters +=1
            if Clusters:
                results.append({'radius':radius, 'right/tot_n°': f"{firstRight+secondRight+thirdRight}/{len(subDf)}", 'avarage endpoints': endpoints/len(subDf), 
                        'firstRight':firstRight, 'correctNessRation':firstRight/len(subDf)*100, 
                        'secondRight':secondRight, 'secondRightRatio':secondRight/secondsCount*100 if secondsCount != 0 else 0,
                        'thirdRight':thirdRight, 'thirdRightRatio':thirdRight/thirdsCount*100  if thirdsCount != 0 else 0,
                        'notFound' : notFound, 'right/tot_clust':f"{firstRightClusters+secondRightClusters+thirdRightClusters}/{len(subDf)}", "Clusters average":endpointsClusters/len(subDf),
                        'firstRightClusters':firstRightClusters, 'correctNessRation':firstRightClusters/len(subDf)*100, 
                        'secondRightClusters':secondRightClusters, 'secondRightRatio':secondRightClusters/secondsCountClusters*100 if secondsCountClusters != 0 else 0,
                        'thirdRightClusters':thirdRightClusters, 'thirdRightRatio':thirdRightClusters/thirdsCountClusters*100  if thirdsCountClusters != 0 else 0,
                        'notFoundClusters' : notFoundClusters})
            else:
                results.append({'radius':radius, 'right/tot_n°': f"{firstRight+secondRight+thirdRight}/{len(subDf)}", 'avarage endpoints': endpoints/len(subDf), 
                        'firstRight':firstRight, 'correctNessRation':firstRight/len(subDf)*100, 
                        'secondRight':secondRight, 'secondRightRatio':secondRight/secondsCount*100 if secondsCount != 0 else 0,
                        'thirdRight':thirdRight, 'thirdRightRatio':thirdRight/thirdsCount*100  if thirdsCount != 0 else 0,
                        'notFound' : notFound})
        for result in results:
            print(result)


def retriveStatsSecondAttack():
    initializeApplication("Strava")


    name = "Data/Stats/Stats2ndAttack"+datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")+".csv"
    n_epochs = 10
    test_data = []
    radiusSet = appInfo.EPZRadiusesList

    activityClusters = []
    activityClusters.append(ActivityCluster.ActivityCluster.initializeActivityClusterFromJson("Data/Strava/39260108/ActivityClusterList.json", 2))
    activityClusters.append(ActivityCluster.ActivityCluster.initializeActivityClusterFromJson("Data/Strava/39260108/ActivityClusterList.json", 3))
    
    attackType = "EPZ" ####To Check
    global dataRepresentation
    dataRepresentation = DataRepresentationFactory.SphericalDataRepresentationFactory().create_data_representation(attackType)

    results = []

    for activityCluster in activityClusters:
        activityClusterActivityList = activityCluster.activityPathList
        for radius in radiusSet:
            for epoch in range(n_epochs):
                preprocessingStart = time.time() #### 
                randomCenter = dataRepresentation.generateCloackedCenter(activityCluster.center, radius)
                
                activityCluster.radius = radius
                activityCluster.cloackedCenter = randomCenter
                activityPathList = random_batch(activityClusterActivityList)
                activityCluster.activityPathList = activityPathList

                            
                epzSearch = epzsearch2.EPZSearch(activityCluster)
                epzSearch.setTrueCenter(randomCenter)

                tau_converged = 10
                preprocessingEnd = time.time() #### 
                preprocessingTime = preprocessingEnd - preprocessingStart

                epz_circles = epzSearch.epz_identification(tau_converged, radius)

                epzIdentificationEnd = time.time() ####
                epzIdentificationTime = epzIdentificationEnd - preprocessingEnd

                possibleEPZs = epzSearch.retriveSensitiveLocation(epz_circles[0])
                sensitiveLocationSearchEnd = time.time() ####
                sensitiveLocationSearchTime = sensitiveLocationSearchEnd - epzIdentificationEnd

                possibleEPZsClusters = epzSearch.retriveSensitiveLocationThroughClusters(epz_circles[0])
                clusteredSensitiveLocationSearchEnd = time.time() ####
                clusteredSensitiveLocationSearchTime = clusteredSensitiveLocationSearchEnd - sensitiveLocationSearchEnd



                results.append({"n": epoch, "radius": radius, "center": activityCluster.center, "randomCenter": randomCenter, 
                                "epzFoundCenter": epz_circles[0],
                                "centerShift": dataRepresentation.distance(randomCenter, activityCluster.center),
                                "endpoints": [utm.to_latlon(*x.center) for x in epzSearch.EndpointsList], "EPZs": [(x['x'], x['y'], x['distances']) for x in possibleEPZs],
                                "distance": [dataRepresentation.distance(activityCluster.center, (x['y'], x['x'])) for x in possibleEPZs] ,
                                "endpointsClusters": list(epzSearch.clusters.itertuples(index=False)), "EPZsClusters": [(x['x'], x['y'], x['distances']) for x in possibleEPZsClusters],
                                "distanceClusters": [dataRepresentation.distance(activityCluster.center, (x['y'], x['x'])) for x in possibleEPZsClusters],
                                "preprocessingTime": preprocessingTime, "epzIdentificationTime": epzIdentificationTime, 
                                "sensitiveLocationSearchTime": sensitiveLocationSearchTime, "clusteredSensitiveLocationSearchTime": clusteredSensitiveLocationSearchTime})
                print(f"radius: {radius}, epoch {epoch} out of {n_epochs}")
                df = pd.DataFrame(results)
                df.to_csv(name, encoding="utf-8", index=False)
    
    return df
  

def retriveStatsWithClusters():
    initializeApplication("Strava")

    fileName = "Data/Stats/Stats"+datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")+".csv"
    n_epochs = 10
    test_data = []
    radiusSet = appInfo.EPZRadiusesList

    activityClusters = []
    activityClusters.append(ActivityCluster.ActivityCluster.initializeActivityClusterFromJson("Data/Strava/39260108/ActivityClusterList.json", 2))
    activityClusters.append(ActivityCluster.ActivityCluster.initializeActivityClusterFromJson("Data/Strava/39260108/ActivityClusterList.json", 3))
    
    attackType = "EPZ" ####To Check
    global dataRepresentation
    dataRepresentation = DataRepresentationFactory.SphericalDataRepresentationFactory().create_data_representation(attackType)

    results = []

    for activityCluster in activityClusters:
        for radius in radiusSet:
            for epoch in range(n_epochs):
                preprocessingStart = time.time() #### 
                randomCenter = dataRepresentation.generateCloackedCenter(activityCluster.center, radius)
                
                randomActivityPathList = random_batch(activityCluster.activityPathList)
                randomActivityList = dataRepresentation.getPolylineList(randomActivityPathList)
                randomActivityEndpoints = disguiseActivityBatch(randomActivityList, randomCenter, radius)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
                clusters = findClusters(randomActivityEndpoints)
                clustersEndpoints = [Point.SphericalPoint(*coords, id="cluster"+str(index)) for index,coords in enumerate(zip(clusters.groupby('cluster').first()['x'],clusters.groupby('cluster').first()['y']))]
                
                epzsa = EPZSearch.EPZSearch(dataRepresentation, randomActivityEndpoints, appInfo, attackType)
                epzsaClusters = EPZSearch.EPZSearch(dataRepresentation, clustersEndpoints, appInfo, attackType)
                processingStart = time.time()   #####
                preprocessingTime = processingStart-preprocessingStart
                possibleEPZs = epzsa.attack()
                processingEnd = time.time()
                normalProcessingTime = processingEnd-processingStart
                possibleEPZsClusters = epzsaClusters.attack()
                clusterProcessingEnd = time.time()
                clusterProcessingTime = clusterProcessingEnd-processingEnd

                listEPZ = sorted(list(possibleEPZs), key= lambda x: -possibleEPZs[x])
                possibleEPZCenters = []
                possibleEPZFrequencies = []
                if len(listEPZ) > 3:
                    for possibleEPZ in listEPZ[:3]:
                        possibleEPZCenters.append(possibleEPZ.center)
                        possibleEPZFrequencies.append(possibleEPZs[possibleEPZ])
                else:
                    for possibleEPZ in listEPZ:
                        possibleEPZCenters.append(possibleEPZ.center)
                        possibleEPZFrequencies.append(possibleEPZs[possibleEPZ])

                listEPZClusters = sorted(list(possibleEPZsClusters), key= lambda x: -possibleEPZsClusters[x])
                possibleEPZCentersClusters = []
                possibleEPZFrequenciesClusters = []
                if len(listEPZClusters) > 3:
                    for possibleEPZ in listEPZClusters[:3]:
                        possibleEPZCentersClusters.append(possibleEPZ.center)
                        possibleEPZFrequenciesClusters.append(possibleEPZs[possibleEPZ])
                else:
                    for possibleEPZ in listEPZClusters:
                        possibleEPZCentersClusters.append(possibleEPZ.center)
                        possibleEPZFrequenciesClusters.append(possibleEPZsClusters[possibleEPZ])

                results.append({"n": epoch, "radius": radius, "center": activityCluster.center, "randomCenter": randomCenter, "centerShift": dataRepresentation.distance(randomCenter, activityCluster.center),
                                "endpoints": [x.center for x in randomActivityEndpoints], "EPZs": possibleEPZCenters, "EPZsFreq": possibleEPZFrequencies,
                                "distance": [dataRepresentation.distance(randomCenter, x) for x in possibleEPZCenters],
                                "endpointsClusters": [x.center for x in clustersEndpoints], "EPZsClusters": possibleEPZCentersClusters, "EPZsFreqClusters": possibleEPZFrequenciesClusters,
                                "distanceClusters": [dataRepresentation.distance(randomCenter, x) for x in possibleEPZCentersClusters],
                                "preprocessingTime": preprocessingTime, "normalProcessingTime": normalProcessingTime, "clusterProcessingTime": clusterProcessingTime})
                
                print(f"radius: {radius}, epoch:{epoch}")
                df = pd.DataFrame(results)
                df.to_csv(fileName, encoding="utf-8", index=False)
    return df
    

def disguiseActivityBatch(randomActivityList, randomCenter, radius, fuzz = False):
    randomActivityEndpoint = []

    for activity in randomActivityList:
        coordsList = activity["polyline"]
        while len(coordsList) > 0 and dataRepresentation.distance(coordsList[0], randomCenter) <= radius:
            last = coordsList.pop(0)
        
        if len(coordsList) == 0:
            continue

        if not fuzz:
            new_point = dataRepresentation.getPointOnCircumference(randomCenter, last, radius)
            coordsList.insert(0, new_point)
            randomActivityEndpoint.append(Point.SphericalPoint(new_point[0],new_point[1], id="start"+str(activity["id"])))
        else:
            randomActivityEndpoint.append(Point.SphericalPoint(coordsList[0][0],coordsList[0][1], id="start"+str(activity["id"])))

        while len(coordsList) > 0 and dataRepresentation.distance(coordsList[-1], randomCenter) <= radius:
            last = coordsList.pop()

        if len(coordsList) == 0:
            continue
        
        if not fuzz:
            new_point = dataRepresentation.getPointOnCircumference(randomCenter, last, radius)
            coordsList.append(new_point)
            randomActivityEndpoint.append(Point.SphericalPoint(new_point[0],new_point[1], id="end"+str(activity["id"])))
        else:
            randomActivityEndpoint.append(Point.SphericalPoint(coordsList[-1][0],coordsList[-1][1], id="end"+str(activity["id"])))
            
    return randomActivityEndpoint
        

def findClusters(randomActivityEndpoints, eps=50/6371000, min_samples=1):
                                        ### 30/6371000 = 30 meters   
    randomActivityEndpoints = [x.center for x in randomActivityEndpoints]
    X = np.array(randomActivityEndpoints)
    dbscan = DBSCAN(eps=eps, min_samples = min_samples, algorithm="ball_tree", metric="haversine")
    db = dbscan.fit(np.radians(X))
    
    labels = db.labels_

    # Create a DataFrame to view results
    clustered_nodes = pd.DataFrame({'x': X[:, 0], 'y': X[:, 1], 'cluster': labels})
    """ unique = clustered_nodes.groupby(['cluster']).first()
    x, y = unique['x'], unique['y']
    plt.plot(x, y, 'o')
    plt.show() """
    return clustered_nodes
    

def random_batch(list):
    batch_size = random.randint(len(list)//3, len(list))
    return random.sample(list, batch_size)


def str_to_array(str):
    return ast.literal_eval(str)


def initializeApplication(appName):
    global appInfo
    appInfo = ApplicationInfo.ApplicationInfo(appName)


if __name__ == "__main__":
    main()
