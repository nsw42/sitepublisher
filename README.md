# sitepublisher

A caching FTP-based website publisher.

## Overview

Intended to facilitate the publishing of locally-generated, single-author websites.
Maintains a hash of the local files that have been published, so that only files
that have been changed get uploaded when next publishing, even if timestamps have
changed as a result of rebuilding the site.

## Usage

Recommended usage is something like the following:

```python
from sitepublisher import Cache, SitePublisher, Submit

with Cache('.publish.cache') as cache:
    publisher = SitePublisher(
        ftpsite='your.server.domain',
        username='bilbo',
        passwd='G4ndalfTheWh1te',
        init_dir='public_html',
        submit=Submit.MissingOrChanged,
        verbose=False,
        cache=cache,
        tls=True)
    publisher.syncdir(dirname='.', remotedirname='', extensions=['.html', '.jpg'])
    publisher.syncdir(dirname='css', extensions=['.css'])
    publisher.syncdir(dirname='images', extensions=['.jpg', '.png'])
```

If you don't need fine-grained control over what gets uploaded, eg because
you're publishing the results of a build script, it's simpler still:

```python
publisher = SitePublisher(...)
publisher.syncdir(dirname='public', remotedirname='.', recurse=True)
```

## Security

Pointing out the obvious: storing your server password in plain-text isn't the
most secure of approaches. But you knew that, and you were already planning to
use [keyring](https://pypi.org/project/keyring/) to manage the password.

## Version history

* v0.1.0: Enable TLS by default for the FTP connection
* v0.0.1: First version in public git
