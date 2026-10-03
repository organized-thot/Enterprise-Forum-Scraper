import time
import requests
import os
import json
import re
import uuid
from math import ceil
from copy import deepcopy
from urllib.parse import urlencode
import configparser
from scrapy.http import Request, FormRequest
from lxml.html import fromstring
from scrapy.crawler import CrawlerProcess

from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)

COOKIE = '__cfduid=dbdbeb0650da2e413f0f58b9b2c75eaf31565924481; xf_csrf=d03E_EFzdgY4WiWB; _ga=GA1.2.842163880.1565924490; _gid=GA1.2.1604312718.1565924490; cf_clearance=0592abbd070214348a2b168ab06759a20ea72575-1565924535-57600-150; xf_notice_dismiss=-1; xf_user=36079%2CIJmPwBbq9nBCBxAi2D2Txt-o0diiv1HZ6UURwi3L; xf_session=W_zYfW5H5uFGhT5Ui2cghdEH8Lyh_xwy; _gat_gtag_UA_139732498_1=1'
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36'


class WwhClubSpider(SitemapSpider):
    name = 'wwhclub_spider'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_url = "https://wwh-club.net"
        self.topic_pattern = re.compile(r'threads/.*\.(\d+)/')
        self.avatar_name_pattern = re.compile(r'.*/(\S+\.\w+)')
        self.pagination_pattern = re.compile(r'.*page-(\d+)')
        self.start_url = 'https://wwh-club.net/index.php'
        self.headers = {
            'user-agent': USER_AGENT,
            # 'cookie': COOKIE,
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1'
        }
        self.use_proxy = 'On'

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
            meta={"cookiejar": uuid.uuid1().hex,
                  "ip": ip},
            cookies=cookies,
            dont_filter=True,
            callback=self.parse
        )

    def parse(self, response):
        forums = response.xpath(
            '//h3[@class="node-title"]/a')
        sub_forums = response.xpath(
            '//ol[@class="node-subNodeFlatList"]/li/a')
        forums.extend(sub_forums)
        for forum in forums:
            url = forum.xpath('@href').extract_first()
            if self.base_url not in url:
                url = self.base_url + url
            # if 'poisk-investicij.93' not in url:
            #     continue
            yield Request(
                url=url,
                headers=self.headers,
                callback=self.parse_forum,
                dont_filter=True
            )

    def parse_forum(self, response):
        print('next_page_url: {}'.format(response.url))
        threads = response.xpath(
            '//a[@data-preview-url]')
        for thread in threads:
            thread_url = thread.xpath('@href').extract_first()
            if self.base_url not in thread_url:
                thread_url = self.base_url + thread_url
            topic_id = self.topic_pattern.findall(thread_url)
            if not topic_id:
                continue
            file_name = '{}/{}-1.html'.format(self.output_path, topic_id[0])
            if os.path.exists(file_name):
                continue
            yield Request(
                url=thread_url,
                headers=self.headers,
                callback=self.parse_thread,
                meta={'topic_id': topic_id[0]},
                dont_filter=True
            )

        next_page = response.xpath(
            '//a[@class="pageNav-jump pageNav-jump--next"]')
        if next_page:
            next_page_url = next_page.xpath('@href').extract_first()
            if self.base_url not in next_page_url:
                next_page_url = self.base_url + next_page_url
            yield Request(
                url=next_page_url,
                headers=self.headers,
                callback=self.parse_forum,
                dont_filter=True
            )

    def parse_thread(self, response):
        topic_id = response.meta['topic_id']
        pagination = self.pagination_pattern.findall(response.url)
        paginated_value = pagination[0] if pagination else 1
        file_name = '{}/{}-{}.html'.format(
            self.output_path, topic_id, paginated_value)
        with open(file_name, 'wb') as f:
            f.write(response.text.encode('utf-8'))
            print(f'{topic_id}-{paginated_value} done..!')

        avatars = response.xpath(
            '//div[@class="message-avatar-wrapper"]/a/img')
        for avatar in avatars:
            avatar_url = avatar.xpath('@src').extract_first()
            if not avatar_url:
                continue
            if not avatar_url.startswith('http'):
                avatar_url = self.base_url + avatar_url
            match = self.avatar_name_pattern.findall(avatar_url)
            if not match:
                continue
            file_name = '{}/{}'.format(self.avatar_path, match[0])
            if os.path.exists(file_name):
                continue
            yield Request(
                url=avatar_url,
                headers=self.headers,
                callback=self.parse_avatar,
                meta={
                    'file_name': file_name,
                },
                dont_filter=True
            )

        next_page = response.xpath(
            '//a[@class="pageNav-jump pageNav-jump--next"]')
        if next_page:
            next_page_url = next_page.xpath('@href').extract_first()
            if self.base_url not in next_page_url:
                next_page_url = self.base_url + next_page_url
            yield Request(
                url=next_page_url,
                headers=self.headers,
                callback=self.parse_thread,
                meta={'topic_id': topic_id},
                dont_filter=True
            )

    def parse_avatar(self, response):
        file_name = response.meta['file_name']
        file_name_only = file_name.rsplit('/', 1)[-1]
        with open(file_name, 'wb') as f:
            f.write(response.body)
            print(f"Avatar {file_name_only} done..!")

class WwhClubScrapper(SiteMapScrapper):
    spider_class = WwhClubSpider
    site_type = 'forum'


if __name__ == "__main__":
    pass