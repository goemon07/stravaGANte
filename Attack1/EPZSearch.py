import collections

class EPZSearch():
    
    def __init__(self, data_representation, activityEndPointList, appInfo, attackType):

        self.attackType = attackType
        self.dataRepresentation = data_representation
        self.activityEndpointList = activityEndPointList
        self.endPointPairs = self.getAllPairs(self.activityEndpointList)
        
        #Initialize App-Specific Parameters
        self.EPZRadiuses = appInfo.getEPZRadiusesList()
        self.intersectionThreshold = appInfo.getIntersectionThreshold()
        self.distanceThreshold = appInfo.getDistanceThreshold()
        self.confidenceThreshold = appInfo.getConfidenceThreshold()
        self.minDistanceThreshold = appInfo.getMinDistanceThreshold()

    def initWithPathList(self, dataRepresentation, activityPathList, appInfo, attackType):
        activityEndpointList = dataRepresentation.getActivityEndpointList(activityPathList)
        return EPZSearch(dataRepresentation, activityEndpointList, appInfo, attackType)

    def attack(self):
        self.initializeAttack()
        self.deleteEPZintersectingActivity()
        self.groupCloseEPZs()
        self.deleteInformationlessEPZ()
        return self.possibleEPZs

    @staticmethod
    def getAllPairs(list):
        return [(a, b) for idx, a in enumerate(list) for b in list[idx + 1:]]

    #Iterate per each pair of activity
    def initializeAttack(self):
        self.possibleEPZs = collections.defaultdict(int)

        for endPointPair in self.endPointPairs:
            SS = self.dataRepresentation.getPossibleEPZfromPointPair(endPointPair, self.EPZRadiuses, self.minDistanceThreshold)
            if SS is not None:
                for EPZ in SS:
                    self.possibleEPZs[EPZ]+=1

    
    #Delete EPZs that countains the start or the end of any activity
    def deleteEPZintersectingActivity(self):
        for EPZ in list(self.possibleEPZs):
            for endPoint in self.activityEndpointList:
                if self.dataRepresentation.distance(endPoint.center, EPZ.center) + self.intersectionThreshold < EPZ.radius:
                    del self.possibleEPZs[EPZ]
                    break
    

    #Grouping EPZs that are closer than a certain Distance Threshold (WITH SAME Radius)
    def groupCloseEPZs(self):
        for EPZ1 in list(self.possibleEPZs):
            for EPZ2 in list(self.possibleEPZs):
                if EPZ1!=EPZ2:
                    if self.dataRepresentation.distance(EPZ1.center,EPZ2.center) < self.distanceThreshold:
                        """ ## Weighted mean of centers
                        new_lat = (EPZ1.lat * self.possibleEPZs[EPZ1] + EPZ2.lat * self.possibleEPZs[EPZ2]) / (self.possibleEPZs[EPZ1] + self.possibleEPZs[EPZ2])
                        new_lon = (EPZ1.lon * self.possibleEPZs[EPZ1] + EPZ2.lon * self.possibleEPZs[EPZ2]) / (self.possibleEPZs[EPZ1] + self.possibleEPZs[EPZ2])
                        EPZ1.lat = new_lat
                        EPZ1.lon = new_lon
                        EPZ1.center = [new_lat, new_lon] """
                        self.possibleEPZs[EPZ1] += self.possibleEPZs[EPZ2]
                        del self.possibleEPZs[EPZ2]


    #Deleting EPZs that are occurred less than a certain Confidence Threshold
    def deleteInformationlessEPZ(self):
        for key,value in list(self.possibleEPZs.items()):
            if value < self.confidenceThreshold:
                del self.possibleEPZs[key]

    
    def convertInLatLon(self):
        self.dataRepresentation.convertEPZList(self.possibleEPZs)