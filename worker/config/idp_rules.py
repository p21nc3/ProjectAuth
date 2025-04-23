IdpRules = {
    "APPLE": {
        "keywords": ["apple"],
        "logos": "apple/",
        "login_request_rule": {
            "domain": "^appleid\\.apple\\.com$",
            "path": "^/auth/authorize",
            "params": [
                {
                    "name": "^client_id$",
                    "value": ".*"
                }
            ]
        },
        "passive_login_request_rule": {},
        "sdks": {
            "SIGN_IN_WITH_APPLE": {
                "login_request_rule": {
                    "domain": "^appleid\\.apple\\.com$",
                    "path": "^/auth/authorize",
                    "params": [
                        {
                            "name": "^client_id$",
                            "value": ".*"
                        },
                        {
                            "name": "^frame_id$",
                            "value": ".*"
                        }
                    ]
                }
            },
            "CUSTOM": {
                "login_request_rule": {
                    "domain": ".*",
                    "path": ".*",
                    "params": []
                }
            }
        }
    },
    "FACEBOOK": {
        "keywords": ["facebook"],
        "logos": "facebook/",
        "login_request_rule": {
            "domain": "facebook\\.com$",
            "path": "/dialog/oauth",
            "params": [
                {
                    "name": "^(client_id|app_id)$",
                    "value": ".*"
                }
            ]
        },
        "passive_login_request_rule": {},
        "sdks": {
            "FACEBOOK_LOGIN": {
                "login_request_rule": {
                    "domain": "facebook\\.com$",
                    "path": "/dialog/oauth",
                    "params": [
                        {
                            "name": "^app_id$",
                            "value": ".*"
                        },
                        {
                            "name": "^channel_url$",
                            "value": "^https://staticxx\\.facebook\\.com/x/connect/xd_arbiter/"
                        }
                    ]
                }
            },
            "CUSTOM": {
                "login_request_rule": {
                    "domain": ".*",
                    "path": ".*",
                    "params": []
                }
            }
        }
    },
    "GOOGLE": {
        "keywords": ["google", "gmail", "gplus"],
        "logos": "google/",
        "login_request_rule": {
            "domain": "^accounts\\.google\\.com$",
            "path": "^(?!.*/iframerpc).*(/auth/authorize|/gsi/select|/oauth2)",
            "params": [
                {
                    "name": "^client_id$",
                    "value": ".*"
                }
            ]
        },
        "passive_login_request_rule": {
            "domain": "^accounts\\.google\\.com$",
            "path": "^(/gsi/status|/gsi/iframe/select)",
            "params": [
                {
                    "name": "^client_id$",
                    "value": ".*"
                }
            ]
        },
        "login_response_rule": {
            "domain": ".*",
            "path": ".*",
            "params": [
                {
                    "name": "^(code|access\_token|id\_token|credential)$",
                    "value": "^(4\/|ya29|ey)"
                }
            ]
        },
        "login_response_originator_rule": {
            "domain": "^accounts\\.google\\.com$",
            "path": ".*",
            "params": []
        },
        "login_attempt_leak_rule": {
            "domain": "^accounts\\.google\\.com$",
            "path": "^(/gsi/status|/gsi/iframe/select)$",
            "params": [
                {
                    "name": "^client_id$",
                    "value": ".*"
                }
            ]
        },
        "token_exchange_leak_rule": {
            "domain": "^accounts\\.google\\.com$",
            "path": "^/gsi/issue$",
            "params": [
                {
                    "name": "^client_id$",
                    "value": ".*"
                }
            ]
        },
        "sdks": {
            "SIGN_IN_WITH_GOOGLE": {
                "login_request_rule": {
                    "domain": "^accounts\\.google\\.com$",
                    "path": "^/gsi/select",
                    "params": [
                        {
                            "name": "^client_id$",
                            "value": ".*"
                        }
                    ]
                }
            },
            "GOOGLE_ONE_TAP": {
                "login_request_rule": {
                    "domain": "^accounts\\.google\\.com$",
                    "path": "^(/gsi/status|/gsi/iframe/select)",
                    "params": [
                        {
                            "name": "^client_id$",
                            "value": ".*"
                        }
                    ]
                }
            },
            "GOOGLE_SIGN_IN_DEPRECATED": {
                "login_request_rule": {
                    "domain": "^accounts\\.google\\.com$",
                    "path": "^/o/oauth2",
                    "params": [
                        {
                            "name": "^client_id$",
                            "value": ".*"
                        },
                        {
                            "name": "^redirect_uri$",
                            "value": "^storagerelay://"
                        }
                    ]
                }
            },
            "CUSTOM": {
                "login_request_rule": {
                    "domain": ".*",
                    "path": ".*",
                    "params": []
                }
            }
        }
    },
    "TWITTER_1.0": {
        "keywords": ["twitter"],
        "logos": "twitter/",
        "login_request_rule": {
            "domain": "^(api\\.twitter\\.com|twitter\\.com)$",
            "path": "/oauth",
            "params": [
                {
                    "name": "^(oauth_token|client_id)$",
                    "value": ".*"
                }
            ]
        },
        "passive_login_request_rule": {},
        "sdks": {
            "CUSTOM": {
                "login_request_rule": {
                    "domain": ".*",
                    "path": ".*",
                    "params": []
                }
            }
        }
    },
    "MICROSOFT": {
        "keywords": ["microsoft", "xbox", "azure"],
        "logos": "microsoft/",
        "login_request_rule": {
            "domain": "^(login\\.live\\.com|login\\.microsoftonline\\.com)$",
            "path": "/oauth",
            "params": [
                {
                    "name": "^client_id$",
                    "value": ".*"
                }
            ]
        },
        "passive_login_request_rule": {},
        "sdks": {
            "CUSTOM": {
                "login_request_rule": {
                    "domain": ".*",
                    "path": ".*",
                    "params": []
                }
            }
        }
    },
    "LINKEDIN": {
        "keywords": ["linkedin"],
        "logos": "linkedin/",
        "login_request_rule": {
            "domain": "^www\\.linkedin\\.com$",
            "path": "/oauth",
            "params": [
                {
                    "name": "^client_id$",
                    "value": ".*"
                }
            ]
        },
        "passive_login_request_rule": {},
        "sdks": {
            "CUSTOM": {
                "login_request_rule": {
                    "domain": ".*",
                    "path": ".*",
                    "params": []
                }
            }
        }
    },
    "BAIDU": {
        "keywords": ["baidu"],
        "logos": "baidu/",
        "login_request_rule": {
            "domain": "^openapi\\.baidu\\.com$",
            "path": "/oauth",
            "params": [
                {
                    "name": "^client_id$",
                    "value": ".*"
                }
            ]
        },
        "passive_login_request_rule": {},
        "sdks": {
            "CUSTOM": {
                "login_request_rule": {
                    "domain": ".*",
                    "path": ".*",
                    "params": []
                }
            }
        }
    },
    "GITHUB": {
        "keywords": ["github"],
        "logos": "github/",
        "login_request_rule": {
            "domain": "^github\\.com$",
            "path": "(/oauth|/login)",
            "params": [
                {
                    "name": "^client_id$",
                    "value": ".*"
                }
            ]
        },
        "passive_login_request_rule": {},
        "sdks": {
            "CUSTOM": {
                "login_request_rule": {
                    "domain": ".*",
                    "path": ".*",
                    "params": []
                }
            }
        }
    },
    "QQ": {
        "keywords": ["qq"],
        "logos": "qq/",
        "login_request_rule": {
            "domain": "^graph\\.qq\\.com$",
            "path": "/oauth",
            "params": [
                {
                    "name": "^client_id$",
                    "value": ".*"
                }
            ]
        },
        "passive_login_request_rule": {},
        "sdks": {
            "CUSTOM": {
                "login_request_rule": {
                    "domain": ".*",
                    "path": ".*",
                    "params": []
                }
            }
        }
    },
    "SINA_WEIBO": {
        "keywords": ["weibo", "sina"],
        "logos": "sina_weibo/",
        "login_request_rule": {
            "domain": "^api\\.weibo\\.com$",
            "path": "/oauth",
            "params": [
                {
                    "name": "^client_id$",
                    "value": ".*"
                }
            ]
        },
        "passive_login_request_rule": {},
        "sdks": {
            "CUSTOM": {
                "login_request_rule": {
                    "domain": ".*",
                    "path": ".*",
                    "params": []
                }
            }
        }
    },
    "WECHAT": {
        "keywords": ["wechat", "weixin"],
        "logos": "wechat/",
        "login_request_rule": {
            "domain": "^open\\.weixin\\.qq\\.com$",
            "path": "/connect/qrconnect",
            "params": [
                {
                    "name": "^appid$",
                    "value": ".*"
                }
            ]
        },
        "passive_login_request_rule": {},
        "sdks": {
            "CUSTOM": {
                "login_request_rule": {
                    "domain": ".*",
                    "path": ".*",
                    "params": []
                }
            }
        }
    },
    "PASSKEY": {
        "keywords": ["passkey", "webauthn", "passwordless", "sign in with a passkey", "use passkey"],
        "logos": "passkey/",
        "login_request_rule": {
            "domain": ".*",
            "path": ".*",
            "params": [
                {
                    "name": "^webauthn$",
                    "value": ".*"
                }
            ]
        },
        "passive_login_request_rule": {
            "domain": ".*",
            "path": ".*",
            "params": []
        },
        "sdks": {
            "WEBAUTHN": {
                "login_request_rule": {
                    "domain": "^webauthn\\..*",
                    "path": "^/authenticate",
                    "params": []
                }
            },
            "CUSTOM": {
                "login_request_rule": {
                    "domain": ".*",
                    "path": ".*",
                    "params": []
                }
            }
        }
    },
    "MFA_GENERIC": {
        "keywords": ["two-factor", "2fa", "mfa", "multi-factor", "verification code", "one-time code", "authenticator", "totp"],
        "logos": "mfa/",
        "login_request_rule": {
            "domain": ".*",
            "path": ".*(2fa|mfa|totp|authenticate|verification|verify).*",
            "params": [
                {
                    "name": "^(code|otp|token)$",
                    "value": ".*"
                }
            ]
        },
        "passive_login_request_rule": {
            "domain": ".*",
            "path": ".*",
            "params": []
        },
        "mfa_step": {
            "selectors": [".otp-input", "#verificationCode", "input[name='code']", "input[name='otp']", "input[name='token']"]
        },
        "sdks": {
            "CUSTOM": {
                "login_request_rule": {
                    "domain": ".*",
                    "path": ".*",
                    "params": []
                }
            }
        }
    },
    "PASSWORD_BASED": {
        "keywords": ["login", "sign in", "username", "password", "email", "account"],
        "logos": "password/",
        "login_request_rule": {
            "domain": ".*",
            "path": ".*(login|signin|auth).*",
            "params": [
                {
                    "name": "^(username|email|password)$",
                    "value": ".*"
                }
            ]
        },
        "passive_login_request_rule": {
            "domain": ".*",
            "path": ".*",
            "params": []
        },
        "form_rule": {
            "fields": {
                "username": ["email", "user", "login", "username"],
                "password": ["pass", "pwd", "password"]
            }
        },
        "sdks": {
            "CUSTOM": {
                "login_request_rule": {
                    "domain": ".*",
                    "path": ".*",
                    "params": []
                }
            }
        }
    }
}
