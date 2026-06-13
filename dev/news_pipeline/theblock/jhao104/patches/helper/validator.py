# -*- coding: utf-8 -*-
"""
Stage 2 overlay — replaces upstream/helper/validator.py.
Applied by setup.sh after clone (cp patches/helper/validator.py upstream/helper/).

Changes from stock validator.py:
  - httpTimeOutValidator:   decorator REMOVED → not in http_validator list
  - customValidatorExample: decorator REMOVED → not in http_validator list
  - httpsTimeOutValidator:  decorator REMOVED → http_validator list empty; httpsValidator()
                            returns True for all http-passers → they get https=True
                            (accurate: they tunnelled HTTPS to theblock) and no wasted
                            qq.com HEAD request per cycle
  - theblockValidator:      NEW, registered as sole @ProxyValidator.addHttpValidator
                            Uses curl_cffi impersonate="chrome" (correct browser JA3)
                            against theblock sitemap index — the CF-pass gate.
"""
__author__ = 'JHao'

import re
from requests import head
from curl_cffi import requests as cffi_requests
from util.six import withMetaclass
from util.singleton import Singleton
from handler.configHandler import ConfigHandler

conf = ConfigHandler()

HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:34.0) Gecko/20100101 Firefox/34.0',
          'Accept': '*/*',
          'Connection': 'keep-alive',
          'Accept-Language': 'zh-CN,zh;q=0.8'}

IP_REGEX = re.compile(r"(.*:.*@)?\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}")


class ProxyValidator(withMetaclass(Singleton)):
    pre_validator = []
    http_validator = []
    https_validator = []

    @classmethod
    def addPreValidator(cls, func):
        cls.pre_validator.append(func)
        return func

    @classmethod
    def addHttpValidator(cls, func):
        cls.http_validator.append(func)
        return func

    @classmethod
    def addHttpsValidator(cls, func):
        cls.https_validator.append(func)
        return func


@ProxyValidator.addPreValidator
def formatValidator(proxy):
    """检查代理格式"""
    return True if IP_REGEX.fullmatch(proxy) else False


# Decorator removed — not in http_validator list (theblockValidator is the sole gate)
def httpTimeOutValidator(proxy):
    """ http检测超时 (disabled: replaced by theblockValidator) """
    proxies = {"http": "http://{proxy}".format(proxy=proxy), "https": "https://{proxy}".format(proxy=proxy)}
    try:
        r = head(conf.httpUrl, headers=HEADER, proxies=proxies, timeout=conf.verifyTimeout)
        return True if r.status_code == 200 else False
    except Exception as e:
        return False


# Decorator removed — not in https_validator list; httpsValidator() returns True for all
# http-passers → they get https=True (accurate: they tunnelled HTTPS to theblock)
# and no wasted qq.com HEAD request per cycle
def httpsTimeOutValidator(proxy):
    """https检测超时 (disabled: https_validator list empty)"""
    proxies = {"http": "http://{proxy}".format(proxy=proxy), "https": "https://{proxy}".format(proxy=proxy)}
    try:
        r = head(conf.httpsUrl, headers=HEADER, proxies=proxies, timeout=conf.verifyTimeout, verify=False)
        return True if r.status_code == 200 else False
    except Exception as e:
        return False


# Decorator removed — not in http_validator list
def customValidatorExample(proxy):
    """自定义validator函数 (disabled: not in http_validator list)"""
    return True


@ProxyValidator.addHttpValidator
def theblockValidator(proxy):
    """CF-pass gate: curl_cffi chrome impersonation → theblock sitemap index.
    Pass: status 200 AND XML marker in first 500 bytes.
    One Session per call — safe across jhao104's 20 sync threads (no shared state).
    proxy scheme: http://host:port for both proxies keys (Stage-1 pool is http-only).
    """
    purl = "http://%s" % proxy
    try:
        s = cffi_requests.Session(impersonate="chrome")
        r = s.get(
            "https://www.theblock.co/sitemap_tbco_index.xml",
            proxies={"http": purl, "https": purl},
            timeout=15,
        )
        head_bytes = r.content[:500]
        return r.status_code == 200 and (
            b"<?xml" in head_bytes
            or b"<sitemapindex" in head_bytes
            or b"<urlset" in head_bytes
            or b"<sitemap>" in head_bytes
        )
    except Exception:
        return False
