import json
import re
import uuid
from datetime import (
    datetime
)
from urllib.parse import urlencode

from lxml.html import fromstring
from scrapy import (
    Request,
    FormRequest
)

from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)

USER = "vrx9@protonmail.com"
PASS = "Night#Bot000"


class TheBotSpider(SitemapSpider):
    name = "thebot_spider"

    # Url stuffs
    base_url = "https://thebot.net"
    login_url = "https://thebot.net/login/login"

    # Xpath stuffs
    forum_xpath = "//h3[@class=\"node-title\"]/a/@href|" \
                  "//a[contains(@class, \"subNodeLink subNodeLink--forum\")]/@href"
    pagination_xpath = "//a[contains(@class,\"pageNav-jump--next\")]/@href"

    thread_xpath = "//div[contains(@class,\"structItem--thread\")]"
    thread_first_page_xpath = ".//div[@class=\"structItem-title\"]/a/@href"
    thread_last_page_xpath = ".//span[@class=\"structItem-pageJump\"]/a[last()]/@href"
    thread_date_xpath = ".//time[contains(@class,\"structItem-latestDate\")]/@datetime"
    thread_page_xpath = "//li[contains(@class,\"pageNav-page--current\")]/a/text()"
    thread_pagination_xpath = "//a[contains(@class,\"pageNav-jump--prev\")]/@href"

    post_date_xpath = "//div/a/time[@datetime]/@datetime"

    avatar_xpath = "//div[@class=\"message-avatar-wrapper\"]/a/img/@src"

    # Login Failed Message
    login_failed_xpath = '//div[contains(@class, "blockMessage blockMessage--error")]'

    avatar_name_pattern = re.compile(
        r".*/(\S+\.\w+)",
        re.IGNORECASE
    )
    pagination_pattern = re.compile(
        r".*/page-(\d+)",
        re.IGNORECASE
    )

    # Other settings
    use_proxy = "VIP"
    use_cloudflare_v2_bypass = True
    sitemap_datetime_format = "%Y-%m-%dT%H:%M:%S"
    post_datetime_format = "%Y-%m-%dT%H:%M:%S"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers.update(
            {
                "Sec-fetch-mode": "navigate",
                "Sec-fetch-site": "none",
                "Sec-fetch-user": "?1",
            }
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
            callback=self.get_token
        )

    def get_token(self, response):

        # Synchronize user agent for cloudfare middleware
        self.synchronize_headers(response)
        
        # Load token
        match = re.findall(r'csrf: \'(.*?)\'', response.text)
        
        # Load param
        params = {
            '_xfRequestUri': '/',
            '_xfWithData': '1',
            '_xfToken': match[0],
            '_xfResponseType': 'json'
        }
        token_url = 'https://thebot.net/login/?' + urlencode(params)

        yield Request(
            url=token_url,
            headers=self.headers,
            callback=self.proceed_for_login,
            meta=self.synchronize_meta(response)
        )

    def proceed_for_login(self, response):

        # Synchronize user agent for cloudfare middleware
        self.synchronize_headers(response)
        
        # Load json data
        json_response = json.loads(response.text)
        html_response = fromstring(json_response["html"]["content"])
        
        # Exact token
        token = html_response.xpath(
            "//input[@name=\"_xfToken\"]/@value")[0]
        
        # Load params
        params = {
            "login": USER,
            "password": PASS,
            "remember": "1",
            "_xfRedirect": "https://thebot.net/",
            "_xfToken": token
        }
        yield FormRequest(
            url="https://thebot.net/login/login",
            callback=self.parse,
            formdata=params,
            headers=self.headers,
            dont_filter=True,
            meta=self.synchronize_meta(response)
        )

    def parse(self, response):

        # Synchronize user agent for cloudfare middleware
        self.synchronize_headers(response)

        # Check if login failed
        self.check_if_logged_in(response)
        
        # Load all forums
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
                meta=self.synchronize_meta(response),
                callback=self.parse_forum
            )

    def parse_thread(self, response):

        # Save generic thread
        yield from super().parse_thread(response)

        # Save avatars
        yield from super().parse_avatars(response)


class TheBotScrapper(SiteMapScrapper):

    spider_class = TheBotSpider
    site_name = 'thebot.cc'
    site_type = 'forum'

    def load_settings(self):
        settings = super().load_settings()
        settings.update(
            {
                'RETRY_HTTP_CODES': [403, 406, 429, 500]
            }
        )
        return settings
