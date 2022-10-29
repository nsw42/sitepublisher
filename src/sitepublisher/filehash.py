import hashlib


def getfilehash(filename):
    """
    Returns md5(filename || file data)
    """
    try:
        handle = open(filename, 'rb')
        # It's tempting to remove the initialisation with the filename,
        # because it makes it harder to manually verify the contents of
        # the cache - but doing so will invalidate all of the cache files
        # that are lying around.
        md5 = hashlib.md5(filename.encode('utf-8'))
        while True:
            data = handle.read(md5.digest_size * 1024)
            if data == b'':
                break
            md5.update(data)
        return md5.hexdigest()
    except IOError:
        return None
