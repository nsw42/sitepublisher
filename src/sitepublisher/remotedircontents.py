from collections import namedtuple


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
