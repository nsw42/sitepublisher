"""
sitepublisher
Class that makes it easy to publish a website via FTP
"""

from collections import namedtuple
import datetime
import ftplib
import hashlib
import os.path
import pickle
import sys
import time


def getfilehash(filename):
    try:
        handle = open(filename, 'rb')
        md5 = hashlib.md5(filename.encode('utf-8'))
        while True:
            data = handle.read(md5.digest_size * 1024)
            if data == b'':
                break
            md5.update(data)
        return md5.hexdigest()
    except IOError:
        return None


class Submit:
    """
    Enum of values that influence how the ftp publisher is to behave.
    Submit.Missing indicates files that are missing (or the wrong size) on the
    remote server
    Submit.ChangedToday indicates files that have changed on the local
    filesystem since midnight.
    Values may be added together
    """
    Missing = 1
    ChangedToday = 2
    MissingOrChangedToday = Missing + ChangedToday
    AllFiles = 0xff


RemoteFile = namedtuple('RemoteFile', ('size', 'hsh'))


class RemoteDirContents(object):
    """
    Class that stores the contents of a remote directory
    """
    def __init__(self):
        self._contents = {}  # leafname -> RemoteFile(val_or_callable, val_or_callable)
        # size value is an integer number of bytes
        # hash value is a string md5.hexdigest()

    def leaf_names(self):
        return self._contents.keys()

    __RemoteFileMissing__ = 1
    __RemoteFileAssumedCorrect__ = 2
    __RemoteFileIsDirectory__ = 3
    __RemoteFileHashUnknown__ = '?'

    def get_file_hash(self, leafname):
        """
        Return values are as follows:
          __RemoteFileMissing__
              The file is not present on the remote server
          __RemoteFileAssumedCorrect__
              The file is present on the remote server, but we do not know
              whether its contents are correct - so assume they are
          __RemoteFileIsDirectory__
              The 'file' is a directory
          __RemoteFileHashUnknown__
              The file exists remotely, but not locally; hash not calculated
          otherwise  md5 hexdigest (as a string)
        """
        remotefile = self._contents.get(leafname, None)
        if remotefile:
            hsh = remotefile.hsh
            if callable(hsh):
                hsh = hsh(leafname)
        else:
            hsh = None
        return hsh

    def get_file_size(self, leafname):
        """
        Return values are as follows:
          None   The file is not present on the remote server
          -1     The 'file' is a directory
          >=0    size in bytes
        """
        remotefile = self._contents.get(leafname, None)
        if remotefile:
            size = remotefile.size
            if callable(size):
                size = size(leafname)
        else:
            size = None
        return size

    def set_file(self, leafname, size, hsh):
        self._contents[leafname] = RemoteFile(size, hsh)


class Cache(object):
    """
    Class that represents a cache of the remote files in a
    directory on an FTP server
    """
    def __init__(self, filename):
        self._filename = filename
        if os.path.exists(filename):
            self._contents = pickle.load(open(filename, 'rb'))
        else:
            self._contents = {}  # remote dir name -> RemoteDirContents

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        self.save()

    def get_dirs(self):
        """
        Return a list of directories that are present in the cache
        """
        return self._contents.keys()

    def get_dir_contents(self, remote_dir_name):
        """
        Return a RemoteDirContents object for the given directory name
        """
        return self._contents.get(remote_dir_name, None)

    def set_dir_contents(self, remote_dir_name, contents):
        """
        Store the given RemoteDirContents against the given directory name
        """
        self._contents[remote_dir_name] = contents

    def save(self):
        pickle.dump(self._contents, open(self._filename, 'wb'))


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


class SitePublisher:
    """
    Class that maintains an FTP connection, making it easy to
    publish a website to an FTP server
    """
    def __init__(self, ftpsite, username, passwd, init_dir, submit, verbose, cache):
        """
        Open a connection to the given site, logging in with the given
        username/password, changing directory to the given directory
        (with / separator), and setting the submit attribute to one
        of the Submit enum values
        cache, if specified, must be a Cache object
        """
        today = datetime.datetime.today().replace(hour=0, minute=0, second=0)
        self.today = time.mktime(today.timetuple())

        self.connection = ftplib.FTP(ftpsite, user=username, passwd=passwd)
        self.submit = submit
        self.verbose = verbose
        self.cd(init_dir)
        self.cache = cache

    def _modified_today(self, filename):
        """
        Return true if the local file has changed today
        """
        file_mtime = os.stat(filename).st_mtime
        # print(filename, today, file_mtime)
        return self.today <= file_mtime

    def cd(self, dirname):
        if dirname[0] == '/':
            self.connection.cwd('/')
            dirname = dirname[1:]
        for one in dirname.split('/'):
            self.connection.cwd(one)

    def syncdir(self,
                dirname,
                extensions=None,
                remotedirname=None,
                submit=None,
                recurse=False):
        """
        Synchronise the directory in accordance with the submit
        attribute passed to the constructor.

        dirname is a local directory name.
        If remotedirname is not given, it is assumed to be the same
        as the local directory name.

        If extensions is given, it must be a list of strings, and
        only files that end with one of the given extensions (e.g. ".png")
        are submitted, irrespective of the value of self.submit

        submit, if specified, must be one of the Submit enum values. If
        not specified, it will default to self.submit
        """
        submit = self.submit if (submit is None) else submit
        output_prefix = dirname
        if remotedirname is not None:
            output_prefix += '(remote="%s")' % remotedirname
        localdirname = dirname
        remotedirname = dirname if (remotedirname is None) else remotedirname
        if remotedirname:
            oldcwd = self.connection.pwd()
            # NB This assumes that remotedirname is a subdirectory of cwd
            if (remotedirname != '.') and (remotedirname not in self.connection.nlst()):
                print('MKDIR (cwd=%s, newdir=%s)' % (self.connection.pwd(), remotedirname))
                self.connection.mkd(remotedirname)
            self.connection.cwd(remotedirname)
        else:
            oldcwd = None
        contents = os.listdir(localdirname)
        # files first
        localfiles = [f for f in contents if os.path.isfile(os.path.join(localdirname, f))]
        if extensions:
            def goodextension(f):
                for ext in extensions:
                    if f.endswith(ext):
                        return True
                return False
            localfiles = [f for f in localfiles if goodextension(f)]
        if self.cache:
            remotedir = RemoteDirCached(self.cache, dirname, self.connection)
        else:
            remotedir = RemoteDirLive(dirname, self.connection)

        localfiles = sorted(localfiles)
        remotefiles = remotedir.get_contents()
        if self.verbose:
            print('%s: %s' % (output_prefix, localfiles))
        for leaf in localfiles:
            localf = os.path.join(localdirname, leaf)
            store = False
            if (submit & Submit.Missing):
                if (os.path.getsize(localf) == remotefiles.get_file_size(leaf)):
                    # sizes match; how about the hash?
                    remotehash = remotefiles.get_file_hash(leaf)
                    assert remotehash != RemoteDirContents.__RemoteFileMissing__
                    assert remotehash != RemoteDirContents.__RemoteFileIsDirectory__
                    if (remotehash != RemoteDirContents.__RemoteFileAssumedCorrect__) and \
                       (remotehash != getfilehash(localf)):
                        store = True
                else:
                    store = True
            if (submit & Submit.ChangedToday) and (self._modified_today(localf)):
                store = True
            if store:
                print(localf)
                self.connection.storbinary('STOR %s' % leaf, open(localf, 'rb'))
                size = os.path.getsize(localf)
                hsh = getfilehash(localf)
                remotefiles.set_file(leaf, size, hsh)  # TOCTOU. :(
        # subdirectories
        if recurse:
            subdirs = [d for d in contents if os.path.isdir(os.path.join(localdirname, d))]
            for d in subdirs:
                if d.startswith('.'):
                    if self.verbose:
                        print('Skipping subdir %s' % d)
                    continue
                self.syncdir(dirname=os.path.join(localdirname, d),
                             extensions=extensions,
                             remotedirname=d,
                             submit=submit,
                             recurse=recurse)
        # and we're done
        if oldcwd:
            self.connection.cwd(oldcwd)
