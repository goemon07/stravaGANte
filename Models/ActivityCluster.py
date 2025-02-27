from Utility.jsonHelper import jsonHelper
from Models import Activity
import matplotlib.pyplot as plt
import os
import geopy.distance
import json
import gpxpy

class ActivityCluster():

    def __init__(self, **kwargs):
        self.id = kwargs.get('id', None)
        self.source = kwargs.get('source', None)
        self.lat = kwargs.get('lat', None)
        self.lon = kwargs.get('lon', None)
        self.center = kwargs.get('center', None)
        self.cloackedLat = kwargs.get('cloacked_lat', None)
        self.cloackedLon = kwargs.get('cloacked_lon', None)
        self.cloackedCenter = kwargs.get('cloacked_center', None)
        self.radius = kwargs.get('radius', None)
        self.radiusMUnit = kwargs.get('radiusMUnit', None)
        self.ActivityClusterListPath = kwargs.get('ActivityClusterListPath', None)
        self.activitiesPath = kwargs.get('activitiesPath', None)
        self.activityIdList = kwargs.get('activityIdList', None)
        if self.lat is None and self.lon is None and self.center is not None:
            self.lat = self.center[0]
            self.lon = self.center[1]
        if self.cloackedLat is None and self.cloackedLon is None and self.cloackedCenter is not None:
            self.cloackedLat = self.cloackedCenter[0]
            self.cloackedLon = self.cloackedCenter[1]
        if self.center is None and self.lat is not None:
            self.center = [self.lat, self.lon]
        if self.cloackedCenter is None and self.cloackedLat is not None:
            self.cloackedCenter = [self.cloackedLat, self.cloackedLon]
        self.activityList = []
        self.activityPathList = []
        for activityId in self.activityIdList:
            self.activityPathList.append(self.activitiesPath+"/"+activityId+".json")        


    def updateActivityList(self):
        activityIdList = jsonHelper.getActivityIdListByPath(self.activitiesPath)
        collectedIdList = []
        for activity in activityIdList:
            latLng = jsonHelper.getJsonValue(os.path.join(self.activitiesPath, activity), "start_latlng")
            distance = geopy.distance.geodesic(latLng, self.center).m
            if distance < self.radius:
                collectedIdList.append(activity.split(".")[0])
        self.updateActivityListToActivityClusterJson(self, collectedIdList)
        return


    def initializeActivityList(self):
        for activity in self.activityIdList:
            currActivity = Activity.Activity.initActivityFromPath(self.activitiesPath +"/"+ activity +".json")
            self.activityList.append(currActivity)
        return
    

    @staticmethod
    def initializeActivityClusterFromJson(jsonPath, id=None):
        jsonData = json.loads(open(jsonPath, encoding="utf-8").read())
        jsonData["ActivityClusterList"].append({"ActivityClusterListPath": jsonPath})
        if id == None:
            return ActivityCluster(**jsonData["ActivityClusterListPath"][0])
        else:
            for activityClusteritem in jsonData["ActivityClusterList"]:
                if activityClusteritem["id"] == id:
                    return ActivityCluster(**activityClusteritem)
            print(f"No ActivityClusterwith id: {id} was found")
            return None


    @staticmethod
    def updateActivityListToActivityClusterJson(activityCluster, activityList):
        with open(activityCluster.ActivityClusterListPath+"/ActivityClusterList.json", 'r+', encoding="UTF-8") as jsonFile:
            jsonData = json.load(jsonFile)
            for activityClusterEntry in jsonData["ActivityClusterList"]:
                if activityCluster["id"] == activityCluster.id:
                    activityClusterEntry["activityIdList"] = activityList
            jsonFile.seek(0)
            json.dump(jsonData, jsonFile, indent = 4)
            jsonFile.truncate()
        return
    
    def updateActivityClusterCenterInJson(self, newCenter):
        if list(newCenter)[0] == "center":
            self.center = newCenter[list(newCenter)[0]]
        else:
            self.cloackedCenter = newCenter[list(newCenter)[0]]
        with open(self.ActivityClusterListPath, 'w+') as jsonFile:
            jsonData = json.load(jsonFile)
            for activityClusterEntry in jsonData["ActivityClusterList"]:
                if activityClusterEntry["id"] == self.id:
                    currentActivityCluster = activityClusterEntry
            currentActivityCluster[list(newCenter)[0]] = newCenter[list(newCenter)[0]]
            jsonFile.seek(0)
            json.dump(jsonData, jsonFile, indent = 4)
            jsonFile.truncate()
        return


    @staticmethod
    def addActivityClusterToJson(activityClusterPath, activityCluster):
        try:
            with open(activityClusterPath, 'r+', encoding="UTF-8") as jsonFile:
                try:
                    jsonData = json.load(jsonFile)
                except json.JSONDecodeError:
                    jsonData = {"ActivityClusterList": []}
                
                for activityClusterEntry in jsonData["ActivityClusterList"]:
                    if activityClusterEntry["center"] == activityCluster["center"]:
                        return
                
                activityCluster["id"] = len(jsonData["ActivityClusterList"]) + 1
                jsonData["ActivityClusterList"].append(activityCluster)
                
                jsonFile.seek(0)
                json.dump(jsonData, jsonFile, indent=4)
                jsonFile.truncate()
        except FileNotFoundError:
            jsonData = {"ActivityClusterList": [activityCluster]}
            activityCluster["id"] = 1
            with open(activityClusterPath, 'w', encoding="UTF-8") as jsonFile:
                json.dump(jsonData, jsonFile, indent=4)
        return


    @staticmethod
    def addClusterToActivityClusterList(activityClusterPath, activityCluster) -> None:
        with open(activityClusterPath, 'r+', encoding="UTF-8") as jsonFile:
            jsonData = json.load(jsonFile)
            activityCluster["id"] = len(jsonData["ActivityClusterList"])+1
            jsonData["ActivityClusterList"].append(activityCluster)
            jsonFile.seek(0)
            json.dump(jsonData, jsonFile, indent=4)
            jsonFile.truncate()
        return

    def addCircleToPlot(self, ax, cloacked = False, color = "black", addLabel = None):
        if cloacked:
            lat, lon = self.cloackedCenter
        else:
            lat, lon = self.center
        radius = self.radius

        ax.add_patch(plt.Circle((lon, lat), radius/111320, fill=False, color=color ))
        if addLabel != None:
            #ax.plot(lon, lat, "ob", label=f"Center={round(lat, 6), round(lon,6)} \n radius={radius} meters")
            ax.plot(lon, lat, "ob", label=addLabel)
        else:
            ax.plot(lon, lat, "ob")

    def __str__(self):
        return f"Cerchio posizionato in {self.center} di raggio {self.radius}"

    
    ## Group together activities that starts within a certain radius
    @staticmethod
    def getAllClusters(activitiesPath, radius=1600, clusterThreshold = 3, checkEnd = True):
        ActivityClusterList = []
        activityIdList = jsonHelper.getActivityIdListByPath(activitiesPath)

        for activityId in activityIdList:
            latlng = jsonHelper.getJsonValue(activitiesPath+"/"+activityId, "start_latlng")
            if len(latlng) != 2:
                continue
            found = False
            for activityCluster in ActivityClusterList:
                if geopy.distance.geodesic(latlng, activityCluster["center"]).m < radius:
                    found = True
                    new_x = (activityCluster["center"][0]*len(activityCluster["activityIdList"])+latlng[0])/(len(activityCluster["activityIdList"])+1)
                    new_y = (activityCluster["center"][1]*len(activityCluster["activityIdList"])+latlng[1])/(len(activityCluster["activityIdList"])+1)
                    activityCluster["activityIdList"].append(activityId.split(".")[0])
                    activityCluster["center"] = [new_x, new_y]
            if not found:
                ActivityClusterList.append({"id": None,  "source": "clustering", "radius": radius, "center": [latlng[0],latlng[1]], "activitiesPath": activitiesPath , "activityIdList": [activityId.split(".")[0]]})
        
        if clusterThreshold == 0:
            return ActivityClusterList
        
        endCheck = []
        for activityCluster in list(ActivityClusterList):
            if len(activityCluster["activityIdList"]) <= clusterThreshold:
                endCheck+=activityCluster["activityIdList"]
                ActivityClusterList.remove(activityCluster)

        if not checkEnd:
            return ActivityClusterList
        
        for activityId in endCheck:
            latlng = jsonHelper.getJsonValue(activitiesPath+"/"+activityId+".json", "end_latlng")
            if len(latlng) != 2:
                continue
            for activityCluster in ActivityClusterList:
                if geopy.distance.geodesic(latlng, activityCluster["center"]).m < radius:
                    found = True
                    new_x = (activityCluster["center"][0]*len(activityCluster["activityIdList"])+latlng[0])/(len(activityCluster["activityIdList"])+1)
                    new_y = (activityCluster["center"][1]*len(activityCluster["activityIdList"])+latlng[1])/(len(activityCluster["activityIdList"])+1)
                    activityCluster["activityIdList"].append(activityId)
                    activityCluster["center"] = [new_x, new_y]

        return ActivityClusterList
