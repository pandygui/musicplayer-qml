#!/usr/bin/python
# -*- coding: utf-8 -*-


import os
import sys
import time
from PyQt5.QtCore import (QObject, pyqtSignal, pyqtSlot,
                          pyqtProperty, QUrl, QDate)
from PyQt5.QtGui import QCursor
from .utils import registerContext, contexts
from .utils import duration_to_string
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QMediaPlaylist
from .playlistworker import DRealLocalMediaContent, DRealOnlineMediaContent
from .coverworker import CoverWorker
from log import logger



class PlayerBin(QMediaPlayer):

    def __init__(self):
        super(PlayerBin, self).__init__()
        self.setNotifyInterval(50)

gPlayer = PlayerBin()


class MediaPlayer(QObject):

    __contextName__ = "MediaPlayer"

    played = pyqtSignal()
    stoped = pyqtSignal()
    paused = pyqtSignal()

    musicInfoChanged = pyqtSignal('QString', 'QString')

    playingChanged = pyqtSignal(bool)

    positionChanged = pyqtSignal('qint64')
    volumeChanged = pyqtSignal(int)
    mutedChanged = pyqtSignal(bool)
    notifyIntervalChanged = pyqtSignal(int)
    playbackModeChanged = pyqtSignal(int)
    stateChanged = pyqtSignal(int)
    mediaStatusChanged = pyqtSignal('QMediaPlayer::MediaStatus')
    bufferStatusChanged = pyqtSignal(int)

    playlistChanged = pyqtSignal('QString')

    currentIndexChanged = pyqtSignal(int)

    titleChanged = pyqtSignal('QString')
    artistChanged = pyqtSignal('QString')
    coverChanged = pyqtSignal('QString')

    downloadCover = pyqtSignal('QString', 'QString')

    requestMusic = pyqtSignal('QString')

    @registerContext
    def __init__(self):
        super(MediaPlayer, self).__init__()
        self._playlist = None

        self._state = 0
        self._isPlaying = False


        self._playbackMode = 4
        self._volume = 0

        self._url = ''
        self._title = ''
        self._artist = ''
        self._cover = ''

        self.initPlayer()

        self.initConnect()

    def initPlayer(self):
        self.notifyInterval = 50

    def initConnect(self):

        self.played.connect(gPlayer.play)
        self.stoped.connect(gPlayer.stop)
        self.paused.connect(gPlayer.pause)

        gPlayer.mediaStatusChanged.connect(self.mediaStatusChanged)
        gPlayer.mediaStatusChanged.connect(self.monitorMediaStatus)
        gPlayer.positionChanged.connect(self.positionChanged)
        gPlayer.durationChanged.connect(self.updateDuration)
        gPlayer.bufferStatusChanged.connect(self.bufferChange)
        gPlayer.error.connect(self.monitorError)

    @pyqtProperty('QVariant', notify=playlistChanged)
    def playlist(self):
        return self._playlist

    @pyqtSlot('QVariant')
    def setPlaylist(self, playlist):
        if self._playlist:
            self._playlist.currentIndexChanged.disconnect(self.currentIndexChanged)

        self._playlist = playlist
        self._playlist.currentIndexChanged.connect(self.currentIndexChanged)
        self.playlistChanged.emit(playlist.name)

    @pyqtSlot('QString')
    def setPlaylistByName(self, name):
        playlistWorker = contexts['PlaylistWorker']

        playbackMode = self._playbackMode
        playlist = playlistWorker.getPlaylistByName(name)
        if playlist:
            if self._playlist and self._playlist.name == playlist.name:
                return
            playlist.setPlaybackMode(playbackMode)
            self.setPlaylist(playlist)
            self.setCurrentIndex(0)


    @pyqtProperty(int, notify=playbackModeChanged)
    def playbackMode(self):
        return self._playbackMode

    @playbackMode.setter
    def playbackMode(self, playbackMode):
        self._playbackMode = playbackMode
        if self._playlist:
            self._playlist.setPlaybackMode(playbackMode)
        self.playbackModeChanged.emit(playbackMode)

    @pyqtProperty(bool, notify=playingChanged)
    def playing(self):
        return self._isPlaying

    @pyqtProperty(int)
    def position(self):
        return gPlayer.position()

    @position.setter
    def position(self, pos):
        gPlayer.setPosition(pos)
        self.positionChanged.emit(pos)

    @pyqtProperty(int, notify=volumeChanged)
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        self._volume = value
        gPlayer.setVolume(value)
        self.volumeChanged.emit(value)

    @pyqtProperty(bool, notify=mutedChanged)
    def muted(self):
        return gPlayer.isMuted()

    @muted.setter
    def muted(self, muted):
        gPlayer.setMuted(muted)
        self.mutedChanged.emit(muted)

    @pyqtProperty(int)
    def notifyInterval(self):
        return gPlayer.notifyInterval()

    @notifyInterval.setter
    def notifyInterval(self, interval):
        gPlayer.setNotifyInterval(interval)
        self.notifyIntervalChanged.emit(interval)

    @pyqtProperty(int)
    def duration(self):
        return gPlayer.duration()

    @pyqtSlot(int)
    def updateDuration(self, duration):
        try:
            index = self._playlist.currentIndex()
            urls = self._playlist.urls
            mediaContents =  self._playlist.mediaContents
            if index < len(urls):
                mediaContent = mediaContents[urls[index]]
                mediaContent.tags.update({'duration': duration})
                mediaContent.duration = duration
        except Exception, e:
            raise e

    @pyqtProperty('QString')
    def positionString(self):
        position = gPlayer.position()
        return duration_to_string(position)

    @pyqtProperty('QString')
    def durationString(self):
        duration = gPlayer.duration()
        if duration <= 0:
            index = self._playlist.currentIndex()
            urls = self._playlist.urls
            mediaContents =  self._playlist.mediaContents
            if index < len(urls):
                mediaContent = mediaContents[urls[index]]
                if 'duration' in mediaContent.tags:
                    duration = mediaContent.tags['duration']
        return duration_to_string(duration)

    @pyqtProperty(bool)
    def seekable(self):
        return gPlayer.isSeekable()

    @pyqtProperty(str)
    def errorString(self):
        return gPlayer.errorString()

    def monitorMediaStatus(self, status):
        if status == 7:
            if self._playlist:
                if self._playlist.playbackMode() == 1:
                    self.playToggle(self._isPlaying)
                elif self._playlist.playbackMode() in [3, 4]:
                    self.next()
        elif status == 4:
            self.buffingBeginTime = time.time()
            self.stop()
            self.play()
        elif status in [3, 6]:
            self.playToggle(self._isPlaying)

    def monitorError(self, error):
        errors = {
            0: "No error has occurred.",
            1: "A media resource couldn't be resolved",
            2: "The format of a media resource isn't (fully) supported. Playback may still be possible, but without an audio or video component",
            3: "A network error occurred",
            4: "There are not the appropriate permissions to play a media resource",
            5: "A valid playback service was not found, playback cannot proceed."
        }
        print(error, errors[error])
        if error == 3:
            url = self.getUrlID()
            if url:
                self.requestMusic.emit(url)

    @pyqtSlot(bool)
    def playToggle(self, playing):
        if playing:
            self.play()
        else:
            self.pause()

        self._isPlaying = playing

        self.playingChanged.emit(self._isPlaying)

    @pyqtSlot()
    def stop(self):
        self.stoped.emit()
        self.state = 0

    @pyqtSlot()
    def play(self):
        self.played.emit()
        self.state = 1

    @pyqtSlot()
    def pause(self):
        self.paused.emit()
        self.state = 2

    @pyqtProperty(int, notify=stateChanged)
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self._state = value
        self.stateChanged.emit(value)

    @pyqtSlot('QString')
    def setMediaUrl(self, url):
        self._url = url
        if url.startswith('http'):
            _url = QUrl(url)
        else:
            _url = QUrl.fromLocalFile(url)

        gPlayer.setMedia(QMediaContent(_url))
        self.playToggle(self._isPlaying)

    @pyqtSlot()
    def previous(self):
        if self._playlist:
            self._playlist.previous()
            currentIndex = self._playlist.currentIndex()
            if self._playlist.playbackMode() == 1:
                count = self._playlist.mediaCount()
                if currentIndex == 0:
                    index = count - 1
                else:
                    index = currentIndex - 1
                self._playlist.setCurrentIndex(index)
            currentIndex = self._playlist.currentIndex()
            self.playMediaByIndex(currentIndex)

    @pyqtSlot()
    def next(self):
        if self._playlist:
            self._playlist.next()
            currentIndex = self._playlist.currentIndex()
            if self._playlist.playbackMode() == 1:
                count = self._playlist.mediaCount()
                
                if currentIndex == count - 1:
                    index = 0
                else:
                    index = currentIndex + 1
                self._playlist.setCurrentIndex(index)
            currentIndex = self._playlist.currentIndex()
            self.playMediaByIndex(currentIndex)

    @pyqtSlot(int)
    def setCurrentIndex(self, index):
        if self._playlist:
            if index < self._playlist.mediaCount():
                self._playlist.setCurrentIndex(index)
                self.playMediaByIndex(index)

    @pyqtSlot(int)
    def playMediaByIndex(self, index):
        urls = self._playlist.urls
        mediaContents =  self._playlist.mediaContents

        if index < len(urls) and index > 0:
            mediaContent = mediaContents[urls[index]]
            url = mediaContent.url

            if isinstance(mediaContent, DRealLocalMediaContent):
                playurl = mediaContent.url
                self.setMediaUrl(playurl)
                self.title = mediaContent.title
                self.artist = mediaContent.artist
                self.cover = mediaContent.cover
            elif isinstance(mediaContent, DRealOnlineMediaContent):
                # self.title = mediaContent.title
                # self.artist = mediaContent.artist
                # self.cover = mediaContent.cover
                self.requestMusic.emit(url)
                return

            # if playurl:
            #     self.setMediaUrl(playurl)
            #     self.title = mediaContent.title
            #     self.artist = mediaContent.artist
            #     self.cover = mediaContent.cover

    def getUrlID(self):
        if self._playlist:
            currentIndex = self._playlist.currentIndex()
            urls = self._playlist.urls
            url = urls[currentIndex]
            return url
        else:
            return None

    def bufferChange(self, progress):
        self.bufferStatusChanged.emit(progress)

    @pyqtSlot('QVariant')
    def playLocalMedia(self, url):
        url = unicode(url)
        urls = self._playlist.urls
        index = urls.index(url)
        self._playlist.setCurrentIndex(index)
        mediaContents =  self._playlist.mediaContents
        mediaContent = mediaContents[url]
        self.title = mediaContent.title
        self.artist = mediaContent.artist
        self.cover = mediaContent.cover

        self.setMediaUrl(url)
        self.playToggle(True)

    @pyqtSlot('QVariant')
    def playOnlineMedia(self, result):
        url = unicode(result['url'])
        urls = self._playlist.urls
        if url in urls:
            index = urls.index(url)
            self._playlist.updateMedia(result['url'], result['tags'])
            self._playlist.setCurrentIndex(index)

            mediaContents =  self._playlist.mediaContents
            mediaContent = mediaContents[url]
            playurl = mediaContent.playlinkUrl
            self.setMediaUrl(playurl)

            self.title = mediaContent.title
            self.artist = mediaContent.artist
            self.cover = mediaContent.cover
            self.playToggle(True)

    @pyqtSlot('QVariant')
    def swicthOnlineMedia(self, result):
        url = unicode(result['url'])
        urls = self._playlist.urls
        index = urls.index(url)

        self._playlist.updateMedia(result['url'], result['tags'])
        self._playlist.setCurrentIndex(index)

        mediaContents =  self._playlist.mediaContents
        mediaContent = mediaContents[url]
        playurl = mediaContent.playlinkUrl
        self.setMediaUrl(playurl)

        self.title = mediaContent.title
        self.artist = mediaContent.artist
        self.cover = mediaContent.cover

    @pyqtProperty(int, notify=currentIndexChanged)
    def currentIndex(self):
        return self._playlist.currentIndex()

    @pyqtProperty('QString', notify=titleChanged)
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = value
        self.titleChanged.emit(value)

    @pyqtProperty('QString', notify=artistChanged)
    def artist(self):
        return self._artist

    @artist.setter
    def artist(self, value):
        self._artist = value
        self.artistChanged.emit(value)

    @pyqtProperty('QString', notify=coverChanged)
    def cover(self):
        return self._cover

    @cover.setter
    def cover(self, cover):
        if cover.startswith('http'):
            index = self._playlist.currentIndex()
            urls = self._playlist.urls
            url = urls[index]
            self.downloadCover.emit(url , cover)
            return
        self._cover = cover
        self.coverChanged.emit(cover)

    def updateCover(self, mediaUrl, coverUrl):
        mediaContents =  self._playlist.mediaContents
        if mediaUrl in mediaContents:
            mediaContent = mediaContents[mediaUrl]
            mediaContent.cover = coverUrl
        self.cover = coverUrl

    @pyqtSlot('QString', result='QString')
    def metaData(self, key):
        return gPlayer.metaData(key)

    def showMetaData(self):
        import json
        metaData = {}
        for key in self.availableMetaData():
            v = self.metaData(key)
            if isinstance(v, QDate):
                v = v.toString('yyyy.MM.dd')
            metaData.update({key: v})
        logger.info(metaData)
        path = os.sep.join(
            [os.path.dirname(os.getcwd()), 'music',
             '%s.json' % self.metaData('Title')])
        f = open(path, 'w')
        f.write(json.dumps(metaData, indent=4))
        f.close()
