from Utility.jsonHelper import jsonHelper
import polyline
from pyproj import Transformer
import geopy.distance
from geographiclib.geodesic import Geodesic
import math
import random


class DataRepresentation:
    def getActivityEndpointList(self):
        pass

    def distance(self):
        pass


class SphericalDataRepresentation(DataRepresentation):
    def __init__(self, attackType="EPZ"):
        self.attackType = attackType

    @staticmethod
    def distance(coords1, coords2):
        return geopy.distance.geodesic(coords1, coords2).meters

    def getPointOnCircumference(self, center, outerPoint, radius):
        geod = Geodesic.WGS84.InverseLine(*center, *outerPoint)
        endpoint = geod.Position(radius, Geodesic.STANDARD)
        return (round(endpoint['lat2'], 5), round(endpoint['lon2'], 5))


class GeocentricDataRepresentation(DataRepresentation):

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
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        t = transformer.transform(lon, lat)
        return t

    @staticmethod
    def transformToLatLon(x, y):
        transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
        return transformer.transform(x, y)[::-1]

    @staticmethod
    def distance(point1, point2):
        x1, y1 = point1
        x2, y2 = point2
        return ((x1-x2)**2+(y1-y2)**2)**0.5

    def getPointOnCircumference(self, center, outerPoint, radius):
        x1, y1 = center
        x2, y2 = outerPoint
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx**2 + dy**2)
        dx /= length
        dy /= length
        dx *= radius
        dy *= radius
        return (round(x1 + dx, 5), round(y1 + dy, 5))


class UTMDataRepresentation(DataRepresentation):

    def __init__(self):
        self.tolatlon = Transformer.from_crs("EPSG:3857", "EPSG:4326")
        self.fromlatlon = Transformer.from_crs("EPSG:4326", "EPSG:3857")

    class UTMEndpoint():
        def __init__(self, x, y, activityID, endpoint, distance):
            self.x = x
            self.y = y
            self.activityID = activityID
            self.endpoint = endpoint
            self.distance = distance
            self.center = [self.x, self.y]

        def __str__(self):
            return f"Endpoint {self.activityID}:{self.endpoint}, Easting: {self.x}, Northing: {self.y}, with {self.distance} meters hidden"

        def getID(self):
            return str(self.activityID)+self.endpoint

        def getCoords(self):
            return [self.x, self.y]

    @staticmethod
    def generateCloackedCenter(center, radius):
        radius_degrees = radius / 111000
        distance = random.uniform(0.1, 0.5)*radius_degrees
        angle = random.uniform(0, 2*math.pi)
        delta_x = math.cos(angle)*distance
        delta_y = math.sin(angle)*distance
        new_x = center[0] + delta_x
        new_y = center[1] + delta_y
        return [new_x, new_y]

    def getActivityEndpointList(self, activityPathList, epz_radius=400):
        activityEndpointList = []
        for activityPath in activityPathList:
            values = jsonHelper.getJsonValues(
                activityPath,
                ["id", "map.EPZ", "map.EPZ_start_distance", "map.EPZ_end_distance"]
            )
            coords = polyline.decode(values["map.EPZ"])
            if len(coords) == 0:
                continue
            start_dist = values.get("map.EPZ_start_distance") or epz_radius
            end_dist = values.get("map.EPZ_end_distance") or epz_radius
            utm_start = self.fromlatlon.transform(coords[0][0], coords[0][1])
            utm_end = self.fromlatlon.transform(coords[-1][0], coords[-1][1])
            if start_dist > 0:
                activityEndpointList.append(self.UTMEndpoint(*utm_start, values["id"], "Start", start_dist))
            if end_dist > 0:
                activityEndpointList.append(self.UTMEndpoint(*utm_end, values["id"], "End", end_dist))
        return activityEndpointList
