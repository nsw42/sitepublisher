import ftplib
import os.path
import sys

from .filehash import getfilehash
from .remotedircontents import RemoteDirContents


class RemoteDir(object):
    """
    Abstract base class for querying a remote directory, based either
    on a cache (RemoteDirCached) or from querying it as needed
    (RemoteDirLive)

    Currently, the directory it represents is determined by
    connection.pwd() at the time of construction
    """
    def __init__(self, localdirname):
        self.localdirname = localdirname

    def get_contents(self):
        """
        Return a RemoteDirContents object representing the contents
        of the current directory
        """
        raise NotImplementedError()


class RemoteDirLive(RemoteDir):
    """
    Implementation of the RemoteDir interface to query the remote
    directory whenever needed
    """

    def __init__(self, localdirname, connection):
        super(RemoteDirLive, self).__init__(localdirname)
        self._connection = connection

    def _callback_get_file_size(self, leafname):
        try:
            return self._connection.size(leafname)
        except ftplib.error_perm:
            return -1  # let's assume that that error always means 'directory'

    def _callback_get_file_hash(self, leafname):
        try:
            _ = self._connection.size(leafname)
            # if we get this far, let's assume that the file is correct
            return RemoteDirContents.__RemoteFileAssumedCorrect__
        except ftplib.error_perm:
            return ''  # let's assume that that error always means 'directory'

    def get_contents(self):
        """
        Return a RemoteDirContents object representing the contents
        of the current directory
        """
        contents = RemoteDirContents()
        for leafname in self._connection.nlst():
            size = self._callback_get_file_size
            hsh = self._callback_get_file_hash
            contents.set_file(leafname, size, hsh)
        return contents


class RemoteDirCached(RemoteDir):
    """
    Implementation of the RemoteDir interface to allow a cache of
    the remote directory to be preserved.

    Currently, the directory it represents is determined by
    connection.pwd() at the time of construction
    """
    def __init__(self, cache, localdirname, connection):
        super(RemoteDirCached, self).__init__(localdirname)
        self._cache = cache
        self._connection = RemoteDirLive(localdirname, connection)
        self._dirname = connection.pwd()

    def get_contents(self):
        """
        Return a RemoteDirContents object representing the contents
        of the current directory
        """
        contents = self._cache.get_dir_contents(self._dirname)
        if not contents:
            print('%s: Populating cache' % self._dirname)
            contents = self._connection.get_contents()
            # invariant: everything we put into the cache is populated with known
            # values, rather than callbacks, so that it may be safely pickled
            for leaf in contents.leaf_names():
                size = contents.get_file_size(leaf)
                hsh = contents.get_file_hash(leaf)
                if hsh == RemoteDirContents.__RemoteFileAssumedCorrect__:
                    localfilename = os.path.join(self.localdirname, leaf)
                    hsh = getfilehash(localfilename)
                    if hsh is None:
                        print(f'WARNING: "{self._dirname}/{leaf}" exists on remote server but not locally '
                              + f'(tried "{localfilename}")', file=sys.stderr)
                        hsh = RemoteDirContents.__RemoteFileHashUnknown__
                contents.set_file(leaf, size, hsh)
            self._cache.set_dir_contents(self._dirname, contents)
        return contents
