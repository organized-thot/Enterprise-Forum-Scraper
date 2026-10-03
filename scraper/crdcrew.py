import re
import uuid

from datetime import datetime
from scrapy.http import Request, FormRequest

from scraper.base_scrapper import SiteMapScrapper, SitemapSpider

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36'
MIN_DELAY = 1
MAX_DELAY = 3

USER = 'nightlion123'
PASS = 'NightLion123'


class CrdcrewSpider(SitemapSpider):
    name = 'crdcrew_cc_spider'

    # Url stuffs
    base_url = "https://crdcrew.cc"
    forum_url = "https://crdcrew.cc/"
    login_url = "https://crdcrew.cc/login/login"

    # Xpaths
    forum_xpath = '//h3[@class="node-title"]/a/@href|' \
                  '//a[contains(@class,"subNodeLink--forum")]/@href'
    thread_xpath = '//div[contains(@class, "structItem structItem--thread")]'
    thread_first_page_xpath = './/div[@class="structItem-title"]' \
                              '/a[contains(@href,"threads/")]/@href'
    thread_last_page_xpath = './/span[@class="structItem-pageJump"]' \
                             '/a[last()]/@href'
    thread_date_xpath = './/time[contains(@class, "structItem-latestDate")]' \
                        '/@data-time'
    pagination_xpath = '//a[contains(@class,"pageNav-jump--next")]/@href'
    thread_pagination_xpath = '//a[contains(@class, "pageNav-jump--prev")]' \
                              '/@href'
    thread_page_xpath = '//li[contains(@class, "pageNav-page--current")]' \
                        '/a/text()'
    post_date_xpath = '//ul[contains(@class, "message-attribution-main")]' \
                      '//time[@data-time]/@data-time'

    avatar_xpath = '//div[@class="message-avatar-wrapper"]/a/img/@src'

    # Recaptcha stuffs
    recaptcha_site_key_xpath = '//div[@data-xf-init="re-captcha"]/@data-sitekey'

    use_proxy = 'VIP'

    # Regex stuffs
    topic_pattern = re.compile(
        r"(?<=\.)\d*?(?=\/)",
        re.IGNORECASE
    )
    avatar_name_pattern = re.compile(
        r".*/(\S+\.\w+)",
        re.IGNORECASE
    )
    # Other settings
    sitemap_datetime_format = "%Y-%m-%dT%H:%M:%S"
    post_datetime_format = "%Y-%m-%dT%H:%M:%S"
    use_cloudflare_v2_bypass = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Encoding": "gzip, deflate"
            }
        )

    def start_requests(self):
        # Temporary action to start spider
        yield Request(
            url=self.temp_url,
            headers=self.headers,
            callback=self.pass_cloudflare
        )

    def pass_cloudflare(self, cookies=None, ip=None):
        # Load cookies and ip
        cookies, ip = self.get_cloudflare_cookies(
            base_url=self.login_url,
            proxy=True,
            fraud_check=False
        )

        if "cf_clearance" not in cookies:
            yield Request(
                url=self.temp_url,
                headers=self.headers,
                callback=self.pass_cloudflare
            )

        # Init request kwargs and meta
        meta = {
            "cookiejar": uuid.uuid1().hex,
            "ip": ip
        }
        request_kwargs = {
            "url": self.login_url,
            "headers": self.headers,
            "callback": self.proceed_for_login,
            "dont_filter": True,
            "cookies": cookies,
            "meta": meta
        }

        yield Request(**request_kwargs)

    def proceed_for_login(self, response):
        # Synchronize user agent for cloudfare middleware
        self.synchronize_headers(response)

        # captcha_response = self.solve_recaptcha(response, proxyless=True).solution.token

        # Exact token
        token = response.xpath(
            '//input[@name="_xfToken"]/@value').extract_first()
        params = {
            'login': USER,
            'password': PASS,
            "remember": '1',
            '_xfRedirect': self.base_url,
            '_xfToken': token,
            # 'g-recaptcha-response': captcha_response
        }

        yield FormRequest(
            url=self.login_url,
            callback=self.parse,
            formdata=params,
            headers=self.headers,
            dont_filter=True,
            meta=self.synchronize_meta(response),
        )

    def parse_thread_date(self, thread_date):
        """
        :param thread_date: str => thread date as string
        :return: datetime => thread date as datetime converted from string,
                            using class sitemap_datetime_format
        """
        try:
            return datetime.fromtimestamp(float(thread_date))
        except:
            return datetime.strptime(
                thread_date.strip(),
                self.sitemap_datetime_format
            )

    def parse_post_date(self, post_date):
        """
        :param post_date: str => post date as string
        :return: datetime => post date as datetime converted from string,
                            using class post_datetime_format
        """
        try:
            return datetime.fromtimestamp(float(post_date))
        except:
            return datetime.strptime(
                post_date.strip(),
                self.post_datetime_format
            )

    def parse_thread(self, response):
        # Parse generic thread
        yield from super().parse_thread(response)
        # Save avatars
        yield from super().parse_avatars(response)


class CrdcrewScrapper(SiteMapScrapper):
    spider_class = CrdcrewSpider
    site_name = 'crdcrew.cc'
    site_type = 'forum'

    def load_settings(self):
        settings = super().load_settings()
        settings.update(
            {
                "RETRY_HTTP_CODES": [403, 406, 429, 500, 503],
                "AUTOTHROTTLE_ENABLED": True,
                "AUTOTHROTTLE_START_DELAY": MIN_DELAY,
                "AUTOTHROTTLE_MAX_DELAY": MAX_DELAY
            }
        )
        return settings
