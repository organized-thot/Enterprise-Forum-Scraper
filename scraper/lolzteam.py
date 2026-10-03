import re
import uuid
import os

import base64
from scrapy import Request
from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)


class LolzSpider(SitemapSpider):
    name = 'lolz_spider'

    # Url stuffs
    base_url = "https://lolz.guru/"

    # Xpath stuffs
    forum_xpath = '//li[@class="node category level_1"]//div[@class="nodeText"]//a[contains(@href, "forums/")]/@href'
    thread_xpath = '//div[@class="discussionListItem--Wrapper"]'
    thread_first_page_xpath = './/a[contains(@href,"threads/")]/@href'
    thread_last_page_xpath = './/nav/a[last()]/@href'
    thread_date_xpath = './/a[contains(@class,"dateTime lastPostInfo")]'\
                        '/abbr/@data-datestring|'\
                        './/a[contains(@class,"dateTime lastPostInfo")]/text()'
    pagination_xpath = '//nav//a[contains(@class, "currentPage")]/text()'
    thread_pagination_xpath = '//nav/a[@class="text"]/@href'
    thread_page_xpath = '//nav//a[contains(@class, "currentPage")]'\
                        '/text()'
    post_date_xpath = '//div[@class="privateControls"]' \
                      '//abbr[@class="DateTime"]/@data-time|'\
                      '//div[@class="privateControls"]' \
                      '//span[@class="DateTime"]/@title'

    avatar_xpath = '//div[@class="avatarHolder"]/a'
    forum_last_page_xpath = '//div[@class="PageNav"]/@data-last'

    # Regex stuffs
    topic_pattern = re.compile(
        r"threads/(\d+)",
        re.IGNORECASE
    )
    avatar_name_pattern = re.compile(
        r'.*/(\S+\.\w+)',
        re.IGNORECASE
    )

    # Other settings
    use_proxy = "On"
    sitemap_datetime_format = '%b %d, %Y'
    post_datetime_format = "%b %d, %Y at %I:%M %p"

    def get_forum_next_page(self, response):
        current_page = response.xpath(self.pagination_xpath).extract_first()
        last_page = response.xpath(self.forum_last_page_xpath).extract_first()
        if not last_page:
            return
        if int(current_page) == 1:
            next_page = response.url.rstrip('/') + '/page-2'
        elif int(current_page) < int(last_page):
            splitted_url = response.url.rsplit('/', 1)
            next_page = splitted_url[0] + '/' + splitted_url[1].replace(
                current_page, str(int(current_page) + 1))
        else:
            return
        if self.base_url not in next_page:
            next_page = self.base_url + next_page
        return next_page

    def get_thread_next_page(self, response):
        current_page = response.xpath(self.thread_page_xpath).extract_first()
        last_page = response.xpath(self.forum_last_page_xpath).extract_first()
        if not last_page:
            return

        if int(current_page) == 1:
            return
        splitted_url = response.url.rsplit('/', 1)
        next_page = splitted_url[0] + '/' + splitted_url[1].replace(
            current_page, str(int(current_page) - 1))
        if self.base_url not in next_page:
            next_page = self.base_url + next_page
        return next_page

    def start_requests(self):

        cookies, ip = self.get_cookies(
            base_url=self.base_url,
            proxy=self.use_proxy,
            fraud_check=False,
        )

        self.logger.info(f'COOKIES: {cookies}')

        # Init request kwargs and meta
        meta = {
            "cookiejar": uuid.uuid1().hex,
            "ip": ip
        }

        yield Request(
            url=self.base_url,
            headers=self.headers,
            meta=meta,
            cookies=cookies
        )

    def parse(self, response):

        # Synchronize user agent for cloudfare middleware
        self.synchronize_headers(response)

        # Load all forums
        all_forums = response.xpath(self.forum_xpath).extract()

        # update stats
        self.crawler.stats.set_value("mainlist/mainlist_count", len(all_forums))
        for forum_url in all_forums:

            # Standardize url
            if self.base_url not in forum_url:
                forum_url = self.base_url + forum_url
            # if 'forums/785' not in forum_url:
            #     continue
            yield Request(
                url=forum_url,
                headers=self.headers,
                meta=self.synchronize_meta(response),
                callback=self.parse_forum
            )

    def parse_thread(self, response):

        # Synchronize headers user agent with cloudfare middleware
        self.synchronize_headers(response)

        # Load topic_id
        topic_id = response.meta.get("topic_id")

        # Check current page to scrape from last page
        current_page = response.xpath(self.thread_page_xpath).extract_first()
        last_page = response.xpath(self.thread_last_page_xpath).extract_first()
        if current_page == "1":

            if not last_page:
                return

            if self.base_url not in last_page:
                last_page = self.base_url + last_page

            yield Request(
                url=last_page,
                headers=self.headers,
                callback=super().parse_thread,
                meta=self.synchronize_meta(
                    response,
                    default_meta={
                        "topic_id": topic_id
                    }
                )
            )
        # Save generic thread
        yield from super().parse_thread(response)

        # Save avatars
        yield from self.parse_avatars(response)

    def parse_avatars(self, response):

        # Synchronize headers user agent with cloudfare middleware
        self.synchronize_headers(response)

        # Save avatar content
        for avatar in response.xpath(self.avatar_xpath):
            avatar_url = avatar.xpath(
                'span[@style and @class]/@style').extract_first()
            if not avatar_url:
                continue
            avatar_url = re.findall(r'url\(\'(.*?)\'\)', avatar_url)
            if not avatar_url:
                continue
            if 'base64,' in avatar_url[0]:
                # Separate the metadata from the image data
                head, data = avatar_url[0].split('base64,', 1)

                # Decode the image data
                plain_data = base64.b64decode(data)

                # Load file name
                user_id = avatar.xpath('@href').re('members/(.*?)/')
                if not user_id:
                    continue
                file_name = os.path.join(
                    self.avatar_path,
                    f'{user_id[0]}.jpg'
                )
                if os.path.exists(file_name):
                    continue
                avatar_name = os.path.basename(file_name)

                # Save avatar
                with open(file_name, "wb") as f:
                    f.write(plain_data)
                    self.logger.info(
                        f"Avatar {avatar_name} done..!"
                    )

                self.crawler.stats.inc_value("mainlist/avatar_saved_count")
                continue

            if self.base_url not in avatar_url[0]:
                avatar_url = self.base_url + avatar_url[0]

            file_name = self.get_avatar_file(avatar_url)

            if file_name is None:
                continue

            if os.path.exists(file_name):
                continue

            yield Request(
                url=avatar_url,
                headers=self.headers,
                callback=self.parse_avatar,
                meta=self.synchronize_meta(
                    response,
                    default_meta={
                        "file_name": file_name
                    }
                ),
            )


class LolzScrapper(SiteMapScrapper):

    spider_class = LolzSpider
    site_name = 'lolzteam.net'
    site_type = 'forum'
