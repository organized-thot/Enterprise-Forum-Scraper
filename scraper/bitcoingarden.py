import re
import uuid

from datetime import datetime
import dateparser

from scrapy import (
    Request,
    FormRequest
)
from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)

class BitcoinGardenSpider(SitemapSpider):

    name = "bitcoingarden_spider"

    # Url stuffs
    base_url = "https://bitcoingarden.org/forum/index.php"

    # Xpath stuffs
    forum_xpath = "//tr[@class=\"windowbg2\"]//a[@class='subject']/@href"
    pagination_xpath = "//div[@class='pagelinks']/strong/following::a[1]/@href"

    thread_xpath = "//div[contains(@class, 'topic_table')]/table/tbody/tr"
    thread_first_page_xpath = ".//span[contains(@id,\"msg\")]/a/@href"
    thread_last_page_xpath = ".//small[@id]/a[last()]/@href"
    thread_date_xpath = "string(.//td[contains(@class,\"lastpost\")])"

    post_date_xpath = "string(//div[contains(@class,'keyinfo')]/div[@class='smalltext'])"
    thread_page_xpath = "//div[contains(@class, 'pagelinks')]/strong/text()"
    thread_pagination_xpath = "(//div[contains(@class, 'nextlinks')]/a/@href)[1]"
    avatar_xpath = "//img[@class='avatar']/@src"

    # Regex stuffs
    topic_pattern = re.compile(
        r"topic=(\d+)",
        re.IGNORECASE
    )
    avatar_name_pattern = re.compile(
        r".*/(\S+\.\w+)",
        re.IGNORECASE
    )

    # Other settings
    sitemap_datetime_format = "%B %d, %Y, %I:%M:%S %p"
    post_datetime_format = "%B %d, %Y, %I:%M:%S %p"

    use_proxy = 'On'
    
    def parse_thread_date(self, thread_date):

        # Check thread date validation
        if not thread_date:
            return

        # Standardize
        thread_date = thread_date.strip()

        # Parsing stuffs
        thread_date = dateparser.parse(thread_date)

        return thread_date

    def parse_post_date(self, post_date):

        # Check thread date validation
        if not post_date:
            return

        post_date = post_date.strip().strip("»").strip("«").split("on:")[1]
        # Standardize
        post_date = post_date.strip()

        post_date = dateparser.parse(post_date)
        return post_date

    def extract_thread_stats(self, thread):
        """
        :param thread: str => thread html contain url and last mod
        :return: thread url: str, thread lastmod: datetime
        """
        # Load selector
        # selector = Selector(text=thread)

        # Load stats
        thread_first_page_url = None
        if self.thread_first_page_xpath:
            thread_first_page_url = thread.xpath(
                self.thread_first_page_xpath
            ).extract_first()

        thread_last_page_url = None
        if self.thread_last_page_xpath:
            thread_last_page_url = thread.xpath(
                self.thread_last_page_xpath
            ).extract_first()

        thread_lastmod = thread.xpath(
            self.thread_date_xpath
        ).extract()

        thread_lastmod = ' '.join(thread_lastmod).strip().split("by")[0]

        # Process stats
        try:
            thread_url = (self.parse_thread_url(thread_last_page_url)
                          or self.parse_thread_url(thread_first_page_url))
        except Exception as err:
            thread_url = None

        try:
            thread_lastmod = self.parse_thread_date(thread_lastmod)
        except Exception as err:
            thread_lastmod = None

        return thread_url, thread_lastmod

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
            callback=self.parse
        )

    def parse(self, response):

        # Synchronize user agent for cloudfare middlewares
        self.synchronize_headers(response)

        # # Load all forums
        all_forums = response.xpath(self.forum_xpath).extract()

        # update stats
        if len(all_forums):
            self.crawler.stats.set_value("mainlist/mainlist_count", len(all_forums))
        
        for forum_url in all_forums:
            # Standardize url
            if self.base_url not in forum_url:
                forum_url = self.base_url + forum_url
        
            yield Request(
                url=forum_url,
                headers=self.headers,
                callback=self.parse_forum,
                meta=self.synchronize_meta(response)
            )

    def parse_forum(self, response, is_first_page=True):

        # Parse sub forums
        yield from self.parse(response)

        # Parse generic forum
        yield from super().parse_forum(response)

    def parse_thread(self, response):

        # Parse generic thread
        yield from super().parse_thread(response)

        # Parse generic avatar
        yield from super().parse_avatars(response)


class BitcoinGardenScrapper(SiteMapScrapper):

    spider_class = BitcoinGardenSpider
    site_type = 'forum'
