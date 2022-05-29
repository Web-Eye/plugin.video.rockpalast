# -*- coding: utf-8 -*-
# Copyright 2021 WebEye
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

import requests
import json


def _getContent(url):
    page = requests.get(url)
    return json.loads(page.content)


class ARDMediathekAPI:

    def __init__(self, url, tag):

        self._posterWidth = 480

        if tag is not None:
            if 'pageNumber' in tag:
                pageNumber = tag.get('pageNumber')
                url = url.replace('{pageNumber}', str(pageNumber))
            if 'pageSize' in tag:
                pageSize = tag.get('pageSize')
                url = url.replace('{pageSize}', str(pageSize))
            if 'posterWidth' in tag:
                self._posterWidth = tag.get('posterWidth')
            if 'quality' in tag:
                self._quality_id = tag.get('quality')

        self._content = _getContent(url)

    def _hasContent(self):
        return self._content is not None

    def getPagination(self):
        if self._hasContent():
            return self._content['pagination']

    def getTeaser(self):
        try:
            teasers = []
            if self._hasContent():
                for teaser in self._content['teasers']:
                    image = teaser['images']['aspect16x9']['src'].replace('{width}', str(self._posterWidth))
                    teasers.append({'availableTo': teaser['availableTo'],
                                    'broadcastedOn': teaser['broadcastedOn'],
                                    'duration': teaser['duration'],
                                    'poster': image,
                                    'title': teaser['longTitle'],
                                    'url': teaser['links']['target']['href']})

                return teasers
        finally:
            pass

    def getItem(self):
        if self._hasContent():
            item = self._content['widgets'][0]
            poster = item['image']['src'].replace('{width}', str(self._posterWidth))
            embedded = item['mediaCollection']['embedded']
            mediastreamarray = embedded['_mediaArray'][0]['_mediaStreamArray']
            url = self._getItemUrl(mediastreamarray)
            duration = embedded['_duration']

            if url is not None:
                return {
                    'title': self._content['title'],
                    'availableTo': item['availableTo'],
                    'broadcastedOn': item['broadcastedOn'],
                    'plot': item['synopsis'],
                    'poster': poster,
                    'url': url,
                    'duration': duration
                }

    def _getItemUrl(self, mediastreamarray):
        if self._quality_id < 5:
            for stream in mediastreamarray:
                if stream['_quality'] == self._quality_id:
                    return stream['_stream']

        else:
            li = list(filter(lambda p: isinstance(p['_quality'], int), mediastreamarray))
            if li is not None and len(li) > 0:
                return max(li, key=lambda p: int(p['_quality']))['_stream']
