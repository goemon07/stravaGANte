from abc import ABC,abstractmethod
from DataRepresentation.DataRepresentation import SphericalDataRepresentation, GeocentricDataRepresentation, UTMDataRepresentation


class DataRepresentationFactory(ABC):
    @abstractmethod
    def create_data_representation(self):
        pass


class SphericalDataRepresentationFactory(DataRepresentationFactory):
    def create_data_representation(self, attackType="EPZ"):
        return SphericalDataRepresentation(attackType)
    
    def __name__(self):
        return "Spherical Data Representation (F)"



class UTMDataRepresentationFactory(DataRepresentationFactory):
    def create_data_representation(self):
        return UTMDataRepresentation()
    
    def __name__(self):
        return "UTM Data Representation (F)"


class GeocentricDataRepresentationFactory(DataRepresentationFactory):
    def create_data_representation(self):
        return GeocentricDataRepresentation()
    
    def __name__(self):
        return "Geocentric Data Representation (F)"