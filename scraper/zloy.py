import re
import os
import uuid

from datetime import datetime, timedelta

from scrapy import (
    Request,
    FormRequest,
    Selector
)
from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)


class ZloySpider(SitemapSpider):

    name = "zloy_spider"

    # Url stuffs
    base_url = "https://forum.zloy.bz/"

    # Xpath stuffs
    forum_xpath = '//a[contains(@href, "forumdisplay.php?")]/@href'
    thread_xpath = '//tr[td[contains(@id, "td_threadtitle_")]]'
    thread_first_page_xpath = './/td[contains(@id, "td_threadtitle_")]/div'\
                              '/a[contains(@href, "showthread.php?")]/@href'
    thread_last_page_xpath = './/td[contains(@id, "td_threadtitle_")]/div/span'\
                             '/a[contains(@href, "showthread.php?")]'\
                             '[last()]/@href'
    thread_date_xpath = './/span[@class="time"]/preceding-sibling::text()'

    pagination_xpath = '//a[@rel="next"]/@href'
    thread_pagination_xpath = '//a[@rel="prev"]/@href'
    thread_page_xpath = '//div[@class="pagenav"]//span/strong/text()'
    post_date_xpath = '//table[contains(@id, "post")]//td[@class="thead"][1]'\
                      '/a[contains(@name,"post")]'\
                      '/following-sibling::text()[1]'
    avatar_xpath = '//a[contains(@href, "member.php?") and img/@src]//img/@src'

    # Regex stuffs
    topic_pattern = re.compile(
        r"t=(\d+)",
        re.IGNORECASE
    )
    avatar_name_pattern = re.compile(
        r"u=(\d+)",
        re.IGNORECASE
    )

    # Recaptcha stuffs
    recaptcha_site_key_xpath = '//div[@data-xf-init="re-captcha"]/@data-sitekey'
    bypass_success_xpath = '//a[contains(@href, "forumdisplay.php?")]'

    # Other settings
    use_proxy = "On"
    post_datetime_format = '%d.%m.%Y'
    sitemap_datetime_format = '%d.%m.%Y'
    cloudfare_delay = 5
    handle_httpstatus_list = [503]

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
                dont_filter=True,
                meta=self.synchronize_meta(response)
            )

    def parse_forum(self, response, is_first_page=True):
        # Check status 503
        if response.status == 503:
            request = response.request
            request.dont_filter = True
            request.meta = {
                "cookiejar": uuid.uuid1().hex
            }
            yield request
            return

        yield from super().parse_forum(response)

    def parse_thread(self, response):
        # Check status 503
        if response.status == 503:
            request = response.request
            request.dont_filter = True
            request.meta = {
                "cookiejar": uuid.uuid1().hex,
                "topic_id": response.meta.get("topic_id")
            }
            yield request
            return

        # Save generic thread
        yield from super().parse_thread(response)

        # Save avatars
        yield from self.parse_avatars(response)


class ZloyScrapper(SiteMapScrapper):

    spider_class = ZloySpider
    site_name = 'zloy.bz'
    site_type = 'forum'

    def load_settings(self):
        settings = super().load_settings()
        settings.update(
            {
                "RETRY_HTTP_CODES": [406, 429, 500],
            }
        )
        return settings
