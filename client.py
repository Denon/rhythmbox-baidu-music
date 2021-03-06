# -*- coding: utf-8 -*-

"""
    A rhythmbox plugin for playing music from baidu music.

    Copyright (C) 2013 pandasunny <pandasunny@gmail.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import logging
import re
import random
import time
import datetime
import urllib
import urllib2
import cookielib
import zlib
import json

def warp_gm_time(fun):
    """ The hook of gm time. """
    def _warp_gm_time(*args):
        args=list(args)
        if args[0]>1899962739:
            args[0]=1899962739
        return fun(*args)
    if  hasattr( fun,'_is_hook'):
        return fun
    _warp_gm_time._is_hook=1
    return _warp_gm_time
time.gmtime=warp_gm_time(time.gmtime)

PASSPORT_URL = "https://passport.baidu.com"
CROSSDOMAIN_URL = "http://user.hao123.com/static/crossdomain.php?"
MUSICBOX_URL = "http://play.baidu.com"
TINGAPI_URL = "http://tingapi.ting.baidu.com"
MUSICMINI_URL = "http://musicmini.baidu.com"
#REFERER_URL = "http://qianqianmini.baidu.com/app/passport/passport_phoenix.html"
#CROSSDOMAIN_REFERER_URL = "http://qianqianmini.baidu.com/app/passport/index.htm"

class InvalidTokenError(Exception):pass
class InvalidUsernameError(Exception): pass
class InvalidLoginError(Exception): pass
class InvalidVerifyCodeError(Exception): pass
class MissVerifyCodeError(Exception): pass


class Client(object):
    """ The class of Baidu Music Client

    Attributes:
        cookie: The name of a file in which you want to save cookies. If its
                value is None, you mean that do not save cookies.
        debug: A boolean indicating if show the debug information or not.
    """

    def __init__(self, cookie="", debug=False):
        """ Initialize the baidu music client class. """

        #self.CLIENTVER = "7.0.4"    # TTPlayer"s client version 
        self.CLIENTVER = "8.1.0.8"  # BaiduMusic"s client version 
        self.APIVER = "v3"          # Baidu Music API version 3
        self.TPL = "qianqian"       # The template of TTPlayer

        self.__bduss = ""           # the string "BDUSS" of cookie
        self.__token = ""           # login token
        self.__codestring = ""      # login codestring
        self.__bdu = ""     # the string "BDU" of cross domain
        self.islogin = False        # a boolean of login

        #self.__cloud = {}           # the cloud information dict
        self.total = 0              # the count of songs in collect list

        #if debug:
            #logging.basicConfig(format="%(asctime)s - %(levelname)s - \
                    #%(message)s", level=logging.DEBUG)

        # If the param "cookie" is a filename, create a cookiejar with the file
        # and check the cookie to comfire whether the client has logged on.

        if cookie:
            self.__cj = cookielib.LWPCookieJar(cookie)
            if os.path.isfile(cookie):
                self.__cj.revert()
                for cookie in self.__cj:
                    if cookie.name == "BDUSS" and cookie.domain == ".baidu.com":
                        logging.info("Login successed!")
                        self.__bduss = cookie.value
                        logging.debug("The cookie 'BDUSS': " + cookie.value)
                        self.islogin = True
        else:
            self.__cj = cookielib.CookieJar()

        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.__cj))
        opener.addheaders = [
                ("Accept", "*/*"),
                ("Accept-Language", "zh-CN"),
                ("Accept-Encoding", "gzip, deflate"),
                ("User-Agent", "Mozilla/4.0 (compatible; MSIE 7.0; \
                        Windows NT 6.1; Trident/6.0; SLCC2; \
                        .NET CLR 2.0.50727; .NET CLR 3.5.30729; \
                        .NET CLR 3.0.30729; Media Center PC 6.0; \
                        .NET4.0C; .NET4.0E)")
                #("User-Agent", "Mozilla/5.0 (X11; Linux i686) \
                        #AppleWebKit/537.36 (KHTML, like Gecko) \
                        #Chrome/29.0.1547.0 Safari/537.36")
                ]
        urllib2.install_opener(opener)

    def __request(self, url, method, params={}, headers={}):
        """ HEAD/POST/GET the date with urllib2.

        Args:
            url: A url which you want to fetch.
            method: A method which one of HEAD, POST, GET.
            params: A dict mapping the parameters.
            headers: A dict mapping the custom headers.

        Returns:
            A string include the response. Or a boolean if method is HEAD.

        Raises:
            HTTPError: urllib2.HTTPError
            URLError: urllib2.URLError
        """

        params = urllib.urlencode(params)

        if method == "GET":
            request = urllib2.Request(url + params, None)
        elif method == "POST":
            request = urllib2.Request(url, params)
        elif method == "HEAD":
            request = urllib2.Request(url + params, None)
            request.get_method = lambda: "HEAD"

        for key in headers:
            request.add_header(key, headers[key])

        try:
            response = urllib2.urlopen(request)
        except urllib2.HTTPError as e:
            print "The server couldn't fulfill the request."
            print url
            print "Error code: " +  e.code
        except urllib2.URLError as e:
            print "We failed to reach a server."
            print url
            print "Reason: " + e.reason
        else:
            self.__save_cookie()
            result = self.unzip(response) if method != "HEAD" else True
            return result

    def __save_cookie(self):
        """ Save the cookie string as a file """
        if isinstance(self.__cj, cookielib.LWPCookieJar):
            self.__cj.save()

    @staticmethod
    def unzip(response):
        """ Decompress the zip response.

        Args:
            response: A file-like object which the function urllib2.urlopen
                    returns.

        Returns:
            A string which be decompress.
        """
        info, result = response.info(), response.read()
        if "Content-Encoding" in info and info["Content-Encoding"] == "gzip":
            try:
                result = zlib.decompress(result, 16+zlib.MAX_WBITS)
            except Exception as e:
                print "Decompress the response failed."
        return result

    def __login_get_id(self):
        """ Get the cookie 'BAIDUID' """
        timestamp = int(time.time())
        url = PASSPORT_URL + "/passApi/js/wrapper.js?"
        params = {
                "cdnversion": timestamp,
                "_": timestamp
                }
        #headers = {"Referer": REFERER_URL}
        self.__request(url, "HEAD", params)
        for cookie in self.__cj:
            if (cookie.name == 'BAIDUID') and (cookie.domain == '.baidu.com'):
                logging.debug("The cookie 'BAIDUID': " + cookie.value)

    def __login_get_token(self):
        """ Get the token string

        Returns:
            A dict which include the token string and the codestring string. The
        dict is as follows:
        {
            "errInfo": { "no": the errno },
            "data": {
                "rememberedUserName": the remembered username,
                "codeString": the codestring,
                "token":the token string,
                "cookie": unknown
            }
        }

        Raises:
            InvalidTokenError: An error occurred get the error token string.
        """
        params = {
            "tpl": self.TPL,
            "apiver": self.APIVER,
            "tt": int(time.time()),
            "class": "login",
            "logintype": "basicLogin",
            "callback": ""
            }
        url = PASSPORT_URL + "/v2/api/?getapi&"
        #headers = {"Referer": REFERER_URL}
        response = json.loads(self.__request(url, "GET", params))

        if response["errInfo"]["no"] == "0":
            self.__token = response["data"]["token"]
            self.__codestring = response["data"]["codeString"]
            logging.debug("login token: " + self.__token)
            logging.debug("login codestring: " + self.__codestring)
        else:
            raise TokenError("Get token faild.")

    def login_check(self, username):
        """ Check login status.

        Returns:
            A boolean about codestring. If the codestring is true, visit the
        url "https://passport.baidu.com/cgi-bin/genimage?<codestring>" to get
        a captcha image. The get image function is self.get_captcha().
        """
        #callback = self.__getCallbackString()
        callback = ""
        url = PASSPORT_URL + "/v2/api/?logincheck&"
        params = {
            "token": self.__token,
            "tpl": self.TPL,
            "apiver": self.APIVER,
            "tt": int(time.time()),
            "username": username,
            "isphone": "false",
            "callback": callback
            }
        #headers = {"Referer": CROSSDOMAIN_REFERER_URL}
        response = self.__request(url, "GET", params)
        self.__codestring = response["data"]["codeString"]
        return bool(self.__codestring)

    def get_captcha(self):
        """ Get the captcha image.

        Returns:
            A file byte about the image.
        """
        url = PASSPORT_URL + "/cgi-bin/genimage?" + self.__codestring
        response = self.__request(url, "GET")
        return response

    def __login(self, username, password, verifycode=None, remember=True):
        """ Post the username and password for login.

        Get html data and find two variables: err_no and hao123Param in
        javascript code.
        The 'err_no' string has three values:
            err_no = 0: login successed
            err_no = 2: username invalid
            err_no = 4: username or password invalid
            err_no = 6: captcha invalid
            err_no = 257: use captcha

        Args:
            username: The user's login name
            password: The user's password
            verifycode: The verify code from image
            remember: A boolean if remembered the username and the password

        Raises:
            InvalidUsernameError: An error occurred post the invalid username.
            InvalidLoginError: An error occurred post the invalid username or
                the invalid password.
            InvalidVerifyCodeError: An error occurred input the invalid verifycode.
            MissVerifyCodeError: An error occurred do not input the verifycode.

        TODO:
            1.use the phone number to login the baidu music
        """
        url = PASSPORT_URL + "/v2/api/?login"
        params = {
            "staticpage": MUSICMINI_URL + "/app/passport/jump.html",
            "charset": "utf-8",
            "token": self.__token,
            "tpl": self.TPL,
            "apiver": self.APIVER,
            "tt": int(time.time()),
            "codestring": self.__codestring,
            "isphone": "false",
            "safeflg": 0,
            "u": "",
            "quick_user": 0,
            "username": username,
            "password": password,
            "verifycode": verifycode,
            "ppui_logintime": random.randint(1000, 99999),
            "callback": ""
            }
        if remember:
            params["mem_pass"] = "on"
        #headers = {"Referer": REFERER_URL}
        response = self.__request(url, "POST", params)

        errno = re.search("err_no=(\d+)", response).group(1)
        if errno == "0":
            logging.info("Login successed!")
            self.__bdu = re.search("hao123Param=(\w+)", response).group(1)
            logging.debug("The cross domain param 'bdu': " + self.__bdu)
        elif errno == "2":
            logging.error("The username is invalid.")
            raise InvalidUsernameError()
        elif errno == "4":
            logging.error("The username or password is invalid.")
            raise InvalidLoginError()
        elif errno == "6":
            logging.error("The captcha is invalid.")
            raise InvalidVerifyCodeError()
        elif errno == "257":
            logging.error("Please input the captcha.")
            raise MissVerifyCodeError()

    def __login_cross_domain(self):
        """ Cross domain login """
        params = {
            "bdu": self.__bdu,
            "t": int(time.time())
            }
        #headers = {"Referer": CROSSDOMAIN_REFERER_URL}
        self.__request(CROSSDOMAIN_URL, "HEAD", params)

    def __login_get_bduss(self):
        """ Get the bduss value """
        url = MUSICMINI_URL + "/app/passport/getBDUSS.php"
        response = self.__request(url, "GET")
        self.__bduss = response[1:-1]

    def login(self, username, password, verifycode=None, remember=True):
        """ Login baidu music.

        Args:
            username: The user's login name
            password: The user's password
            verifycode: The verify code from image
            remember: A boolean if remembered the username and the password

        Returns:
            A boolean whether the client has logged on.
        """
        if not self.islogin:
            self.__login_get_id()
            self.__login_get_token()
            self.__login(username, password, remember)
            self.__login_cross_domain()
            self.__login_get_bduss()
            self.islogin = True
        return int(self.islogin)

    def logout(self):
        """ Logout baidu music """
        self.__cj.clear()
        self.__save_cookie()
        self.islogin = False
        logging.info("Logout successed!")
        return not self.islogin

    def __get_cloud_info(self):
        """ Get the information of baidu cloud music.

        Returns:
            A dict which has four items: cloud_surplus: the remaining quota;
            cloud_total: the quota; cloud_used: the used quota; level: the
            user's level, the possible values are 0, 1, 2.
        """
        url = MUSICMINI_URL + "/app/cloudMusic/spaceSongs.php?"
        params = {"bduss": self.__bduss}
        response = json.loads(self.__request(url, "GET", params))
        logging.debug("cloud_total: %s; cloud_used: %s; cloud_surplus: %s",
                response["cloud_total"], response["cloud_used"],
                response["cloud_surplus"])
        return response

    def get_collect_ids(self, start, size=200):
        """ Get all the ids of collect list.

        Returns:
            A list include all song ids.
            The response data is a dict like this:
            {
                "query": {
                    "cloud_type": unknown,
                    "type": "song",
                    "start": the start number,
                    "size": the size of ids,
                    "_": timestamp
                },
                "errorCode": the error(22000 is normal),
                "data": {
                    "quota": the cloud quota,
                    "songList": [{
                        "id": the song id,
                        "ctime": ctime
                    }, ... ]
                }
            }
        """
        url = MUSICBOX_URL + "/data/mbox/collectlist?"
        params = {
            "cloud_type": 0,
            "type": "song",
            "start": start,
            "size": size,
            "_": int(time.time())
            }
        response = json.loads(self.__request(url, "GET", params))
        if response["errorCode"] == 22000:
            song_ids = [song["id"] for song in response["data"]["songList"]]
            logging.debug("The total of song: %i", len(song_ids))
            logging.debug("The song IDs: %s", str(song_ids))
            self.total = int(response["data"]["total"])
            return song_ids
        return False

    def get_song_info(self, song_ids):
        """ Get basic information of songs whose id in the param 'song_ids'.

        Returns:
            A list includes the dicts of song. This list is a part of response.
            The response data is a dict like this:
            {
                "errorCode": the error(22000 is normal),
                "data": {
                    "songList": [{
                        "queryId": the song id,
                        "albumId": the album id,
                        "albumName": the album title,
                        "artistId": the artist id,
                        "artistName": the artist name,
                        "songId": the song id,
                        "songName": the song title,
                        "songPicBig": the big cover,
                        "songPicRadio": the radio cover,
                        "songPicSmall": the small cover,
                        "del status": 0, # unknown
                        "relateStatus": 0, # unknown
                        "resourceType": 0 #unknown
                    }, ... ]
                }
            }
        """
        url = MUSICBOX_URL + "/data/music/songinfo"
        params = {"songIds": ",".join(map(str, song_ids))}
        response = json.loads(self.__request(url, "POST", params))
        if response["errorCode"] == 22000:
            result = response["data"]["songList"]
            logging.debug("The song list: %s", str(result))
            return result
        return False

    def get_song_links(self, song_ids, link_type=False, is_hq=False):
        """ Get the informations about song's links.

        Args:
            song_ids: A list includes the song ids.
            link_type: A boolean about link which be got.
            is_hq: A boolean.

        Returns:
            A list is the response which is as follows:
            [{
                song_id: (int)the song id,
                song_title: (str)the song title,
                append: (null),
                song_artist: (str)artist,
                album_title: (str)album title,
                album_image_url: (null),
                lyric_url: (str)lyric file url,
                version: (null),
                copy_type: (str)unknown(1),
                resource_source: (str)source,
                has_mv: (str)undefined,
                file_list: [{
                    file_id: (int)file id,
                    url: (str)the song url,
                    display_url: (str)the song display url,
                    format: (str)format(ma3, flac),
                    hash: (str)hash,
                    size: (int)filesize,
                    kbps: (int)rate,
                    duration: (int)time,
                    url_expire_time: (int)expire time,
                    is_hq: (int)is HQ file
                }, ...]
            }, ...]
        """
        artist = title = []
        url = MUSICMINI_URL + "/app/link/getLinks.php?"
        params = {
            "songId": "@@".join(map(str, song_ids)),
            "songArtist": "@@".join(artist),
            "songTitle": "@@".join(title),
            "songAppend": "",
            "linkType": int(link_type),
            "isLogin": int(self.islogin),
            "clientVer": self.CLIENTVER,
            "isHq": int(is_hq),
            "isCloud": 0,
            "hasMV": "undefined"
            }
        response = json.loads(self.__request(url, "GET", params))
        return response

    def search(self, keyword, page_no=1, page_size=30):
        """ Search songs with keywords.

        Args:
            keyword: the keyword with music.
            page_no: the search page number.
            page_size: the size of songs per page.

        Returns:
            A dict about songs and other informations.
        """
        url = TINGAPI_URL + "/v1/restserver/ting?"
        params = {
                "method": "baidu.ting.search.common",
                "format": "json",
                "from": "bmpc",
                "version": "1.0.0",
                "page_size": page_size,
                "page_no": page_no,
                "query": keyword,
            }

        response = json.loads(self.__request(url, "GET", params))
        return response

    def add_collect_songs(self, song_ids):
        """ Add songs to the collect list.

        Args:
            song_ids: A list of songs.

        Returns:
            A list of songs which were been added. Or False when failed.
        """
        url = TINGAPI_URL + "/v1/restserver/ting?"
        params = {
                "method": "baidu.ting.favorite.addSongFavorites",
                "format": "json",
                "from": "bmpc",
                "version": "1.0.0",
                "bduss": self.__bduss,
                "songId": ",".join(map(str, song_ids))
            }
        headers = {
                "Referer": "http://pc.music.baidu.com",
                "User-Agent": "bmpc_1.0.0"
                }

        response = json.loads(self.__request(url, "GET", params, headers))
        return response["result"] if response["error_code"] == 22000 else False

    def delete_collect_songs(self, song_ids):
        """ Remove songs from the collect list.

        Args:
            song_ids: A list of songs.

        Returns:
            A boolean.
        """
        url = TINGAPI_URL + "/v1/restserver/ting?"
        params = {
                "method": "baidu.ting.favorite.delCollectSong",
                "format": "json",
                "from": "bmpc",
                "version": "1.0.0",
                "bduss": self.__bduss,
                "songId": ",".join(map(str, song_ids))
            }
        headers = {
                "Referer": "http://pc.music.baidu.com",
                "User-Agent": "bmpc_1.0.0"
                }

        response = json.loads(self.__request(url, "GET", params, headers))
        return True if response["error_code"] == 22000 else False

    # playlist information
    def get_playlists(self, page_no=0, page_size=50):
        """ Get all playlists.

        Args:
            page_no: The number of page.
            page_size: The count of playlists in a page.

        Returns:
            Three variables includes "havemore", "total", "play_list".
            play_list = {
                "id": string,
                "title": string,
                "author":null,
                "tag":null,
                "description":null,
                "create_time": int,
                "covers":null,
                "song_count": string,
                "collected_count":null,
                "recommend_count":null,
                "songlist":null,
                "access_control":0,
                "diy_type":1,
                "status":null,
                "pic_180": string # playlist coverart
                }
        """
        url = TINGAPI_URL + "/v1/restserver/ting?"
        params = {
                "method": "ting.baidu.diy.getPlaylists",
                "format": "json",
                "from": "bmpc",
                "version": "1.0.0",
                "bduss": self.__bduss,
                "with_song": 0,
                "page_no": page_no,
                "page_size": page_size,
            }
        headers = {
                "Referer": "http://pc.music.baidu.com",
                "User-Agent": "bmpc_1.0.0"
                }

        response = json.loads(self.__request(url, "GET", params, headers))
        if response["error_code"] == 22000:
            result = response["havemore"], response["total"], response["play_list"]
        else:
            result = False
        return result

    def get_playlist(self, playlist_id):
        """ Get all the ids of online playlist.

        Args:
            playlist_id: The id of online playlist.

        Returns:
            A list include all song ids.
            The response data is a dict like this:
            {
                "query": {
                    "sid": "1",
                    "playListId": the size of ids,
                    "_": timestamp
                },
                "errorCode": the error(22000 is normal),
                "data": {
                    "songIds": a list
                }
            }
        """
        url = MUSICBOX_URL + "/data/playlist/getDetail?"
        params = {
                "sid": 1,
                "playListId": playlist_id,
                "_": int(time.time())
                }
        response = json.loads(self.__request(url, "GET", params))
        return response["data"]["songIds"] if response["errorCode"] == 22000 \
                else False

    def add_playlist(self, title):
        """ Add a playlist in cloud.

        Args:
            title: The title of a playlist which were been added.

        Returns:
            The id of playlist.
        """
        url = TINGAPI_URL + "/v1/restserver/ting?"
        params = {
                "method": "baidu.ting.diy.addList",
                "format": "json",
                "from": "bmpc",
                "version": "1.0.0",
                "bduss": self.__bduss,
                "title": title,
            }
        headers = {
                "Referer": "http://pc.music.baidu.com",
                "User-Agent": "bmpc_1.0.0"
                }
        response = json.loads(self.__request(url, "GET", params, headers))
        return response["result"]["listId"] if response["error_code"] == 22000 \
                else False

    def delete_playlist(self, playlist_id):
        """ Delete a playlist in cloud.

        Args:
            playlist_id: The id of a playlist.

        Returns:
            A boolean.
        """
        url = TINGAPI_URL + "/v1/restserver/ting?"
        params = {
                "method": "baidu.ting.diy.delList",
                "format": "json",
                "from": "bmpc",
                "version": "1.0.0",
                "bduss": self.__bduss,
                "listId": int(playlist_id),
            }
        headers = {
                "Referer": "http://pc.music.baidu.com",
                "User-Agent": "bmpc_1.0.0"
                }
        response = json.loads(self.__request(url, "GET", params, headers))
        return True if response["error_code"] == 22000 else False

    def rename_playlist(self, playlist_id, title):
        """ Rename a playlist in cloud.

        Args:
            playlist_id: The id of a playlist.
            title: The title of a playlist.

        Returns:
            A boolean.
        """
        url = TINGAPI_URL + "/v1/restserver/ting?"
        params = {
                "method": "baidu.ting.diy.upList",
                "format": "json",
                "from": "bmpc",
                "version": "1.0.0",
                "bduss": self.__bduss,
                "listId": int(playlist_id),
                "title": title,
            }
        headers = {
                "Referer": "http://pc.music.baidu.com",
                "User-Agent": "bmpc_1.0.0"
                }
        response = json.loads(self.__request(url, "GET", params, headers))
        return True if response["error_code"] == 22000 else False

    def add_playlist_songs(self, playlist_id, song_ids):
        """ Add songs to a playlist.

        Args:
            playlist_id: The id of a playlist.
            song_ids: The ids list of songs.

        Returns:
            A list includes the ids of songs which were added.
        """
        url = TINGAPI_URL + "/v1/restserver/ting?"
        params = {
                "method": "baidu.ting.diy.addListSong",
                "format": "json",
                "from": "bmpc",
                "version": "1.0.0",
                "bduss": self.__bduss,
                "listId": int(playlist_id),
                "songId": ",".join(map(str, song_ids)),
            }
        headers = {
                "Referer": "http://pc.music.baidu.com",
                "User-Agent": "bmpc_1.0.0"
                }
        response = json.loads(self.__request(url, "GET", params, headers))
        return response["result"]["add"] if response["error_code"] == 22000 \
                else False

    def delete_playlist_songs(self, playlist_id, song_ids):
        """ Delete songs to a playlist.

        Args:
            playlist_id: The id of a playlist.
            song_ids: The ids list of songs.

        Returns:
            A boolean.
        """
        url = TINGAPI_URL + "/v1/restserver/ting?"
        params = {
                "method": "baidu.ting.diy.delListSong",
                "format": "json",
                "from": "bmpc",
                "version": "1.0.0",
                "bduss": self.__bduss,
                "listId": int(playlist_id),
                "songId": ",".join(map(str, song_ids)),
            }
        headers = {
                "Referer": "http://pc.music.baidu.com",
                "User-Agent": "bmpc_1.0.0"
                }
        response = json.loads(self.__request(url, "GET", params, headers))
        return True if response["error_code"] == 22000 else False
