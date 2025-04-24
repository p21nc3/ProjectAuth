import json
import argparse
from playwright.sync_api import sync_playwright


IDPS = {
    "APPLE": {
        "login_url": "https://appleid.apple.com",
        "cookie_urls": [
            "https://appleid.apple.com"
        ]
    },
    "FACEBOOK": {
        "login_url": "https://facebook.com",
        "cookie_urls": [
            "https://facebook.com"
        ]
    },
    "GOOGLE": {
        "login_url": "https://accounts.google.com",
        "cookie_urls": [
            "https://accounts.google.com"
        ]
    },
    "TWITTER_1.0": {
        "login_url": "https://twitter.com",
        "cookie_urls": [
            "https://twitter.com"
        ]
    },
    "LINKEDIN": {
        "login_url": "https://linkedin.com",
        "cookie_urls": [
            "https://linkedin.com"
        ]
    },
    "MICROSOFT": {
        "login_url": "https://login.live.com",
        "cookie_urls": [
            "https://login.live.com"
        ]
    },
    "BAIDU": {
        "login_url": "https://passport.baidu.com",
        "cookie_urls": [
            "https://passport.baidu.com"
        ]
    },
    "GITHUB": {
        "login_url": "https://github.com",
        "cookie_urls": [
            "https://github.com"
        ]
    },
    "QQ": {
        "login_url": "https://graph.qq.com",
        "cookie_urls": [
            "https://graph.qq.com"
        ]
    },
    "SINA_WEIBO": {
        "login_url": "https://weibo.com",
        "cookie_urls": [
            "https://weibo.com"
        ]
    },
    "WECHAT": {
        "login_url": "https://open.weixin.qq.com",
        "cookie_urls": [
            "https://open.weixin.qq.com"
        ]
    }
}


def main():
    parser = argparse.ArgumentParser(description="Generate idp cookie store")
    parser.add_argument("idp", type=str, choices=IDPS.keys(), help="idp name")
    args = parser.parse_args()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context()
        page = context.new_page()

        page.goto(IDPS[args.idp]["login_url"])
        _ = input("Submit idp credentials and press enter to continue")
        cookies = context.cookies(urls=IDPS[args.idp]["cookie_urls"])
        print(json.dumps(cookies))

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
