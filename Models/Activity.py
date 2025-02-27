import os
import polyline
import matplotlib.pyplot as plt
import json
from Utility.jsonHelper import jsonHelper
import gpxpy
import gpxpy.gpx

class Activity():

    def __init__(self, **kwargs):
        self.id = kwargs.get('id', None)
        self.startDate = kwargs.get('start_date', None)
        self.userId = kwargs.get('athlete.id', None)
        self.distance = kwargs.get('distance', None)
        self.moving_time = kwargs.get('moving_time', None)
        self.elapsed_time = kwargs.get('elapsed_time', None)
        self.type = kwargs.get('type', None)
        self.startPoint = kwargs.get('start_latlng', None)
        self.endPoint = kwargs.get('end_latlng', None)
        self.maps = kwargs.get('map', None)
        self.activityPath = kwargs.get('activityPath', None)



    @staticmethod
    def initActivityFromPath(activityPath) :
        keyList = ["id", "start_date", "athlete.id", "distance", "moving_time", "elapsed_time", "type", "start_latlng", "end_latlng", "map"]
        valueList = jsonHelper.getJsonValues(activityPath, keyList)
        valueList['activityPath'] = activityPath
        return Activity(**valueList)
    


    def __str__(self):
        return f"Activity {self.id} of user {self.userId}, starts at {self.startPoint} and ends at {self.endPoint} and it's long {self.distance}"
    


    def decodePolyline(self, whatPolyLine = "polyline"):
        # print(self.maps[whatPolyLine])
        coordsList = polyline.decode(self.maps[whatPolyLine], 5, geojson=True)
        # coordsList = polyline.decode("polyline", 5, geojson=True)
        return [coords[::-1] for coords in coordsList]
            
    

    @staticmethod
    def encodePolyline(coordsList):
        return polyline.encode([coords[::-1] for coords in coordsList], 5, geojson=True)



    def addActivityToPlot(self, plt, whatPolyline = "EPZ",  addLabel = False):
        coordinateList = self.decodePolyline(whatPolyline)
        ys, xs = zip(*coordinateList)
        plt.plot(xs[0], ys[0], marker='o', color='g', ms=5)
        if addLabel:
            plt.plot(xs ,ys, label=str(self.id)+whatPolyline)
        else:
            plt.plot(xs ,ys)
        plt.plot(xs[-1], ys[-1], marker='x', color='r', ms=5)
        return [(ys[0], xs[0]), (ys[-1], xs[-1])]


    def plotActivity(self):
        plt.figure()
        self.addActivityToPlot(plt)
        plt.legend(loc="upper left")
        plt.show()


    def disguiseActivityInCluster(self, activityCluster, dataRepresentation, fuzz=False, cloacked = False, updateJson=False):
        if cloacked:
            if activityCluster.cloackedCenter is None:
                activityCluster.updateActivityClusterCenterInJson({'cloackedCenter':dataRepresentation.generateCloackedCenter(activityCluster.center, activityCluster.radius)})
            center = activityCluster.cloackedCenter
        else:
            center = activityCluster.center
        center = dataRepresentation.transformLatLon(*center)
        coordsList = self.decodePolyline()
        coordsList = dataRepresentation.convertCoordsListIntoRepresentation(coordsList)

        while dataRepresentation.distance(coordsList[0], center) <= activityCluster.radius:
            coordsList.pop(0)
        
        #Fuzz Radius
        if not fuzz:
            new_point = dataRepresentation.getPointOnCircumference(center, coordsList[0], activityCluster.radius)
            coordsList.insert(0, new_point)

        while dataRepresentation.distance(coordsList[-1], center) <= activityCluster.radius:
            coordsList.pop()

        #Fuzz Radius
        if not fuzz:
            new_point = dataRepresentation.getPointOnCircumference(center, coordsList[-1], activityCluster.radius)
            coordsList.append(new_point)

        coordsList = dataRepresentation.convertCoordsListIntoLatLon(coordsList)
        if dataRepresentation.__class__.__name__ == "GeocentricDataRepresentation":
            return coordsList
        
        if cloacked:
            self.cloackedEPZpolyLine = self.encodePolyLine(coordsList)
            if updateJson:
                self.updateActivityJson("map.cloackedepz_polyline", self.cloackedEPZpolyLine)
            return
        else:
            self.EPZpolyLine = self.encodePolyline(coordsList)
            if updateJson:
                self.updateActivityJson("map.epz_polyline", self.EPZpolyLine)
            return
        

    def completeDisguiseActivityInCluster(self, center, radius, cloackedCenter, sphericRepresentation, geoRepresentation):
        coordsList = self.decodePolyline()
        cloackedCoordsList = coordsList.copy()
        geoCoordsList = coordsList.copy()
        ## Cut Start
        while sphericRepresentation.distance(coordsList[0], center) < radius:
            last = coordsList.pop(0)
        #Fuzz Radius
        new_point = sphericRepresentation.getPointOnCircumference(tuple(center), last, coordsList[0], radius)
        coordsList.insert(0, new_point)
        ## Cut End
        while sphericRepresentation.distance(coordsList[-1], center) <= radius:
            last = coordsList.pop()
        #Fuzz Radius
        new_point = sphericRepresentation.getPointOnCircumference(center, last, coordsList[-1], radius)
        coordsList.append(new_point)
        ## Save encoded
        self.maps["EPZ"] = self.encodePolyline(coordsList)
        self.maps["EPZ+Fuzz"] = self.encodePolyline(coordsList[1:-1])
        

        ###     Disguise with cloacking
        ## Cut Start
        while sphericRepresentation.distance(cloackedCoordsList[0], cloackedCenter) < radius:
            last = cloackedCoordsList.pop(0)
        #Fuzz Radius
        new_point = sphericRepresentation.getPointOnCircumference(cloackedCenter, last, cloackedCoordsList[0], radius)
        cloackedCoordsList.insert(0, new_point)
        ## Cut End
        while sphericRepresentation.distance(cloackedCoordsList[-1], cloackedCenter) <= radius:
            last = cloackedCoordsList.pop()
        #Fuzz Radius
        new_point = sphericRepresentation.getPointOnCircumference(cloackedCenter, last, coordsList[-1], radius)
        cloackedCoordsList.append(new_point)
        ## Save Encoded
        self.maps["CloackedEPZ"] = self.encodePolyline(cloackedCoordsList)
        self.maps["CloackedEPZ+Fuzz"] = self.encodePolyline(cloackedCoordsList[1:-1])
        
        
        ###     Disguise GEOCENTRIC Data representation     ###
        geoCoordsList = geoRepresentation.convertCoordsListIntoRepresentation(coordsList)
        geoCenter = geoRepresentation.transformLatLon(*center)
        geoCloackedCoordsList = geoCoordsList.copy()
        ## Cut Start
        while geoRepresentation.distance(geoCoordsList[0], geoCenter) < radius:
            geoCoordsList.pop(0)
        #Fuzz Radius
        new_point = geoRepresentation.getPointOnCircumference(geoCenter, geoCoordsList[0], radius)
        geoCoordsList.insert(0, new_point)
        ## Cut End
        while geoRepresentation.distance(geoCoordsList[-1], geoCenter) <= radius:
            geoCoordsList.pop()
        #Fuzz Radius
        new_point = geoRepresentation.getPointOnCircumference(geoCenter, coordsList[-1], radius)
        geoCoordsList.append(new_point)
        ## Save encoded
        geoCoordsList = geoRepresentation.convertCoordsListIntoLatLon(geoCoordsList)
        self.maps["GeocentricEPZ"] = self.encodePolyline(geoCoordsList)
        self.maps["GeocentricEPZ+Fuzz"] = self.encodePolyline(geoCoordsList[1:-1])

        
        ###     GEOCENTRIC Disguise with cloacking        
        geoCloackedCenter = geoRepresentation.transformLatLon(*cloackedCenter)
        ## Cut Start
        while geoRepresentation.distance(geoCloackedCoordsList[0], geoCloackedCenter) < radius:
            geoCloackedCoordsList.pop(0)
        #Fuzz Radius
        new_point = geoRepresentation.getPointOnCircumference(geoCloackedCenter, geoCloackedCoordsList[0], radius)
        geoCloackedCoordsList.insert(0, new_point)
        ## Cut End
        while geoRepresentation.distance(geoCloackedCoordsList[-1], geoCloackedCenter) <= radius:
            geoCloackedCoordsList.pop()
        #Fuzz Radius
        new_point = geoRepresentation.getPointOnCircumference(geoCloackedCenter, geoCloackedCoordsList[-1], radius)
        geoCloackedCoordsList.append(new_point)
        ## Save encoded
        geoCloackedCoordsList = geoRepresentation.convertCoordsListIntoLatLon(geoCloackedCoordsList)
        self.maps["GeocentricCloackedEPZ"] = self.encodePolyline(geoCloackedCoordsList)
        self.maps["GeocentricCloackedEPZ+Fuzz"] = self.encodePolyline(geoCloackedCoordsList[1:-1])

        # Clean old manipulations
        toDelete = ["epz_polyLine", "cloackedepz_polyline", "epz_polyline"]
        for delete in toDelete:
            if delete in self.maps:
                del self.maps[delete]

        ## Update Json
        self.updateActivityJson("map", self.maps)
        return self.maps


    def updateActivityJson(self, key, value):  
        with open(self.activityPath, 'r+', encoding="UTF-8") as jsonFile:
            jsonData = json.load(jsonFile)
            dividedKey = key.split('.')
            jsonSubData = jsonData

            for subKey in dividedKey[:-1]:
                if subKey not in jsonSubData:
                    jsonSubData[subKey] = ""
                jsonSubData = jsonSubData[subKey]
                
            jsonSubData[dividedKey[-1]]=value
            
            jsonFile.seek(0)
            json.dump(jsonData, jsonFile, indent = 4)
            jsonFile.truncate()
        return


    #################### GPX handling ####################
    def encode_polyline_from_gpx(gpx_file):
        try:
            with open(gpx_file, 'r') as f:
                gpx = gpxpy.parse(f)
        except FileNotFoundError:
            print(f"Error: GPX file not found at '{gpx_file}'")
            return None
        except gpxpy.gpx.GPXException as e:
            print(f"Error parsing GPX file: {e}")
            return None

        coordList = []
        for point in gpx.routes[0].points:
            coordList.append((point.latitude, point.longitude))

        if not coordList:
            print("No track coordList found in the GPX file.")
            return None, None, None
        else:
            start_point = (coordList[0][0], coordList[0][1])
            end_point = (coordList[-1][0], coordList[-1][1])
            return Activity.encodePolyline(coordList), start_point, end_point

   
    @staticmethod
    def initializeActivityFromGpx(gpxPath):
        encoded_polyline, start_point, end_point = Activity.encode_polyline_from_gpx(gpxPath)

        if encoded_polyline:
            json_file_path = os.path.join(gpxPath.replace(".gpx", ".json"))
            with open(json_file_path, 'w', encoding='utf-8') as json_file:
                json.dump({
                    "map": {
                        "polyline": encoded_polyline
                    },
                    "start_latlng": start_point,
                    "end_latlng": end_point
                }, json_file, ensure_ascii=False, indent=4)
            
            return 1
        else:
            return 0