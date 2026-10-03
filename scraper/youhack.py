import re
import uuid
from datetime import datetime

import dateparser
from scrapy import (
    Request,
    FormRequest
)

from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)

LOGINS = [
    {"USER": "Firefly13", "PASS": "X$$-Fl71hf7jsos2"},
    {"USER": "blackchain", "PASS": "BlackX$$19P1781jh"},
    {"USER": "SilverData", "PASS": "NewX$$_P127ds7"}
]

class YouHackSpider(SitemapSpider):
    name = 'youhack_spider'
    

    base_url = "https://youhack.xyz/"
    change_language_url = f"{base_url}misc/language?language_id=1&redirect={base_url}"

    # Xpath stuffs
    captcha_form_css = "form[action]"
    forum_xpath = '//h3[@class="nodeTitle"]/a[contains(@href, "forums/")]/@href|' \
                  '//ol[@class="subForumList"]//h4[@class="nodeTitle"]/a/@href'
    thread_xpath = '//li[contains(@id, "thread-")]'
    thread_first_page_xpath = './/h3[@class="title"]' \
                              '/a[contains(@href,"threads/")]/@href'
    thread_last_page_xpath = './/span[@class="itemPageNav"]' \
                             '/a[last()]/@href'
    thread_date_xpath = './/dl[@class="lastPostInfo"]//*[@class="DateTime"]/@data-time|' \
                        './/dl[@class="lastPostInfo"]//*[@class="DateTime"]/@title|' \
                        './/dl[@class="lastPostInfo"]//a[@class="dateTime"]/*/@title|' \
                        './/dl[@class="lastPostInfo"]//a[@class="dateTime"]/*/text()'
    pagination_xpath = '//nav/a[last()]/@href'
    thread_pagination_xpath = '//nav/a[@class="text"]/@href'
    thread_page_xpath = '//nav//a[contains(@class, "currentPage")]' \
                        '/text()'
    post_date_xpath = '//div[@class="privateControls"]' \
                      '//abbr[@class="DateTime"]/@data-time|' \
                      '//div[@class="privateControls"]' \
                      '//span[@class="DateTime"]/@title'

    avatar_xpath = '//div[@class="avatarHolder"]/a/img/@src'

    recaptcha_site_key_xpath = '//div[@class="g-recaptcha"]/@data-sitekey'
    # Regex stuffs
    topic_pattern = re.compile(
        r"threads/(\d+)/",
        re.IGNORECASE
    )
    avatar_name_pattern = re.compile(
        r".*/(\w+\.\w+)",
        re.IGNORECASE
    )
    pagination_pattern = re.compile(
        r"page-(\d+)",
        re.IGNORECASE
    )

    # Other settings
    fraudulent_threshold = 10
    use_proxy = "On"
    sitemap_datetime_format = "%d.%m.%Y at %I:%M %p"
    post_datetime_format = "%d.%m.%Y at %I:%M %p"
    get_cookies_delay = 5
    get_cookies_retry = 1

    def start_requests(self):
       
        # cookies, ip = self.get_cookies(
        #     base_url=self.base_url,
        #     proxy=self.use_proxy,
        #     fraud_check=False,
        # )
       
        # self.logger.info(f'COOKIES: {cookies}')

  

        # Init request kwargs and meta
        meta = {
            "cookiejar": uuid.uuid1().hex,
           #  "ip": ip
        }

        yield Request(
            url=self.base_url,
            headers=self.headers,
            callback=self.parse_captcha,
            errback=self.check_site_error,
            dont_filter=True,
            # cookies=cookies,
            meta=meta
        )

    def parse_captcha(self, response):
        # Synchronize cloudfare user agent
        self.synchronize_headers(response)

        if response.xpath(self.recaptcha_site_key_xpath):
            formdata = {
                "g-recaptcha-response": self.solve_recaptcha(response).solution.token,
                "swp_sessionKey": response.xpath("//input[@name='swp_sessionKey']/@value").extract_first()
            }

            yield FormRequest.from_response(
                response,
                formcss=self.captcha_form_css,
                formdata=formdata,
                meta=self.synchronize_meta(response),
                dont_filter=True,
                headers=self.headers,
                callback=self.parse
            )
        else:
            yield Request(
                url=self.base_url,
                headers=self.headers,
                callback=self.set_language_to_english,
                meta=self.synchronize_meta(response),
                dont_filter=True,
            )

    def set_language_to_english(self, response):
        yield Request(
            url=self.change_language_url,
            headers=self.headers,
            errback=self.check_site_error,
            dont_filter=True,
            meta=self.synchronize_meta(response),
            callback=self.parse
        )

    def parse(self, response):
        # Synchronize user agent for cloudfare middleware
        self.synchronize_headers(response)

        if response.xpath(self.recaptcha_site_key_xpath):
            yield Request(
                url=self.base_url,
                headers=self.headers,
                callback=self.parse_captcha,
                meta={
                    "cookiejar": uuid.uuid1().hex
                },
                dont_filter=True,
            )

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

    def parse_thread_date(self, thread_date):
        if not thread_date:
            return
        try:
            return datetime.fromtimestamp(float(thread_date))
        except:
            return dateparser.parse(thread_date.strip(), [self.sitemap_datetime_format])

    def parse_post_date(self, post_date):
        if not post_date:
            return
        try:
            return datetime.fromtimestamp(float(post_date))
        except:
            return dateparser.parse(post_date.strip(), [self.post_datetime_format])


class YouHackScrapper(SiteMapScrapper):
    spider_class = YouHackSpider
    site_name = 'youhack.xyz'
    site_type = 'forum'

    def load_settings(self):
        settings = super().load_settings()
        settings.update(
            {
                "RETRY_HTTP_CODES": [403, 429, 500, 503],
            }
        )
        return settings
