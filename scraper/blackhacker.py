import re
import os
import uuid
import hashlib

from datetime import datetime, timedelta

from scrapy import (
    Request,
    FormRequest,
    Selector
)
from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)

USER='gordon418'
PASS='Nightlion#123'

class BlackHackerSpider(SitemapSpider):

    name = "blackhacker"

    # Url stuffs
    base_url = "https://blackhacker.pw/"
    login_url = "https://blackhacker.pw/member.php?action=login"
    # Xpath stuffs

    # Forum xpath #
    login_form_css = 'form[action*="login.php?do=login"]'
    forum_xpath = '//a[contains(@href, "forumdisplay.php?")]/@href'
    thread_xpath = '//tr[td[contains(@id, "td_threadtitle_")]]'
    thread_first_page_xpath = './/td[contains(@id, "td_threadtitle_")]/div'\
                              '/a[contains(@href, "showthread.php?")]/@href'
    thread_last_page_xpath = './/td[contains(@id, "td_threadtitle_")]/div/span'\
                             '/a[contains(@href, "showthread.php?")]'\
                             '[last()]/@href'
    thread_date_xpath = './/span[@class="time"]/preceding-sibling::text()'

    pagination_xpath = '//a[@rel="next"]/@href'
    thread_pagination_xpath = '//a[@rel="prev"]/@href'
    thread_page_xpath = '//div[@class="pagenav"]//span/strong/text()'
    post_date_xpath = '//table[contains(@id, "post")]//td[@class="thead"][1]'\
                      '/a[contains(@name,"post")]'\
                      '/following-sibling::text()[1]'
    avatar_xpath = '//a[contains(@href, "member.php?") and img/@src]'

    login_failed_xpath = '//div[contains(., "Вы ввели неправильное имя или пароль")]'

    # Regex stuffs
    topic_pattern = re.compile(
        r"t=(\d+)",
        re.IGNORECASE
    )
    avatar_name_pattern = re.compile(
        r"u=(\d+)",
        re.IGNORECASE
    )

    # Other settings
    use_proxy = "On"
    cloudfare_delay = 10
    handle_httpstatus_list = [503]
    post_datetime_format = '%d.%m.%Y, %H:%M'
    sitemap_datetime_format = '%d.%m.%Y'

    def start_requests(self):
        # Temporary action to start spider
        yield Request(
            url=self.temp_url,
            headers=self.headers,
            callback=self.pass_cloudflare
        )

    def pass_cloudflare(self, cookies=None, ip=None):
        # Load cookies and ip
        cookies, ip = self.get_cloudflare_cookies(
            base_url=self.login_url,
            proxy=True,
            fraud_check=False
        )
        
        if "cf_clearance" not in cookies:
            yield Request(
                url=self.temp_url,
                headers=self.headers,
                callback=self.pass_cloudflare
            )

        # Init request kwargs and meta
        meta = {
            "cookiejar": uuid.uuid1().hex,
            "ip": ip
        }
        request_kwargs = {
            "url": self.base_url,
            "headers": self.headers,
            "callback": self.parse_login,
            "dont_filter": True,
            "cookies": cookies,
            "meta": meta
        }

        yield Request(**request_kwargs)

    def parse_login(self, response):
        self.synchronize_headers(response)

        md5_pass = hashlib.md5(PASS.encode('utf-8')).hexdigest()
        security_token = response.xpath(
            '//input[@name="securitytoken"]/@value').extract_first()

        formdata = {
            "vb_login_username": USER,
            "vb_login_password": "",
            "vb_login_md5password": md5_pass,
            "vb_login_md5password_utf": md5_pass,
            "cookieuser": '1',
            "url": "/member.php?action=login",
            "do": "login",
            "securitytoken": security_token,
            "s": ''
        }

        yield FormRequest.from_response(
            response,
            formcss=self.login_form_css,
            formdata=formdata,
            dont_filter=True,
            headers=self.headers,
            meta=self.synchronize_meta(response),
            callback=self.parse_start
        )

    def parse_thread_date(self, thread_date):
        """
        :param thread_date: str => thread date as string
        :return: datetime => thread date as datetime converted from string,
                            using class sitemap_datetime_format
        """
        # Standardize thread_date
        thread_date = thread_date.strip()
        if "днес" in thread_date.lower():
            return datetime.today()
        elif "вчера" in thread_date.lower():
            return datetime.today() - timedelta(days=1)
        else:
            return datetime.strptime(
                thread_date,
                self.sitemap_datetime_format
            )

    def parse_post_date(self, post_date):
        """
        :param post_date: str => post date as string
        :return: datetime => post date as datetime converted from string,
                            using class sitemap_datetime_format
        """
        # Standardize thread_date
        post_date = post_date.strip()
        if not post_date:
            return

        if "днес" in post_date.lower():
            return datetime.today()
        elif "вчера" in post_date.lower():
            return datetime.today() - timedelta(days=1)
        else:
            return datetime.strptime(
                post_date,
                self.post_datetime_format
            )

    def parse_start(self, response):
        self.synchronize_headers(response)

        self.check_if_logged_in(response)

        yield Request(
            url=self.base_url,
            headers=self.headers,
            callback=self.parse,
            meta=self.synchronize_meta(response)
        )

    def parse(self, response):
        # Synchronize cloudfare user agent
        self.synchronize_headers(response)

        self.check_if_logged_in(response)

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
                callback=self.parse_forum,
                meta=self.synchronize_meta(response)
            )

    def parse_thread(self, response):

        # Save generic thread
        yield from super().parse_thread(response)

        # Save avatars
        yield from self.parse_avatars(response)

    def parse_avatars(self, response):

        # Synchronize headers user agent with cloudfare middleware
        self.synchronize_headers(response)

        # Save avatar content
        for avatar in response.xpath(self.avatar_xpath):
            avatar_url = avatar.xpath('img/@src').extract_first()

            # Standardize avatar url
            if not avatar_url.lower().startswith("http"):
                avatar_url = self.base_url + avatar_url

            if 'image/svg' in avatar_url:
                continue

            user_url = avatar.xpath('@href').extract_first()
            match = self.avatar_name_pattern.findall(user_url)
            if not match:
                continue

            file_name = os.path.join(
                self.avatar_path,
                f'{match[0]}.jpg'
            )

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

    def check_bypass_success(self, browser):
        return bool(
            browser.current_url.startswith(self.base_url) and
            browser.find_elements_by_xpath(
                '//input[@id="navbar_username"]'
            )
        )


class BlackHackerScrapper(SiteMapScrapper):

    spider_class = BlackHackerSpider
    site_name = 'blackhacker.ru'
    site_type = 'forum'
