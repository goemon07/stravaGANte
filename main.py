from DataCollector import AuthController, ActivityRetriever
from Utility import ApplicationInfo, jsonHelper
from Models import ActivityCluster, User, Activity
from Attack1 import EPZSearch
from Attack2 import EPZSearch as EPZSearch2
from DataRepresentation import DataRepresentationFactory

import itertools
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import datetime
import time
import os


def main():
    initializeApplication("Strava")

    

    clusterAllActivities()
    ####    Test Attack
    """ attackType = "EPZ"
    dataRepresentation = DataRepresentationFactory.GeocentricDataRepresentationFactory().create_data_representation(attackType)
    #dataRepresentation = DataRepresentationFactory.SphericalDataRepresentationFactory().create_data_representation(attackType)
    activityCluster = ActivityCluster.ActivityCluster.initializeActivityClusterFromJson("Data/Strava/39260108/ActivityClusterList.json", 1)
    testAttack(activityCluster.activityPathList[:10], dataRepresentation, attackType) """


def singleDisguiseTest(activityClusterPath = "Data/Strava/39260108/ActivityClusterList.json", activityClusterId = "1", dataRepresentation = DataRepresentationFactory.GeocentricDataRepresentationFactory().create_data_representation(), plot = False):
    #dataRepresentation = DataRepresentationFactory.SphericalDataRepresentationFactory().create_data_representation()
    
    activityCluster = ActivityCluster.ActivityCluster.initializeActivityClusterFromJson(activityClusterPath, activityClusterId)
    activity = Activity.Activity.initActivityFromPath(activityCluster.activityPathList[0])
    fig, ax = plt.subplots()
    
    coordsList = activity.decodePolyline("polyline")
    addPolylineToPlot(ax, coordsList, "base polyline")
    coordsList = dataRepresentation.convertCoordsListIntoRepresentation(coordsList)
    startCoordsList = dataRepresentation.convertCoordsListIntoLatLon(coordsList)
    addPolylineToPlot(ax, startCoordsList, "polyline - DoubleTransformed")
    center = dataRepresentation.transformLatLon(*activityCluster.center)
    while dataRepresentation.distance(coordsList[0], center) < activityCluster.radius:
        last = coordsList.pop(0)
    #ax.plot(*last[::-1], "xr")
    while dataRepresentation.distance(coordsList[-1], center) < activityCluster.radius:
        last = coordsList.pop()
    #ax.plot(*last[::-1], "xr")
    coordsList = dataRepresentation.convertCoordsListIntoLatLon(coordsList)

    if plot:
        addPolylineToPlot(ax, coordsList, "EPZ")
        activityCluster.addCircleToPlot(ax)
        plt.legend(loc="upper right")
        plt.show()


def fullDisguiseOfActivityCluster(activityClusterPath = "Data/Strava/39260108/ActivityClusterList.json", activityClusterId = "1"):
    activityCluster = ActivityCluster.ActivityCluster.initializeActivityClusterFromJson(activityClusterPath, activityClusterId)
    geocentricData = DataRepresentationFactory.GeocentricDataRepresentationFactory().create_data_representation()
    sphericalData = DataRepresentationFactory.SphericalDataRepresentationFactory().create_data_representation()
    for activityPath in activityCluster.activityPathList:
        activity = Activity.Activity.initActivityFromPath(activityPath)
        activity.completeDisguiseActivityInCluster(activityCluster.center, 800, activityCluster.cloackedCenter, sphericalData, geocentricData)


def compairDataRepresentation(activityClusterPath = "Data/Strava/39260108/ActivityClusterList.json", activityClusterId = "1", firstN = 5, attackType = "EPZ+Fuzz"):
    geocentricData = DataRepresentationFactory.GeocentricDataRepresentationFactory().create_data_representation(attackType)
    sphericalData = DataRepresentationFactory.SphericalDataRepresentationFactory().create_data_representation(attackType)

    activityCluster = ActivityCluster.ActivityCluster.initializeActivityClusterFromJson(activityClusterPath, activityClusterId)
    
    geocentricEndpoints = geocentricData.getActivityEndpointList(activityCluster.activityPathList[0:firstN])
    sphericalEndpoints = sphericalData.getActivityEndpointList(activityCluster.activityPathList[0:firstN])
    
    geocentricCircleList = geocentricData.getPossibleEPZfromPointPair(geocentricEndpoints, [200, 400, 800, 1000,1300, 1600], 0)
    sphericalCircleList = sphericalData.getPossibleEPZfromPointPair(sphericalEndpoints, [200, 400, 800, 1000,1300, 1600], 0)
    geocentricData.convertEPZList(geocentricCircleList) ## Funziona

    
    fig, ax = plt.subplots()
    for n in range(firstN):
        activity = Activity.Activity.initActivityFromPath(activityCluster.activityPathList[n])
        activity.addActivityToPlot(ax, attackType)
        activity.addActivityToPlot(ax,"GeocentricEPZ+Fuzz")

        activityStart = sphericalEndpoints[n+1].center
        activityEnd = sphericalEndpoints[n+0].center
        geoActivityStart = geocentricEndpoints[n+1].center
        geoActivityEnd = geocentricEndpoints[n+0].center
        geoConvertedStart = geocentricData.transformToLatLon(*geoActivityStart)
        geoConvertedEnd = geocentricData.transformToLatLon(*geoActivityEnd)
        ax.plot(*activityStart[::-1], "or")
        ax.plot(*activityEnd[::-1], "or")
        ax.plot(*geoConvertedStart[::-1], "ob")
        ax.plot(*geoConvertedEnd[::-1], "ob")

    for sph, geo in zip(sphericalCircleList, geocentricCircleList)[:firstN]:
        sph.addCircleToPlot(ax)
        geo.addCircleToPlot(ax, color="red")

    plt.show()


def collectImages():
    distanceThSet = [2,4,7,10]
    confidenceThSet = [2,3,4]
    intersectionThSet = [0.1, 0.2, 0.4, 0.5]
    minDistThSet = [40,70,150]
    ThSet = list(itertools.product(distanceThSet,confidenceThSet, intersectionThSet, minDistThSet))
    for th in ThSet :
        
        appInfo.DistanceThreshold = th[0]
        appInfo.ConfidenceThreshold = th[1]
        
        appInfo.IntersectionThreshold = th[2]
       
        appInfo.MinDistanceThreshold = th[3]
       
        testAttack()


def testAttack(activityPathList, dataRepresentation, attackType = "EPZ+Fuzz"):
    
    possibleEPZs = attack(activityPathList,dataRepresentation, attackType)
    
    listEPZ = sorted(list(possibleEPZs), key= lambda x: -possibleEPZs[x])


    for possibleEPZ in listEPZ[:3]:
        print(possibleEPZ, "numerosità:", possibleEPZs[possibleEPZ])
    
    fig, ax = plt.subplots()

    colors = list(mcolors.CSS4_COLORS.keys())
    for index, possibleEPZ in enumerate(listEPZ[:3]):
        possibleEPZ.addCircleToPlot(ax, addColor=colors[19+index], addLabel = possibleEPZs[possibleEPZ])
    plt.plot()


    addPolylineToPlot(ax, Activity.Activity.initActivityFromPath(activityPathList[0]).decodePolyline(attackType), "base")
    for activityPath in activityPathList:
        activity = Activity.Activity.initActivityFromPath(activityPath)
        coordsList = activity.decodePolyline(attackType)
        
        if dataRepresentation.__class__.__name__ == "GeocentricDataRepresentation":
            coordsList = dataRepresentation.convertCoordsListIntoRepresentation(coordsList)
            coordsList = dataRepresentation.convertCoordsListIntoLatLon(coordsList)
            addPolylineToPlot(ax, coordsList, attackType+" - DoubleTransformed")
        else:
            addPolylineToPlot(ax, coordsList, attackType)
        

    

    ax.plot()
    folderPath = 'images/'+datetime.datetime.now().strftime("%Y-%m-%d")+"/"
    if not os.path.exists(os.path.dirname(folderPath)):
        os.makedirs(os.path.dirname(folderPath))
    figName=folderPath+'epzPlotted'+datetime.datetime.now().strftime("%H-%M-%S")+'.png'
    plt.title(f"{dataRepresentation.__class__.__name__} \n Intersection Threshold = {appInfo.IntersectionThreshold}, Distance Threshold = {appInfo.DistanceThreshold} \n Confidence Threshold = {appInfo.ConfidenceThreshold}, MinDistance Threshold = {appInfo.MinDistanceThreshold} ")
    plt.legend(loc="upper right")
    plt.show()
    fig.savefig(figName)


def initializeApplication(appName):
    global appInfo
    appInfo = ApplicationInfo.ApplicationInfo(appName)


def fetchDataFromApplication():
    authController = AuthController.AuthController(appInfo)
    session = authController.retriveSession()
    activityRetriver = ActivityRetriever.ActivityRetriever(session, appInfo)
    activityRetriver.fetchActivity()


def initializeUser(username):
    helper = jsonHelper.jsonHelper(appInfo)
    user = User.User(username)
    user.setActivity(helper)
    return user


def attack(activityPathList, dataRepresentation, AttackType):
    epzsa = EPZSearch.EPZSearch(dataRepresentation, activityPathList, appInfo, AttackType)
    now = time.time()
    print("start")
    epzsa.initializeAttack()
    print(len(epzsa.possibleEPZs))
    now2 = time.time()
    print(now2-now)
    epzsa.deleteEPZintersectingActivity()
    print(len(epzsa.possibleEPZs))
    now3 = time.time()
    print(now3-now2)
    epzsa.groupCloseEPZs()
    print(len(epzsa.possibleEPZs))
    now4 = time.time()
    print(now4-now3)
    epzsa.deleteInformationlessEPZ()
    now5 = time.time()
    print(now5-now4)
    epzsa.convertInLatLon()
    return epzsa.possibleEPZs


def secondAttack(clusterPath = "Data/Strava/39260108/ActivityClusterList.json", clusterId = 1):
    activityCluster = ActivityCluster.ActivityCluster.initializeActivityClusterFromJson(clusterPath, clusterId)
    epzSearch = EPZSearch2.EPZSearch(activityCluster)

    tau_converged = 10
    tau_disjoint = 1600
    epz_circles = epzSearch.epz_identification(tau_converged, tau_disjoint)

    print("Identified EPZs (center, radius):")
    
    for center, radius, _ in epz_circles:
        print(f"Center: {center}, Radius: {radius}")
    
    epzSearch.retriveSensitiveLocation(epz_circles[0])
    epzSearch.retriveSensitiveLocationThroughClusters(epz_circles[0])


def addPolylineToPlot(plt, coordinateList, label=None):
    ys, xs = zip(*coordinateList)
    plt.plot(xs[0], ys[0], marker='o', color='g', ms=5)
    if label is None:
        plt.plot(xs ,ys)
    else:
        plt.plot(xs ,ys, label=label)
    plt.plot(xs[-1], ys[-1], marker='x', color='r', ms=5)


####    Plotting activity
def plotUserActivity(userId="39260108"):        
    plt.figure()
    user = initializeUser(userId)
    for activity in user.activityList:
        activity.addActivityToPlot(plt)
    plt.legend(loc="upper left")
    plt.show() 

  
####    Test Activity clustering
def clusterAllActivities(userPath="Data/Strava/39260108"):
    activityClusterList = ActivityCluster.ActivityCluster.getAllClusters(userPath+"/activities", 1600)
    for activityCluster in activityClusterList:
        ActivityCluster.ActivityCluster.addActivityClusterToJson(userPath+"/ActivityClusterList.json", activityCluster)
    

####        Test for disguising Activities
def disguiseActivityInCluster(clusterPath="Data/Strava/39260108/ActivityClusterList.json", clusterId=1, dataRepresentation=DataRepresentationFactory.SphericalDataRepresentationFactory().create_data_representation("EPZ"), updateJson=True):
    activityCluster = ActivityCluster.ActivityCluster.initializeActivityClusterFromJson(clusterPath, clusterId)
    activityCluster.initializeActivityList()

    for activity in activityCluster.activityList:
        activity.disguiseActivityInCluster(activityCluster, dataRepresentation, updateJson=updateJson)
        activity.disguiseActivityInCluster(activityCluster, dataRepresentation, cloacked=True, updateJson=updateJson)

if __name__ == "__main__":
    main()



    


    
   
