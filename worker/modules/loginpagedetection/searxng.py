import os
import logging
import requests
from urllib.parse import quote
from modules.helper.url import URLHelper


logger = logging.getLogger(__name__)


class Searxng:


    SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://searxng:8080")


    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result

        self.search_engines = config["login_page_config"]["metasearch_strategy_config"]["search_engines"]
        self.search_term = config["login_page_config"]["metasearch_strategy_config"]["search_term"]
        self.search_results_number = config["login_page_config"]["metasearch_strategy_config"]["search_results_number"]
        self.login_page_url_regexes = config["login_page_config"]["login_page_url_regexes"]

        self.resolved_url = result["resolved"]["url"]
        self.resolved_domain = result["resolved"]["domain"]
        self.resolved_tld = URLHelper.get_tld(self.resolved_domain)


    def start(self):
        logger.info(f"Starting searxng login page detection for: {self.resolved_tld}")

        # https://docs.searxng.org/dev/search_api.html
        search_url = "{0}?q={1}&engines={2}&safesearch=0&format=json".format(
            self.SEARXNG_URL,
            quote(self.search_term.replace("%s", self.resolved_tld)),
            ",".join(reversed([e.strip().lower() for e in self.search_engines]))
        )

        # query multiple searxng pages until we have at least search_results_number results
        page_no = 1
        hit_ctr = 0
        searxng_candidates = []
        while len(searxng_candidates) < self.search_results_number:

            # store previous result count to check if new page returns any new results
            prev_res_count = len(searxng_candidates)

            # query searxng page
            try:
                search_url_paged = f"{search_url}&pageno={page_no}"
                logger.info(f"Requesting searxng results on page #{page_no}: {search_url_paged}")
                r = requests.get(search_url_paged, headers={"Accept": "application/json"})
                if r.status_code != 200:
                    logger.info(f"Invalid status code while requesting searxng results: {r.status_code}")
                    break # stop search
                rjson = r.json()
                results = rjson["results"]
                unresponsive_engines = rjson["unresponsive_engines"]
            except requests.exceptions.RequestException as c:
                logger.info(f"Error while requesting searxng results")
                logger.debug(c)
                break # stop search

            # number of results on this page
            logger.info(f"Received #{len(results)} results from searxng on page #{page_no}")

            # check for unresponsive engines
            if unresponsive_engines:
                logger.info(f"Following search engines are unresponsive: {unresponsive_engines}")

            # filter and prioritize searxng candidates
            for i, r in enumerate(results):
                hit_ctr += 1 # count hits across all pages

                # check if search result url is on same tld as resolved url
                if not URLHelper.is_same_tld(self.resolved_url, r["url"]):
                    logger.info(f"Search result url {i+1} of {len(results)} is on different tld")
                    continue

                # avoid duplicate search result urls
                if any(c["login_page_candidate"] == r["url"] for c in searxng_candidates):
                    logger.info(f"Search result url {i+1} of {len(results)} is duplicate")
                    continue

                # consider search result url of any priority because we searched with "login" keyword
                priority = URLHelper.prio_of_url(r["url"], self.login_page_url_regexes)

                # store search result url as login page candidate
                searxng_candidates.append({
                    "login_page_candidate": URLHelper.normalize(r["url"]),
                    "login_page_strategy": "METASEARCH",
                    "login_page_priority": priority,
                    "login_page_info": {
                        "result_hit": hit_ctr,
                        "result_engines": [e.upper() for e in r["engines"]],
                        "result_raw": r
                    }
                })

            # break if we have enough results
            if len(searxng_candidates) >= self.search_results_number:
                logger.info(f"Searxng found {len(searxng_candidates)} of min. {self.search_results_number} results, stopping search")
                break

            # break if this page does not return any results
            if not len(results):
                logger.info(f"Searxng did not find any results on page #{page_no}, stopping search")
                break

            # break if this page does not return any new results (i.e., duplicates, different tlds, ...)
            if prev_res_count == len(searxng_candidates):
                logger.info(f"Searxng did not find any new results on page #{page_no}, stopping search")
                break

            # next iteration queries next page
            page_no += 1

        # do not sort searxng candidates by priority (we rely on the searxng ordering)

        # store searxng candidates in result
        for i, c in enumerate(searxng_candidates):
            if i < self.search_results_number: self.result["login_page_candidates"].append(c)
            # else: self.result["additional_login_page_candidates"].append(c)
