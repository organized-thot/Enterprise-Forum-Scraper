import re
import uuid
import dateparser

from scrapy.http import Request, FormRequest
from datetime import datetime, timedelta
from scraper.base_scrapper import SitemapSpider, SiteMapScrapper

USER = 'ajanlar123'
PASS = 'Ajanlar123!'

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36'


class AjanlarSpider(SitemapSpider):
    name = 'ajanlar_spider'
    base_url = "http://ajanlar.org/"

    login_url = "http://ajanlar.org/member.php?action=login"

    # Xpaths
    login_form_xpath = "//form[@action='member.php']"
    forum_xpath = '//tbody//a[contains(@href, "Forum-")]/@href'
    pagination_xpath = '//div[@class="pagination"]' \
                       '/a[@class="pagination_next"]/@href'
    thread_xpath = '//tr[@class="inline_row"]'
    thread_first_page_xpath = './/span[contains(@id,"tid_")]/a/@href'
    thread_last_page_xpath = './/td[contains(@class,"forumdisplay_")]/div' \
                             '/span/span[contains(@class,"smalltext")]' \
                             '/a[last()]/@href'
    thread_date_xpath = './/td[contains(@class,"forumdisplay")]//span[@class="lastpost smalltext"]/text()[1]' \
                        '|.//td[contains(@class,"forumdisplay")]//span[@class="lastpost smalltext"]/span/@title'
    thread_pagination_xpath = '//div[@class="pagination"]' \
                              '//a[@class="pagination_previous"]/@href'
    thread_page_xpath = '//span[@class="pagination_current"]/text()'
    post_date_xpath = '//span[@class="post_date"]/text()[1]'

    avatar_xpath = '//div[@class="author_avatar"]/a/img/@src'
    post_key_xpath = '//input[@name="my_post_key"]/@value'

    sitemap_datetime_format = "%d.%m.%Y, %H:%M"
    post_datetime_format = "%d.%m.%Y, %H:%M"

    # Login Failed Message
    login_failed_xpath = '//div[contains(@class, "blockMessage blockMessage--error")]'

    # Regex stuffs
    avatar_name_pattern = re.compile(
        r".*/(\S+\.\w+)",
        re.IGNORECASE
    )
    pagination_pattern = re.compile(
        r".*page=(\d+)",
        re.IGNORECASE
    )

    # Login Failed Message
    login_failed_xpath = '//div[@class="error"]'

    # captcha stuffs
    bypass_success_xpath = '//a[@class="guestnav" and text()="Login"]'

    # Other settings
    use_proxy = "VIP"
    use_cloudflare_v2_bypass = True
    handle_httpstatus_list = [403, 404]
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
            callback=self.parse_login
        )

    def parse_login(self, response):
        # Synchronize user agent in cloudfare middleware
        self.synchronize_headers(response)

        my_post_key = response.xpath(self.post_key_xpath).extract_first()

        yield FormRequest.from_response(
            response,
            formxpath=self.login_form_xpath,
            formdata={
                'action': 'do_login',
                'url': f'{self.base_url}index.php',
                'my_post_key': my_post_key,
                'remember': 'yes',
                'username': USER,
                'password': PASS
            },
            headers=self.headers,
            dont_filter=True,
            meta=self.synchronize_meta(response)
        )

    def parse_thread_date(self, thread_date):
        """
        :param thread_date: str => thread date as string
        :return: datetime => thread date as datetime converted from string,
                            using class sitemap_datetime_format
        """
        thread_date = thread_date.replace("Saat:", "").strip()

        try:
            return datetime.strptime(
                thread_date.strip(),
                self.post_datetime_format
            )
        except:
            return dateparser.parse(thread_date).replace(tzinfo=None)

    def parse_post_date(self, post_date):
        """
        :param post_date: str => post date as string
        :return: datetime => post date as datetime converted from string,
                            using class post_datetime_format
        """
        post_date = post_date.replace("Saat:", "").strip()

        try:
            return datetime.strptime(
                post_date.strip(),
                self.post_datetime_format
            )
        except:
            return dateparser.parse(post_date).replace(tzinfo=None)

    def parse_thread(self, response):
        self.synchronize_headers(response)

        yield from super().parse_thread(response)
        yield from super().parse_avatars(response)


class AjanlarScrapper(SiteMapScrapper):
    spider_class = AjanlarSpider
    site_name = 'ajanlar.org'
    site_type = 'forum'

    def load_settings(self):
        settings = super().load_settings()
        settings.update(
            {
                "RETRY_HTTP_CODES": [403, 406, 408, 410, 429, 500, 502, 503, 504, 522, 524],
                'CLOSESPIDER_ERRORCOUNT': 1
            }
        )
        return settings
