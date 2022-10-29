# sitepublisher

A caching FTP-based website publisher.

## Usage

Recommended usage is something like the following:

```python
from sitepublisher import Cache, SitePublisher, Submit

with Cache('.publish.cache') as cache:
    publisher = SitePublisher(
        ftpsite='your.server.domain',
        username='bilbo',
        passwd='gandalf',
        init_dir='public_html',
        submit=Submit.Missing,
        verbose=True,
        cache=cache)
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
most secure of approaches.
