import os
import re

from scrapy.http import Request, FormRequest
from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper,
    PROXY_USERNAME,
    PROXY_PASSWORD,
    PROXY
)

import uuid


from selenium.webdriver import (
    Chrome,
    ChromeOptions
)


USER = 'Cyrax_011'
PASS = 'Night#India065'

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_2) '\
             'AppleWebKit/537.36 (KHTML, like Gecko) '\
             'Chrome/81.0.4044.138 Safari/537.36'


class DemonForumsSpider(SitemapSpider):
    name = 'demonforums_spider'

    use_proxy = "VIP"
    proxy_countries = ['us', 'uk']

    handle_httpstatus_list = [403, 503]

    ip_check_xpath = "//text()[contains(.,\"Your IP\")]"

    rotation_tries = 0

    base_url = 'https://demonforums.net/'
    avatar_name_pattern = re.compile(r'avatar_(\d+\.\w+)')
    pagination_pattern = re.compile(r'.*page=(\d+)')

    # # Xpath stuffs
    forum_xpath = '//a[contains(@href, "Forum-")]/@href'
    thread_xpath = '//tr[contains(@class,"inline_row")]'

    thread_first_page_xpath = './/span[contains(@class, "subject_")'\
                              ' and contains(@id, "tid_")]/a'

    thread_last_page_xpath = './/td[contains(@class,"lastpost")]//'\
                             'a[text()="Last Post"]/@href'

    # thread date later
    thread_date_xpath = './/td[contains(@class,"last_post")]/span/span/@title|'\
                        './/td[contains(@class,"last_post")]/span/a[last()]/'\
                        'following-sibling::text()'

    pagination_xpath = '//a[contains(@class,"pagination_next")]/@href'

    thread_pagination_xpath = '//a[contains(@class,"pagination_previous")]'\
                              '/@href'

    thread_page_xpath = '//span[contains(@class,"pagination_current")]/text()'

    post_date_xpath = '//span[@class="post_date"]/span/@title|//span'\
                      '[@class="post_date"]/text()'

    avatar_xpath = '//div[@class="author_avatar"]//img/@src'
    
    # Login Failed Message
    login_failed_xpath = '//div[contains(., "You have entered an invalid username or password")]'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_url = 'https://demonforums.net/'
        # self.headers = {
        #     'accept': 'text/html,application/xhtml+xml,application/xml'
        #               ';q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,'
        #               'application/signed-exchange;v=b3;q=0.9',
        #     'accept-language': 'en-US,en;q=0.9',
        #     'cache-control': 'max-age=0',
        #     'referer': 'https://demonforums.net/',
        #     'sec-fetch-dest': 'document',
        #     'sec-fetch-mode': 'navigate',
        #     'sec-fetch-site': 'same-origin',
        #     'sec-fetch-user': '?1',
        #     'upgrade-insecure-requests': '1',
        #     'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6)'
        #                   ' AppleWebKit/537.36 (KHTML, like Gecko) Chrome/'
        #                   '85.0.4183.83 Safari/537.36'
        # }

    def start_requests(self):
        cookies, ip = self.get_cookies(
            base_url=self.base_url,
            proxy=self.use_proxy,
            fraud_check=False,
        )

        self.logger.info(f'COOKIES: {cookies}')

        # Init request kwargs and meta
        meta = {
            "cookiejar": uuid.uuid1().hex,
            "ip": ip
        }

        self.logger.info(f'COOKIES: {cookies}')
        yield Request(
            url=self.base_url,
            headers=self.headers,
            callback=self.process_login,
            cookies=cookies,
            meta=meta,
            dont_filter=True
        )

    def parse_captcha(self, response):
        ip_ban_check = response.xpath(
            self.ip_check_xpath
        ).extract_first()

        # Report bugs
        if "error code: 1005" in response.text:
            self.logger.info(
                "Ip for error 1005 code. Rotating."
            )
        elif ip_ban_check:
            self.logger.info(
                "%s has been permanently banned. Rotating." % ip_ban_check
            )

        if self.use_proxy == 'Off':
            return

        if self.rotation_tries < 20:
            self.rotation_tries += 1
            yield from self.start_requests()

    def process_login(self, response):

        self.synchronize_headers(response)

        if response.status == 403:
            yield from self.parse_captcha(response)
            return

        my_post_key = response.xpath(
            '//input[@name="my_post_key"]/@value').extract_first()
        if not my_post_key:
            return

        self.logger.info("Found post_key")

        form_data = {
            'action': 'do_login',
            'url': '',
            'quick_login': '1',
            'my_post_key': my_post_key,
            'quick_username': USER,
            'quick_password': PASS,
            'quick_remember': 'yes',
            'submit': 'Login',
        }
        login_url = 'https://demonforums.net/member.php'
        yield FormRequest(
            url=login_url,
            formdata=form_data,
            callback=self.parse,
            headers=response.request.headers,
            meta=self.synchronize_meta(response),
            dont_filter=True,
        )

    def parse(self, response):

        self.synchronize_headers(response)

        if response.status == 403:
            yield from self.parse_captcha(response)
            return
        
        # Check if login failed
        self.check_if_logged_in(response)

        yield Request(
            url=self.base_url,
            callback=self.parse_start,
            headers=response.request.headers,
            meta=self.synchronize_meta(response),
            dont_filter=True
        )

    def parse_start(self, response):

        # Synchronize user agent for cloudfare middlewares
        self.synchronize_headers(response)

        # If captcha detected
        if response.status in [503, 403]:
            yield from self.parse_captcha(response)
            return

        # Load all forums
        all_forums = response.xpath(self.forum_xpath).extract()

        # update stats
        self.crawler.stats.set_value("mainlist/mainlist_count", len(all_forums))

        for forum_url in all_forums:
            # Standardize url
            if 'http://' not in forum_url and 'https://' not in forum_url:
                if self.base_url not in forum_url:
                    forum_url = self.base_url + forum_url

            yield Request(
                url=forum_url,
                headers=self.headers,
                callback=self.parse_forum,
                meta=self.synchronize_meta(response)
            )

    def parse_thread(self, response):

        self.synchronize_headers(response)

        if response.status == 403:
            meta = response.meta.copy()
            tries = meta.get('tries', 1)
            if tries < 20:
                meta['tries'] = tries + 1
                yield Request(
                    url=response.url,
                    callback=self.parse_forum,
                    headers=response.request.headers,
                    meta=self.synchronize_meta(response),
                    dont_filter=True
                )
                return

        yield from super().parse_thread(response)
        yield from super().parse_avatars(response)

class DemonForumsScrapper(SiteMapScrapper):

    spider_class = DemonForumsSpider
    site_name = 'demonforums.net'
    site_type = 'forum'
