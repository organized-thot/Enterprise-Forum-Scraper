import re
import uuid

from datetime import (
    datetime,
    timedelta
)
from scrapy import (
    Request,
    FormRequest
)
from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)


class BreakinginSpider(SitemapSpider):
    name = "breakingin_spider"

    # Url stuffs
    base_url = "https://www.breakingin.to/"

    # Xpath stuffs
    forum_xpath = '//div[@id="ipsLayout_mainArea"]//h4[contains(@class, "ipsDataItem_title ipsType_large")]/a/@href'

    pagination_xpath = '//a[@class="pagination_next"]/@href'

    thread_xpath = '//div[@id="ipsLayout_mainArea"]//div[@class="ipsBox"]/ol/li[contains(@class, "ipsDataItem ipsDataItem_responsivePhoto")]'
    thread_first_page_xpath = './div[@class="ipsDataItem_main"]/h4//a/@href'
    thread_last_page_xpath = './div[@class="ipsDataItem_main"]/h4//span[contains(@class, "ipsPagination_mini")]/span[last()]/a/@href'
    thread_date_xpath = './ul[contains(@class, "ipsDataItem_lastPoster")]//time/@datetime'

    thread_pagination_xpath = '//ul[@class="ipsPagination"]//li[@class="ipsPagination_prev"]/a/@href'
    thread_page_xpath = '//ul[@class="ipsPagination"]/li[contains(@class, "ipsPagination_active")]/a/text()'
    post_date_xpath = '//div[@class="ipsType_reset"]//time/@datetime'

    avatar_xpath = '//div[@class="cAuthorPane_photo"]//img/@src'

    # Regex stuffs
    avatar_name_pattern = re.compile(
        r".*/(\S+\.\w+)",
        re.IGNORECASE
    )
    pagination_pattern = re.compile(
        r".*page/(\d+)",
        re.IGNORECASE
    )

    use_proxy = "On"

    # Other settings
    sitemap_datetime_format = "%Y-%m-%dT%H:%M:%S"
    post_datetime_format = "%Y-%m-%dT%H:%M:%S"

    def parse_thread_date(self, thread_date):
        """
        :param thread_date: str => thread date as string
        :return: datetime => thread date as datetime converted from string,
                            using class sitemap_datetime_format
        """

        return datetime.strptime(
            thread_date.strip()[:-1],
            self.sitemap_datetime_format
        )

    def parse_post_date(self, post_date):
        """
        :param post_date: str => post date as string
        :return: datetime => post date as datetime converted from string,
                            using class post_datetime_format
        """
        return datetime.strptime(
            post_date.strip()[:-1],
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
            callback=self.parse
        )

    def parse(self, response):

        # Synchronize user agent for cloudfare middleware
        self.synchronize_headers(response)

        # Load all forums
        all_forums = response.xpath(self.forum_xpath).extract()

        # update stats
        self.crawler.stats.set_value("mainlist/mainlist_count", len(all_forums))
        
        for forum_url in all_forums:
            # Standardize forum url
            if self.base_url not in forum_url:
                forum_url = response.urljoin(forum_url)

            yield Request(
                url=forum_url,
                headers=self.headers,
                meta=self.synchronize_meta(response),
                callback=self.parse_forum
            )

    def parse_forum(self, response):

        # Parse sub forums
        yield from self.parse(response)

        # Parse generic forum
        yield from super().parse_forum(response)

    def parse_thread(self, response):

        # Save generic thread
        yield from super().parse_thread(response)

        # Save avatars
        yield from super().parse_avatars(response)


class BreakinginScrapper(SiteMapScrapper):
    spider_class = BreakinginSpider
    site_type = 'forum'


if __name__ == "__main__":
    pass
