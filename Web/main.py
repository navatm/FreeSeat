#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
from google.appengine.ext.webapp import template
import webapp2
from google.appengine.ext import db
import logging
from logging import debug
import random
import string
from data import *
import re
from RoomsParser import RoomsParser
import urllib2

ROOMS_URL = r"http://gezer.bgu.ac.il/compclass/compclass.php"
DEFAULT_ROOMS_LIST = "105,119,120,303,310,121,218,Aranne"
ROOMS_LIST_PROP_NAME = "roomsList"

def setCookieValue(rquestHandler, name, val):
    name = str(name)
    val = str(val)
    val = val.replace(",", "|")
    rquestHandler.response.headers.add_header(
            'Set-Cookie',
            '%s=%s' % (name, val),
            )

class MainHandler(webapp2.RequestHandler):
    def shouldAskForAppDownload(self):
        src = self.request.get("src")
        return "Android" in self.request.headers["User-Agent"] and \
                src != "androidWrapper"
    
    def showRelevantPage(self):
        roomsList = self.request.cookies.get(ROOMS_LIST_PROP_NAME)
        if not roomsList is None and roomsList != "":
            roomsList = roomsList.replace("|", ",")
            self.redirect("/rooms?rooms=%s" % roomsList)
        else:
            template_values = {}
            path = os.path.join(os.path.dirname(__file__), 'sections.html')
            self.response.out.write(template.render(path, template_values))

    def get(self):
        if self.shouldAskForAppDownload():
            template_values = {}
            path = os.path.join(os.path.dirname(__file__), 'GooglePlay.html')
            self.response.out.write(template.render(path, template_values))
        else:
            self.showRelevantPage()

def listFormat(listString):
    return "'" + listString.replace(",", "','") + "'"

def whereStatementIfNeeded(roomsList):
    if roomsList is None:
        return ""
    else:
        return "WHERE name IN (" + listFormat(roomsList) + ") "

def roomsQuery(roomsList = None):
    rooms = db.GqlQuery("SELECT * "
                        "FROM Room " + \
                        whereStatementIfNeeded(roomsList) + \
                        "ORDER BY free DESC")
    return rooms

class RoomsHandler(webapp2.RequestHandler):
    def get(self):
        roomsNames = self.request.get("rooms")
        setCookieValue(self, ROOMS_LIST_PROP_NAME, roomsNames)
        try:
            rooms = roomsQuery(roomsNames)
            defaultRooms = roomsQuery(DEFAULT_ROOMS_LIST)
            # Add the rooms that everyone can use:
            template_values = {
                'rooms': rooms,
                'defaultRooms': defaultRooms,
            }

            path = os.path.join(os.path.dirname(__file__), 'rooms.html')
            self.response.out.write(template.render(path, template_values))
        except:
            template_values = {}
            path = os.path.join(os.path.dirname(__file__), 'overload.html')
            self.response.out.write(template.render(path, template_values))

def int2(strToInt):
    if strToInt == "":
        return 0
    return int(strToInt)

def parseOccupancy(occStr):
    MASK = "  (.*?)\n .*? (.*?) "
    couple = re.findall(MASK, occStr)
    if len(couple) == 1:
        return (int2(couple[0][0]), int2(couple[0][1]))
    else:
        return (0, 0)

class SelectSectionHandler(webapp2.RequestHandler):
    def get(self):
        setCookieValue(self, ROOMS_LIST_PROP_NAME, "")
        self.redirect("/")

class UpdateRoomsHandler(webapp2.RequestHandler):
    def getRoomsFromGezer(self):
        rp = RoomsParser()
        rp.feed(urllib2.urlopen(ROOMS_URL).read())
        rooms = rp.getRooms()

        return rooms

    def compareDbAndGezerRoom(self, dbRoom, gezerRoom):
        return (dbRoom.link == gezerRoom[-1] and 
               (dbRoom.occupied, dbRoom.total) ==
                parseOccupancy(gezerRoom[-2]))
        
    def get(self):
        import re

        dbRooms = roomsQuery()
        gezerRooms = self.getRoomsFromGezer()

        for dbRoom in dbRooms:
            roomName = dbRoom.longName
            if not gezerRooms.has_key(roomName):
                logging.warning("Room not found! %s" % roomName)
                logging.warning("Rooms list %s" % str(gezerRooms.keys()))
                continue
            if not self.compareDbAndGezerRoom(dbRoom,
                gezerRooms[roomName]):
                room = gezerRooms[roomName]
                debug("Change found in %s" % roomName)

                #dbRoom = Room.get_or_insert(room[1])
                dbRoom.link = room[-1]
                (dbRoom.occupied, dbRoom.total) = parseOccupancy(room[-2])
                dbRoom.free = dbRoom.total - dbRoom.occupied
                dbRoom.put()
            else:
                pass
                #debug("No change in %s" % roomName)

class NewRoomsHandler(webapp2.RequestHandler):
    def get(self):
        import re
        rp = RoomsParser()
        rp.feed(urllib2.urlopen(ROOMS_URL).read())
        rooms = rp.getRooms()
        #self.response.out.write(len(rooms))
        for room_key in rooms:
            room = rooms[room_key]
            debug("room %s" % room[1])
            dbRoom = Room.get_or_insert(room[1])
            dbRoom.link = room[-1]
            (dbRoom.occupied, dbRoom.total) = parseOccupancy(room[-2])
            dbRoom.free = dbRoom.total - dbRoom.occupied
            long_name_nums = re.findall("\d+", room[1])
            dbRoom.longName = unicode(room[1])
            #if dbRoom.name == "" or dbRoom.name is None:
            #    dbRoom.name = long_name_nums[-1]
            #if (dbRoom.building == "" or dbRoom.building is None) and len(long_name_nums) == 2:
            #    dbRoom.building = long_name_nums[0]
            dbRoom.put()

app = webapp2.WSGIApplication([('/', MainHandler),
                               ('/updateRooms', UpdateRoomsHandler),
                               ('/getNewRooms', NewRoomsHandler),
                               ('/selectSection', SelectSectionHandler),
                               ('/rooms', RoomsHandler)],
                              debug=True)
