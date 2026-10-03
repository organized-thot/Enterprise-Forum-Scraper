import re
import uuid
from datetime import datetime
from scrapy.http import Request
from scraper.base_scrapper import SitemapSpider, SiteMapScrapper


class BruteSpider(SitemapSpider):
    name = 'brute_spider'
    base_url = 'https://brute.pw'

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
    post_date_xpath = '//article//time[@data-time]/@data-time'

    avatar_xpath = '//div[@class="message-avatar-wrapper"]/a/img/@src'

    # Regex stuffs
    topic_pattern = re.compile(
        r"/threads/(\d+)",
        re.IGNORECASE
    )

    avatar_name_pattern = re.compile(
        r".*/(\S+\.\w+)",
        re.IGNORECASE
    )

    pagination_pattern = re.compile(
        r".*/page-(\d+)",
        re.IGNORECASE
    )

    # captcha stuffs
    ip_check_xpath = "//text()[contains(.,\"Your IP\")]"
    check_solved_xpath = '//h3[@class="node-title"]'

    # Recaptcha stuffs
    recaptcha_site_key_xpath = '//div[@data-xf-init="re-captcha"]/@data-sitekey'

    # Other settings
    use_proxy = "VIP"
    use_cloudflare_v2_bypass = True
    sitemap_datetime_format = "%Y-%m-%dT%H:%M:%S"
    post_datetime_format = "%Y-%m-%dT%H:%M:%S"

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
        )

    def parse_thread(self, response):

        # Parse generic thread
        yield from super().parse_thread(response)

        # Save avatars
        yield from super().parse_avatars(response)

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


class BruteScrapper(SiteMapScrapper):
    spider_class = BruteSpider
    site_name = 'brute.pw'
    site_type = 'forum'

    def load_settings(self):
        settings = super().load_settings()
        settings.update(
            {
                "RETRY_HTTP_CODES": [406, 429, 500, 503],
            }
        )
        return settings
