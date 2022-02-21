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

from libs.kodion.addon import Addon
from libs.ardmediathek_api import ARDMediathekAPI
from libs.kodion.gui_manager import *

from libs.kodion.utils import Utils as kodionUtils
from libs.utils import utils
from libs.translations import *


def buildArgs(method, url=None, tag=None):
    item = {
        'method': method,
    }

    if url is not None:
        item['url'] = url

    if tag is not None:
        item['tag'] = tag

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

        self._showname = show_name
        self._DEFAULT_IMAGE_URL = ''

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
        self._t = Translations(self._addon)
        self._quality_id = int(self._addon.getSetting('quality'))
        self._PAGESIZE = {
            '0': 5,
            '1': 10,
            '2': 15,
            '3': 20,
            '4': 25,
            '5': 30
        }[self._addon.getSetting('page_itemCount')]
        self._skip_itemPage = (self._addon.getSetting('skip_itemPage') == 'true')
        # self._suppress_MusicClips = (addon.getSetting('suppress_MusicClips') == 'true')
        # self._suppress_durationSeconds = {
        #     '0': 0,
        #     '1': 30,
        #     '2': 60,
        #     '3': 180,
        #     '4': 300
        # }[addon.getSetting('suppress_duration')]

        self._DirectoryBuilded = False

    def setItemView(self, url, tag=None):

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

    # def _isValidTeaser(self, teaser):
    #     if self._suppress_MusicClips and 'Musik bei Inas Nacht:' in teaser['title']:
    #         return False
    #
    #     if self._suppress_durationSeconds > 0 and teaser['duration'] < self._suppress_durationSeconds:
    #         return False
    #
    #     return True

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
                                      infoLabels=infoLabels, args=buildArgs('item', teaser['url']))
        self._DirectoryBuilded = True

    def addClip(self, teaser):
        url = teaser['url']
        self.setItemView(url, None)

    def setListView(self, url, tag=None):
        API = ARDMediathekAPI(url, tag)
        pagination = API.getPagination()
        teasers = API.getTeaser()

        if teasers is not None:
            for teaser in teasers:
                # if self._isValidTeaser(teaser):
                if True:
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
                tag = {
                    'pageNumber': pageNumber + 1,
                    'pageSize': self._PAGESIZE,
                    'posterWidth': self._POSTERWIDTH
                }
                self._guiManager.addDirectory(title=f'Page {strPageNumber}',
                                              args=buildArgs('list', self._BASEURL, json.dumps(tag)))

        self._DirectoryBuilded = True

    def setSearchView(self, url, tag=None):
        search_guuid = 'not NONE'
        if tag is not None and 'search_guuid' in tag:
            search_guuid = tag.get('search_guuid')

        if self._addon.getSetting('search_guuid') != search_guuid:
            self._addon.setSetting('search_guuid', search_guuid)
            _filter = self._guiManager.getInput('', self._t.getString(SEARCHHEADER), False)
            if _filter != '':
                url = self._SEARCHURL.replace('{searchstring}', f'{self._showname}|{_filter}')
                self.setListView(url, tag)

    def setHomeView(self, url, tag=None):
        self._guiManager.addDirectory(title=self._t.getString(HOME),
                                      args=buildArgs('list', self._BASEURL, json.dumps(tag)))

        self._guiManager.addDirectory(title=self._t.getString(SEARCH),
                                      args=buildArgs('search', self._BASEURL, json.dumps(tag)))
        self._DirectoryBuilded = True

    def DoSome(self):

        args = get_query_args(sys.argv[2])
        if args is None or args.__len__() == 0:
            tag = {
                'pageNumber': 0,
                'pageSize': self._PAGESIZE,
                'posterWidth': self._POSTERWIDTH,
                'search_guuid': str(uuid.uuid4())
            }

            args = buildArgs('home', self._BASEURL, tag)

        method = args.get('method')
        url = args.get('url')
        tag = args.get('tag')

        if tag is not None and isinstance(tag, str):
            tag = json.loads(tag)

        {
            'home': self.setHomeView,
            'search': self.setSearchView,
            'list': self.setListView,
            'item': self.setItemView
        }[method](url, tag)

        # self._guiManager.addSortMethod(GuiManager.SORT_METHOD_NONE)
        # self._guiManager.addSortMethod(GuiManager.SORT_METHOD_DATE)

        if self._DirectoryBuilded:
            self._guiManager.endOfDirectory()
