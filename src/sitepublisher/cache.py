import json
import os.path

from .remotedircontents import RemoteDirContents


class Cache(object):
    """
    Class that represents a cache of the remote files in a
    directory on an FTP server. Can be used as a context
    manager, automatically saving changes on exit.
    """
    def __init__(self, filename):
        self._filename = filename
        self._contents = {}  # remote dir name -> RemoteDirContents
        if os.path.exists(filename):
            for dirname, dircontents in json.load(open(filename, 'r')).items():
                dircontentsobj = RemoteDirContents()
                for leaf, (size, hsh) in dircontents.items():
                    dircontentsobj.set_file(leaf, size, hsh)
                self._contents[dirname] = dircontentsobj

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
        to_save = {}
        for dirname, dircontents in self._contents.items():
            to_save[dirname] = dircontents._contents
        json.dump(to_save, open(self._filename, 'w'), indent=2, sort_keys=True)
