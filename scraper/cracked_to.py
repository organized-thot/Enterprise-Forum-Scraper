import time
import requests
import os
import re
import uuid
import scrapy
from math import ceil
import configparser
from scrapy.http import Request, FormRequest
from scrapy.crawler import CrawlerProcess
from scraper.base_scrapper import SitemapSpider, SiteMapScrapper

LOGINS = [
    {"USER": "MrBashMan", "PASS": "Reg-Crack!pass2"},
    {"USER": "avalanche1337", "PASS": "Crack_Lanch718@2"},
]

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.117 Safari/537.36'


class CrackedToSpider(SitemapSpider):
    name = 'cracked_spider'

    base_url = "https://cracked.io/"
    login_url = f"{base_url}member.php?action=login"

    # Css stuffs
    login_form_xpath = "//form[@action='member.php']"
    forum_xpath = "//a[starts-with(@href, 'Forum-')]/@href"

    # Xpath stuffs
    pagination_xpath = "//a[@class='pagination_next']/@href"
    thread_xpath = "//table[@id='topiclist']//tr[contains(@class, 'inline_row')]"
    thread_first_page_xpath = ".//span[contains(@id,'tid_')]/a[contains(@href,'Thread-')]/@href"
    thread_last_page_xpath = './/a[text()="Last Post"]/@href'

    thread_date_xpath = ".//span[contains(@class,'lastpost')]/a/span/@title|"\
                        ".//span[contains(@class,'lastpost')]/a/text()|"\
                        ".//span[contains(@class,'lastpost')]/text()"\

    thread_pagination_xpath = "//a[@class='pagination_previous']/@href"

    thread_page_xpath = "//span[contains(@class,'pagination_current')]/text()"

    post_date_xpath = '//span[@class="post_date"]/text()[contains(., "-")]|' \
                      '//span[@class="post_date"]/span[@title]/@title'

    avatar_xpath = '//div[@class="author_avatar"]/a/img/@src'

    recaptcha_site_key_xpath = '//div[@class="g-recaptcha"]/@data-sitekey'

    # Regex stuffs
    avatar_name_pattern = re.compile(
        r".*avatar_(\d+\.\w+)\?",
        re.IGNORECASE
    )

    pagination_pattern = re.compile(
        r".*page=(\d+)",
        re.IGNORECASE
    )

    # Login Failed Message
    login_failed_xpath = '//ul[@class="error_message"]'

    # captcha stuffs
    bypass_success_xpath = '//a[@class="guestnav" and text()="Login"]'

    # Other settings
    use_proxy = "VIP"
    use_cloudflare_v2_bypass = True
    sitemap_datetime_format = "%m-%d-%Y"
    handle_httpstatus_list = [403]
    get_cookies_retry = 10
    fraudulent_threshold = 10

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
            url=self.login_url,
            headers=self.headers,
            meta=meta,
            cookies=cookies,
            callback=self.parse_main
        )

    def parse_main(self, response):
        # Synchronize cloudfare user agent
        self.synchronize_headers(response)

        # Login stuffs
        self.post_headers.update(self.headers)

        my_post_key = response.xpath(
            '//input[@name="my_post_key"]/@value').extract_first()
        if not my_post_key:
            return
        login = self.get_login(LOGINS)
        yield FormRequest.from_response(
            response,
            formxpath=self.login_form_xpath,
            formdata={
                "username": login["USER"],
                "password": login["PASS"],
                "remember": "yes",
                "action": "do_login",
                "url": f'{self.base_url}index.php',
                "g-recaptcha-response": self.solve_recaptcha(response, proxyless=True).solution.token,
                'my_post_key': my_post_key
            },
            headers=self.headers,
            dont_filter=True,
            meta=self.synchronize_meta(response)
        )

    def parse_forum(self, response, thread_meta={}, is_first_page=True):

        # Check if login success
        self.check_if_logged_in(response)

        # Load sub forums
        if is_first_page:
            yield from self.parse(response)

        # Parse main forum
        yield from super().parse_forum(
            response,
            thread_meta=thread_meta,
            is_first_page=is_first_page
        )

    def parse_thread(self, response):

        # Synchronize headers user agent with cloudfare middleware
        self.synchronize_headers(response)

        # Parse main thread
        yield from super().parse_thread(response)

        # Parse avatar
        yield from super().parse_avatars(response)


class CrackedToScrapper(SiteMapScrapper):
    spider_class = CrackedToSpider
    site_name = 'cracked.to'
    site_type = 'forum'
