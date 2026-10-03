import re
import uuid
from datetime import datetime

from scrapy import (
    Request,
    FormRequest
)
from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)

USERNAME = "Cyrax_011"
PASSWORD = "Night#India065"
MAX_TRY_TO_LOG_IN_COUNT = 3


class SkyNetZoneSpider(SitemapSpider):

    name = 'skynetzone_spider'

    # Url stuffs
    base_url = 'https://skynetzone.pw'
    login_url = f'{base_url}/login/login'

    # Xpath stuffs
    login_form_xpath = "//form[@action='/login/login']"

    forum_xpath = '//h3[@class="node-title"]/a/@href|'\
                  '//a[contains(@class,"subNodeLink--forum")]/@href'
    thread_xpath = '//div[contains(@class, "structItem structItem--thread")]'
    thread_first_page_xpath = './/div[@class="structItem-title"]'\
                              '/a[contains(@href,"threads/")]/@href'
    thread_last_page_xpath = './/span[@class="structItem-pageJump"]'\
                             '/a[last()]/@href'
    thread_date_xpath = './/time[contains(@class, "structItem-latestDate")]'\
                        '/@data-time'
    pagination_xpath = '//a[contains(@class,"pageNav-jump--next")]/@href'
    thread_pagination_xpath = '//a[contains(@class, "pageNav-jump--prev")]'\
                              '/@href'
    thread_page_xpath = '//li[contains(@class, "pageNav-page--current")]'\
                        '/a/text()'
    post_date_xpath = '//div/a/time[@data-time]/@data-time'

    avatar_xpath = '//div[@class="message-avatar-wrapper"]/a/img/@src'

    # Login Failed Message
    login_failed_xpath = '//div[contains(@class, "blockMessage blockMessage--error")]'
    
    # Recaptcha stuffs
    recaptcha_site_key_xpath = '//div[@data-sitekey]/@data-sitekey'

    # Regex stuffs
    topic_pattern = re.compile(r'threads/.*\.(\d+)/', re.IGNORECASE)
    avatar_name_pattern = re.compile(r".*/(\S+\.\w+)", re.IGNORECASE)
    pagination_pattern = re.compile(r'.*page-(\d+)', re.IGNORECASE)

    # Other settings
    use_proxy = "VIP"
    use_cloudflare_v2_bypass = True
    download_delay = 0.3
    download_thread = 10

    def start_requests(self):
        self._try_to_log_in_count = 0
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
            "ip": ip,
            "cf_cookies": cookies
        }

        yield Request(
            url=self.login_url,
            dont_filter=True,
            headers=self.headers,
            callback=self.parse_login,
            meta=meta,
            cookies=cookies
        )

    def parse_login(self, response):
        self._try_to_log_in_count += 1

        self.synchronize_headers(response)

        # Solve reCAPTCHA
        solved_captcha = self.solve_recaptcha(response, proxyless=True)
        self.logger.debug(f'reCAPTCHA token: {solved_captcha.solution.token}')

        formdata = {
            'login': USERNAME,
            'password': PASSWORD,
            'g-recaptcha-response': solved_captcha.solution.token
        }

        meta = self.synchronize_meta(response)
        meta['solved_captcha'] = solved_captcha

        yield FormRequest.from_response(
            response,
            formxpath=self.login_form_xpath,
            formdata=formdata,
            dont_click=True,
            dont_filter=True,
            headers=self.headers,
            cookies=response.meta.get('cf_cookies'),
            callback=self.check_if_logged_in,
            meta=meta
        )

    def check_if_logged_in(self, response):
        solved_captcha = response.meta['solved_captcha']
        # check if logged in successfully
        if response.xpath(self.forum_xpath):
            # report a good CAPTCHA
            solved_captcha.report_good()
            # start forum scraping
            yield from super().parse(response)
            return

        err_msg = response.css('div.blockMessage--error::text').get()
        if err_msg:
            if 'CAPTCHA' in err_msg:
                # report a bad CAPTCHA
                solved_captcha.report_bad()

            if self._try_to_log_in_count >= MAX_TRY_TO_LOG_IN_COUNT:
                self.logger.error('Unable to log in! Exceeded maximum try count!')
                return

            yield from self.parse_login(response)
        else:
            self.logger.error('Unable to log in to the forum!')

    def parse_thread(self, response):

        # Parse generic thread
        yield from super().parse_thread(response)

        # Parse generic avatar
        yield from super().parse_avatars(response)

    def parse_thread_date(self, thread_date):
        """
        :param thread_date: str => thread date as string
        :return: datetime => thread date as datetime converted from string,
                            using class sitemap_datetime_format
        """
        try:
            return datetime.fromtimestamp(float(thread_date))
        except Exception:
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
        except Exception:
            return datetime.strptime(
                post_date.strip(),
                self.post_datetime_format
            )


class SkyNetZoneScrapper(SiteMapScrapper):

    spider_class = SkyNetZoneSpider
    site_name = 'skynetzone.pw'
    site_type = 'forum'

    def load_settings(self):
        settings = super().load_settings()
        settings.update({
            'RETRY_HTTP_CODES': [406, 408, 429, 500, 502, 503, 504, 522, 524],
        })
        return settings
