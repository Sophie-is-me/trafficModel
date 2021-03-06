import math
import random
import itertools

import matplotlib.colors as colors

from model.trajectory import Trajectory
from model.direction import Direction
from model.road import Road


class Car():
    id_generator = itertools.count(1)

    def __init__(self, *args, **kwargs):
        self.id = "car_" + str(next(self.id_generator))
        self.source = None
        self.target = None
        self.path = []
        self.graph = kwargs.get('graphList', None)
        if self.graph is not None:
            self.setPath()
        lane = kwargs.get('lane', random.choice(
            self.path.pop().lanes) if self.path else None)
        position = kwargs.get('position', 0)
        self.color = colors.rgb2hex(
            (random.random(), random.random(), random.random()))
        self._speed = 0
        self.width = 1.5
        self.length = 3 + random.randint(0, 3)
        self.maxSpeed = 20
        self.maxAcceleration = 0.3
        self.maxDeceleration = 3
        self.slowProb = 0.3
        self.trajectory = Trajectory(self, lane, position)
        self.__alive = True
        self.preferedLane = None
        self.nextLane = None
        self.timeHeadway = 1.5
        self.s0 = 2

    @property
    def speed(self):
        return self._speed

    @speed.setter
    def speed(self, speed):
        if speed < 0:
            speed = 0
        if speed > self.maxSpeed:
            speed = self.maxSpeed
        self._speed = speed

    @property
    def alive(self):
        return self.__alive

    @alive.setter
    def alive(self, alive):
        self.__alive = alive
        if self.__alive is False:
            self.release()

    @property
    def coords(self):
        return self.trajectory.coords

    @property
    def direction(self):
        return self.trajectory.direction

    def setPath(self):
        self.source = random.choice(list(self.graph.keys()))
        self.target = random.choice(list(self.graph.keys()))
        while self.source == self.target:
            self.target = random.choice(list(self.graph.keys()))
            if self.source != self.target:
                break

        self.Dijkstra()

    def release(self):
        self.trajectory.release()

    def getAcceleration(self):
        nextCarDistance = self.trajectory.nextCarDistance
        distanceToNextCar = max(nextCarDistance["distance"], 0)
        distanceToNextCar = distanceToNextCar if distanceToNextCar != 0 \
            else float('inf')
        distanceToStopLine = self.trajectory.distanceToStopLine
        a = self.maxAcceleration
        b = self.maxDeceleration
        deltaSpeed = (self.speed - nextCarDistance["car"].speed) \
            if nextCarDistance["car"] is not None else 0
        freeRoadCoeff = (self.speed / self.maxSpeed) ** 4
        distanceGap = self.s0
        timeGap = self.speed * self.timeHeadway
        breakGap = self.speed * deltaSpeed / (2 * math.sqrt(a * b))
        safeDistance = distanceGap + timeGap + breakGap
        busyRoadCoeff = (safeDistance / distanceToNextCar) ** 2 \
            if nextCarDistance["car"] is not None else 0
        safeIntersectionDistance = 1 + timeGap + self.speed ** 2 / (2 * b)
        intersectionCoeff = ((safeIntersectionDistance / distanceToStopLine) ** 2) \
            if distanceToStopLine != 0 else 0
        coeff = (1 - freeRoadCoeff) if nextCarDistance["car"] is None and self.nextLane is None \
            else 1 - freeRoadCoeff - busyRoadCoeff - intersectionCoeff
        # coeff = 1 - freeRoadCoeff - busyRoadCoeff - intersectionCoeff
        # newAcc = self.maxAcceleration * coeff if self.maxAcceleration * coeff > -b else -b
        return self.maxAcceleration * coeff

    def move(self, delta):
        acce = self.getAcceleration()
        self.speed += acce * delta

        if not self.trajectory.isChangingLanes and self.pickNextLane():
            currentLane = self.trajectory.current.lane
            turnNumber = currentLane.getTurnDirection(self.nextLane)
            if turnNumber is Direction.LEFT:
                preferedLane = currentLane.leftmostAdjacent
            elif turnNumber is Direction.RIGHT:
                preferedLane = currentLane.rightmostAdjacent
            elif turnNumber is Direction.STRAIGHT:
                preferedLane = currentLane
            if preferedLane is not currentLane:
                self.trajectory.changeLane(preferedLane)

        step = self.speed * delta + 0.5 * acce * delta ** 2
        if (self.trajectory.timeToMakeTurn(step)) \
                and self.nextLane is None:
            self.alive = False         
            return

        self.trajectory.moveForward(step)

    def pickNextRoad(self):
        intersection = self.trajectory.nextIntersection
        currentLane = self.trajectory.current.lane
        possibleRoads = [road for road in intersection.roads
                         if road.target is not currentLane.road.source]
        if not possibleRoads:
            return None
        nextRoad = random.choice(possibleRoads)
        return nextRoad

    def popNextRoad(self):
        return self.path.pop() if self.path else None

    def pickNextLane(self):
        self.nextLane = None
        nextRoad = self.pickNextRoad() if not self.graph \
            else self.popNextRoad()
        if not nextRoad:
            self.nextLane = None
            return None
        laneNumber = random.randint(0, nextRoad.lanesNumber - 1)
        turnNumber = self.trajectory.current.lane.getTurnDirection(
            nextRoad.lanes[laneNumber])
        if turnNumber is Direction.RIGHT:
            self.nextLane = nextRoad.rightmostLane
        elif turnNumber is Direction.STRAIGHT:
            self.nextLane = nextRoad.lanes[laneNumber]
        elif turnNumber is Direction.LEFT:
            self.nextLane = nextRoad.leftmostLane
        assert self.nextLane is not None
        return self.nextLane

    def popNextLane(self):
        nextLane = self.nextLane
        self.nextLane = None
        self.preferedLane = None
        return nextLane

    def Dijkstra(self):
        vertex = set()
        prev = dict()
        shortRange = dict()
        intersectionList = []
        for i in self.graph.keys():
            shortRange[i] = math.inf
            vertex.add(i)
            prev[i] = 0

        shortRange[self.source] = 0
        Z = set()
        while Z != vertex:
            vzdiff = vertex - Z
            u = vzdiff.pop()

            vzdiff.add(u)
            minimum = shortRange[u]

            for i in vzdiff:
                if shortRange[i] < minimum:
                    minimum = shortRange[i]
                    u = i

            Z.add(u)

            for target, road in self.graph[u].items():
                if shortRange[target] > shortRange[u] + road.length:
                    shortRange[target] = shortRange[u] + road.length
                    prev[target] = u

            if u == self.target:
                while prev[u] != 0:
                    intersectionList.append(u)
                    u = prev[u]

                intersectionList.append(u)
                intersectionList.reverse()
                self.path = [self.graph[source][target] for source, target in zip(
                    intersectionList, intersectionList[1:])]
                self.path.reverse()
                break
