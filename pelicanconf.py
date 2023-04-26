AUTHOR = 'KwonHan'
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

# Blogroll
LINKS = (
        ('IZ4U.NET', 'https://iz4u.net/'),
)

# Social widget
SOCIAL = (
            ('Twitter', 'https://twitter.com/darjeelingt'),
            ('Mastodon', 'https://mtd.pythonasia.org/web/@darjeeling'),
            ('Facebook','https://www.facebook.com/kwonhan.bae'),
            ('Linkedin','https://www.linkedin.com/in/kwonhanbae/'),
)

DEFAULT_PAGINATION = 10

# Uncomment following line if you want document-relative URLs when developing
#RELATIVE_URLS = True


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
