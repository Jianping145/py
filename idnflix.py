# -*- coding: utf-8 -*-
# IDNFLIX Spider v7.6 - 蜂蜜影视
# 站点播放源以 vidsrc 系 embed 为主；解析 vs_src 拿到内层播放页，并扩展多镜像线路
import re
import time
import json
import datetime
import requests
import urllib3
from urllib.parse import urlparse, urljoin, quote, unquote, parse_qs
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
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self._cache = {}

    def getName(self):
        return "IDNFLIX"

    def isVideoFormat(self, url):
        if not url:
            return False
        low = url.lower()
        return any(e in low for e in (".m3u8", ".mp4", ".mkv", ".ts", ".mpd"))

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
        headers = headers or self.site_headers
        try:
            r = self.session.get(
                url, headers=headers, timeout=timeout,
                allow_redirects=True, verify=False,
            )
            return r
        except Exception as e:
            self.log("GET err %s %s" % (url[:80], e))
            return None

    # ---------- home / list ----------
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
            {"type_name": "Sci-Fi", "type_id": "jenis/sci-fi"},
            {"type_name": "Thriller", "type_id": "jenis/thriller"},
            {"type_name": "Korea", "type_id": "negara/korea-selatan"},
            {"type_name": "Japan", "type_id": "negara/jepang"},
            {"type_name": "USA", "type_id": "negara/usa"},
            {"type_name": "2024", "type_id": "tahun/2024"},
            {"type_name": "2025", "type_id": "tahun/2025"},
            {"type_name": "2026", "type_id": "tahun/2026"},
        ]
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        try:
            r = self._get(self.site + "/")
            if not r:
                return {"list": []}
            soup = BeautifulSoup(r.text, "html.parser")
            return {"list": self._parse_items(soup, 40)}
        except Exception as e:
            self.log("homeVideo %s" % e)
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            base = "%s/%s" % (self.site, tid)
            if str(pg) != "1":
                base += "?page=%s" % pg
            r = self._get(base)
            if not r:
                return {"list": [], "page": 1, "pagecount": 1, "limit": 40, "total": 0}
            soup = BeautifulSoup(r.text, "html.parser")
            items = self._parse_items(soup, 40)
            return {
                "list": items,
                "page": int(pg),
                "pagecount": int(pg) + 1,
                "limit": 40,
                "total": 999999,
            }
        except Exception as e:
            self.log("category %s" % e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 40, "total": 0}

    def _parse_items(self, soup, limit=40):
        items, seen = [], set()
        covers = soup.select("a.item__cover[href]")
        if not covers:
            covers = soup.select('a[href*="/movie/"]')
        for cover in covers:
            if len(items) >= limit:
                break
            href = (cover.get("href") or "").strip()
            if not href or href in seen:
                continue
            if "/movie/" not in href:
                continue
            seen.add(href)
            vid = self._make_id(href)
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
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "",
                })
        return items

    def searchContent(self, key, quick, pg="1"):
        try:
            url = "%s/?search=%s" % (self.site, quote(key))
            r = self._get(url)
            if not r:
                return {"list": []}
            soup = BeautifulSoup(r.text, "html.parser")
            return {"list": self._parse_items(soup, 40), "page": 1, "pagecount": 1}
        except Exception:
            return {"list": []}

    # ---------- detail ----------
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

            # 原始播放链接
            raw_players = []
            for a in soup.select("ul.episode li.list-item a[href]"):
                href = (a.get("href") or "").strip()
                if not href:
                    continue
                label = a.get_text(" ", strip=True)
                label = re.sub(r"\s+", " ", label).replace("PLAY", "").strip()[:50] or "Play"
                raw_players.append((label, href))

            if not raw_players:
                for href in re.findall(
                    r'https?://(?:vidsrc|vidlink|videasy|vidrock|rumble|embed)[^"\s\'<>]+',
                    html, re.I,
                ):
                    raw_players.append(("Play", href.replace("&amp;", "&")))

            if not raw_players:
                return {"list": []}

            # 提取 imdb / tmdb，扩展多线路镜像
            imdb = ""
            m = re.search(r"(tt\d{5,})", html)
            if m:
                imdb = m.group(1)
            for _, href in raw_players:
                m = re.search(r"(tt\d{5,})", href)
                if m:
                    imdb = m.group(1)
                    break
            tmdb = ""
            m = re.search(r"vidsrc[^\"']*/(?:movie|tv)/(\d+)", html)
            if m:
                tmdb = m.group(1)

            expanded = self._expand_servers(raw_players, imdb, tmdb)

            # 按服务商分组
            servers = {}
            for label, purl in expanded:
                srv = self._classify_server(purl)
                servers.setdefault(srv, []).append((label, purl))

            priority = [
                "Vidsrc2", "Vidsrc.sh", "Vidsrc.me", "Vidsrc", "Vidsrc.to",
                "Videasy", "Vidlink", "Rumble", "2Embed", "Other",
            ]
            from_list, url_list = [], []
            for srv in priority:
                if srv not in servers:
                    continue
                eps = servers[srv]
                from_list.append(srv)
                url_list.append("#".join("%s$%s" % (l, u) for l, u in eps))
            for srv, eps in servers.items():
                if srv in from_list:
                    continue
                from_list.append(srv)
                url_list.append("#".join("%s$%s" % (l, u) for l, u in eps))

            if not from_list:
                return {"list": []}

            return {"list": [{
                "vod_id": path,
                "vod_name": title,
                "vod_pic": pic,
                "vod_year": year,
                "vod_content": desc,
                "vod_play_from": "$$$".join(from_list),
                "vod_play_url": "$$$".join(url_list),
            }]}
        except Exception as e:
            self.log("detail %s" % e)
            return {"list": []}

    def _expand_servers(self, raw_players, imdb, tmdb):
        """把单一 embed 扩成多镜像，提高可播概率"""
        out = []
        seen = set()

        def add(label, url):
            if not url or url in seen:
                return
            seen.add(url)
            out.append((label, url))

        for label, href in raw_players:
            add(label, href.replace("&amp;", "&"))

        mid = tmdb or imdb
        if imdb:
            add("Vidsrc2", "https://vidsrc2.ru/embed/movie?imdb=%s" % imdb)
            add("Vidsrc.sh", "https://vidsrc.sh/embed/movie/%s" % imdb)
            add("Vidsrc.me", "https://vidsrc.me/embed/movie/%s" % imdb)
            add("Vidsrc.to", "https://vidsrc.to/embed/movie/%s" % imdb)
            add("2Embed", "https://www.2embed.cc/embed/%s" % imdb)
        if tmdb:
            add("Vidsrc.sh/T", "https://vidsrc.sh/embed/movie/%s" % tmdb)
            add("Videasy", "https://player.videasy.net/movie/%s" % tmdb)
            add("Vidlink", "https://vidlink.pro/movie/%s" % tmdb)
        return out

    def _classify_server(self, url):
        if not url:
            return "Other"
        low = url.lower()
        if "vidsrc2" in low:
            return "Vidsrc2"
        if "vidsrc.sh" in low:
            return "Vidsrc.sh"
        if "vidsrc.me" in low:
            return "Vidsrc.me"
        if "vidsrc.to" in low:
            return "Vidsrc.to"
        if "vidsrc." in low:
            return "Vidsrc"
        if "videasy" in low:
            return "Videasy"
        if "vidlink" in low:
            return "Vidlink"
        if "rumble" in low:
            return "Rumble"
        if "2embed" in low:
            return "2Embed"
        return "Other"

    # ---------- player ----------
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
                    "header": self._play_headers(flag, url),
                }

            low = url.lower()

            # Rumble
            if "rumble.com" in low:
                direct = self._extract_rumble(url)
                if direct:
                    return {
                        "parse": 0, "jx": 0, "url": direct,
                        "header": {
                            "User-Agent": self.ua,
                            "Referer": "https://rumble.com/",
                            "Origin": "https://rumble.com",
                        },
                    }

            # Vidlink
            if "vidlink" in low:
                direct = self._extract_vidlink(url)
                if direct:
                    return {
                        "parse": 0, "jx": 0, "url": direct,
                        "header": {
                            "User-Agent": self.ua,
                            "Referer": "https://vidlink.pro/",
                            "Origin": "https://vidlink.pro",
                        },
                    }

            # vidsrc 系：解析 vs_src 拿到内层播放器，交给壳嗅探
            if any(x in low for x in ("vidsrc", "vsembed", "stellarconductor")):
                resolved = self._resolve_vidsrc(url)
                if resolved:
                    if self.isVideoFormat(resolved):
                        return {
                            "parse": 0, "jx": 0, "url": resolved,
                            "header": self._play_headers(flag, resolved),
                        }
                    return {
                        "parse": 1, "jx": 0, "url": resolved,
                        "header": self._play_headers(flag, resolved),
                    }

            # 2embed 等：直接嗅探
            if "2embed" in low:
                return {
                    "parse": 1, "jx": 0, "url": url,
                    "header": {"User-Agent": self.ua, "Referer": "https://www.2embed.cc/"},
                }

            # 默认：壳内嗅探播放
            return {
                "parse": 1,
                "jx": 0,
                "url": url,
                "header": self._play_headers(flag, url),
            }
        except Exception as e:
            self.log("player %s" % e)
            return {
                "parse": 1,
                "url": self._abs(str(id)),
                "header": {"User-Agent": self.ua},
            }

    def _play_headers(self, flag, url=""):
        low = (url or "").lower()
        if "vidsrc" in low or "stellar" in low:
            return {
                "User-Agent": self.ua,
                "Referer": "https://vidsrc.sh/",
                "Origin": "https://vidsrc.sh",
            }
        if "videasy" in low:
            return {
                "User-Agent": self.ua,
                "Referer": "https://player.videasy.net/",
            }
        return {
            "User-Agent": self.ua,
            "Referer": self.site + "/",
        }

    def _resolve_vidsrc(self, embed_url):
        """vidsrc embed -> vs_src.php -> 内层 player 页"""
        if embed_url in self._cache:
            return self._cache[embed_url]
        try:
            # 已是内层
            if "stellarconductornexus.com" in embed_url or "/embed/player/" in embed_url:
                return embed_url

            r = self._get(embed_url, headers={
                "User-Agent": self.ua,
                "Referer": self.site + "/",
            }, timeout=12)
            if not r or r.status_code != 200:
                return None

            html = r.text
            # data-api="/vs_src.php?type=movie&id=xxx"
            m = re.search(r'data-api="([^"]+)"', html)
            api = ""
            if m:
                api = m.group(1).replace("&amp;", "&")
                if api.startswith("/"):
                    api = "%s://%s%s" % (urlparse(r.url).scheme, urlparse(r.url).netloc, api)
            else:
                # 从 URL 推断
                mid = ""
                m2 = re.search(r"/embed/(?:movie|tv)/([^/?&#]+)", embed_url)
                if m2:
                    mid = m2.group(1)
                else:
                    qs = parse_qs(urlparse(embed_url).query)
                    mid = (qs.get("imdb") or qs.get("tmdb") or qs.get("id") or [""])[0]
                if not mid:
                    return None
                host = "%s://%s" % (urlparse(embed_url).scheme, urlparse(embed_url).netloc)
                # tv?
                typ = "tv" if "/tv" in embed_url or "type=tv" in embed_url else "movie"
                api = "%s/vs_src.php?type=%s&id=%s" % (host, typ, mid)

            self.log("vs_src %s" % api)
            rj = self._get(api, headers={
                "User-Agent": self.ua,
                "Referer": embed_url,
                "Accept": "application/json",
            }, timeout=10)
            if not rj or rj.status_code != 200:
                return None
            try:
                data = rj.json()
            except Exception:
                return None
            src = data.get("src") or data.get("url") or ""
            if not src:
                return None

            # 再进一层拿 playerUrl（更接近真实播放器，嗅探成功率更高）
            r2 = self._get(src, headers={
                "User-Agent": self.ua,
                "Referer": embed_url,
            }, timeout=12)
            if r2 and r2.status_code == 200:
                m = re.search(r'window\.CFG\s*=\s*(\{.*?\})\s*;', r2.text)
                if m:
                    try:
                        cfg = json.loads(m.group(1))
                        p = cfg.get("playerUrl") or ""
                        if p:
                            if p.startswith("/"):
                                p = "%s://%s%s" % (
                                    urlparse(src).scheme, urlparse(src).netloc, p
                                )
                            self._cache[embed_url] = p
                            return p
                    except Exception:
                        pass
            self._cache[embed_url] = src
            return src
        except Exception as e:
            self.log("resolve_vidsrc %s" % e)
            return None

    def _extract_rumble(self, rumble_url):
        try:
            m = re.search(r"/embed/([a-zA-Z0-9]+)", rumble_url)
            if not m:
                return None
            video_id = m.group(1)
            pub = ""
            m2 = re.search(r"[?&]pub=([a-zA-Z0-9]+)", rumble_url)
            if m2:
                pub = m2.group(1)
            apis = [
                "https://rumble.com/api/v1.0/embed/%s?pub=%s" % (video_id, pub),
                "https://rumble.com/api/v1.0/embed/%s" % video_id,
                "https://rumble.com/embedJS/u3/?request=video&ver=2&v=%s" % video_id,
            ]
            for api in apis:
                r = self._get(api, headers={
                    "User-Agent": self.ua,
                    "Referer": rumble_url,
                    "Origin": "https://rumble.com",
                    "Accept": "application/json,*/*",
                }, timeout=10)
                if not r or r.status_code != 200:
                    continue
                try:
                    j = r.json()
                except Exception:
                    j = None
                if j:
                    found = self._find_media_deep(j, ".m3u8") or self._find_media_deep(j, ".mp4")
                    if found:
                        return found
                m3 = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', r.text)
                if m3:
                    return m3.group(1)
        except Exception as e:
            self.log("rumble %s" % e)
        return None

    def _extract_vidlink(self, vidlink_url):
        try:
            m = re.search(r"/(movie|tv)/(\d+)", vidlink_url)
            if not m:
                return None
            media_type, tmdb_id = m.group(1), m.group(2)
            for api in (
                "https://vidlink.pro/api/b/%s/%s" % (media_type, tmdb_id),
                "https://vidlink.pro/api/%s/%s" % (media_type, tmdb_id),
            ):
                r = self._get(api, headers={
                    "User-Agent": self.ua,
                    "Referer": vidlink_url,
                    "Origin": "https://vidlink.pro",
                    "Accept": "application/json",
                }, timeout=10)
                if not r or r.status_code != 200:
                    continue
                try:
                    j = r.json()
                    found = self._find_media_deep(j, ".m3u8")
                    if found:
                        return found
                except Exception:
                    m3 = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', r.text)
                    if m3:
                        return m3.group(1)
        except Exception as e:
            self.log("vidlink %s" % e)
        return None

    def _find_media_deep(self, data, ext):
        if isinstance(data, str):
            if ext in data and data.startswith("http"):
                return data
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str) and ext in v and v.startswith("http"):
                    return v
                r = self._find_media_deep(v, ext)
                if r:
                    return r
        elif isinstance(data, list):
            for item in data:
                r = self._find_media_deep(item, ext)
                if r:
                    return r
        return None

    def localProxy(self, param):
        try:
            url = unquote((param or {}).get("url", ""))
            if not url:
                return [400, "text/plain", b"missing url"]
            r = self.session.get(
                url, headers={"User-Agent": self.ua},
                timeout=20, verify=False, stream=True,
            )
            ctype = r.headers.get("Content-Type", "application/octet-stream")
            return [r.status_code, ctype, r.content]
        except Exception as e:
            return [500, "text/plain", str(e).encode()]
