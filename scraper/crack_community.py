import re
import uuid

from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)

from scrapy import Request


class CrackCommunitySpider(SitemapSpider):
    name = "crackcommunity_spider"

    # Url stuffs
    base_url = "http://crackcommunity.com/"

    # Xpath stuffs
    # Forum xpath #
    forum_xpath = '//*[@class="nodeTitle"]/a[contains(@href,"forums")]/@href'
    pagination_xpath = '//div[@class="PageNav"]/nav/a[@class="text"]/@href'

    # Thread xpath #
    thread_xpath = '//li[contains(@id,"thread")]'
    thread_first_page_xpath = './/h3[@class="title"]/a/@href'
    thread_last_page_xpath = './/span[@class="itemPageNav"]/a[last()]/@href'

    thread_date_xpath = './/dl[@class="lastPostInfo"]' \
                        '//a[@class="dateTime"]/abbr/@data-time|' \
                        './/dl[@class="lastPostInfo"]' \
                        '//a[@class="dateTime"]/span/text()'
    thread_pagination_xpath = '//div[@class="PageNav"]/nav/a[contains(text(),"Prev")]/@href'
    thread_page_xpath = '//div[@class="PageNav"]/nav/a[@class="currentPage "]/text()'

    # Post xpath #
    post_date_xpath = './/a[@class="datePermalink"]//abbr/@data-time|' \
                      './/a[@class="datePermalink"]//span/@title'
    avatar_xpath = '//div[@class="avatarHolder"]/a/img/@src'

    # captcha stuffs
    ip_check_xpath = '//text()[contains(.,"Your IP")]'
    use_proxy = 'On'

    # Regex pattern
    avatar_name_pattern = re.compile(
        r".*/(\S+\.\w+)",
        re.IGNORECASE
    )
    pagination_pattern = re.compile(
        r".*page-(\d+)",
        re.IGNORECASE
    )

    # Other settings
    sitemap_datetime_format = "%b %d, %Y at %I:%M %p"
    post_datetime_format = "%b %d, %Y at %I:%M %p"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
            callback=self.parse,
            errback=self.check_site_error
        )

    def parse(self, response):

        # Synchronize header user agent with cloudfare middleware
        self.synchronize_headers(response)

        # Load all forums
        all_forums = response.xpath(self.forum_xpath).extract()

        # update stats
        self.crawler.stats.set_value("mainlist/mainlist_count", len(all_forums))

        # Loop forums
        for forum_url in all_forums:

            # Standardize url
            if self.base_url not in forum_url:
                forum_url = self.base_url + forum_url

            yield Request(
                url=forum_url,
                headers=self.headers,
                meta=self.synchronize_meta(response),
                callback=self.parse_forum
            )

    def check_bypass_success(self, browser):
        if ("blocking your access based on IP address" in browser.page_source or
                browser.find_elements_by_css_selector('.cf-error-details')):
            raise RuntimeError("HackForums.net is blocking your access based on IP address.")

        element = browser.find_elements_by_xpath('//*[@class=\"nodeTitle\"]')
        return bool(element)

    def parse_thread(self, response):

        # Parse generic thread
        yield from super().parse_thread(response)

        # Parse generic avatar
        yield from super().parse_avatars(response)


class CrackCommunityScrapper(SiteMapScrapper):
    spider_class = CrackCommunitySpider
    site_name = 'crackcommunity.com'
    site_type = 'forum'
