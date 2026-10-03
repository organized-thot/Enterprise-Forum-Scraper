import re
import uuid

from scrapy import Request

from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)
from datetime import datetime


USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/84.0.4147.135 Safari/537.36')


class CardingSiteSpider(SitemapSpider):
    name = 'cardingsite_spider'

    # Url stuffs
    base_url = "https://cardingsite.cc/"

    # Xpath stuffs
    forum_xpath = '//h3[@class="node-title"]/a/@href'
    pagination_xpath = '//a[contains(@class, "pageNav-jump--next") and text()="Next"]/@href'
    thread_xpath = '//div[contains(@class, "structItem--thread")]'
    thread_first_page_xpath = './/div[@class="structItem-title"]/a[last()]/@href'
    thread_last_page_xpath = './/span[@class="structItem-pageJump"]/a[last()]/@href'
    thread_date_xpath = './/time[contains(@class, "structItem-latestDate")]/@datetime'
    thread_page_xpath = '//nav//li[contains(@class,"pageNav-page--current")]/a/text()'
    thread_pagination_xpath = '//nav//a[contains(text(),"Prev")]/@href'
    post_date_xpath = '//article//time/@title'
    avatar_xpath = '//article//a[contains(@class, "avatar")]/img/@src'

    # Regex stuffs
    topic_pattern = re.compile(
        r"threads/.*\.(\d+)",
        re.IGNORECASE
    )
    avatar_name_pattern = re.compile(
        r".*/(\S+\.\w+)",
        re.IGNORECASE
    )

    # captcha stuffs
    bypass_success_xpath = '//a[@href="/login/"]'

    # Other settings
    use_proxy = "On"
    sitemap_datetime_format = '%b %d, %Y'
    post_datetime_format = '%b %d, %Y'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers = {
            "User-Agent": USER_AGENT
        }

    def start_requests(self):
        # Temporary action to start spider
        yield Request(
            url=self.temp_url,
            headers=self.headers,
            callback=self.pass_cloudflare
        )

    def pass_cloudflare(self, response):
        # Load cookies and ip
        cookies, ip = self.get_cloudflare_cookies(
            base_url=self.base_url,
            proxy=True,
            fraud_check=False
        )

        yield Request(
            url=self.base_url,
            headers=self.headers,
            meta={
                "cookiejar": uuid.uuid1().hex,
                "ip": ip
            },
            cookies=cookies,
            callback=self.parse
        )

    def parse(self, response):

        # Synchronize cloudfare user agent
        self.synchronize_headers(response)

        all_forums = response.xpath(self.forum_xpath).extract()

        # update stats
        self.crawler.stats.set_value("mainlist/mainlist_count", len(all_forums))
        for forum_url in all_forums:

            yield response.follow(
                url=forum_url,
                headers=self.headers,
                callback=self.parse_forum,
                meta=self.synchronize_meta(response),
            )

    def parse_thread(self, response):

        # Parse generic thread
        yield from super().parse_thread(response)

        # Parse generic avatar
        yield from super().parse_avatars(response)


class CardingSiteScraper(SiteMapScrapper):

    spider_class = CardingSiteSpider
    site_name = 'cardingsite.cc'
    site_type = 'forum'

    def load_settings(self):
        settings = super().load_settings()
        settings.update(
            {
                "USER_AGENT": USER_AGENT
            }
        )
        return settings
