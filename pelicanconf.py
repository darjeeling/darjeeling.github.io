import os
import pprint
from pathlib import Path

AUTHOR = 'KwonHan Bae'

SITENAME = 'Eyes For you'
SITEURL = ''

PATH = 'content'

ARTICLE_PATHS = ['articles']

article_multi_directoy_source_target = Path(PATH) / 'articles'
subdirectories = []
for target_dir in article_multi_directoy_source_target.glob("*" + os.sep):
    subdirectories.append(
        target_dir.relative_to(Path(PATH))
    )

# Reconstruct the ARTICLE_PATHS list with a new list of subdirectories.
ARTICLE_PATHS = ARTICLE_PATHS + subdirectories

TIMEZONE = 'Asia/Seoul'

DEFAULT_LANG = 'ko'

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

# URL Settings
# https://docs.getpelican.com/en/stable/settings.html#url-settings
ARTICLE_URL = 'posts/{lang}/{date:%Y}/{date:%m}/{date:%d}/{slug}/'
ARTICLE_SAVE_AS = 'posts/{lang}/{date:%Y}/{date:%m}/{date:%d}/{slug}/index.html'
PAGE_URL = 'pages/{slug}/'
PAGE_SAVE_AS = 'pages/{slug}/index.html'
PAGE_LANG_URL = 'pages/{slug}-{lang}.html'


GOOGLE_ANALYTICS='G-DFEVBR8NWY'

# Tag pages
TAGS_URL = 'tags.html'
TAGS_SAVE_AS = 'tags.html'
TAG_URL = 'tag/{slug}.html'
TAG_SAVE_AS = 'tag/{slug}.html'

# Blogroll
LINKS = (
    ('About Me','/pages/about-me/'),
    ('PSF!','/tag/psf.html'),
)

# Social widget
SOCIAL = (
            ('Twitter', 'https://twitter.com/darjeelingt'),
            ('Mastodon', 'https://mtd.pythonasia.org/web/@darjeeling'),
            ('github','https://github.com/darjeeling/'),
            ('Facebook','https://www.facebook.com/kwonhan.bae'),
            ('Linkedin','https://www.linkedin.com/in/kwonhanbae/'),
)

DEFAULT_PAGINATION = 10
DEFAULT_LANG = 'en'
PAGES_ON_MENU = False
INDEXES_ON_MENU = True

# Uncomment following line if you want document-relative URLs when developing
RELATIVE_URLS = True

PLUGINS = ['sitemap']
THEME = 'pelican-chemistry'


# https://github.com/pelican-plugins/sitemap
SITEMAP = {
    "exclude": ["tag/", "category/"],
    "format": "xml",
    "priorities": {
        "articles": 0.5,
        "indexes": 0.5,
        "pages": 0.5
    },
    "changefreqs": {
        "articles": "monthly",
        "indexes": "daily",
        "pages": "monthly"
    }
}

EXTRA_PATH_METADATA = {
    'extra/favicon.ico': {'path': 'favicon.ico'},
}


MARKDOWN = {
    'extension_configs': {
        'markdown.extensions.extra': {},
        'markdown.extensions.admonition': {},
        'markdown.extensions.codehilite': {
            'css_class': 'highlight'
        },
        'markdown.extensions.meta': {},
        'markdown.extensions.toc': {
            'permalink': 'true',
        },
    }
}
