# -*- coding: utf-8 -*-
# IDNFLIX Spider v8.4 - 蜂蜜影视
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

    def _resolve_imdb(self, title):
        """用 TVmaze 免费接口把标题解析成 imdb id"""
        if not title:
            return ""
        try:
            # 去掉中文括号副标题噪音
            q = re.sub(r"[（(][^）)]*[）)]", " ", title)
            q = re.sub(r"\s+", " ", q).strip()
            r = self._req(
                "GET",
                "https://api.tvmaze.com/search/shows?q=%s" % quote(q[:80]),
                headers={"User-Agent": self.ua, "Accept": "application/json"},
            )
            if not r or r.status_code != 200:
                return ""
            arr = r.json()
            if not isinstance(arr, list):
                return ""
            for item in arr[:8]:
                show = item.get("show") or {}
                ext = show.get("externals") or {}
                imdb = ext.get("imdb") or ""
                if imdb and str(imdb).startswith("tt"):
                    return str(imdb)
        except Exception as e:
            self.log("tvmaze %s" % e)
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
                label = label.replace("PLAY", "").strip()
                # 规范集名
                m = re.search(r"(S\d+E\d+)", label, re.I)
                if m:
                    label = m.group(1).upper()
                else:
                    m = re.search(r"Ep\.?\s*(\d+(?:\s*[-~]\s*\d+)?)", label, re.I)
                    if m:
                        label = "Ep." + m.group(1).replace(" ", "")
                    elif re.search(r"server\s*\d+", label, re.I):
                        label = "正片"
                    else:
                        label = label[:40] or "Play"
                raw.append((label, href))

            if not raw:
                return {"list": []}

            imdb = ""
            m = re.search(r"(tt\d{5,})", html)
            if m:
                imdb = m.group(1)
            if not imdb:
                imdb = self._resolve_imdb(title)
            lines = self._build_play_lines(raw, imdb=imdb, title=title)
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


    def _build_play_lines(self, raw, imdb="", title=""):
        """多格式 embed → Vidlink 优先；Rumble/YT/DM 独立线路；动画补 Videasy(imdb)。"""
        tv_path_re = re.compile(r"(?:/embed)?/tv/([^/]+)/(\d+)/(\d+)", re.I)
        tv_id_re = re.compile(r"(?:/v\d+)?/embed/tv/(\d+)(?:\D|$)", re.I)
        movie_re = re.compile(r"(?:/embed)?/movie/([^/?&#]+)", re.I)
        imdb_re = re.compile(r"(tt\d{5,})", re.I)
        q_tmdb_re = re.compile(r"[?&]tmdb=(\d+)", re.I)
        q_season_re = re.compile(r"[?&]season=(\d+)", re.I)
        q_episode_re = re.compile(r"[?&]episode=(\d+)", re.I)
        se_label_re = re.compile(r"S(\d+)E(\d+)", re.I)
        ep_num_re = re.compile(r"Ep\.?\s*(\d+)", re.I)

        vidlink_eps, videasy_eps, vidsrc_eps = [], [], []
        rumble_eps, youtube_eps, dailymotion_eps = [], [], []

        embed2_eps = []  # 2embed 对蜂蜜沙箱更友好

        def add_tv(label, tid, s, e, keep_href=None):
            s, e = int(s), int(e)
            # Videasy 优先（Vidlink 在沙箱 WebView 常被拦截）
            videasy_eps.append("%s$https://player.videasy.net/tv/%s/%s/%s" % (label, tid, s, e))
            embed2_eps.append("%s$https://www.2embed.cc/embedtv/%s&s=%s&e=%s" % (label, tid, s, e))
            vidlink_eps.append("%s$https://vidlink.pro/tv/%s/%s/%s" % (label, tid, s, e))
            if keep_href:
                vidsrc_eps.append("%s$%s" % (label, keep_href))
            else:
                vidsrc_eps.append("%s$https://vidsrc.sh/embed/tv/%s/%s/%s" % (label, tid, s, e))

        def add_movie(label, mid, keep_href=None):
            videasy_eps.append("%s$https://player.videasy.net/movie/%s" % (label, mid))
            if str(mid).startswith("tt"):
                embed2_eps.append("%s$https://www.2embed.cc/embed/%s" % (label, mid))
            else:
                embed2_eps.append("%s$https://www.2embed.cc/embed/tmdb/%s" % (label, mid))
            vidlink_eps.append("%s$https://vidlink.pro/movie/%s" % (label, mid))
            if keep_href:
                vidsrc_eps.append("%s$%s" % (label, keep_href))
            elif str(mid).startswith("tt"):
                vidsrc_eps.append("%s$https://vidsrc2.ru/embed/movie?imdb=%s" % (label, mid))
            else:
                vidsrc_eps.append("%s$https://vidsrc.sh/embed/movie/%s" % (label, mid))

        tmdb_ids_seen = set()
        max_ep_hint = 1
        ongoing = False

        for label, href in raw:
            href = (href or "").replace("&amp;", "&").strip()
            low = href.lower()
            if "on going" in (label or "").lower() or "ongoing" in low:
                ongoing = True

            ls, le = "1", "1"
            mlab = se_label_re.search(label or "")
            if mlab:
                ls, le = str(int(mlab.group(1))), str(int(mlab.group(2)))
                max_ep_hint = max(max_ep_hint, int(le))
            else:
                mlab = ep_num_re.search(label or "")
                if mlab:
                    le = str(int(mlab.group(1)))
                    max_ep_hint = max(max_ep_hint, int(le))

            # Rumble / YouTube / Dailymotion（动画站常用）
            if "rumble.com" in low:
                rumble_eps.append("%s$%s" % (label, href))
                continue
            if "youtube.com" in low or "youtu.be" in low:
                youtube_eps.append("%s$%s" % (label, href))
                continue
            if "dailymotion.com" in low:
                dailymotion_eps.append("%s$%s" % (label, href))
                continue

            # 路径 tv/id/s/e
            m = tv_path_re.search(href)
            if m:
                tmdb_ids_seen.add(m.group(1))
                add_tv(label, m.group(1), m.group(2), m.group(3), href)
                continue

            # ?tmdb=&season=&episode=
            mq = q_tmdb_re.search(href)
            if mq:
                tid = mq.group(1)
                tmdb_ids_seen.add(tid)
                s = q_season_re.search(href)
                e = q_episode_re.search(href)
                s = s.group(1) if s else ls
                e = e.group(1) if e else le
                max_ep_hint = max(max_ep_hint, int(e))
                if "/movie" in low and "/tv" not in low:
                    add_movie(label, tid, href)
                else:
                    add_tv(label, tid, s, e, href)
                continue

            # /embed/tv/{id} 无集数
            m = tv_id_re.search(href)
            if m:
                tid = m.group(1)
                tmdb_ids_seen.add(tid)
                add_tv(label, tid, ls, le, href)
                continue

            m = movie_re.search(href)
            if m:
                add_movie(label, m.group(1), href)
                continue

            m = imdb_re.search(href)
            if m:
                add_movie(label, m.group(1), href)
                continue

            if "vidlink" in low or "videasy" in low:
                vidlink_eps.append("%s$%s" % (label, href))
                continue

            m = re.search(r"(?:tmdb[=/]|[?&]id=)(\d{3,})", href, re.I)
            if m:
                tmdb_ids_seen.add(m.group(1))
                add_tv(label, m.group(1), ls, le, href)
                continue

            vidsrc_eps.append("%s$%s" % (label, href))

        # 连载只挂了 1 集时，用 tmdb 按 Vidlink 补全 S01E01..E40（可点集数更多）
        if tmdb_ids_seen and len(vidlink_eps) <= 2:
            tid = next(iter(tmdb_ids_seen))
            # 已有的集数
            have = set()
            for x in vidlink_eps:
                mm = se_label_re.search(x.split("$")[0])
                if mm:
                    have.add((int(mm.group(1)), int(mm.group(2))))
            total = 40 if ongoing or len(vidlink_eps) <= 1 else max(max_ep_hint, 12)
            total = max(total, max_ep_hint)
            new_vl, new_ve = [], []
            for ep in range(1, total + 1):
                if (1, ep) in have:
                    # keep existing label order later
                    continue
                lab = "S01E%02d" % ep
                new_vl.append("%s$https://vidlink.pro/tv/%s/1/%s" % (lab, tid, ep))
                new_ve.append("%s$https://player.videasy.net/tv/%s/1/%s" % (lab, tid, ep))
            # 合并：已有的放前面，再补全
            if new_vl:
                # 重建完整 1..total
                full_vl, full_ve = [], []
                existing_map = {}
                for x in vidlink_eps:
                    mm = se_label_re.search(x.split("$")[0])
                    if mm:
                        existing_map[(int(mm.group(1)), int(mm.group(2)))] = x
                for ep in range(1, total + 1):
                    key = (1, ep)
                    lab = "S01E%02d" % ep
                    if key in existing_map:
                        full_vl.append(existing_map[key])
                    else:
                        full_vl.append("%s$https://vidlink.pro/tv/%s/1/%s" % (lab, tid, ep))
                    full_ve.append("%s$https://player.videasy.net/tv/%s/1/%s" % (lab, tid, ep))
                vidlink_eps = full_vl
                videasy_eps = full_ve

        # 动画等只有 Rumble/YT 时：用 imdb 生成 Videasy / Vidsrc 分集（通常比 Rumble 更清晰）
        if imdb and (rumble_eps or youtube_eps or dailymotion_eps) and not vidlink_eps:
            ep_nums = []
            for lab, _ in [(x.split("$")[0], x.split("$")[-1]) for x in rumble_eps + dailymotion_eps]:
                mm = ep_num_re.search(lab)
                if mm:
                    ep_nums.append(int(mm.group(1)))
            if not ep_nums:
                ep_nums = list(range(1, 25))
            hi = max(ep_nums)
            # 覆盖 1..max（Rumble 有的集）
            vasy, vsrc = [], []
            for ep in range(1, hi + 1):
                lab = "Ep.%s" % ep
                vasy.append("%s$https://player.videasy.net/tv/%s/1/%s" % (lab, imdb, ep))
                vsrc.append("%s$https://vidsrc.me/embed/tv?imdb=%s&season=1&episode=%s" % (lab, imdb, ep))
            videasy_eps = vasy
            # vidsrc 备用
            if not vidsrc_eps:
                vidsrc_eps = vsrc

        # Rumble 集数名排序（数字升序）
        def _ep_key(item):
            lab = item.split("$")[0]
            mm = ep_num_re.search(lab)
            return int(mm.group(1)) if mm else 0

        if rumble_eps:
            rumble_eps = sorted(rumble_eps, key=_ep_key)
        if videasy_eps and imdb:
            videasy_eps = sorted(videasy_eps, key=_ep_key)

        # 分集升序（S01E01 在前）
        def _se_key(item):
            lab = item.split("$")[0]
            mm = se_label_re.search(lab)
            if mm:
                return (int(mm.group(1)), int(mm.group(2)))
            mm = ep_num_re.search(lab)
            return (0, int(mm.group(1))) if mm else (0, 0)

        for lst_name in ("videasy_eps", "embed2_eps", "vidlink_eps", "vidsrc_eps"):
            lst = locals().get(lst_name) or []
            if lst and any(se_label_re.search(x.split("$")[0]) or ep_num_re.search(x.split("$")[0]) for x in lst):
                locals()[lst_name]  # no-op
        if videasy_eps:
            videasy_eps = sorted(videasy_eps, key=_se_key)
        if embed2_eps:
            embed2_eps = sorted(embed2_eps, key=_se_key)
        if vidlink_eps:
            vidlink_eps = sorted(vidlink_eps, key=_se_key)
        if vidsrc_eps:
            vidsrc_eps = sorted(vidsrc_eps, key=_se_key)

        lines = []
        # Vidlink 在蜂蜜沙箱 WebView 常被其自身检测拦截，故排后
        if videasy_eps:
            lines.append(("Videasy", "#".join(videasy_eps)))
        if embed2_eps:
            lines.append(("2Embed", "#".join(embed2_eps)))
        if vidlink_eps:
            lines.append(("Vidlink", "#".join(vidlink_eps)))
        if rumble_eps:
            lines.append(("Rumble", "#".join(rumble_eps)))
        if dailymotion_eps:
            lines.append(("Dailymotion", "#".join(dailymotion_eps)))
        if youtube_eps:
            lines.append(("YouTube", "#".join(youtube_eps)))
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
            if "rumble.com" in low:
                return {
                    "parse": 1, "jx": 0, "url": url,
                    "header": {
                        "User-Agent": self.ua,
                        "Referer": "https://rumble.com/",
                        "Origin": "https://rumble.com",
                    },
                }
            if "youtube.com" in low or "youtu.be" in low:
                return {
                    "parse": 1, "jx": 0, "url": url,
                    "header": {"User-Agent": self.ua, "Referer": "https://www.youtube.com/"},
                }
            if "dailymotion.com" in low:
                return {
                    "parse": 1, "jx": 0, "url": url,
                    "header": {"User-Agent": self.ua, "Referer": "https://www.dailymotion.com/"},
                }
            if "2embed" in low:
                return {
                    "parse": 1, "jx": 0, "url": url,
                    "header": {"User-Agent": self.ua, "Referer": "https://www.2embed.cc/"},
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
