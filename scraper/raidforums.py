import os
import re
import sys
import uuid

from scrapy.http import Request

from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.190 Safari/537.36'


class RaidForumsSpider(SitemapSpider):
    name = 'raidforums_spider'

    # Url stuffs
    base_url = "https://raidforums.com/"

    # Regex stuffs
    pagination_pattern = re.compile(
        r'.*page=(\d+)',
        re.IGNORECASE
    )
    username_pattern = re.compile(
        r'User-(.*)',
        re.IGNORECASE
    )
    avatar_name_pattern = re.compile(
        r'.*/(\S+\.\w+)',
        re.IGNORECASE
    )

    # Xpath stuffs
    forum_sitemap_xpath = '//sitemap[loc[contains(text(),"sitemap-threads.xml")]]/loc/text()'
    thread_sitemap_xpath = '//url[loc[contains(text(),"/Thread-")] and lastmod]'
    thread_url_xpath = '//loc[not(contains(text(), "?page="))]/text()'
    thread_lastmod_xpath = "//lastmod/text()"

    forum_xpath = '//td[contains(@class,"trow")]/a[@class="forums__forum-name"]/@href'
    thread_xpath = '//table[contains(@class,"forum-display__thread-list")]/' \
                   'tr[td[contains(@class,"forumdisplay")] and ' \
                   'contains(@class,"forum-display__thread")]'
    thread_date_xpath = './/span[contains(@class,"smalltext")]/text()[contains(.,"at")]|' \
                        './/span[contains(@class,"smalltext")]/span[@title]/@title'
    thread_first_page_xpath = './/span[@class=" subject_new" and contains(@id,"tid")]/a/@href'
    thread_last_page_xpath = './/span[@class="smalltext"]/text()[contains(.,")")]/preceding-sibling::a[1]/@href'
    pagination_xpath = '//a[@class="pagination_next"]/@href'
    thread_pagination_xpath = '//section[@id="thread-navigation"]//a[@class="pagination_previous"]/@href'
    thread_page_xpath = '//span[@class="pagination_current"]/text()'
    post_date_xpath = '//span[@class="post_date"]/text()[contains(.,"at")]|' \
                      '//span[@class="post_date"]/span[@title]/@title'
    avatar_xpath = '//div[@class="post__user"]/a/img/@src'

    use_proxy = "VIP"
    use_cloudflare_v2_bypass = True

    # Other settings
    sitemap_datetime_format = "%B %d, %Y at %I:%M %p"
    post_datetime_format = "%B %d, %Y at %I:%M %p"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers.update(
            {
                "User-Agent": USER_AGENT
            }
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

        # Synchronize headers user agent with cloudfare middleware
        self.synchronize_headers(response)

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

    def parse_forum(self, response, thread_meta={}, is_first_page=True):

        # Parse generic forums
        if not self.useronly:
            yield from super().parse_forum(response, thread_meta={}, is_first_page=True)

        # Parse sub forums
        yield from self.parse(response)

        if '--getusers' not in sys.argv:
            return

        # Parse users
        users = response.xpath('//span[@class="author smalltext"]/a')
        for user in users:
            user_url = user.xpath('@href').extract_first()
            if self.base_url not in user_url:
                user_url = self.base_url + user_url
            user_id = self.username_pattern.findall(user_url)
            if not user_id:
                continue

            file_name = '{}/{}.html'.format(self.user_path, user_id[0])
            if os.path.exists(file_name):
                continue

            yield Request(
                url=user_url,
                headers=self.headers,
                callback=self.parse_user,
                meta={
                    'file_name': file_name,
                    'user_id': user_id[0]
                }
            )

    def parse_user(self, response):
        file_name = response.meta['file_name']
        with open(file_name, 'wb') as f:
            f.write(response.text.encode('utf-8'))
            print(f"User {response.meta['user_id']} done..!")
        user_history = response.xpath(
            '//span[text()="Username Changes:"]'
            '/following-sibling::a[1]'
        )
        if user_history:
            history_url = user_history.xpath('@href').extract_first()
            if self.base_url not in history_url:
                history_url = self.base_url + history_url
            yield Request(
                url=history_url,
                headers=self.headers,
                callback=self.parse_user_history,
                meta={'user_id': response.meta['user_id']}
            )

    def parse_user_history(self, response):
        user_id = response.meta['user_id']

        file_name = '{}/{}-history.html'.format(self.user_path, user_id)
        with open(file_name, 'wb') as f:
            f.write(response.text.encode('utf-8'))
            print(f"History for user {user_id} done..!")

    def parse_thread(self, response):

        # Parse generic thread
        yield from super().parse_thread(response)

        # Parse generic avatar
        yield from super().parse_avatars(response)

    # def set_users_path(self):
    #     self.user_path = os.path.join(
    #         self.output_path,
    #         'users'
    #     )
    #     if not os.path.exists(self.user_path):
    #         os.makedirs(self.user_path)

    def parse_avatars(self, response):

        # Synchronize headers user agent with cloudfare middleware
        self.synchronize_headers(response)

        # Save avatar content
        all_avatars = response.xpath(self.avatar_xpath).extract()
        for avatar_url in all_avatars:

            temp_url = avatar_url
            # Standardize avatar url
            if not avatar_url.lower().startswith("http"):
                temp_url = response.urljoin(avatar_url)

            avatar_url = temp_url

            if 'image/svg' in avatar_url:
                continue

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


class RaidForumsScrapper(SiteMapScrapper):
    spider_class = RaidForumsSpider
    site_name = 'raidforums.com'
    site_type = 'forum'

    def load_settings(self):
        settings = super().load_settings()
        settings.update(
            {
                "RETRY_HTTP_CODES": [403, 429, 500],
            }
        )
        return settings


if __name__ == '__main__':
    print("Success!")
