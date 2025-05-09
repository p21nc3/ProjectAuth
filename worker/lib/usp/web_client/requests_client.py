"""requests-based implementation of web client class."""

from http import HTTPStatus
from typing import Optional, Dict

import requests

from .abstract_client import (
    AbstractWebClient,
    AbstractWebClientResponse,
    AbstractWebClientSuccessResponse,
    WebClientErrorResponse,
    RETRYABLE_HTTP_STATUS_CODES,
)


class RequestsWebClientSuccessResponse(AbstractWebClientSuccessResponse):
    """
    requests-based successful response.
    """

    __slots__ = [
        '__requests_response',
        '__max_response_data_length',
    ]

    def __init__(self, requests_response: requests.Response, max_response_data_length: Optional[int] = None):
        self.__requests_response = requests_response
        self.__max_response_data_length = max_response_data_length

    def status_code(self) -> int:
        return int(self.__requests_response.status_code)

    def status_message(self) -> str:
        message = self.__requests_response.reason
        if not message:
            message = HTTPStatus(self.status_code(), None).phrase
        return message

    def header(self, case_insensitive_name: str) -> Optional[str]:
        return self.__requests_response.headers.get(case_insensitive_name.lower(), None)

    def raw_data(self) -> bytes:
        if self.__max_response_data_length:
            data = self.__requests_response.content[:self.__max_response_data_length]
        else:
            data = self.__requests_response.content

        return data


class RequestsWebClientErrorResponse(WebClientErrorResponse):
    """
    requests-based error response.
    """
    pass


class RequestsWebClient(AbstractWebClient):
    """requests-based web client to be used by the sitemap fetcher."""

    # https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers
    __USER_AGENT = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'

    __HTTP_REQUEST_TIMEOUT = 60
    """
    HTTP request timeout.

    Some webservers might be generating huge sitemaps on the fly, so this is why it's rather big.
    """

    __slots__ = [
        '__max_response_data_length',
        '__timeout',
        '__proxies',
    ]

    def __init__(self):
        self.__max_response_data_length = None
        self.__timeout = self.__HTTP_REQUEST_TIMEOUT
        self.__proxies = {}

    def set_timeout(self, timeout: int) -> None:
        """Set HTTP request timeout."""
        # Used mostly for testing
        self.__timeout = timeout

    def set_proxies(self, proxies: Dict[str, str]) -> None:
        """
        Set proxies from dictionnary where:

        * keys are schemes, e.g. "http" or "https";
        * values are "scheme://user:password@host:port/".

        For example:

            proxies = {'http': 'http://user:pass@10.10.1.10:3128/'}
        """
        # Used mostly for testing
        self.__proxies = proxies

    def set_max_response_data_length(self, max_response_data_length: int) -> None:
        self.__max_response_data_length = max_response_data_length

    def get(self, url: str) -> AbstractWebClientResponse:
        try:
            response = requests.get(
                url,
                timeout=self.__timeout,
                stream=True,
                headers={'User-Agent': self.__USER_AGENT},
                proxies=self.__proxies
            )
        except requests.exceptions.Timeout as ex:
            # Retryable timeouts
            return RequestsWebClientErrorResponse(message=str(ex), retryable=True)

        except requests.exceptions.RequestException as ex:
            # Other errors, e.g. redirect loops
            return RequestsWebClientErrorResponse(message=str(ex), retryable=False)

        else:

            if 200 <= response.status_code < 300:
                return RequestsWebClientSuccessResponse(
                    requests_response=response,
                    max_response_data_length=self.__max_response_data_length,
                )
            else:

                message = '{} {}'.format(response.status_code, response.reason)

                if response.status_code in RETRYABLE_HTTP_STATUS_CODES:
                    return RequestsWebClientErrorResponse(message=message, retryable=True)
                else:
                    return RequestsWebClientErrorResponse(message=message, retryable=False)
