# -*- coding: utf-8 -*-
# *  This Program is free software; you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License as published by
# *  the Free Software Foundation; either version 2, or (at your option)
# *  any later version.
# *
# *  This Program is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with this program; see the file LICENSE.txt.  If not, write to
# *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# *  http://www.gnu.org/copyleft/gpl.html
# *
#
#    This script is based on script.randomitems & script.wacthlist & script.xbmc.callbacks
#    Thanks to their original authors and pilulli

# TODO branch github and use version with monitorext in lib and remove dependency from addon.xml
# TODO reload MonitorEx and Listener with settings change

debug = True
remote = False
import sys
if debug:
    if remote:
        sys.path.append(r'C:\\Users\\Ken User\\AppData\\Roaming\\XBMC\\addons\\script.ambibox\\resources\\lib\\'
                        r'pycharm-debug.py3k\\')
        import pydevd
        pydevd.settrace('192.168.1.103', port=51234, stdoutToServer=True, stderrToServer=True)
    else:
        sys.path.append('C:\Program Files (x86)\JetBrains\PyCharm 3.1.3\pycharm-debug-py3k.egg')
        import pydevd
        pydevd.settrace('localhost', port=51234, stdoutToServer=True, stderrToServer=True)

import os
from json import loads as jloads
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import subprocess

import abc
import urllib2
from urlparse import urlparse
import socket
import traceback

__addon__ = xbmcaddon.Addon('script.xbmc.callbacks2')
__cwd__ = xbmc.translatePath(__addon__.getAddonInfo('path')).decode('utf-8')
__scriptname__ = __addon__.getAddonInfo('name')
__version__ = str(__addon__.getAddonInfo('version'))
__settings__ = xbmcaddon.Addon("script.xbmc.callbacks2")
__language__ = __settings__.getLocalizedString
__settingsdir__ = xbmc.translatePath(os.path.join(__cwd__, 'resources')).decode('utf-8')
__resource__ = xbmc.translatePath(os.path.join(__cwd__, 'resources', 'lib')).decode('utf-8')
__author__ = 'KenV99'
__options__ = dict()
sys.path.append(__resource__)
import monitorext

def notification(text, *silence):
    """
    Display an XBMC notification box, optionally turn off sound associated with it
    @type text: str
    @type silence: bool
    """
    text = text.encode('utf-8')
    if __options__['notifications'] or __options__['tester']:
        icon = __settings__.getAddonInfo("icon")
        smallicon = icon.encode("utf-8")
        dialog = xbmcgui.Dialog()
        if __options__['tester']:
            dialog.ok(__scriptname__, text)
        else:
            if silence:
                dialog.notification(__scriptname__, text, smallicon, 1000, False)
            else:
                dialog.notification(__scriptname__, text, smallicon, 1000, True)


def debug(txt):
    if isinstance(txt, str):
        txt = txt.decode("utf-8")
    message = u"$$$ [%s] - %s" % (__scriptname__, txt)
    xbmc.log(msg=message.encode("utf-8"), level=xbmc.LOGDEBUG)


def info(txt):
    if isinstance(txt, str):
        txt = txt.decode("utf-8")
    message = u"$$$ [%s] - %s" % (__scriptname__, txt)
    xbmc.log(msg=message.encode("utf-8"), level=xbmc.LOGNOTICE)


def read_settings(ddict):
    """
    Reads settings from settings.xml and loads gloval __options__ and Dispatcher.ddict
    @param ddict: dictionary objet from Dispatcher
    @type ddict: dict
    """
    global __options__
    _settings = xbmcaddon.Addon("script.xbmc.callbacks2")
    setlist = ['user_monitor_playback', 'notifications', 'arg_eventid', 'arg_mediatype', 'arg_filename',
               'arg_title', 'arg_aspectratio', 'arg_resolution', 'arg_profilepath', 'arg_stereomode']
    for i in setlist:
        __options__[i] = (_settings.getSetting(i) == 'true')
    __options__['interval'] = int(float(_settings.getSetting('interval')))
    __options__['needs_listener'] = __options__['monitorStereoMode'] = __options__['monitorProfiles'] = False
    __options__['monitorPlayback'] = False
    setlist = ['onPlaybackStarted', 'onPlaybackStopped', 'onPlaybackPaused', 'onPlaybackResumed', 'onDatabaseUpdated',
               'onScreensaverActivated', 'onScreensaverDeactivated', 'onShutdown', 'onStereoModeChange',
               'onProfileChange', 'onIdle', 'onStartup']
    for i in setlist:
        setid = (i + '_type').decode('utf-8')
        mtype = _settings.getSetting(setid)
        if mtype != 'none' and mtype != '':
            setid = (i + '_str').decode('utf-8')
            if mtype == 'script':
                mstr = _settings.getSetting(setid + '.scr')
            elif mtype == 'python':
                mstr = _settings.getSetting(setid + '.pyt')
            elif mtype == 'builtin':
                mstr = _settings.getSetting(setid + '.btn')
            else:
                mstr = _settings.getSetting(setid + '.htp')
            if mstr == '':
                break
            if mtype == 'script' or mtype == 'python':
                setid = (i + '_arg').decode('utf-8')
                argstr = _settings.getSetting(setid)
            else:
                argstr = ''
            worker = Factory.build_worker(mtype, mstr, argstr)
            if mtype == 'script':
                setid = (i + '_shell').decode('utf-8')
                if _settings.getSetting(setid) == 'true':
                    worker.needs_shell = True
                else:
                    worker.needs_shell = False
            worker.event_id = i
            ddict[i] = worker
            if i in ['onStereoModeChange', 'onProfileChange']:
                __options__['needs_listener'] = True
                if i == 'onStereoModeChange':
                    __options__['monitorStereoMode'] = True
                else:
                    __options__['monitorProfiles'] = True
            elif i in ['onPlaybackStarted', 'onPlaybackStopped']:
                if __options__['user_monitor_playback']:
                    __options__['needs_listener'] = True
                    __options__['monitorPlayback'] = True
            if i == 'onIdle':
                __options__['idle_time'] = int(_settings.getSetting('idle_time'))


class Factory(object):
    """
    Factory object for building workers with abstract worker superclass and specific subclasses of worker
    """

    @staticmethod
    def build_worker(worker_type, cmd_string, argstr):
        """
        Builds workers
        @param worker_type: script, python, builtin, json, http
        @type worker_type: str
        @param cmd_string: the main command, language specific
        @type cmd_string: str
        @param argstr: user arguments as entered in settings
        @type argstr: list
        @return:
        """
        worker = None
        if worker_type == 'script':
            worker = WorkerScript(cmd_string, argstr)
        elif worker_type == 'python':
            worker = WorkerPy(cmd_string, argstr)
        elif worker_type == 'builtin':
            worker = WorkerBuiltin(cmd_string, argstr)
        elif worker_type == 'json':
            worker = WorkerJson(cmd_string, argstr)
        elif worker_type == 'http':
            worker = WorkerHTTP(cmd_string, argstr)
        if worker.passed:
            return worker


class Player(xbmc.Player):
    """
    Subclasses xbmc.Player
    """
    global __options__
    dispatcher = None

    def __init__(self):
        super(Player, self).__init__()

    @staticmethod
    def playing_type():
        try:
            if __options__['tester']:
                return 'testing'
            substrings = ['-trailer', 'http://']
            rtype = 'unknown'
            filename = ''
            isMovie = False
            if xbmc.Player.isPlayingAudio(xbmc.Player()):
                rtype = "music"
            else:
                if xbmc.getCondVisibility('VideoPlayer.Content(movies)'):
                    isMovie = True
            try:
                filename = xbmc.Player.getPlayingFile(xbmc.Player())
            except:
                pass
            if filename[0:3] == 'pvr':
                rtype = 'liveTV'
                if __options__['monitorPlayback']:
                    xbmc.sleep(5000)
            elif filename != '':
                for string in substrings:
                    if string in filename:
                        isMovie = False
                        break
            if isMovie:
                rtype = "movie"
            elif xbmc.getCondVisibility('VideoPlayer.Content(episodes)'):
                # Check for tv show title and season to make sure it's really an episode
                if xbmc.getInfoLabel('VideoPlayer.Season') != "" and xbmc.getInfoLabel('VideoPlayer.TVShowTitle') != "":
                    rtype = "episode"
            return rtype
        except Exception, e:
            return 'unknown'

    def getTitle(self):
        try:
            if __options__['tester']:
                return 'testing'
            if self.isPlayingAudio():
                return xbmc.getInfoLabel('MusicPlayer.Title')
            if self.isPlayingVideo():
                if xbmc.getCondVisibility('VideoPlayer.Content(episodes)'):
                    if xbmc.getInfoLabel('VideoPlayer.Season') != "" and xbmc.getInfoLabel('VideoPlayer.TVShowTitle') != "":
                        return (xbmc.getInfoLabel('VideoPlayer.TVShowTitle') + '-' + xbmc.getInfoLabel('VideoPlayer.Season')
                               + '-' + xbmc.getInfoLabel('VideoPlayer.Title'))
                else:
                    return xbmc.getInfoLabel('VideoPlayer.Title')
        except Exception, e:
            return 'unknown'

    def getAspectRatio(self):
        if __options__['tester']:
            return 'testing'
        else:
            return xbmc.getInfoLabel("VideoPlayer.VideoAspect")

    def getResoluion(self):
        if __options__['tester']:
            return 'testing'
        else:
            return xbmc.getInfoLabel("VideoPlayer.VideoResolution")

    def onPlayBackStarted(self):
        if not __options__['monitorPlayback']:
            self.onPlayBackStartedEx()

    def onPlayBackStartedEx(self):
        runtimeargs = []
        if __options__['arg_mediatype']:
            runtimeargs.append('type=' + self.playing_type())
        if __options__['arg_filename']:
            runtimeargs.append('file=' + self.getPlayingFile())
        if __options__['arg_title']:
            runtimeargs.append('title=' + self.getTitle())
        if self.isPlayingVideo():
            if __options__['arg_aspectratio']:
                runtimeargs.append('aspectratio=' + self.getAspectRatio())
            if __options__['arg_resolution']:
                runtimeargs.append('resolution=' + self.getResoluion())
        try:
            self.dispatcher.dispatch('onPlaybackStarted', runtimeargs)
        except Exception, e:
            pass

    def onPlayBackStopped(self):
        if not __options__['monitorPlayback']:
            self.onPlayBackStoppedEx()

    def onPlayBackEnded(self):
        self.onPlayBackStopped()

    def onPlayBackStoppedEx(self):
        self.dispatcher.dispatch('onPlaybackStopped', [])

    def onPlayBackPaused(self):
        self.dispatcher.dispatch('onPlaybackPaused', [])

    def onPlayBackResumed(self):
        self.dispatcher.dispatch('onPlaybackResumed', [])


class Monitor(monitorext.MonitorEx):  # monitorext.MonitorEx
    """
    Subclasses MonitorEx which is a subclass of xbmc.Monitor
    """
    player = None
    dispatcher = None

    def __init__(self, monitorStereoMode, monitorProfiles, monitorPlayback):
        """
        @type monitorStereoMode: bool
        @type monitorProfiles: bool
        @type monitorPlayback: bool
        """
        monitorext.MonitorEx.__init__(self, monitorStereoMode, monitorProfiles, monitorPlayback)

    def onDatabaseUpdated(self, database):
        self.dispatcher.dispatch('onDatabaseUpdated', [])

    def onScreensaverActivated(self):
        self.dispatcher.dispatch('onScreensaverActivated', [])

    def onScreensaverDeactivated(self):
        self.dispatcher.dispatch('onScreensaverDeactivated', [])

    def onSettingsChanged(self):
        self.dispatcher.ddict = None
        self.dispatcher.ddict = dict()
        read_settings(self.dispatcher.ddict)

    def onStereoModeChange(self):
        runtimeargs = []
        if __options__['arg_stereomode']:
            if __options__['tester']:
                runtimeargs = ['stereomode=testing']
            else:
                runtimeargs = ['stereomode=' + self.getCurrentStereoMode()]
        self.dispatcher.dispatch('onStereoModeChange', runtimeargs)

    def onProfileChange(self):
        runtimeargs = []
        if __options__['arg_profilepath']:
            if __options__['tester']:
                runtimeargs = ['profilepath=testing']
            else:
                runtimeargs = ['profilepath=' + self.getCurrentProfile()]
        self.dispatcher.dispatch('onProfileChange', runtimeargs)

    def onPlaybackStarted(self):
        self.player.onPlayBackStartedEx()

    def onPlaybackStopped(self):
        self.player.onPlayBackStoppedEx()


class Dispatcher():
    """
    Class for dispatching workers to jobs
    """
    ddict = dict()

    def __init__(self):
        self.ddict = dict()

    def dispatch(self, event_id, runtimeargs):
        if event_id in self.ddict:
            worker = self.ddict[event_id]
            if __options__['arg_eventid']:
                runtimeargs = ['event=' + event_id] + runtimeargs
            info('Executing command: [%s] for event: %s' % (worker.cmd_str, event_id))
            result = worker.run(runtimeargs)
            if result[0]:
                info('Command for %s resulted in ERROR: %s' % (event_id, result[1]))
                notification(__language__(32051) % (event_id, result[1]))
            else:
                info('Command for %s executed successfully' % event_id)
                notification(__language__(32052) % event_id)
            return result
        else:
            return [True, 'No registered command for \'%s\'' % event_id]


class AbstractWorker():
    """
    Abstract class for command specific workers to follow
    """
    __metaclass__ = abc.ABCMeta
    event_id = ''

    def __init__(self, cmd_str, userargs):
        self.cmd_str = cmd_str
        self.userargs = userargs
        self.passed = self.check()

    @abc.abstractmethod
    def check(self):
        pass

    @abc.abstractmethod
    def run(self, runtimeargs):
        err = None  # True if error occured
        msg = ''    # string containing error message or return message
        return[err, msg]


class WorkerScript(AbstractWorker):
    needs_shell = False

    def check(self):
        self.cmd_str = []
        tmp = xbmc.translatePath(self.cmd_str).decode('utf-8')
        if xbmcvfs.exists(tmp):
            self.cmd_str.append(tmp)
            self.separate_userargs()
        else:
            return False

    def separate_userargs(self):
        if len(self.userargs) > 0:
            ret = []
            new = str(self.userargs).split(' ')
            tst = ''
            for i in new:
                tst = tst + i + ' '
                if os.path.isfile(tst):
                    tst.rstrip()
                    ret.append(tst)
                elif len(ret) > 1:
                    ret.append(i)
            if len(ret) == 0:
                for i in new:
                    ret.append(i)
            self.userargs = ret

    def run(self, runtimeargs):
        err = False
        msg = ''
        margs = self.cmd_str + runtimeargs + self.userargs
        try:
            result = subprocess.check_output(margs, shell=self.needs_shell, stderr=subprocess.STDOUT)
            if result is not None:
                msg = result
        except subprocess.CalledProcessError, e:
            err = True
            msg = e.output
        except:
            e = sys.exc_info()[0]
            err = True
            msg = e.reason + '\n' + traceback.format_exc()
        return [err, msg]


class WorkerPy(AbstractWorker):

    def check(self):
        tmp = xbmc.translatePath(self.cmd_str).decode('utf-8')
        if xbmcvfs.exists(tmp):
            fn, ext = os.path.splitext(tmp)
            if ext == '.py':
                self.cmd_str = tmp
                return True
        else:
            return False

    def run(self, runtimeargs):
        err = False
        msg = ''
        args = ', '.join(runtimeargs) + ', ' + self.userargs
        try:
            if len(args) > 1:
                result = xbmc.executebuiltin('XBMC.RunScript(%s, %s)' % (self.cmd_str, args))
            else:
                result = xbmc.executebuiltin('XBMC.RunScript(%s)' % self.cmd_str)
            if result is not None:
                msg = result
        except:
            e = sys.exc_info()[0]
            err = True
            msg = e.reason + '\n' + traceback.format_exc()
        return [err, msg]


class WorkerBuiltin(AbstractWorker):

    def check(self):
        return True

    def run(self, runtimeargs):
        err = False
        msg = ''
        try:
            result = xbmc.executebuiltin(self.cmd_str)
            if result != '':
                err = True
                msg = result
        except:
            e = sys.exc_info()[0]
            err = True
            msg = e.reason + '\n' + traceback.format_exc()
        return [err, msg]


class WorkerHTTP(AbstractWorker):

    def check(self):
        o = urlparse(self.cmd_str)
        if o.scheme != '' and o.netloc != '' and o.path != '':
            return True
        else:
            return False

    def run(self, runtimeargs):
        err = False
        msg = ''
        try:
            u = urllib2.urlopen(self.cmd_str, timeout=20)
            result = u.read()
            msg = str(result)
        except urllib2.URLError, e:
            err = True
            msg = e.reason
        except socket.timeout, e:
            err = True
            msg = 'The request timed out, host unreachable'
        except:
            e = sys.exc_info()[0]
            err = True
            msg = e.reason + '\n' + traceback.format_exc()
        return [err, msg]


class WorkerJson(AbstractWorker):

    def check(self):
        return True

    def run(self, runtimeargs):
        err = False
        msg = ''
        try:
            result = xbmc.executeJSONRPC(self.cmd_str)
            msg = jloads(result)
        except:
            e = sys.exc_info()[0]
            err = True
            msg = e.reason + '\n' + traceback.format_exc()
        return [err, msg]


class Main():
    dispatcher = None
    mm = None
    player = None

    @staticmethod
    def run():
        global __options__
        try:
            __options__['tester'] = False
            info('Starting %s version %s' % (__scriptname__, __version__))

            dispatcher = Dispatcher()
            read_settings(dispatcher.ddict)
            if 'onStartup' in dispatcher.ddict:
                dispatcher.dispatch('onStartup', [])
            mm = Monitor(__options__['monitorStereoMode'], __options__['monitorProfiles'],
                         __options__['monitorPlayback'])
            mm.dispatcher = dispatcher
            player = Player()
            player.dispatcher = dispatcher
            mm.player = player
            sleep_int = __options__['interval']
            if __options__['needs_listener']:
                mm.Listen(interval=sleep_int)
            executed_idle = False
            idletime = 60 * __options__['idle_time']
            while not xbmc.abortRequested:
                if 'onIdle' in dispatcher.ddict:
                    if xbmc.getGlobalIdleTime() > idletime:
                        if not executed_idle:
                            dispatcher.dispatch('onIdle', [])
                            executed_idle = True
                    else:
                        executed_idle = False
                xbmc.sleep(sleep_int)
            if 'onShutdown' in dispatcher.ddict:
                dispatcher.dispatch('onShutdown', [])
            if mm is not None:
                mm.StopListening()
                del mm
            del player
            del dispatcher
            info('Stopped %s' % __scriptname__)
        except Exception, e:
            e = sys.exc_info()[0]
            msg = ''
            if hasattr(e, 'message'):
                msg += e.message
            msg = msg + '\n' + traceback.format_exc()
            info('Unhandled Error occured: %s' % msg)
            sys.exit()

    def __init__(self):
        pass

if __name__ == '__main__':
    Main().run()
