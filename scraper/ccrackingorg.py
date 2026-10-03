import os
import re
import uuid

from scrapy.http import Request, FormRequest
from datetime import datetime, timedelta
from scraper.base_scrapper import SitemapSpider, SiteMapScrapper


class CCrackingOrgSpider(SitemapSpider):
    name = 'ccrackingorg_spider'
    base_url = "https://c-cracking.org/"

    # Xpaths
    forum_xpath = '//div[@class="ipsDataItem_main"]//h4/a/@href|' \
                  '//div[@class="ipsDataItem_main"]/ul/li' \
                  '/a[contains(@href, "forum/")]/@href'
    pagination_xpath = '//li[@class="ipsPagination_next"]/a/@href'
    thread_xpath = '//li[contains(@class, "ipsDataItem ")]'
    thread_first_page_xpath = './/span[@class="ipsType_break ipsContained"]/a/@href'
    thread_last_page_xpath = './/span[contains(@class, "ipsPagination_mini")]' \
                             '/span[contains(@class, "ipsPagination_")][last()]/a/@href'
    thread_date_xpath = './/li[@class="ipsType_light"]/a/time/@datetime'
    thread_pagination_xpath = '//li[@class="ipsPagination_prev"]/a/@href'
    thread_page_xpath = '//li[contains(@class, "ipsPagination_active")]/a/text()'
    post_date_xpath = '//div[contains(@class, "ipsColumn")]//a/time[@datetime]/@datetime'

    avatar_xpath = '//aside//div[contains(@class, "cAuthorPane_")]//a[contains(@class, "ipsUserPhoto")]/img/@src'

    # Regex stuffs
    topic_pattern = re.compile(
        r'topic/(\d+)-',
        re.IGNORECASE
    )
    avatar_name_pattern = re.compile(
        r'.*/(\S+\.\w+)',
        re.IGNORECASE
    )

    # Recaptcha stuffs
    recaptcha_site_key_xpath = '//div[@data-xf-init="re-captcha"]/@data-sitekey'

    # Other settings
    use_proxy = "VIP"
    use_cloudflare_v2_bypass = True
    handle_httpstatus_list = [403]
    sitemap_datetime_format = "%Y-%m-%dT%H:%M:%S"
    post_datetime_format = "%Y-%m-%dT%H:%M:%S"

    def start_requests(self):
        yield Request(
            url="https://google.com",
            headers=self.headers,
            callback=self.pass_cloudflare
        )

    def pass_cloudflare(self, cookies=None, ip=None):
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
        request_kwargs = {
            "url": self.base_url,
            "headers": self.headers,
            "callback": self.parse,
            "dont_filter": True,
            "cookies": cookies,
            "meta": meta
        }

        yield Request(**request_kwargs)

    def parse(self, response):
        # Synchronize cloudfare user agent
        self.synchronize_headers(response)
        all_forums = response.xpath(self.forum_xpath).extract()

        # update stats
        self.crawler.stats.set_value("mainlist/mainlist_count", len(all_forums))
        for forum_url in all_forums:
            # Standardize url
            if self.base_url not in forum_url:
                forum_url = self.base_url + forum_url

            yield Request(
                url=forum_url,
                headers=self.headers,
                callback=self.parse_forum,
                meta=self.synchronize_meta(response),
            )

    def parse_forum(self, response, is_first_page=True):
        # Synchronize header user agent with cloudfare middleware
        self.synchronize_headers(response)

        sub_forums = response.xpath(self.forum_xpath).extract()

        for forum_url in sub_forums:

            # Standardize url
            if self.base_url not in forum_url:
                forum_url = self.base_url + forum_url
            yield Request(
                url=forum_url,
                headers=self.headers,
                callback=self.parse_forum,
                meta=self.synchronize_meta(response),
            )
        yield from super().parse_forum(response)

    def parse_thread(self, response):

        # Parse generic thread
        yield from super().parse_thread(response)

        # Parse generic avatar
        yield from super().parse_avatars(response)


class CCrackingOrgScrapper(SiteMapScrapper):
    spider_class = CCrackingOrgSpider
    site_name = 'ccracking.org'
    site_type = 'forum'
