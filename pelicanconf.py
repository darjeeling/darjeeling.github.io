AUTHOR = 'KwonHan Bae'
SITENAME = 'Eyes For you'
SITEURL = ''

PATH = 'content'

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
ARTICLE_URL = 'posts/{lang}/{date:%Y}/{date:%b}/{date:%d}/{slug}/'
ARTICLE_SAVE_AS = 'posts/{lang}/{date:%Y}/{date:%b}/{date:%d}/{slug}/index.html'
PAGE_URL = 'pages/{slug}/'
PAGE_SAVE_AS = 'pages/{slug}/index.html'
PAGE_LANG_URL = 'pages/{slug}-{lang}.html'

# Blogroll
LINKS = (
        ('IZ4U.NET', 'https://iz4u.net/'),
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
PAGES_ON_MENU = True

# Uncomment following line if you want document-relative URLs when developing
#RELATIVE_URLS = True

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
