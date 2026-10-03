import re
import json
import uuid

from datetime import datetime, timedelta
from lxml.html import fromstring
from urllib.parse import urlencode

from scrapy import (
    Request,
    FormRequest,
    Selector
)
from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)

USER = 'nightlion123'
PASS = 'NightLion123'


class ImhatimiSpider(SitemapSpider):
    name = 'imhatimi_spider'

    # Url stuffs
    base_url = "https://imhatimi.org"
    login_url = f'{base_url}/forum/login/login'

    # Xpaths
    forum_xpath = '//h3[@class="node-title"]/a/@href|' \
                  '//a[contains(@class,"subNodeLink--forum")]/@href'
    thread_xpath = '//div[contains(@class, "structItem structItem--thread")]'
    thread_first_page_xpath = './/div[@class="structItem-title"]' \
                              '/a[contains(@href,"threads/")]/@href'
    thread_last_page_xpath = './/span[@class="structItem-pageJump"]' \
                             '/a[last()]/@href'
    thread_date_xpath = './/time[contains(@class, "structItem-latestDate")]' \
                        '/@datetime'
    pagination_xpath = '//a[contains(@class,"pageNav-jump--next")]/@href'
    thread_pagination_xpath = '//a[contains(@class, "pageNav-jump--prev")]' \
                              '/@href'
    thread_page_xpath = '//li[contains(@class, "pageNav-page--current")]' \
                        '/a/text()'
    post_date_xpath = '//ul[contains(@class, "message-attribution-main")]' \
                      '//time[contains(@class, "u-dt")]/@datetime'

    avatar_xpath = '//div[@class="message-avatar-wrapper"]/a/img/@src'

    # Login Failed Message
    login_failed_xpath = '//div[contains(@class, "blockMessage blockMessage--error")]'

    # Recaptcha stuffs
    hcaptcha_site_key_xpath = "//div[@data-sitekey]/@data-sitekey"

    # Other settings
    use_proxy = "VIP"
    use_cloudflare_v2_bypass = True
    handle_httpstatus_list = [403]
    sitemap_datetime_format = "%Y-%m-%dT%H:%M:%S"
    post_datetime_format = "%Y-%m-%dT%H:%M:%S"

    # Regex stuffs
    topic_pattern = re.compile(
        r'threads/.*\.(\d+)/',
        re.IGNORECASE
    )
    avatar_name_pattern = re.compile(
        r".*/(\S+\.\w+)",
        re.IGNORECASE
    )

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
            "callback": self.parse_main,
            "dont_filter": True,
            "cookies": cookies,
            "meta": meta
        }

        yield Request(**request_kwargs)

    def parse_main(self, response):
        # Synchronize user agent for cloudfare middleware
        self.synchronize_headers(response)

        yield Request(
            url=self.login_url,
            headers=self.headers,
            callback=self.proceed_for_login,
            meta=self.synchronize_meta(response)
        )

    def proceed_for_login(self, response):
        # Synchronize user agent for cloudfare middleware
        self.synchronize_headers(response)

        captcha_response = self.solve_hcaptcha(response,
                                               proxyless=True,
                                               site_url=self.login_url)

        # Exact token
        token = response.xpath(
            '//input[@name="_xfToken"]/@value').extract_first()
        params = {
            'login': USER,
            'password': PASS,
            "remember": '1',
            '_xfRedirect': f'{self.base_url}/forum/',
            '_xfToken': token,
            'g-recaptcha-response': captcha_response,
            'h-captcha-response': captcha_response
        }

        yield FormRequest(
            url=self.login_url,
            callback=self.parse_post_login,
            formdata=params,
            headers=self.headers,
            dont_filter=True,
            meta=self.synchronize_meta(response),
        )

    def parse_post_login(self, response):
        # Synchronize user agent for cloudfare middleware
        self.synchronize_headers(response)

        # Load backup code url
        yield Request(
            url=self.base_url,
            headers=self.headers,
            dont_filter=True,
            callback=self.parse,
            meta=self.synchronize_meta(response),
        )

    def parse_thread_date(self, thread_date):
        """
        :param thread_date: str => thread date as string
        :return: datetime => thread date as datetime converted from string,
                            using class sitemap_datetime_format
        """

        return datetime.strptime(
            thread_date.strip()[:-5],
            self.sitemap_datetime_format
        )

    def parse_post_date(self, post_date):
        """
        :param post_date: str => post date as string
        :return: datetime => post date as datetime converted from string,
                            using class post_datetime_format
        """
        return datetime.strptime(
            post_date.strip()[:-5],
            self.post_datetime_format
        )

    def parse_thread(self, response):

        if response.status == 403:
            err_msg = response.css(
                '.p-body-pageContent > .blockMessage::text').get()
            if err_msg:
                self.logger.warning('%s - %s', response.url, err_msg.strip())

        # Parse generic thread
        yield from super().parse_thread(response)

        # Parse generic avatar
        yield from super().parse_avatars(response)


class ImhatimiScrapper(SiteMapScrapper):
    spider_class = ImhatimiSpider
    site_name = 'imhatimi.org'
    site_type = 'forum'

    def load_settings(self):
        settings = super().load_settings()
        settings.update({
            'RETRY_HTTP_CODES': [403, 406, 408, 429, 500, 502, 503, 504, 522, 524],
            'CLOSESPIDER_ERRORCOUNT': 1
        })
        return settings
