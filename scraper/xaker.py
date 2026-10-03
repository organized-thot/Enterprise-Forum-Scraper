import re
import uuid
from urllib.parse import urlencode
import dateparser
from scrapy import (
    Request,
    FormRequest
)
from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)

USER = "Cyrax011"
PASS = "4hr63yh38a61SDW0"


class XakerSpider(SitemapSpider):
    name = 'xaker_spider'

    # Url stuffs
    base_url = "https://xak.guru/"

    # Xpath stuffs
    forum_xpath = '//ol[@class="nodeList"]//h3/a/@href'
    thread_xpath = '//ol[@class="discussionListItems"]/li'
    thread_first_page_xpath = './/h3[@class="title"]'\
                              '/a[contains(@href,"threads/")]/@href'
    thread_last_page_xpath = './/span[@class="itemPageNav"]'\
                             '/a[last()]/@href'

    thread_date_xpath = './/abbr[contains(@class,"DateTime")]/@data-datestring|'\
                        './/dl[@class="lastPostInfo"]//span[@class="DateTime"]'\
                        '/@title'

    pagination_xpath = '//nav/a[last()]/@href'
    thread_pagination_xpath = '//nav/a[@class="text"]/@href'
    thread_page_xpath = '//nav//a[contains(@class, "currentPage")]'\
                        '/text()'
    post_date_xpath = '//div[contains(@class,"privateControls")]//span[@'\
                      'class="DateTime"]/@title|//div[@class="privateCon'\
                      'trols"]//abbr[@class="DateTime"]/@data-datestring|'\
                      '//div[contains(@class,"privateControls")]//span[@'\
                      'class="DateTime"]/text()'

    avatar_xpath = '//div[contains(@class,"avatarHolder")]//img/@src'

    # Login Failed Message
    login_failed_xpath = '//div[contains(@class, "errorPanel")]'

    # captcha stuffs
    ip_check_xpath = "//text()[contains(.,\"Your IP\")]"

    # Regex stuffs
    topic_pattern = re.compile(
        r"threads/(\d+).*",
        re.IGNORECASE
    )
    avatar_name_pattern = re.compile(
        r".*/(\d+\.\w+)",
        re.IGNORECASE
    )
    pagination_pattern = re.compile(
        r".*/page-(\d+)",
        re.IGNORECASE
    )

    # Recaptcha stuffs
    recaptcha_site_key_xpath = '//div[@data-xf-init="re-captcha"]/@data-sitekey'
    bypass_success_xpath = '//ol[@class="nodeList"]//h3/a'

    # Other settings
    use_proxy = "On"


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
            callback=self.parse_start
        )

    def parse_captcha(self, response):
        ip_ban_check = response.xpath(
            self.ip_check_xpath
        ).extract_first()

        # Init cookies, ip
        cookies, ip = None, None

        # Report bugs
        if "error code: 1005" in response.text:
            self.logger.info(
                "Ip for error 1005 code. Rotating."
            )
        elif ip_ban_check:
            self.logger.info(
                "%s has been permanently banned. Rotating." % ip_ban_check
            )
        else:
            cookies, ip = self.get_cloudflare_cookies(
                base_url=self.base_url,
                proxy=True,
                fraud_check=False
            )

        yield from self.start_requests(cookies=cookies, ip=ip)

    def parse_start(self, response):

        # Synchronize user agent for cloudfare middlewares
        self.synchronize_headers(response)

        # If captcha detected
        if response.status in [503, 403]:
            yield from self.parse_captcha(response)
            return

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
                callback=self.parse_forum,
                meta=self.synchronize_meta(response)
            )

    def parse_thread(self, response):

        # Save generic thread
        yield from super().parse_thread(response)

        # Save avatars
        yield from super().parse_avatars(response)


class XakerScrapper(SiteMapScrapper):

    spider_class = XakerSpider
    site_name = 'xaker.name'
    site_type = 'forum'

    def load_settings(self):
        spider_settings = super().load_settings()
        return spider_settings
