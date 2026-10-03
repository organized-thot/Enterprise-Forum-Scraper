import uuid
import asyncio
import aiohttp
import json
from random import choice

from scrapy import Selector


class IpHandler(object):

    ip_api = "http://api.ipify.org/?format=json"
    fraudulent_api = "https://scamalytics.com/ip/%s"

    def __init__(self, **kwargs):
        from scraper.base_scrapper import (
            VIP_PROXY_USERNAME,
            VIP_PROXY_PASSWORD,
            VIP_PROXY,
            UNBLOCKER_PROXY_USERNAME,
            UNBLOCKER_PROXY_PASSWORD,
            UNBLOCKER_PROXY,
            PROXY_USERNAME,
            PROXY_PASSWORD,
            PROXY
        )
        self.use_proxy = kwargs.get("use_proxy")
        self.logger = kwargs.get("logger")
        self.fraudulent_threshold = kwargs.get("fraudulent_threshold", 100)
        self.ip_batch_size = kwargs.get("ip_batch_size", 20)
        self.country = kwargs.get("proxy_countries")
        self.city = kwargs.get("proxy_cities")
        
        if self.use_proxy == 'VIP':
            self.proxy_username = VIP_PROXY_USERNAME
            self.proxy_password = VIP_PROXY_PASSWORD
            self.proxy = VIP_PROXY
        elif self.use_proxy == 'Unblocker':
            self.proxy_username = UNBLOCKER_PROXY_USERNAME
            self.proxy_password = UNBLOCKER_PROXY_PASSWORD
            self.proxy = UNBLOCKER_PROXY
        else:
            self.proxy_username = PROXY_USERNAME
            self.proxy_password = PROXY_PASSWORD
            self.proxy = PROXY

        if self.country:
            country = choice(self.country)
            self.proxy_username = "%s-country-%s" % (
                self.proxy_username,
                country
            )

            if self.city:
                city = choice(self.city)
                self.proxy_username = "%s-city-%s" % (
                    self.proxy_username,
                    city
                )

    async def fetch(self, url, **kwargs):

        # Load session
        session = aiohttp.ClientSession()

        # Load method
        method = kwargs.get("method")
        if method not in ["get", "post"]:
            method = "get"
        else:
            del kwargs["method"]

        # Load response
        if method == "get":
            response = await session.get(url, **kwargs)
        else:
            response = await session.post(url, **kwargs)

        # Load text response
        try:
            text = await response.text()
        except Exception as err:
            text = None

        # Close session
        await session.close()

        return response

    async def get_fraud_score(self, ip):
        
        try:
            # Load response
            response = await self.fetch(self.fraudulent_api % ip)

            # Load selector
            selector = Selector(text=await response.text())

            # Load score
            score = selector.xpath(
                "//div[@class=\"score\"]/text()"
            ).extract_first()
        except Exception as err:
            score = None

        if not score:
            return self.fraudulent_threshold

        # Standardize score
        score = int(score.split()[-1])

        return score

    async def get_ip_score(self, session_id):

        # Load proxy
        while True:
            try:
                username = "%s-session-%s" % (
                    self.proxy_username,
                    session_id
                )
                response = await self.fetch(
                    self.ip_api,
                    proxy=self.proxy % (
                        username,
                        self.proxy_password
                    )
                )
                break
            except Exception as err:
                session_id = uuid.uuid1().hex
                continue
        
        # Load ip
        try:
            ip = json.loads(await response.text()).get("ip")
            x_lum_ip = response.headers.get('x-luminati-ip', None)
        except:
            return '10.10.10.10', self.fraudulent_threshold + 1, None

        # Load score
        score = await self.get_fraud_score(ip)

        return ip, score, x_lum_ip

    def loop_good_ip(self):
        request_pool = []
        index = 0
        while index < self.ip_batch_size:
            index += 1
            session_id = uuid.uuid1().hex
            request_pool.append(
                self.get_ip_score(session_id)
            )

        # Load loop
        loop = asyncio.get_event_loop()

        # Load loop results
        results = loop.run_until_complete(
            asyncio.gather(*request_pool)
        )

        # Sort result
        results.sort(key=lambda x: x[1])

        return results[0]

    def get_good_ip(self):

        while True:
            ip, score, lum_ip = self.loop_good_ip()
            if score > self.fraudulent_threshold:
                self.logger.info(
                    "Ip %s has fraudulent score of %s, "
                    "above threshold %s, aborting." % (
                        ip, score, self.fraudulent_threshold
                    )
                )
                continue

            # Report good ip
            if lum_ip:
                self.logger.info(
                    "Find out good ip %s (%s) with fraudulent score of %s, "
                    "below threshold %s, continue." % (
                        ip, lum_ip, score, self.fraudulent_threshold
                    )
                )
                return lum_ip
            else:
                self.logger.info(
                    "Find out good ip %s with fraudulent score of %s, "
                    "below threshold %s, continue." % (
                        ip, score, self.fraudulent_threshold
                    )
                )
            return ip
