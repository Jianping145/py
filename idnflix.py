# -*- coding: utf-8 -*-
# IDNFLIX Spider v7.8 - 蜂蜜影视
# 播放优先改写为 vidlink.pro（蜂蜜嗅探可播）
import re
import json
import requests
import urllib3
from urllib.parse import urlparse, urljoin, quote, unquote
from bs4 import BeautifulSoup

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Spider(BaseSpider):
    def init(self, extend=""):
        self.site = "https://idnflix.com"
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        )
        self.site_headers = {
            "User-Agent": self.ua,
            "Referer": self.site + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
        }
        self.session = requests.Session()
        ad = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", ad)
        self.session.mount("https://", ad)

    def getName(self):
        return "IDNFLIX"

    def isVideoFormat(self, url):
        if not url:
            return False
        low = url.lower()
        return any(x in low for x in (".m3u8", ".mp4", ".mkv", ".ts", ".mpd"))

    def manualVideoCheck(self):
        return True

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    def log(self, msg):
        try:
            print("[IDNFLIX] %s" % msg)
        except Exception:
            pass

    def _abs(self, href):
        if not href:
            return ""
        if href.startswith("http"):
            return href
        if href.startswith("//"):
            return "https:" + href
        return urljoin(self.site, href)

    def _make_id(self, href):
        try:
            if href.startswith(self.site):
                p = urlparse(href)
                path = p.path + (("?" + p.query) if p.query else "")
                return quote(path, safe="/?=&%")
            return href
        except Exception:
            return href

    def _get(self, url, headers=None, timeout=15):
        try:
            return self.session.get(
                url, headers=headers or self.site_headers,
                timeout=timeout, allow_redirects=True, verify=False,
            )
        except Exception as e:
            self.log("GET %s" % e)
            return None

    def homeContent(self, filter):
        classes = [
            {"type_name": "Film", "type_id": "kategori/film"},
            {"type_name": "TV Series", "type_id": "kategori/tv-series"},
            {"type_name": "18+", "type_id": "kategori/18-keatas"},
            {"type_name": "Donghua", "type_id": "kategori/donghua"},
            {"type_name": "Action", "type_id": "jenis/action"},
            {"type_name": "Comedy", "type_id": "jenis/comedy"},
            {"type_name": "Drama", "type_id": "jenis/drama"},
            {"type_name": "Horror", "type_id": "jenis/horror"},
            {"type_name": "Romance", "type_id": "jenis/romance"},
            {"type_name": "Korea", "type_id": "negara/korea-selatan"},
            {"type_name": "Japan", "type_id": "negara/jepang"},
            {"type_name": "USA", "type_id": "negara/usa"},
            {"type_name": "2024", "type_id": "tahun/2024"},
            {"type_name": "2025", "type_id": "tahun/2025"},
            {"type_name": "2026", "type_id": "tahun/2026"},
        ]
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        r = self._get(self.site + "/")
        if not r:
            return {"list": []}
        return {"list": self._parse_items(BeautifulSoup(r.text, "html.parser"), 40)}

    def categoryContent(self, tid, pg, filter, extend):
        base = "%s/%s" % (self.site, tid)
        if str(pg) != "1":
            base += "?page=%s" % pg
        r = self._get(base)
        if not r:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 40, "total": 0}
        items = self._parse_items(BeautifulSoup(r.text, "html.parser"), 40)
        return {
            "list": items, "page": int(pg), "pagecount": int(pg) + 1,
            "limit": 40, "total": 999999,
        }

    def searchContent(self, key, quick, pg="1"):
        r = self._get("%s/?search=%s" % (self.site, quote(key)))
        if not r:
            return {"list": []}
        return {"list": self._parse_items(BeautifulSoup(r.text, "html.parser"), 40)}

    def _parse_items(self, soup, limit=40):
        items, seen = [], set()
        covers = soup.select("a.item__cover[href]") or soup.select('a[href*="/movie/"]')
        for cover in covers:
            if len(items) >= limit:
                break
            href = (cover.get("href") or "").strip()
            if not href or href in seen or "/movie/" not in href:
                continue
            seen.add(href)
            img = cover.find("img")
            pic = self._abs(img.get("src", "")) if img else ""
            title = (img.get("alt", "") if img else "").strip()
            parent = cover.find_parent("div", class_="item")
            if parent:
                h3 = parent.select_one("h3.item__title a")
                if h3:
                    title = h3.get_text(strip=True) or title
            if title:
                items.append({
                    "vod_id": self._make_id(href),
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "",
                })
        return items

    def detailContent(self, ids):
        try:
            path = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
            url = self._abs(unquote(path))
            r = self._get(url, timeout=18)
            if not r:
                return {"list": []}
            html = r.text
            soup = BeautifulSoup(html, "html.parser")

            title = ""
            h1 = soup.select_one("h1.section__title--head") or soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)

            pic = ""
            bg = soup.select_one(".section__details-bg")
            if bg and bg.get("data-bg"):
                pic = bg["data-bg"]

            year = ""
            yl = soup.select_one('.item__meta a[href*="/tahun/"]')
            if yl:
                year = yl.get_text(strip=True)

            desc = ""
            de = soup.select_one(".item__description p, .item__description")
            if de:
                desc = de.get_text(strip=True)[:1500]

            raw = []
            for a in soup.select("ul.episode li.list-item a[href]"):
                href = (a.get("href") or "").strip().replace("&amp;", "&")
                if not href:
                    continue
                label = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
                label = label.replace("PLAY", "").strip()[:60] or "Play"
                m = re.search(r"(S\d+E\d+)", label, re.I)
                if m:
                    label = m.group(1).upper()
                raw.append((label, href))

            if not raw:
                return {"list": []}

            lines = self._build_play_lines(raw)
            if not lines:
                return {"list": []}

            return {"list": [{
                "vod_id": path,
                "vod_name": title,
                "vod_pic": pic,
                "vod_year": year,
                "vod_content": desc,
                "vod_play_from": "$$$".join([x[0] for x in lines]),
                "vod_play_url": "$$$".join([x[1] for x in lines]),
            }]}
        except Exception as e:
            self.log("detail %s" % e)
            return {"list": []}

    def _build_play_lines(self, raw):
        """把分集改写成 vidlink.pro（蜂蜜可嗅探播放）+ 少量备用。"""
        # embed/tv/{id}/{s}/{e} 或 embed/movie/{id}
        tv_re = re.compile(
            r"/embed/tv/([^/]+)/(\d+)/(\d+)", re.I
        )
        movie_re = re.compile(
            r"/embed/movie/([^/?&#]+)", re.I
        )
        imdb_re = re.compile(r"(tt\d{5,})", re.I)

        vidlink_eps = []
        videasy_eps = []
        vidsrc_eps = []

        for label, href in raw:
            href = href.replace("&amp;", "&")
            m = tv_re.search(href)
            if m:
                tid, season, episode = m.group(1), m.group(2), m.group(3)
                vidlink_eps.append(
                    "%s$https://vidlink.pro/tv/%s/%s/%s" % (label, tid, season, episode)
                )
                videasy_eps.append(
                    "%s$https://player.videasy.net/tv/%s/%s/%s" % (label, tid, season, episode)
                )
                vidsrc_eps.append(
                    "%s$https://vidsrc.sh/embed/tv/%s/%s/%s" % (label, tid, season, episode)
                )
                continue

            m = movie_re.search(href)
            if m:
                mid = m.group(1)
                vidlink_eps.append("%s$https://vidlink.pro/movie/%s" % (label, mid))
                videasy_eps.append("%s$https://player.videasy.net/movie/%s" % (label, mid))
                vidsrc_eps.append("%s$https://vidsrc.sh/embed/movie/%s" % (label, mid))
                continue

            m = imdb_re.search(href)
            if m:
                imdb = m.group(1)
                # 电影 imdb
                if "/tv" not in href.lower():
                    vidlink_eps.append("%s$https://vidlink.pro/movie/%s" % (label, imdb))
                    vidsrc_eps.append(
                        "%s$https://vidsrc2.ru/embed/movie?imdb=%s" % (label, imdb)
                    )
                else:
                    vidsrc_eps.append("%s$%s" % (label, href))
                continue

            # 原样保留
            vidsrc_eps.append("%s$%s" % (label, href))

        lines = []
        if vidlink_eps:
            lines.append(("Vidlink", "#".join(vidlink_eps)))
        if videasy_eps:
            lines.append(("Videasy", "#".join(videasy_eps)))
        if vidsrc_eps:
            lines.append(("Vidsrc", "#".join(vidsrc_eps)))
        return lines

    def playerContent(self, flag, id, vipFlags):
        try:
            url = unquote(str(id)).strip()
            if not url.startswith("http"):
                url = self._abs(url)

            if self.isVideoFormat(url):
                return {
                    "parse": 0,
                    "jx": 0,
                    "url": url,
                    "header": {
                        "User-Agent": self.ua,
                        "Referer": "https://vidlink.pro/",
                    },
                }

            low = url.lower()
            # vidlink / videasy：蜂蜜嗅探可播
            if "vidlink.pro" in low:
                return {
                    "parse": 1,
                    "jx": 0,
                    "url": url,
                    "header": {
                        "User-Agent": self.ua,
                        "Referer": "https://vidlink.pro/",
                        "Origin": "https://vidlink.pro",
                    },
                }
            if "videasy" in low:
                return {
                    "parse": 1,
                    "jx": 0,
                    "url": url,
                    "header": {
                        "User-Agent": self.ua,
                        "Referer": "https://player.videasy.net/",
                    },
                }

            # 其它 embed 也走嗅探
            return {
                "parse": 1,
                "jx": 0,
                "url": url,
                "header": {
                    "User-Agent": self.ua,
                    "Referer": self.site + "/",
                },
            }
        except Exception as e:
            self.log("player %s" % e)
            return {
                "parse": 1,
                "url": str(id),
                "header": {"User-Agent": self.ua},
            }

    def localProxy(self, param):
        try:
            url = unquote((param or {}).get("url", ""))
            if not url:
                return [400, "text/plain", b"missing"]
            r = self.session.get(
                url, headers={"User-Agent": self.ua},
                timeout=20, verify=False,
            )
            return [
                r.status_code,
                r.headers.get("Content-Type", "application/octet-stream"),
                r.content,
            ]
        except Exception as e:
            return [500, "text/plain", str(e).encode()]
