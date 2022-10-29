"""
sitepublisher
Class that makes it easy to publish a website via FTP
"""

import datetime
import ftplib
import os.path
import time

from .filehash import getfilehash
from .remotedir import RemoteDirCached, RemoteDirLive
from .remotedircontents import RemoteDirContents


class Submit:
    """
    Enum of values that influence how the ftp publisher is to behave.
    Submit.MissingOrChanged indicates files that are missing (or the wrong
      size) on the remote server, or whose (md5) hash have changed since the
      site was last published.
    Submit.ChangedToday indicates files that have changed on the local
      filesystem since midnight.
    Values may be added together
    """
    MissingOrChanged = 1
    ChangedToday = 2
    MissingOrChangedToday = MissingOrChanged + ChangedToday
    AllFiles = 0xff


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
            if (submit & Submit.MissingOrChanged):
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
