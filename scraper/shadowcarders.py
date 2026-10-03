import os
import re
import scrapy
import uuid
import time

from scrapy.exceptions import CloseSpider
from datetime import datetime
import dateparser

from scrapy import (
    Request,
    FormRequest,
    Selector
)
from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)

# username = 'cyrax101'
USER = 'donotreplytothismailever@gmail.com'
PASS = 'nightlion123'

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36'


class ShadowCardersSpider(SitemapSpider):

    name = 'shadowcarders_spider'

    # Url stuffs
    base_url = "https://shadowcarders.com"
    login_url = "https://shadowcarders.com/login/login"

    # Css stuffs
    login_form_css = "//form[@id='login']"
    forum_xpath = "//a[contains(@href, 'Forum-')]/@href"

    # Xpath stuffs
    forum_xpath = '//ol[@class="nodeList"]//h3[@class="nodeTitle"]/a/@href'

    pagination_xpath = '//a[text()="Next >"]/@href'

    thread_xpath = '//li[contains(@id, "thread-")]'
    thread_first_page_xpath = './/h3[@class="title"]/a/@href'
    thread_last_page_xpath = './/span[@class="itemPageNav"]/a[last()]/@href'
    thread_date_xpath = './/dl[@class="lastPostInfo"]//a[@class="dateTime"]//abbr/@data-time|' \
                        './/dl[@class="lastPostInfo"]//a[@class="dateTime"]/span/@title'
    thread_page_xpath = '//nav/a[contains(@class,"currentPage")]/text()'
    thread_pagination_xpath = '//nav/a[contains(text()," Prev")]/@href'

    post_date_xpath = '//div[contains(@class, "messageInfo")]//abbr[@class="DateTime"]/@title|'\
                      '//div[contains(@class, "messageInfo")]//span[@class="DateTime"]/@title|'\
                      '//div[contains(@class, "messageInfo")]//abbr[@class="DateTime"]/text()'

    avatar_xpath = '//a[@data-avatarhtml="true"]/img/@src'

    # Login Failed Message
    login_failed_xpath = '//div[contains(@class, "errorPanel")]'
    
    # Regex stuffs
    topic_pattern = re.compile(
        r".(\d+)/",
        re.IGNORECASE
    )
    pagination_pattern = re.compile(
        r"page-(\d+)",
        re.IGNORECASE
    )

    # Other settings
    sitemap_datetime_format = "%b %d, %y"
    post_datetime_format = '%d %b %Y at %H:%M %p'

    # Regex stuffs
    avatar_name_pattern = re.compile(
        r".*/(\S+\.\w+)",
        re.IGNORECASE
    )

    # Other settings
    use_proxy = "On"
    handle_httpstatus_list = [403]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers = {
            "User-Agent": USER_AGENT
        }

    def get_avatar_file(self, url=None):
        if url is None:
            return
        if "image/svg" in url:
            return

        return super().get_avatar_file(url)

    def parse_thread_date(self, thread_date):
        """
        :param thread_date: str => thread date as string
        :return: datetime => thread date as datetime converted from string,
                            using class sitemap_datetime_format
        """

        if thread_date is None:
            return datetime.today()

        return dateparser.parse(thread_date)

    def parse_post_date(self, post_date):
        """
        :param post_date: str => post date as string
        :return: datetime => post date as datetime converted from string,
                            using class post_datetime_format
        """

        if post_date is None:
            return datetime.today()

        return dateparser.parse(post_date)
    
    def start_requests(self, **kwargs):

        cookies, ip = self.get_cloudflare_cookies(
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
            cookies=cookies,
            callback=self.parse_start
        )

    def get_cookies_extra(self, browser):
        def find_element(name):
            for element in browser.find_elements_by_name(name):
                if element.is_displayed():
                    return element
        try:
            browser.implicitly_wait(15)
            browser.find_element_by_xpath("//a[href='login/']").click()
            print("-"*100)
            find_element('login').send_keys(USER)
            password_field = find_element('password')
            password_field.send_keys(PASS)
            password_field.submit()
            # browser.find_element_by_xpath("//input[value='Log in']").click()
        except:
            return False

        # Check if login success
        print(browser.page_source.lower())
        return USER.lower() in browser.page_source.lower()

    def parse_start(self, response):

        # Synchronize user agent in cloudfare middleware
        self.synchronize_headers(response)

        # Check if login failed
        self.check_if_logged_in(response)

        # Load all forums
        all_forums = response.xpath(self.forum_xpath).extract()

        # update stats
        self.crawler.stats.set_value("mainlist/mainlist_count", len(all_forums))
        for forum in all_forums:

            if self.base_url not in forum:
                forum = self.base_url + '/' + forum

            yield Request(
                url=forum,
                headers=self.headers,
                callback=self.parse_forum,
                meta=self.synchronize_meta(response)
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

        # Parse main thread
        yield from super().parse_thread(response)

        # Parse avatar thread
        yield from super().parse_avatars(response)

        # Save user content
        users = response.xpath("//div[@class=\"postbitdetail\"]/span/a")
        for user in users:
            user_url = user.xpath("@href").extract_first()
            if self.base_url not in user_url:
                user_url = self.base_url + user_url
            user_name = user.xpath("span/text()").extract_first()
            if not user_name:
                user_name = user.xpath("text()").extract_first()
            if not user_name:
                user_name = user.xpath("font/text()").extract_first()
            file_name = '{}/{}.html'.format(self.user_path, user_name)
            if os.path.exists(file_name):
                continue
            yield Request(
                url=user_url,
                headers=self.headers,
                callback=self.parse_user,
                meta=self.synchronize_meta(
                    response,
                    default_meta={
                        "file_name": file_name,
                        "user_name": user_name,
                    }
                )
            )

    def parse_user(self, response):
        # Synchronize headers
        self.synchronize_headers(response)

        # Save user contents
        file_name = response.meta.get("file_name")
        user_name = response.meta.get("user_name")
        with open(file_name, 'wb') as f:
            f.write(response.text.encode('utf-8'))
            self.logger.info(
                f"User {user_name} done..!"
            )

        user_history = response.xpath(
            "//div[@class=\"usernamehistory\"]/a"
        )

        # Parse user history
        if user_history:
            history_url = user_history.xpath("@href").extract_first()

            if self.base_url not in history_url:
                history_url = self.base_url + history_url

            yield Request(
                url=history_url,
                headers=self.headers,
                callback=self.parse_user_history,
                meta=self.synchronize_meta(
                    response,
                    default_meta={
                        "user_name": user_name,
                    }
                )
            )

    def parse_user_history(self, response):
        user_name = response.meta['user_name']
        file_name = '{}/{}-history.html'.format(self.user_path, user_name)
        with open(file_name, 'wb') as f:
            f.write(response.text.encode('utf-8'))
            self.logger.info(
                f"History for user {user_name} done..!"
            )

    def check_bypass_success(self, browser):
        return bool(browser.find_elements_by_xpath('//form[@id="login"]'))


class ShadowCardersScrapper(SiteMapScrapper):

    spider_class = ShadowCardersSpider
    site_name = 'shadowcarders.com'
    site_type = 'forum'

    def load_settings(self):
        settings = super().load_settings()
        settings.update(
            {
                "USER_AGENT": USER_AGENT
            }
        )
        return settings

