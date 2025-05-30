from Utility.jsonHelper import jsonHelper
from Models import Point, PossibleEPZ
import polyline
from pyproj import Transformer
import geopy.distance
from geographiclib.geodesic import Geodesic
import math
import random
import utm
from pyproj import Transformer

class DataRepresentation:
    def getActivityEndpointList(self):
        pass

    def getPossibleEPZfromPointPair(self):
        pass

    def distance(self):
        pass

    def convertEPZList(self, possibleEPZs):
        pass

class SphericalDataRepresentation(DataRepresentation):
    def __init__(self, attackType):
        self.attackType = attackType
    

    def getPolylineList(self, activityPathList):
        activityList = []
        for activityPath in activityPathList:
            values = jsonHelper.getJsonValues(activityPath, ["id", "map"])
            coords = polyline.decode(values["map"]["polyline"])
            activityList.append({"id": values["id"], "polyline": coords})
        return activityList


    def getActivityEndpointList(self, activityPathList):
        activityEndpointList = []
        for activityPath in activityPathList:
            # values = jsonHelper.getJsonValues(activityPath, ["id", "map.epz_polyline"])
            # coords = polyline.decode(values["map.epz_polyline"])
            values = jsonHelper.getJsonValues(activityPath, ["id", "map.polyline"])
            coords = polyline.decode(values["map.polyline"])
            # print(coords[0])
            activityEndpointList.append(Point.SphericalPoint(coords[0][0],coords[0][1], id="start"+str(values["id"])))
            activityEndpointList.append(Point.SphericalPoint(coords[-1][0],coords[-1][1], id="end"+str(values["id"])))
        return activityEndpointList

    def getPossibleEPZfromPointPair(self, endPointPair, EPZRadiuses, minDistanceThreshold=4000):
        circleList = []
        if isinstance(endPointPair[0].__class__, Point.Point.__class__):
            lat1, lon1 = endPointPair[0].center
            lat2, lon2 = endPointPair[1].center
        else:
            lat1, lon1 = endPointPair[0]
            lat2, lon2 = endPointPair[1]
        mid_point = self.midPoint(lat1, lon1, lat2, lon2)
        mid_distance = geopy.distance.geodesic((lat1, lon1), mid_point).meters
        if mid_distance*2 < minDistanceThreshold:
            return circleList
        for r in EPZRadiuses:
            if mid_distance > r:
                continue
            segment_len = (r**2 - mid_distance**2)**0.5
            geod = Geodesic.WGS84
            azimuth = geod.InverseLine(lat1, lon1, lat2, lon2).azi1
            endpoint = geod.Direct(*mid_point, azimuth+90, segment_len)
            endpoint2 = geod.Direct(*mid_point, azimuth-90, segment_len)
            circleList.append(PossibleEPZ.PossibleEPZ(**{"lat":endpoint["lat2"],"lon":endpoint["lon2"],"radius": r}))
            circleList.append(PossibleEPZ.PossibleEPZ(**{"lat":endpoint2["lat2"],"lon":endpoint2["lon2"],"radius": r}))
        return circleList     
    
    @staticmethod
    def midPoint(lat1, lon1, lat2, lon2):
        lat1 = math.radians(lat1)
        lat2 = math.radians(lat2)
        lon1 = math.radians(lon1)
        lon2 = math.radians(lon2)

        bx = math.cos(lat2) * math.cos(lon2 - lon1)
        by = math.cos(lat2) * math.sin(lon2 - lon1)
        lat3 = math.atan2(math.sin(lat1) + math.sin(lat2), \
            math.sqrt((math.cos(lat1) + bx) * (math.cos(lat1) \
            + bx) + by**2))
        lon3 = lon1 + math.atan2(by, math.cos(lat1) + bx)

        return [math.degrees(lat3), math.degrees(lon3)]

    @staticmethod
    def distance(coords1, coords2):
        return geopy.distance.geodesic(coords1, coords2).meters

    def convertEPZList(self, possibleEPZs):
        pass

    def getPointOnCircumference(self, center, outerPoint, radius):
        geod = Geodesic.WGS84.InverseLine(*center, *outerPoint)
        endpoint = geod.Position(radius, Geodesic.STANDARD)        
        return (round(endpoint['lat2'], 5), round(endpoint['lon2'], 5))
    
    @staticmethod
    def generateCloackedCenter(center, radius):
        radius_degrees = radius/111000
        distance = random.uniform(0.4, 0.9) * radius_degrees
        angle = random.uniform(0 , 2*math.pi)
        delta_lat = math.cos(angle)*distance
        delta_lon = math.sin(angle)*distance
        new_lat = center[0] + delta_lat
        new_lon = center[1] + delta_lon
        return [new_lat, new_lon]
    
    @staticmethod
    def transformLatLon(lat, lon):
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"Invalid latitude or longitude values: lat={lat}, lon={lon}")
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        return transformer.transform(lat, lon)

    @staticmethod
    def transformToLatLon(x, y, z):
        transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
        #return transformer.transform(x, y, z)
        return transformer.transform(x, y)[::-1]

class GeocentricDataRepresentation(DataRepresentation):

    def getActivityEndpointList(self, activityPathList):
        activityEndpointList = []
        for activityPath in activityPathList:
            values = jsonHelper.getJsonValues(activityPath, ["id", "map.polyline"])
            coords = polyline.decode(values["map.polyline"])
            # start_x, start_y = self.transformLatLon(coords[0][0],coords[0][1])
            # end_x, end_y = self.transformLatLon(coords[-1][0],coords[-1][1])
            start_lat, start_lon = coords[0][0], coords[0][1]
            end_lat, end_lon = coords[-1][0],coords[-1][1]
            activityEndpointList.append(Point.SphericalPoint(start_lat, start_lon, id="start"+str(values["id"])))
            activityEndpointList.append(Point.SphericalPoint(end_lat, end_lon, id="end"+str(values["id"])))
        return activityEndpointList
    
    def convertCoordsListIntoRepresentation(self, coordsList):
        coordsList = [coords for coords in coordsList if not any(math.isnan(coord) for coord in coords)]
        return [self.transformLatLon(lat, lon) for lat, lon in coordsList]

    def convertCoordsListIntoLatLon(self, coordsList):
        c = []
        for x, y in coordsList:
            c.append(self.transformToLatLon(x, y))
        return c
    
    @staticmethod
    def transformLatLon(lat, lon):
        if any([math.isnan(lat), math.isnan(lon)]):
            print(f"Invalid latitude or longitude values: lat={lat}, lon={lon}")
        # transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        t = transformer.transform(lon, lat)
        return t

    @staticmethod
    def transformToLatLon(x, y):
        # transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
        transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
        return transformer.transform(x, y)[::-1]

    @staticmethod
    def distance(point1, point2):
        x1,y1 = point1
        x2,y2 = point2
        return ((x1-x2)**2+(y1-y2)**2)**0.5
    
    def getPossibleEPZfromPointPair(self, pointPair, EPZRadiuses, minDistanceThreshold):
        circleList = []
        if self.distance(pointPair[0].center, pointPair[1].center)<minDistanceThreshold:
            return circleList
        x1, y1 = pointPair[0].center
        x2, y2 = pointPair[1].center
        # delta x, delta y between points
        dx, dy = x2 - x1, y2 - y1
        # dist between points
        q = math.sqrt(dx**2 + dy**2)
        if q == 0:
            return
        x3, y3 = (x1+x2)/2, (y1+y2)/2
        for r in EPZRadiuses:
            if q > 2*r :
                continue
            d = math.sqrt(r**2-(q/2)**2)
            centerX1 = x3 - d*dy/q
            centerY1 = y3 + d*dx/q
            centerX2 = x3 + d*dy/q
            centerY2 = y3 - d*dx/q
            circleList.append(PossibleEPZ.PossibleEPZ(**{"lat":centerX1,"lon":centerY1,"radius": r}))
            circleList.append(PossibleEPZ.PossibleEPZ(**{"lat":centerX2,"lon":centerY2,"radius": r}))
        return circleList
    
    def convertEPZList(self, possibleEPZs):
        for epz in possibleEPZs:
            epz.center = self.transformToLatLon(*epz.center)
        return
    
    def getPointOnCircumference(self, center, outerPoint, radius):
        x1, y1 = center
        x2, y2 = outerPoint
        dx = x2 - x1
        dy = y2 - y1
        # Calcola la lunghezza euclidea del vettore direzionale
        length = math.sqrt(dx**2 + dy**2)
        # Normalizza il vettore direzionale
        dx /= length
        dy /= length
        # Moltiplica il vettore direzionale per la distanza desiderata
        dx *= radius
        dy *= radius
        return (round(x1 + dx, 5), round(y1 + dy, 5))

    @staticmethod
    def generateCloackedCenter(center, radius):
        radius_degrees = radius / 111000
        distance = random.uniform(0.4, 0.9)*radius_degrees
        angle = random.uniform(0, 2*math.pi)
        delta_x = math.cos(angle)*distance
        delta_y = math.sin(angle)*distance
        new_x = center[0] + delta_x
        new_y = center[1] + delta_y
        return [new_x, new_y]
    
class UTMDataRepresentation(DataRepresentation):

    def __init__(self):
        self.tolatlon= Transformer.from_crs("EPSG:3857", "EPSG:4326")
        self.fromlatlon = Transformer.from_crs("EPSG:4326", "EPSG:3857")

    class UTMEndpoint():
        #def __init__(self, easting, northing, zoneNumber, zoneLetter, activityID, endpoint, distance):
        def __init__(self, x, y, activityID, endpoint, distance):
            #self.easting = easting
            #self.northing = northing
            self.x = x
            self.y = y
            #self.zoneNumber = zoneNumber
            #self.zoneLetter = zoneLetter
            self.activityID = activityID
            self.endpoint = endpoint
            self.distance = distance
            #self.center = [self.easting, self.northing, self.zoneNumber, self.zoneLetter]
            self.center = [self.x, self.y]
        
        def __str__(self):
            return f"Endpoint {self.activityID}:{self.endpoint}, Easting: {self.easting}, Northing: {self.northing}, {self.zoneNumber}, '{self.zoneLetter}', with {self.distance} meters hidden"

        def getID(self):
            return str(self.activityID)+self.endpoint
        
        def getCoords(self):
            #return [self.easting, self.northing, self.zoneNumber, self.zoneLetter ]
            return [self.x, self.y]
        

    def initActivityEndpointList(self, activityCLuster):
        activityEndpointList = []
        # cloackedCenterUTM = self.transformLatLon(activityCLuster.cloackedCenter[0], activityCLuster.cloackedCenter[1])
        #cloackedCenterUTM = utm.from_latlon(activityCLuster.cloackedCenter[0], activityCLuster.cloackedCenter[1])
        cloackedCenterUTM = self.fromlatlon.transform(activityCLuster.cloackedCenter[0], activityCLuster.cloackedCenter[1])
        for activityPath in activityCLuster.activityPathList:
            values = jsonHelper.getJsonValues(activityPath, ["id", "map.polyline"])
            coords = polyline.decode(values["map.polyline"])
            if len(coords) == 0:
                continue
            distance = 0
            #firstUTM = utm.from_latlon(*coords.pop(0)) ### is decoding output LatLon format? AAAAA
            firstUTM = self.fromlatlon.transform(*coords.pop(0)) ### is decoding output LatLon format? AAAAA
            if self.utmDistance(firstUTM, cloackedCenterUTM) < activityCLuster.radius: 
                for coord in coords:
                    #nextUTM = utm.from_latlon(*coord)
                    nextUTM = self.fromlatlon.transform(*coord)
                    distance += self.utmDistance(nextUTM, firstUTM)
                    if self.utmDistance(nextUTM, cloackedCenterUTM) > activityCLuster.radius:
                        break
                    else:
                        firstUTM = nextUTM
                activityEndpointList.append(self.UTMEndpoint(*nextUTM, values["id"], "Start", distance))
            
            distance = 0
            coordsReverse = coords[::-1]
            #lastUTM = utm.from_latlon(*coordsReverse.pop()) ### is decoding output LatLon format?
            lastUTM = self.fromlatlon.transform(*coordsReverse.pop()) ### is decoding output LatLon format?
            if self.utmDistance(lastUTM, cloackedCenterUTM) < activityCLuster.radius: 
                for coord in coordsReverse:
                    #beforeUTM = utm.from_latlon(*coord)
                    beforeUTM = self.fromlatlon.transform(*coord)
                    distance += self.utmDistance(beforeUTM, lastUTM)
                    if self.utmDistance(beforeUTM, cloackedCenterUTM) > activityCLuster.radius:
                        break
                    else:
                        lastUTM = beforeUTM
                activityEndpointList.append(self.UTMEndpoint(*beforeUTM, values["id"], "End", distance))
        return activityEndpointList
    
    

    @staticmethod
    def utmDistance(utm1, utm2):
        x1,y1 = utm1[:2]
        x2,y2 = utm2[:2]
        return ((x1-x2)**2+(y1-y2)**2)**0.5

    def getActivityEndpointList(self, activityPathList):
        activityEndpointList = []
        for activityPath in activityPathList:
            values = jsonHelper.getJsonValues(activityPath, ["id", "map.polyline"])
            coords = polyline.decode(values["map.polyline"])
            if len(coords) == 0:
                continue
            #utm_start = utm.from_latlon(coords[0][0],coords[0][1])
            utm_start = self.fromlatlon.transform(coords[0][0],coords[0][1])
            #utm_end = utm.from_latlon(coords[-1][0],coords[-1][1])
            utm_end = self.fromlatlon.transform(coords[-1][0],coords[-1][1])
            activityEndpointList.append(self.UTMEndpoint(*utm_start))
            activityEndpointList.append(self.UTMEndpoint(*utm_end))
        return activityEndpointList
