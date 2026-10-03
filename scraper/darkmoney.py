import re
import uuid
from datetime import datetime

import dateparser
from scrapy import Request
from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)


class DarkMoneySpider(SitemapSpider):
    name = "darkmoney.pl"

    # Url stuffs
    base_url = "https://darkmoney.pl/"
    translate_to_eng_url = base_url + "?langid=1"

    # Xpath stuffs
    forum_xpath = '//tbody[contains(@id,"collapseobj_forum")]/tr/td[1]/div/a/@href'
    thread_xpath = '//tbody[contains(@id,"threadbits")]/tr'
    thread_first_page_xpath = './/td[contains(@id,"td_threadtitle")]//a[contains(@id, "thread_title")]/@href'
    thread_last_page_xpath = './/td[contains(@id,"td_threadtitle")]//span[contains(@class,"smallfont")]/a[last()]/@href'

    thread_date_xpath = './/span[@class="time"]/preceding-sibling::text()'

    pagination_xpath = '//a[@rel="next"]/@href'
    thread_pagination_xpath = '//a[@rel="prev"]/@href'
    thread_page_xpath = '//div[@class="pagenav"]//span/strong/text()'

    post_date_xpath = '//table[contains(@id, "post")]//td[@class="thead"][1]' \
                      '/a[contains(@name,"post")]' \
                      '/following-sibling::text()[1]'
    avatar_xpath = '//div[@id="posts"]//tr[@valign="top"]/td[1]//a[contains(@rel, "nofollow")]/img/@src'

    # Regex stuffs
    topic_pattern = re.compile(
        r".-(\d+).",
        re.IGNORECASE
    )
    avatar_name_pattern = re.compile(
        r".dateline=(\d+).",
        re.IGNORECASE
    )

    # Other settings
    use_proxy = "VIP"
    use_cloudflare_v2_bypass = True
    post_datetime_format = '%d-%m-%Y, %H:%M'
    sitemap_datetime_format = '%d-%m-%Y'

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

        yield Request(
            url=self.base_url,
            headers=self.headers,
            meta={
                "cookiejar": uuid.uuid1().hex,
                "ip": ip
            },
            cookies=cookies,
            errback=self.check_site_error,
            callback=self.change_language_to_english
        )

    def change_language_to_english(self, response):
        self.synchronize_headers(response)
        yield Request(
            url=self.translate_to_eng_url,
            headers=self.headers,
            meta=self.synchronize_meta(response),
            errback=self.check_site_error
        )

    def parse_thread(self, response):
        # Save generic thread
        yield from super().parse_thread(response)

        # Save avatars
        yield from self.parse_avatars(response)

    def check_bypass_success(self, browser):
        return bool(
            browser.current_url.startswith(self.base_url) and
            browser.find_elements_by_xpath(
                '//tbody[contains(@id,"collapseobj_forum")]/tr/td[1]/div/a'
            )
        )

    def parse_thread_date(self, thread_date):
        """
        :param thread_date: str => thread date as string
        :return: datetime => thread date as datetime converted from string,
                            using class sitemap_datetime_format
        """
        try:
            return datetime.strptime(
                thread_date.strip(),
                self.sitemap_datetime_format
            )
        except:
            return dateparser.parse(thread_date).replace(tzinfo=None)

    def get_topic_id(self, url=None):
        """
        :param url: str => thread url
        :return: str => extracted topic id from thread url
        """
        try:
            return self.topic_pattern.findall(url)[-1]
        except Exception as err:
            return

class DarkMoneyScrapper(SiteMapScrapper):
    spider_class = DarkMoneySpider
    site_name = 'darkmoney.pl'
    site_type = 'forum'

    def load_settings(self):
        settings = super().load_settings()
        settings.update(
            {
                "RETRY_HTTP_CODES": [500, 502, 503, 504, 522, 524, 406, 408, 429],
            }
        )
        return settings
