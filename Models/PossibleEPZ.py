import matplotlib.pyplot as plt

class PossibleEPZ():
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', None)
        self.source = kwargs.get('source', None)
        self.lat = kwargs.get('lat', None)
        self.lon = kwargs.get('lon', None)
        self.x = kwargs.get('x', None)
        self.y = kwargs.get('y', None)
        if self.x is not None:
            self.center = [self.x, self.y]
        if self.lat is not None:
            self.center = [self.lat, self.lon]
        self.radius = kwargs.get('radius', None)

    def getCenter4Plot(self):
        return [self.lon, self.lat]
    
    def transformToLatLon(self, lat, lon):
        self.lat = lat
        self.lon = lon
        self.center = [self.lat, self.lon]
        
    def addCircleToPlot(self, ax, addColor = "black", addLabel = None):
        ax.add_patch(plt.Circle(self.getCenter4Plot(), self.radius/111320, fill=False, color=addColor ))
        if addLabel != None:
            #ax.plot(self.lon, self.lat, "ob", label=f"Center={round(self.center[0], 6), round(self.center[1],6)} \n radius={self.radius} meters")
            ax.plot(self.lon, self.lat, "o", label=addLabel, color=addColor)
        else:
            ax.plot(self.lon, self.lat, "o", color=addColor)
    

    def __str__(self):
        return f"Cerchio posizionato in {self.center} di raggio {self.radius}"