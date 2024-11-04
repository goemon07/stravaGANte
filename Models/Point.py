from abc import ABC, abstractmethod

class Point(ABC):
    @abstractmethod
    def __init__(self):
        pass

class SphericalPoint(Point):
    def __init__(self, lat, lon, id=None, radius=6371000):
        self.lat = lat
        self.lon = lon
        self.id = id
        self.radius = radius
        self.center = [self.lat, self.lon]
        
    def __str__(self):
        return f"lat: {self.lat}, lon: {self.lon}"
    
class GeocentricPoint(Point):
    def __init__(self, x, y, id=None):
        self.x = x
        self.y = y
        self.id = id
        self.center = [self.x, self.y]

    def __str__(self):
        return f"x: {self.x}, y: {self.y}"