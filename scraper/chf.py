import uuid
import re

from scrapy.http import Request
from scraper.base_scrapper import SitemapSpider, SiteMapScrapper


USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_2) '\
             'AppleWebKit/537.36 (KHTML, like Gecko) '\
             'Chrome/81.0.4044.138 Safari/537.36'


class ChfSpider(SitemapSpider):
    name = 'chf_spider'
    base_url = 'https://goldway.bz/'

    # Xpaths
    forum_xpath = '//h3[@class="node-title"]/a/@href|'\
                  '//a[contains(@class,"subNodeLink--forum")]/@href'
    thread_xpath = '//div[contains(@class, "structItem structItem--thread")]'
    thread_first_page_xpath = './/div[@class="structItem-title"]'\
                              '/a[contains(@href,"threads/")]/@href'
    thread_last_page_xpath = './/span[@class="structItem-pageJump"]'\
                             '/a[last()]/@href'
    thread_date_xpath = './/time[contains(@class, "structItem-latestDate")]'\
                        '/@datetime'
    pagination_xpath = '//a[contains(@class,"pageNav-jump--next")]/@href'
    thread_pagination_xpath = '//a[contains(@class, "pageNav-jump--prev")]'\
                              '/@href'
    thread_page_xpath = '//li[contains(@class, "pageNav-page--current")]'\
                        '/a/text()'
    post_date_xpath = '//header[contains(@class,"message-attribution")]'\
                      '//time[@datetime]/@datetime'

    avatar_xpath = '//div[@class="message-avatar-wrapper"]/a/img/@src'

    # Regex stuffs
    topic_pattern = re.compile(
        r"[/?]threads/(\d+)",
        re.IGNORECASE
    )

    avatar_name_pattern = re.compile(
        r".*/(\S+\.\w+)",
        re.IGNORECASE
    )

    # Other settings
    handle_httpstatus_list = [403]
    use_proxy = "On"
    sitemap_datetime_format = "%Y-%m-%dT%H:%M:%S"
    post_datetime_format = "%Y-%m-%dT%H:%M:%S"
    fraudulent_threshold = 60
    get_cookies_delay = 6

    def start_requests(self):

        cookies, ip = self.get_cookies(
            base_url=self.base_url,
            proxy=self.use_proxy,
            fraud_check=False,
            check_captcha=True
        )

        self.logger.info(f'COOKIES: {cookies}')

        # Init request kwargs and meta
        meta = {
            "cookiejar": uuid.uuid1().hex,
            "ip": ip
        }

        yield Request(
            url=self.base_url,
            headers=self.headers,
            meta=meta,
            cookies=cookies,
            errback=self.check_site_error
        )

    def parse(self, response):
        # Synchronize cloudfare user agent
        self.synchronize_headers(response)

        all_forums = response.xpath(self.forum_xpath).extract()

        # update stats
        self.crawler.stats.set_value("mainlist/mainlist_count", len(all_forums))
        for forum_url in all_forums:

            yield Request(
                url=response.urljoin(forum_url),
                headers=self.headers,
                callback=self.parse_forum,
                meta=self.synchronize_meta(response),
            )

    def parse_thread(self, response):
        self.synchronize_headers(response)

        # Parse generic thread
        yield from super().parse_thread(response)

        # Save avatars
        yield from super().parse_avatars(response)


class ChfScrapper(SiteMapScrapper):

    spider_class = ChfSpider
    site_name = 'goldway.bz'
    site_type = 'forum'

    def load_settings(self):
        settings = super().load_settings()
        settings.update(
            {
                "RETRY_HTTP_CODES": [403, 406, 429, 500, 503],
                'COOKIES_ENABLED': True
            }
        )
        return settings
