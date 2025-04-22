import logging
import uuid
from typing import List
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, Error, TimeoutError, Page
from modules.browser.browser import PlaywrightBrowser, PlaywrightHelper
from modules.helper.tmp import TmpHelper
from modules.helper.url import URLHelper


logger = logging.getLogger(__name__)


class Paths:


    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result

        self.browser_config = config["browser_config"]
        self.paths = config["login_page_config"]["paths_strategy_config"]["paths"]
        self.subdomains = config["login_page_config"]["paths_strategy_config"]["subdomains"]
        self.login_page_url_regexes = config["login_page_config"]["login_page_url_regexes"]

        self.resolved_url = urlparse(result["resolved"]["url"])
        self.base_scheme = self.resolved_url.scheme
        self.base_domain = self.resolved_url.netloc


    def start(self):
        logger.info(f"Starting paths login page detection for: {self.base_domain}")

        base_urls = [f"{self.base_scheme}://{self.base_domain}"]
        base_urls.extend([
            f"{self.base_scheme}://{subdomain}.{URLHelper.get_tld(self.base_domain)}" \
            for subdomain in self.subdomains
        ])

        with TmpHelper.tmp_dir() as pdir, sync_playwright() as pw:
            context, page = PlaywrightBrowser.instance(pw, self.browser_config, pdir)
            try:
                for base_url in base_urls:
                    lpc = self.check_base_url_for_paths(page, base_url, self.paths)
                    if lpc:
                        priority = URLHelper.prio_of_url(lpc, self.login_page_url_regexes)
                        self.result["login_page_candidates"].append({
                            "login_page_candidate": URLHelper.normalize(lpc),
                            "login_page_strategy": "PATHS",
                            "login_page_priority": priority
                        })
                        break # stop after first successful path
                PlaywrightHelper.close_context(context)
            except TimeoutError as e:
                logger.warning(f"Timeout while checking paths: {self.base_domain}")
                logger.debug(e)
            except Error as e:
                logger.warning(f"Error while checking paths: {self.base_domain}")
                logger.debug(e)


    def check_base_url_for_paths(self, page: Page, base_url: str, paths: List[str]) -> None|str:
        randpath_url = f"{base_url}/{uuid.uuid4()}"
        logger.info(f"Checking random path on '{base_url}' for 200 status code: {randpath_url}")

        try:
            r = page.goto(randpath_url)
            s = r.status if r else None
            if not s or s == 200:
                logger.info(f"Random path on '{base_url}' returned status code {s} (paths strategy not suitable): {randpath_url}")
                return
            else:
                logger.info(f"Random path on '{base_url}' returned status code {s} (paths strategy suitable): {randpath_url}")
        except TimeoutError as e:
            logger.info(f"Timeout while checking random path on '{base_url}': {randpath_url}")
            logger.debug(e)
            return
        except Error as e:
            logger.info(f"Error while checking random path on '{base_url}': {randpath_url}")
            logger.debug(e)
            return

        for path in paths:
            try:
                r = page.goto(f"{base_url}{path}")
                s = r.status if r else None
                if s and s == 200:
                    logger.info(f"Path on '{base_url}' returned status code {s}: {path} -> {r.url}")
                    return f"{base_url}{path}" # stop after first successful path
                else:
                    logger.info(f"Path on '{base_url}' returned status code {s}: {path}")
            except TimeoutError as e:
                logger.info(f"Timeout while checking path: {base_url}{path}")
                logger.debug(e)
            except Error as e:
                logger.info(f"Error while checking path: {base_url}{path}")
                logger.debug(e)
