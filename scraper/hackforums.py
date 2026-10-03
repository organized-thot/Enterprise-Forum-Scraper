import uuid
import re


from scrapy import (
    Request,
    FormRequest,
    Selector
)
from scraper.base_scrapper import (
    SitemapSpider,
    SiteMapScrapper
)

# USERNAME = "vrx9"
# PASSWORD = "Night#Hack001"
# USERNAME = "z234567890"
# PASSWORD = "KL5uyxBQ8cEz4mW"
USERNAME = "gamer418"
PASSWORD = "Nightlion#123"


class HackForumsSpider(SitemapSpider):
    name = "hackforums_spider"

    # Url stuffs
    base_url = "https://hackforums.net/"
    login_url = "https://hackforums.net/member.php?action=login"

    # Css stuffs
    login_form_css = 'form[action*="/member.php"]'

    # Xpath stuffs
    forum_xpath = "//a[contains(@href,\"forumdisplay.php\")]/@href"
    login_check_xpath = "//span[@class=\"welcome\"]/strong/a/text()[contains(.,\"%s\")]" % USERNAME
    ip_check_xpath = "//text()[contains(.,\"Your IP\")]"
    pagination_xpath = "//a[@class=\"pagination_next\"]/@href"

    thread_xpath = "//tr[@class=\"inline_row\"]"
    thread_first_page_xpath = ".//span[contains(@id,\"tid\")]/a/@href"
    thread_last_page_xpath = ".//span[@class=\"smalltext\" and contains(text(),\"Pages:\")]/a[last()]/@href"
    thread_date_xpath = ".//span[@class=\"lastpost smalltext\"]/text()[contains(.,\"-\")]|" \
                        ".//span[@class=\"lastpost smalltext\"]/span[@title]/@title"
    post_date_xpath = "//span[@class=\"post_date\"]/text()[contains(.,\"-\")]|" \
                      "//span[@class=\"post_date\"]/span/@title"
    avatar_xpath = "//div[@class=\"author_avatar\"]/a/img/@src"

    thread_page_xpath = "//span[@class=\"pagination_current\"]/text()"
    thread_pagination_xpath = "//a[@class=\"pagination_previous\"]/@href"
    hcaptcha_site_key_xpath = "//script[@data-sitekey]/@data-sitekey"

    login_failed_xpath = "//div[contains(., 'correct the following errors')] |" \
                    "//*[contains(., 'been suspended or you have been banned')]"

    # Regex stuffs
    topic_pattern = re.compile(
        r"tid=(\d+)",
        re.IGNORECASE
    )
    avatar_name_pattern = re.compile(
        r".*/(\S+\.\w+)",
        re.IGNORECASE
    )
    pagination_pattern = re.compile(
        r".*page=(\d+)",
        re.IGNORECASE
    )

    # Other settings
    sitemap_datetime_format = "%m-%d-%Y, %I:%M %p"
    post_datetime_format = "%m-%d-%Y, %I:%M %p"
    handle_httpstatus_list = [403, 503]
    get_cookies_delay = 60
    get_cookies_retry = 4
    fraudulent_threshold = 10

    use_proxy = "VIP"
    proxy_countries = ['us', 'uk']

    def parse_captcha(self, response):
        ip_ban_check = response.xpath(
            self.ip_check_xpath
        ).extract_first()

        # Init cookies, ip
        cookies, ip = None, None

        # Report bugs
        if "error code: 1005" in response.text:
            self.logger.info(
                "Ip for error 1005 code. Rotating."
            )
        elif ip_ban_check:
            self.logger.info(
                "%s has been permanently banned. Rotating." % ip_ban_check
            )
        else:
            cookies, ip = self.get_cloudflare_cookies(
                base_url=self.login_url,
                proxy=True,
                fraud_check=False
            )

        yield from self.pass_cloudflare(cookies=cookies, ip=ip)

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
        
        print(f'IP Address: {ip}')

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

    def get_cookies_extra(self, browser):
        # Handle login
        browser.execute_script(
            "document.querySelector(\"[name=username]\").value = \"%s\"" % USERNAME
        )
        browser.execute_script(
            "document.querySelector(\"[name=password]\").value = \"%s\"" % PASSWORD
        )
        browser.execute_script(
            "document.querySelector(\"form>div>[name=submit]\").click()"
        )

        # Check if login success
        return USERNAME.lower() in browser.page_source.lower()

    def solve_cookies_captcha(self, browser, proxy=None):
        # Init success
        success = True

        # Load selector
        selector = Selector(text=browser.page_source)

        # Check if ban ip
        if "blocking your access based on IP address" in browser.page_source:
            self.logger.info(
                "Get cookies rotated into banned ip, resetting."
            )
            success = False
            return browser, success

        # Check if captcha exist
        site_key = selector.xpath(self.hcaptcha_site_key_xpath).extract_first()
        if not site_key:
            self.logger.info(
                "Get cookies do not find captcha, return cookies."
            )
            return browser, success

        # Load captcha response
        captcha_response = self.solve_hcaptcha(
            selector, 
            proxy=proxy,
            site_url=browser.current_url
        )

        # Display captcha box
        browser.execute_script(
            "document.querySelector(\"[name=h-captcha-response]\").setAttribute(\"style\",\"display: block\")"
        )
        browser.execute_script(
            "document.querySelector(\"[name=g-recaptcha-response]\").setAttribute(\"style\",\"display: block\")"
        )

        # Input captcha response
        browser.execute_script(
            "document.querySelector(\"[name=h-captcha-response]\").innerText = \"%s\"" % captcha_response
        )
        browser.execute_script(
            "document.querySelector(\"[name=g-recaptcha-response]\").innerText = \"%s\"" % captcha_response
        )

        # Submit form
        browser.execute_script(
            "document.querySelector(\"#hcaptcha_submit\").click()"
        )

        return browser, success

    def check_bypass_success(self, browser):
        if ("blocking your access based on IP address" in browser.page_source or
                browser.find_elements_by_css_selector('.cf-error-details')):
            raise RuntimeError("HackForums.net is blocking your access based on IP address.")

        return bool(
            browser.find_elements_by_css_selector('form[action="member.php"]')
        )

    def parse_login(self, response):

        # Synchronize user agent for cloudfare middlewares
        self.synchronize_headers(response)

        if response.status in [503, 403]:
            yield from self.parse_captcha(response)
            return

        yield FormRequest.from_response(
            response,
            formcss=self.login_form_css,
            formdata={
                "username": USERNAME,
                "password": PASSWORD,
                "quick_gauth_code": "",
                "remember": "yes",
                "submit": "Login",
                "action": "do_login",
                "url": self.base_url
            },
            dont_filter=True,
            headers=self.headers,
            meta=self.synchronize_meta(response),
            callback=self.parse_start
        )

    def parse_start(self, response):

        # Synchronize user agent for cloudfare middlewares
        self.synchronize_headers(response)

        self.check_if_logged_in(response)

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
                callback=self.parse_forum,
                meta=self.synchronize_meta(response)
            )

    def parse_thread(self, response):

        # Parse generic thread
        yield from super().parse_thread(response)

        # Parse generic avatar
        yield from super().parse_avatars(response)


class HackForumsScrapper(SiteMapScrapper):

    spider_class = HackForumsSpider
    site_type = 'forum'

if __name__ == "__main__":
    pass
