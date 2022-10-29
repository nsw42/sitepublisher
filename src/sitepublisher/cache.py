import os.path
import pickle


class Cache(object):
    """
    Class that represents a cache of the remote files in a
    directory on an FTP server. Can be used as a context
    manager, automatically saving changes on exit.
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
