# -*- coding: utf-8 -*-
# IDNFLIX Spider v8.0 - 蜂蜜影视
# 自动过 wssplash 门禁（GET + wsidchk），播放优先 vidlink.pro 嗅探
# extend 可选代理: {"proxy":"http://127.0.0.1:7890"}
import re
import json
import requests
import urllib3
from urllib.parse import urlparse, urljoin, quote, unquote, urlencode
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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Upgrade-Insecure-Requests": "1",
        }
        self.session = requests.Session()
        ad = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", ad)
        self.session.mount("https://", ad)
        self.proxy = None
        self._gate_ok = False
        self._apply_extend(extend)

    def _apply_extend(self, extend):
        if not extend:
            return
        obj = extend
        if isinstance(extend, str):
            extend = extend.strip()
            if not extend:
                return
            try:
                obj = json.loads(extend)
            except Exception:
                if extend.startswith("http") or extend.startswith("socks"):
                    obj = {"proxy": extend}
                else:
                    return
        if isinstance(obj, dict):
            proxy = obj.get("proxy") or obj.get("proxies")
            if proxy:
                if isinstance(proxy, dict):
                    self.proxy = proxy
                else:
                    self.proxy = {"http": proxy, "https": proxy}

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
            if "idnflix.com" in href:
                p = urlparse(href)
                path = p.path + (("?" + p.query) if p.query else "")
                return quote(path, safe="/?=&%")
            return href
        except Exception:
            return href

    def _req(self, method, url, **kwargs):
        kwargs.setdefault("timeout", 20)
        kwargs.setdefault("verify", False)
        kwargs.setdefault("allow_redirects", True)
        if self.proxy:
            kwargs["proxies"] = self.proxy
        headers = kwargs.pop("headers", None) or dict(self.site_headers)
        try:
            if method == "GET":
                return self.session.get(url, headers=headers, **kwargs)
            return self.session.post(url, headers=headers, **kwargs)
        except Exception as e:
            self.log("%s %s" % (method, e))
            return None

    def _is_challenge(self, html):
        if not html:
            return False
        if "One moment, please" in html or "Mohon tunggu" in html:
            return True
        if "wsidchk" in html and "/movie/" not in html:
            return True
        return False

    def _js_sum(self, g_expr, e_expr):
        try:
            import subprocess
            js = "console.log((%s)+(%s))" % (g_expr, e_expr)
            return subprocess.check_output(
                ["node", "-e", js], text=True, stderr=subprocess.DEVNULL, timeout=3
            ).strip()
        except Exception:
            return ""

    def _form_id(self, big, c_hex):
        try:
            import subprocess
            part1 = big.split("var a0X=window")[0]
            m = re.search(
                r"function a0J\(\)\{var ([a-z])=\[([\s\S]*?)\];a0J=function\(\)\{return \1;\};return a0J\(\);\}",
                big,
            )
            if not m:
                return ""
            code = (
                part1 + "\n" + m.group(0)
                + "\nconsole.log('7fa3b767c4'+'60b54a2be4'+a0y(%s)+'c7');\n" % c_hex
            )
            return subprocess.check_output(
                ["node", "-e", code], text=True, stderr=subprocess.DEVNULL, timeout=4
            ).strip()
        except Exception as e:
            self.log("form_id %s" % e)
            return ""

    def _pass_gate(self, html):
        """过 One moment 门禁：GET action?wsidchk&pdata&id&ts&cttl → 写 wssplashchk cookie"""
        try:
            scripts = re.findall(r"<script>([\s\S]*?)</script>", html)
            big = next((sc for sc in scripts if len(sc) > 1000 or "wsidchk" in sc), "")
            if not big:
                return False
            g_m = re.search(r"G=(\+\(\(.*?\)\)),J=", html)
            e_m = re.search(r"E=(\+\(\(.*?\)\)),a=", html)
            ts_m = re.search(r"'ts','(\d+)'", html)
            path_m = re.search(r"'(/z0[a-f0-9]+)'", html)
            pdata_m = re.search(r"k='([^']+)'", html)
            if not all([g_m, e_m, ts_m, path_m, pdata_m]):
                return False
            wsidchk = self._js_sum(g_m.group(1), e_m.group(1))
            if not wsidchk:
                return False
            aw = re.search(r"a0w=\{([^}]+)\}", html)
            c_hex = "0x169"
            if aw:
                cm = re.search(r"c:(0x[0-9a-f]+)", aw.group(1))
                if cm:
                    c_hex = cm.group(1)
            cid = self._form_id(big, c_hex)
            if not cid:
                return False
            params = {
                "wsidchk": wsidchk,
                "pdata": unquote(pdata_m.group(1)),
                "id": cid,
                "ts": ts_m.group(1),
                "cttl": "0",
            }
            action = self.site + path_m.group(1) + "?" + urlencode(params)
            headers = dict(self.site_headers)
            headers["Referer"] = self.site + "/"
            r = self._req("GET", action, headers=headers)
            if not r:
                return False
            # 成功会带 wssplashchk
            ck = requests.utils.dict_from_cookiejar(self.session.cookies)
            if "wssplashchk" in ck:
                self._gate_ok = True
                self.log("gate ok cookie set")
                return True
            # 再探首页
            r2 = self._req("GET", self.site + "/", headers=headers)
            if r2 and not self._is_challenge(r2.text) and "/movie/" in r2.text:
                self._gate_ok = True
                self.log("gate ok home")
                return True
            self.log("gate fail status=%s" % (r.status_code if r else None))
            return False
        except Exception as e:
            self.log("gate err %s" % e)
            return False

    def _fetch_html(self, url):
        headers = dict(self.site_headers)
        headers["Referer"] = self.site + "/"
        r = self._req("GET", url, headers=headers)
        if not r:
            return ""
        html = r.text
        if self._is_challenge(html):
            if self._pass_gate(html):
                r = self._req("GET", url, headers=headers)
                html = r.text if r else ""
            else:
                # 再试一次整流程
                r0 = self._req("GET", self.site + "/", headers=headers)
                if r0 and self._is_challenge(r0.text):
                    self._pass_gate(r0.text)
                r = self._req("GET", url, headers=headers)
                html = r.text if r else ""
        return html or ""

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
        html = self._fetch_html(self.site + "/")
        if not html:
            return {"list": []}
        return {"list": self._parse_items(BeautifulSoup(html, "html.parser"), 40)}

    def categoryContent(self, tid, pg, filter, extend):
        base = "%s/%s" % (self.site, tid)
        if str(pg) != "1":
            base += "?page=%s" % pg
        html = self._fetch_html(base)
        if not html:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 40, "total": 0}
        items = self._parse_items(BeautifulSoup(html, "html.parser"), 40)
        return {
            "list": items, "page": int(pg), "pagecount": int(pg) + 1,
            "limit": 40, "total": 999999,
        }

    def searchContent(self, key, quick, pg="1"):
        html = self._fetch_html("%s/?search=%s" % (self.site, quote(key)))
        if not html:
            return {"list": []}
        return {"list": self._parse_items(BeautifulSoup(html, "html.parser"), 40)}

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
            html = self._fetch_html(url)
            if not html:
                return {"list": []}
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
                elif re.search(r"server\s*\d+", label, re.I):
                    label = "正片"
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
        tv_re = re.compile(r"(?:/embed)?/tv/([^/]+)/(\d+)/(\d+)", re.I)
        movie_re = re.compile(r"(?:/embed)?/movie/([^/?&#]+)", re.I)
        imdb_re = re.compile(r"(tt\d{5,})", re.I)
        vidlink_eps, videasy_eps, vidsrc_eps = [], [], []

        for label, href in raw:
            href = (href or "").replace("&amp;", "&").strip()
            low = href.lower()

            if "vidlink.pro" in low:
                m = tv_re.search(href)
                if m:
                    tid, s, e = m.group(1), m.group(2), m.group(3)
                    vidlink_eps.append("%s$https://vidlink.pro/tv/%s/%s/%s" % (label, tid, s, e))
                    videasy_eps.append("%s$https://player.videasy.net/tv/%s/%s/%s" % (label, tid, s, e))
                    continue
                m = movie_re.search(href)
                if m:
                    mid = m.group(1)
                    vidlink_eps.append("%s$https://vidlink.pro/movie/%s" % (label, mid))
                    videasy_eps.append("%s$https://player.videasy.net/movie/%s" % (label, mid))
                    continue

            m = tv_re.search(href)
            if m:
                tid, s, e = m.group(1), m.group(2), m.group(3)
                vidlink_eps.append("%s$https://vidlink.pro/tv/%s/%s/%s" % (label, tid, s, e))
                videasy_eps.append("%s$https://player.videasy.net/tv/%s/%s/%s" % (label, tid, s, e))
                vidsrc_eps.append("%s$https://vidsrc.sh/embed/tv/%s/%s/%s" % (label, tid, s, e))
                continue

            m = movie_re.search(href)
            if m:
                mid = m.group(1)
                vidlink_eps.append("%s$https://vidlink.pro/movie/%s" % (label, mid))
                videasy_eps.append("%s$https://player.videasy.net/movie/%s" % (label, mid))
                if mid.startswith("tt"):
                    vidsrc_eps.append("%s$https://vidsrc2.ru/embed/movie?imdb=%s" % (label, mid))
                else:
                    vidsrc_eps.append("%s$https://vidsrc.sh/embed/movie/%s" % (label, mid))
                continue

            m = imdb_re.search(href)
            if m:
                imdb = m.group(1)
                vidlink_eps.append("%s$https://vidlink.pro/movie/%s" % (label, imdb))
                videasy_eps.append("%s$https://player.videasy.net/movie/%s" % (label, imdb))
                vidsrc_eps.append("%s$https://vidsrc2.ru/embed/movie?imdb=%s" % (label, imdb))
                continue

            if "vidlink" in low or "videasy" in low:
                vidlink_eps.append("%s$%s" % (label, href))
            else:
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
                    "parse": 0, "jx": 0, "url": url,
                    "header": {"User-Agent": self.ua, "Referer": "https://vidlink.pro/"},
                }
            low = url.lower()
            if "vidlink.pro" in low:
                return {
                    "parse": 1, "jx": 0, "url": url,
                    "header": {
                        "User-Agent": self.ua,
                        "Referer": "https://vidlink.pro/",
                        "Origin": "https://vidlink.pro",
                    },
                }
            if "videasy" in low:
                return {
                    "parse": 1, "jx": 0, "url": url,
                    "header": {"User-Agent": self.ua, "Referer": "https://player.videasy.net/"},
                }
            return {
                "parse": 1, "jx": 0, "url": url,
                "header": {"User-Agent": self.ua, "Referer": self.site + "/"},
            }
        except Exception as e:
            self.log("player %s" % e)
            return {"parse": 1, "url": str(id), "header": {"User-Agent": self.ua}}

    def localProxy(self, param):
        try:
            url = unquote((param or {}).get("url", ""))
            if not url:
                return [400, "text/plain", b"missing"]
            r = self.session.get(
                url, headers={"User-Agent": self.ua},
                timeout=20, verify=False, proxies=self.proxy,
            )
            return [r.status_code, r.headers.get("Content-Type", "application/octet-stream"), r.content]
        except Exception as e:
            return [500, "text/plain", str(e).encode()]
