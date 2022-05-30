# -*- coding: utf-8 -*-
# Copyright 2022 WebEye
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import json
import sys
import urllib
import urllib.parse
import uuid
import mysql.connector

from libs.database.database_api import DBAPI
from libs.kodion.addon import Addon
from libs.ardmediathek_api import ARDMediathekAPI
from libs.kodion.gui_manager import *

from libs.kodion.utils import Utils as kodionUtils
from libs.utils import utils
from libs.translations import *


def buildArgs(method, url=None, pageNumber=None, search_guuid=None):
    item = {
        'method': method,
    }

    if url is not None:
        item['url'] = url

    if pageNumber is not None:
        item['pageNumber'] = pageNumber

    if search_guuid is not None:
        item['search_guuid'] = search_guuid

    return item


def get_query_args(s_args):
    args = urllib.parse.parse_qs(urllib.parse.urlparse(s_args).query)

    for key in args:
        args[key] = args[key][0]
    return args


class ArdMediathekClient:

    def __init__(self, addon_id, mediathek_id, channel, show_name, fanart_id):

        # -- Constants ----------------------------------------------
        self._ADDON_ID = addon_id
        self._BASEURL = f'https://api.ardmediathek.de/page-gateway/widgets/{channel}/asset/{mediathek_id}' \
                        '?pageNumber={pageNumber}&pageSize={' \
                        'pageSize}&embedded=true&seasoned=false&seasonNumber=&withAudiodescription=false' \
                        '&withOriginalWithSubtitle=false&withOriginalversion=false'

        self._SEARCHURL = f'https://page.ardmediathek.de/page-gateway/widgets/{channel}/search/vod' \
                          '?searchString={searchstring}&pageNumber={pageNumber}'

        self._DEFAULT_IMAGE_URL = ''
        self._showname = show_name

        width = getScreenWidth()
        if width >= 2160:
            fanart = f'special://home/addons/{self._ADDON_ID}/resources/assets/2160p/fanart.jpg'
        elif width >= 1080:
            fanart = f'special://home/addons/{self._ADDON_ID}/resources/assets/1080p/fanart.jpg'
        else:
            fanart = f'special://home/addons/{self._ADDON_ID}/resources/assets/720p/fanart.jpg'

        fanart = kodionUtils.translatePath(fanart)
        self._guiManager = GuiManager(sys.argv[1], self._ADDON_ID, self._DEFAULT_IMAGE_URL, fanart)
        self._POSTERWIDTH = int(width/3)
        self._guiManager.setContent('movies')

        # -- Settings -----------------------------------------------
        self._addon = Addon(self._ADDON_ID)
        self._addon_name = self._addon.getAddonInfo('name')
        self._addon_icon = self._addon.getAddonInfo('icon')
        self._t = Translations(self._addon)
        self._quality_id = int(self._addon.getSetting('quality'))
        self._PAGESIZE = int(self._addon.getSetting('page_itemCount'))
        self._skip_itemPage = (self._addon.getSetting('skip_itemPage') == 'true')
        self._suppress_Interview = (self._addon.getSetting('suppress_Interview') == 'true')
        self._suppress_Unplugged = (self._addon.getSetting('suppress_Unplugged') == 'true')
        self._suppress_durationSeconds = int(self._addon.getSetting('suppress_duration'))

        self._db_enabled = (self._addon.getSetting('database_enabled') == 'true')
        self._db_config = None
        if self._db_enabled:
            self._db_config = {
                'host': self._addon.getSetting('db_host'),
                'port': int(self._addon.getSetting('db_port')),
                'user': self._addon.getSetting('db_username'),
                'password': self._addon.getSetting('db_password'),
                'database': 'KodiWebGrabber_Test'
            }
            self._skip_itemPage = True

        self._DirectoryBuilded = False

    def setItemView(self, url=None, pageNumber=None, search_guuid=None):

        tag = {
            'posterWidth': self._POSTERWIDTH,
            'quality': self._quality_id
        }

        API = ARDMediathekAPI(url, tag)
        item = API.getItem()
        if item is not None:
            title = item['title']

            infoLabels = {
                'Title': title,
                'Plot': item['plot'],
                'Date': item['broadcastedOn'],
                'Aired': item['broadcastedOn'],
                'Duration': item['duration']
            }

            self._guiManager.addItem(title=title, url=item['url'], poster=item['poster'], _type='video',
                                     infoLabels=infoLabels)
            self._DirectoryBuilded = True

    def _isValidTeaser(self, teaser):
        if self._suppress_Interview and 'Interview' in teaser['title']:
            return False

        if self._suppress_Unplugged and 'Unplugged:' in teaser['title']:
            return False

        if self._suppress_durationSeconds > 0 and teaser['duration'] < self._suppress_durationSeconds:
            return False

        return True

    def addItemPage(self, teaser):
        title = teaser['title']
        duration, unit = utils.getDuration(int(teaser['duration']))
        duration = {
            'hours': duration + f' {self._t.getString(HOURS)}',
            'minutes': duration + f' {self._t.getString(MINUTES)}',
            'seconds': duration + f' {self._t.getString(SECONDS)}',
        }[unit]

        broadcastedOn = utils.formatDateTime(utils.getDateTime(teaser['broadcastedOn'], '%Y-%m-%dT%H:%M:%SZ'),
                                             '%d.%m.%Y, %H:%M:%S')
        availableTo = utils.formatDateTime(utils.getDateTime(teaser['availableTo'], '%Y-%m-%dT%H:%M:%SZ'),
                                           '%d.%m.%Y, %H:%M:%S')

        plot = f'[B]{title}[/B]\n\n[B]{self._t.getString(DURATION)}[/B]: {duration}\n' \
               f'[B]{self._t.getString(BROADCASTEDON)}[/B]: {broadcastedOn}\n' \
               f'[B]{self._t.getString(AVAILABLETO)}[/B]: {availableTo} '

        infoLabels = {
            'Title': title,
            'Plot': str(plot),
            'Date': teaser['broadcastedOn'],
            'Aired': teaser['broadcastedOn'],
            'Duration': teaser['duration']
        }

        self._guiManager.addDirectory(title=title, poster=teaser['poster'], _type='Video',
                                      infoLabels=infoLabels, args=buildArgs(method='item', url=teaser['url']))
        self._DirectoryBuilded = True

    def addClip(self, teaser):
        if not self._db_enabled:
            url = teaser['url']
            self.setItemView(url)

        else:
            title = teaser['title']
            broadcastedOn = utils.convertDateTime(teaser['broadcastedOn'], '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d')

            infoLabels = {
                'Title': title,
                'Plot': teaser['plot'],
                'Date': broadcastedOn,
                'Aired': broadcastedOn,
                'Duration': teaser['duration']
            }

            self._guiManager.addItem(title=title, url=teaser['url'], poster=teaser['poster'], _type='video',
                                     infoLabels=infoLabels)

    def setListView(self, url=None, pageNumber=None, search_guuid=None):
        if pageNumber is None:
            pageNumber = 0
        tag = {
            'pageNumber': pageNumber,
            'pageSize': self._PAGESIZE,
            'posterWidth': self._POSTERWIDTH,
            'quality': self._quality_id,
            'suppress_Interview': self._suppress_Interview,
            'suppress_Unplugged': self._suppress_Unplugged,
            'suppress_durationSeconds': self._suppress_durationSeconds

        }

        if not self._db_enabled:
            if url is None:
                url = self._BASEURL
            API = ARDMediathekAPI(url, tag)
        else:
            try:
                API = DBAPI(self._db_config, tag)
            except mysql.connector.Error as e:
                self._guiManager.setToastNotification(self._addon_name, e.msg, image=self._addon_icon)
                return

        teasers = API.getTeaser()
        pagination = API.getPagination()

        if teasers is not None:
            for teaser in teasers:
                if self._db_enabled or self._isValidTeaser(teaser):
                    {
                        False: self.addItemPage,
                        True: self.addClip
                    }[self._skip_itemPage](teaser)

        if pagination is not None:
            pageNumber = int(pagination['pageNumber'])
            pageSize = int(pagination['pageSize'])
            totalElements = int(pagination['totalElements'])

            if totalElements > ((pageNumber + 1) * pageSize):
                strPageNumber = str(pageNumber + 2)
                self._guiManager.addDirectory(title=f'Page {strPageNumber}',
                                              args=buildArgs('list', pageNumber=pageNumber+1))

        self._DirectoryBuilded = True

    def setSearchView(self, url=None, pageNumber=None, search_guuid=None):
        # TODO: searching in database....
        if self._addon.getSetting('search_guuid') == search_guuid:
            _filter = self._guiManager.getInput('', self._t.getString(SEARCHHEADER), False)
            if _filter != '':
                _filter = _filter.replace(' ', '+')
                _searchstring = urllib.parse.quote(f'{self._showname}|{_filter}')
                url = self._SEARCHURL.replace('{searchstring}', _searchstring)
                self.setListView(url, pageNumber)

        else:
            self._addon.setSetting('search_guuid', search_guuid)

    def setHomeView(self, url=None, pageNumber=None, search_guuid=None):

        search_guuid = str(uuid.uuid4())
        self._addon.setSetting('search_guuid', search_guuid)

        self._guiManager.addDirectory(title=self._t.getString(HOME),
                                      args=buildArgs(method='list', pageNumber=pageNumber))

        self._guiManager.addDirectory(title=self._t.getString(SEARCH),
                                      args=buildArgs(method='search', pageNumber=pageNumber, search_guuid=search_guuid))
        self._DirectoryBuilded = True

    def DoSome(self):

        args = get_query_args(sys.argv[2])
        if args is None or args.__len__() == 0:
            args = buildArgs(method='home')

        method = args.get('method')
        url = None
        if 'url' in args:
            url = args.get('url')
        pageNumber = None
        if 'pageNumber' in args:
            pageNumber = args.get('pageNumber')
        search_guuid = None
        if 'search_guuid' in args:
            search_guuid = args.get('search_guuid')

        {
            'home': self.setHomeView,
            'search': self.setSearchView,
            'list': self.setListView,
            'item': self.setItemView
        }[method](url, pageNumber, search_guuid)

        # self._guiManager.addSortMethod(GuiManager.SORT_METHOD_NONE)
        # self._guiManager.addSortMethod(GuiManager.SORT_METHOD_DATE)

        if self._DirectoryBuilded:
            self._guiManager.endOfDirectory()
