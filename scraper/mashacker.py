import re
import uuid
from scrapy.http import Request
from scraper.base_scrapper import SiteMapScrapper, SitemapSpider
import dateparser
from datetime import datetime


USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_2) '\
             'AppleWebKit/537.36 (KHTML, like Gecko) '\
             'Chrome/79.0.3945.117 Safari/537.36',


class MasHackerSpider(SitemapSpider):
    name = 'mashacker_spider'

    base_url = "http://www.mashacker.com/"

    # # Xpath stuffs
    forum_xpath = '//div[@class="datacontainer"]//h2[@class="forumtitle"]/a'\
                  '/@href|//li[@class="subforum"]/a/@href'

    thread_xpath = '//li[contains(@class,"threadbit")]'
    thread_first_page_xpath = './/h3[@class="threadtitle"]/a[@class="title"]/@href'
    thread_last_page_xpath = './/dl[contains(@class,"pagination")]//dd//span[last()]/a/@href'

    thread_date_xpath = './/div[contains(@class,"author")]//span/a[contains(@class,"username")][1]/@title' #split date later

    pagination_xpath = '//a[@rel="next"]/@href'
    thread_pagination_xpath = '//a[@rel="prev"]/@href'
    thread_page_xpath = '//span[@class="selected"]/a/@href'
    post_date_xpath = '//span[@class="date"]/text()'

    avatar_xpath = '//a[@class="postuseravatar"]/img/@src'

    topic_pattern = re.compile(r'showthread\.php/(\d+)-')
    avatar_name_pattern = re.compile(r'.*/(\S+\.\w+)')
    pagination_pattern = re.compile(r'.*/page(\d+)')

    # # Recaptcha stuffs
    bypass_success_xpath = '//div[@class="datacontainer"]'

    # # Other settings
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
            callback=self.parse
        )

    def parse_thread_date(self, thread_date):
        if thread_date:
            thread_date = thread_date.split('on')[-1]
            return dateparser.parse(thread_date)
        else:
            return datetime.datetime.now()

    def parse_thread(self, response):

        # Save generic thread
        yield from super().parse_thread(response)

        # Save avatars
        yield from super().parse_avatars(response)


class MasHackerScrapper(SiteMapScrapper):

    spider_class = MasHackerSpider
    site_name = 'mashacker.com'
    site_type = 'forum'
