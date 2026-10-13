# -*- coding: utf-8 -*-
# 洛雪TV - 蜂蜜影视/Fongmi 爬虫
# 网站: https://tv.lxyy.club/
# 列表: ranking / quark / TMDB discover
# 播放: 采集源直链 + 公共解析（洛雪4K需网页授权，App不可用）

import json
import re
import ssl
import time
from urllib.parse import quote, unquote, urljoin, urlencode
from urllib.request import Request, urlopen, build_opener, HTTPSHandler, install_opener

try:
    import requests
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False


class Spider:
    def __init__(self):
        self.site_url = "https://tv.lxyy.club"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.site_url + "/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.tmdb_img = "https://image.tmdb.org/t/p/w500"
        self.source_priority = ["jl", "mj", "qilin", "360zy", "dytt", "ik", "md", "fy"]
        self.parse_routes = [
            {"id": "official_default", "name": "默认解析", "type": "iframe",
             "api": "https://svip.qlplayer.cyou/?url="},
            {"id": "official_mugf3fgl", "name": "闪电", "type": "iframe",
             "api": "https://bfq.txnp.cn/excessive?url="},
            {"id": "official_muh2ffwq", "name": "m1907", "type": "iframe",
             "api": "https://im1907.top/?jx="},
        ]
        self._parse_routes_loaded = False
        self.primary = [
            ("recommend", "推荐"),
            ("movie", "电影"),
            ("series", "剧集"),
            ("anime", "动漫"),
            ("quark_电影", "夸克·电影"),
            ("quark_电视剧", "夸克·电视剧"),
            ("quark_综艺", "夸克·综艺"),
            ("quark_动漫", "夸克·动漫"),
            ("quark_短剧", "夸克·短剧"),
        ]
        self.catalog = {}
        self._init_catalog()
        # 忽略 SSL 证书问题（部分设备缺根证书）
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            install_opener(build_opener(HTTPSHandler(context=ctx)))
        except Exception:
            pass

    def init(self, extend=""):
        return

    def getName(self):
        return "洛雪TV"

    def _init_catalog(self):
        movie_base = {
            "sort_by": "popularity.desc",
            "include_adult": "false",
            "include_video": "false",
        }
        series_base = {
            "sort_by": "popularity.desc",
            "include_null_first_air_dates": "false",
            "include_adult": "false",
        }

        def add(group, cid, name, endpoint=None, params=None, countries=None, media_type=None):
            if endpoint is None:
                endpoint = "discover/movie" if group == "movie" else "discover/tv"
            base = dict(movie_base if group == "movie" else series_base)
            if params:
                base.update(params)
            mt = media_type or ("movie" if group == "movie" else "tv")
            self.catalog[cid] = {
                "group": group,
                "name": name,
                "endpoint": endpoint,
                "params": base,
                "countries": countries,
                "media_type": mt,
            }

        add("movie", "movie-all", "全部")
        add("movie", "movie-popular", "热门")
        add("movie", "movie-latest", "最新", params={"sort_by": "primary_release_date.desc"})
        add("movie", "movie-rated", "高分", params={"sort_by": "vote_average.desc", "vote_count.gte": "200"})
        add("movie", "cn-movie", "国产", params={"with_original_language": "zh", "with_origin_country": "CN"})
        add("movie", "movie-hktw", "港澳台", countries=["HK", "TW", "MO"])
        add("movie", "movie-western", "欧美", params={"with_original_language": "en"})
        add("movie", "movie-jpkr", "日韩", countries=["JP", "KR"])
        add("movie", "movie-action", "动作", params={"with_genres": "28"})
        add("movie", "movie-comedy", "喜剧", params={"with_genres": "35"})
        add("movie", "movie-romance", "爱情", params={"with_genres": "10749"})
        add("movie", "movie-mystery", "悬疑", params={"with_genres": "9648"})
        add("movie", "movie-scifi", "科幻", params={"with_genres": "878"})
        add("movie", "movie-horror", "恐怖", params={"with_genres": "27"})
        add("movie", "movie-animation", "动画", params={"with_genres": "16"})
        add("movie", "movie-documentary", "纪录片", params={"with_genres": "99"})

        add("series", "series-all", "全部")
        add("series", "series-hot", "热播")
        add("series", "series-latest", "最新", params={"sort_by": "first_air_date.desc"})
        add("series", "series-rated", "高分", params={"sort_by": "vote_average.desc", "vote_count.gte": "200"})
        add("series", "cn-tv", "国产", params={"with_original_language": "zh", "with_origin_country": "CN", "without_genres": "16"})
        add("series", "series-korea", "韩剧", params={"with_origin_country": "KR"})
        add("series", "series-japan", "日剧", params={"with_origin_country": "JP"})
        add("series", "series-western", "欧美", params={"with_original_language": "en"})
        add("series", "series-action", "动作冒险", params={"with_genres": "10759"})
        add("series", "series-comedy", "喜剧", params={"with_genres": "35"})
        add("series", "series-mystery", "悬疑", params={"with_genres": "9648"})
        add("series", "series-crime", "犯罪", params={"with_genres": "80"})
        add("series", "series-scifi", "科幻奇幻", params={"with_genres": "10765"})
        add("series", "series-animation", "动画", params={"with_genres": "16"})
        add("series", "series-documentary", "纪录片", params={"with_genres": "99"})
        add("series", "western-animation", "英文动画", params={"with_genres": "16", "with_original_language": "en"})

        add("anime", "anime-all", "全部", params={"with_genres": "16"})
        add("anime", "anime-cn", "国漫", params={"with_genres": "16", "with_original_language": "zh", "with_origin_country": "CN"})
        add("anime", "anime-japan", "日漫", params={"with_genres": "16", "with_origin_country": "JP"})
        add("anime", "anime-western", "欧美", params={"with_genres": "16", "with_original_language": "en"})
        add("anime", "anime-latest", "最新", params={"with_genres": "16", "sort_by": "first_air_date.desc"})
        add("anime", "anime-rated", "高分", params={"with_genres": "16", "sort_by": "vote_average.desc", "vote_count.gte": "100"})

    # ---------- HTTP ----------
    def fetch(self, url, timeout=12, method="GET", data=None, retries=2):
        last_err = None
        for i in range(retries + 1):
            try:
                if HAS_REQUESTS:
                    if method == "POST":
                        resp = requests.post(
                            url, headers=self.headers, json=data,
                            timeout=timeout, verify=False,
                        )
                    else:
                        resp = requests.get(
                            url, headers=self.headers,
                            timeout=timeout, verify=False,
                        )
                    resp.encoding = "utf-8"
                    if resp.status_code == 200 and resp.text:
                        return resp.text
                    last_err = f"status={resp.status_code}"
                else:
                    body = None
                    if method == "POST":
                        body = json.dumps(data or {}).encode("utf-8")
                        req = Request(url, data=body, headers={
                            **self.headers,
                            "Content-Type": "application/json",
                        })
                    else:
                        req = Request(url, headers=self.headers)
                    with urlopen(req, timeout=timeout) as resp:
                        return resp.read().decode("utf-8", errors="ignore")
            except Exception as e:
                last_err = e
                time.sleep(0.4 * (i + 1))
        print(f"[FETCH ERROR] {url}: {last_err}")
        return ""

    def fetch_json(self, url, timeout=12, method="GET", data=None):
        text = self.fetch(url, timeout, method, data)
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            return {}

    def ok_json(self, obj):
        return json.dumps(obj, ensure_ascii=False)

    def tmdb_poster(self, path):
        if not path:
            return ""
        if str(path).startswith("http"):
            return path
        return self.tmdb_img + path

    def item_to_vod(self, item, source="ranking"):
        if source == "ranking":
            title = item.get("title") or ""
            tmdb_id = str(item.get("tmdbId") or item.get("id") or "")
            media = item.get("mediaType") or "movie"
            pic = self.tmdb_poster(item.get("posterPath") or "")
            remarks = f"{item.get('people', '')}人在看" if item.get("people") else str(media)
            vod_id = f"tmdb_{media}_{tmdb_id}"
        elif source == "quark":
            title = item.get("title") or ""
            pic = item.get("src") or ""
            remarks = item.get("episodes") or item.get("year") or item.get("score") or ""
            vod_id = "quark_" + quote(title)[:100]
        elif source == "collect":
            title = item.get("name") or item.get("title") or ""
            pic = item.get("pic") or ""
            remarks = item.get("remarks") or item.get("year") or ""
            src = item.get("source") or "jl"
            cid = str(item.get("id") or "")
            vod_id = f"col_{src}_{cid}"
        elif source == "tmdb_discover":
            if item.get("media_type"):
                media = item.get("media_type")
            elif "title" in item and "name" not in item:
                media = "movie"
            elif "name" in item:
                media = "tv"
            else:
                media = "movie"
            title = item.get("title") or item.get("name") or ""
            tmdb_id = str(item.get("id") or "")
            pic = self.tmdb_poster(item.get("poster_path") or "")
            remarks = item.get("release_date") or item.get("first_air_date") or ""
            try:
                if item.get("vote_average"):
                    remarks = f"★{round(float(item.get('vote_average')), 1)}"
            except Exception:
                pass
            vod_id = f"tmdb_{media}_{tmdb_id}"
        else:
            media = item.get("media_type") or ("tv" if item.get("name") else "movie")
            title = item.get("title") or item.get("name") or ""
            tmdb_id = str(item.get("id") or "")
            pic = self.tmdb_poster(item.get("poster_path") or "")
            remarks = item.get("release_date") or item.get("first_air_date") or ""
            if item.get("vote_average"):
                remarks = f"★{item.get('vote_average')}"
            vod_id = f"tmdb_{media}_{tmdb_id}"

        return {
            "vod_id": str(vod_id),
            "vod_name": str(title),
            "vod_pic": str(pic),
            "vod_remarks": str(remarks),
        }

    def collect_search(self, keyword, page=1):
        url = f"{self.site_url}/api/proxy.php?action=search&wd={quote(str(keyword))}&page={page}"
        data = self.fetch_json(url)
        return data.get("results") or []

    def collect_detail(self, source, cid):
        url = (
            f"{self.site_url}/api/proxy.php?action=detail"
            f"&source={quote(str(source))}&id={quote(str(cid))}"
        )
        data = self.fetch_json(url)
        details = data.get("details") or []
        return details[0] if details else {}

    def load_parse_routes(self):
        if self._parse_routes_loaded:
            return
        data = self.fetch_json(f"{self.site_url}/api/proxy.php?action=config")
        routes = data.get("official_routes") or []
        parsed = []
        for r in routes:
            api = (r.get("api") or "").strip()
            name = (r.get("name") or "").strip()
            if not api or not name:
                continue
            rtype = (r.get("type") or "iframe").lower()
            # 站内 json/官方限定解析需要网页 authorization，App 不可用
            if rtype == "json" or r.get("official_only"):
                continue
            if not api.startswith("http"):
                continue
            parsed.append({
                "id": r.get("id") or name,
                "name": name,
                "type": rtype,
                "api": api,
            })
        if parsed:
            self.parse_routes = parsed
        self._parse_routes_loaded = True

    def abs_api(self, api):
        if not api:
            return ""
        if api.startswith("http"):
            return api
        return self.site_url + (api if api.startswith("/") else "/" + api)

    def is_official_page(self, url):
        low = (url or "").lower()
        return any(x in low for x in [
            "v.qq.com", "iqiyi.com", "youku.com", "mgtv.com",
            "bilibili.com", "b23.tv", "ixigua.com", "pptv.com",
        ])

    def is_direct_video(self, url):
        low = (url or "").lower()
        return any(x in low for x in [".m3u8", ".mp4", ".flv", ".ts", "/playback/", ".m3u"])

    def build_parse_url(self, route, raw_url):
        api = self.abs_api(route.get("api") or "")
        if not api:
            return raw_url
        if api.endswith("url=") or api.endswith("jx="):
            return api + quote(raw_url, safe="")
        sep = "&" if "?" in api else "?"
        return f"{api}{sep}url={quote(raw_url, safe='')}"

    def expand_with_parsers(self, flag, eps_joined):
        self.load_parse_routes()
        if not eps_joined:
            return []
        first = eps_joined.split("#")[0]
        sample = first.split("$")[-1] if "$" in first else first

        if self.is_direct_video(sample) and not self.is_official_page(sample):
            return [(flag, eps_joined)]

        if self.is_official_page(sample):
            out = []
            for route in self.parse_routes:
                rname = route.get("name") or "解析"
                new_eps = []
                for ep in eps_joined.split("#"):
                    if not ep:
                        continue
                    if "$" in ep:
                        name, url = ep.split("$", 1)
                    else:
                        name, url = "正片", ep
                    new_eps.append(f"{name}${self.build_parse_url(route, url)}")
                if new_eps:
                    out.append((f"{flag}·{rname}", "#".join(new_eps)))
            out.append((f"{flag}·原链", eps_joined))
            return out

        return [(flag, eps_joined)]

    def platform_label(self, url, fallback="官方"):
        u = (url or "").lower()
        if "v.qq.com" in u or "qq.com" in u:
            return "腾讯视频"
        if "bilibili.com" in u or "b23.tv" in u:
            return "B站"
        if "iqiyi.com" in u:
            return "爱奇艺"
        if "youku.com" in u:
            return "优酷"
        if "mgtv.com" in u:
            return "芒果TV"
        return fallback

    def build_play_lists(self, detail, source_name="", source_key=""):
        lines = []
        episodes_groups = detail.get("episodes") or []
        if not episodes_groups:
            raw = detail.get("play_url") or ""
            if raw and isinstance(raw, str) and "$" in raw:
                lines.append((source_name or source_key or "默认", raw.replace("$$$", "#")))
            return lines

        first = episodes_groups[0] if episodes_groups else {}
        if isinstance(first, dict) and "url" in first and "episodes" not in first:
            flag = source_name or source_key or "默认"
            eps = []
            for ep in episodes_groups:
                name = ep.get("name") or "正片"
                u = ep.get("url") or ""
                if u:
                    eps.append(f"{name}${u}")
            if eps:
                lines.append((flag, "#".join(eps)))
            return lines

        for idx, group in enumerate(episodes_groups):
            if not isinstance(group, dict):
                continue
            eps_raw = group.get("episodes") or []
            eps = []
            sample_url = ""
            for ep in eps_raw:
                name = ep.get("name") or "正片"
                u = ep.get("url") or ""
                if u:
                    if not sample_url:
                        sample_url = u
                    eps.append(f"{name}${u}")
            if not eps:
                continue
            flag = group.get("name") or group.get("flag") or ""
            if not flag or flag in ("None", "null"):
                if source_key == "qilin" or (source_name and "官采" in str(source_name)):
                    flag = self.platform_label(sample_url, source_name or f"官方{idx + 1}")
                else:
                    flag = source_name or source_key or f"线路{idx + 1}"
            else:
                if source_name and str(source_name) not in str(flag):
                    flag = f"{source_name}·{flag}"
            lines.append((str(flag), "#".join(eps)))
        return lines

    def pick_collect_rows(self, title):
        results = self.collect_search(title)
        if not results:
            return []
        exact = [r for r in results if (r.get("name") or "").strip() == title.strip()]
        t = title.strip().replace(" ", "")
        fuzzy = []
        if not exact:
            for r in results:
                n = (r.get("name") or "").strip().replace(" ", "")
                if n and (n == t or t in n or n in t):
                    fuzzy.append(r)
        pool = exact if exact else (fuzzy if fuzzy else results)

        by_src = {}
        for r in pool:
            src = r.get("source") or ""
            if not src or not r.get("id"):
                continue
            name = (r.get("name") or "").strip()
            score = 0
            if name == title.strip():
                score += 100
            elif title.strip() in name:
                score += 50
            remarks = r.get("remarks") or ""
            if any(x in remarks for x in ("正片", "HD", "完结", "全")):
                score += 5
            if any(x in name for x in ("解说", "解读", "预告")):
                score -= 50
            prev = by_src.get(src)
            if not prev or score > prev[0]:
                by_src[src] = (score, r)

        ordered = []
        for src in self.source_priority:
            if src in by_src:
                ordered.append(by_src.pop(src)[1])
        for score, r in sorted(by_src.values(), key=lambda x: -x[0]):
            ordered.append(r)
        return ordered

    def tmdb_discover(self, catalog_id, page=1):
        conf = self.catalog.get(catalog_id)
        if not conf:
            return [], 1
        params = dict(conf["params"])
        params["page"] = str(page)
        params["language"] = "zh-CN"
        countries = conf.get("countries")
        if countries:
            params["with_origin_country"] = "|".join(countries)
        endpoint = conf["endpoint"]
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        qs = urlencode(params)
        url = f"{self.site_url}/api/tmdb.php?path={endpoint}&{qs}"
        data = self.fetch_json(url)
        results = data.get("results") or []
        mt = conf.get("media_type") or "movie"
        for r in results:
            r.setdefault("media_type", mt)
        total_pages = int(data.get("total_pages") or 1)
        return results, total_pages

    def filter_values_for_group(self, group):
        vals = []
        for cid, conf in self.catalog.items():
            if conf["group"] == group:
                vals.append({"n": conf["name"], "v": cid})
        return vals

    def _parse_extend(self, extend):
        if isinstance(extend, dict):
            return extend
        if not extend:
            return {}
        if isinstance(extend, str):
            try:
                obj = json.loads(extend)
                return obj if isinstance(obj, dict) else {}
            except Exception:
                return {}
        return {}

    # ---------- 蜂蜜影视接口 ----------
    def homeContent(self, filter):
        try:
            classes = [{"type_id": tid, "type_name": name} for tid, name in self.primary]
            filters = {
                "movie": [{"key": "cate", "name": "分类", "value": self.filter_values_for_group("movie")}],
                "series": [{"key": "cate", "name": "分类", "value": self.filter_values_for_group("series")}],
                "anime": [{"key": "cate", "name": "分类", "value": self.filter_values_for_group("anime")}],
            }
            videos = []
            data = self.fetch_json(f"{self.site_url}/api/ranking.php")
            for item in (data.get("items") or [])[:30]:
                videos.append(self.item_to_vod(item, "ranking"))
            # 兜底：推荐为空时用夸克电视剧
            if not videos:
                data = self.fetch_json(
                    f"{self.site_url}/api/quark-ranking.php?channel={quote('电视剧')}&limit=30"
                )
                for item in (data.get("items") or [])[:30]:
                    videos.append(self.item_to_vod(item, "quark"))
            return self.ok_json({"class": classes, "filters": filters, "list": videos})
        except Exception as e:
            print(f"[homeContent] {e}")
            return self.ok_json({"class": [{"type_id": "recommend", "type_name": "推荐"}], "list": []})

    def homeVideoContent(self):
        try:
            data = self.fetch_json(f"{self.site_url}/api/ranking.php")
            videos = [self.item_to_vod(item, "ranking") for item in (data.get("items") or [])[:40]]
            if not videos:
                data = self.fetch_json(
                    f"{self.site_url}/api/quark-ranking.php?channel={quote('电影')}&limit=40"
                )
                videos = [self.item_to_vod(item, "quark") for item in (data.get("items") or [])[:40]]
            return self.ok_json({"list": videos})
        except Exception as e:
            print(f"[homeVideoContent] {e}")
            return self.ok_json({"list": []})

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if str(pg).isdigit() else 1
            tid = str(tid or "recommend")
            extend = self._parse_extend(extend)
            cate = str(extend.get("cate") or "")
            videos = []
            pagecount = 1
            total = 0

            if tid == "recommend":
                data = self.fetch_json(f"{self.site_url}/api/ranking.php")
                all_v = [self.item_to_vod(item, "ranking") for item in (data.get("items") or [])]
                page_size = 20
                start = (page - 1) * page_size
                videos = all_v[start:start + page_size]
                total = len(all_v)
                pagecount = max(1, (total + page_size - 1) // page_size)

            elif tid.startswith("quark_"):
                channel = tid.replace("quark_", "", 1)
                url = f"{self.site_url}/api/quark-ranking.php?channel={quote(channel)}&limit=60"
                data = self.fetch_json(url)
                all_v = [self.item_to_vod(item, "quark") for item in (data.get("items") or [])]
                page_size = 20
                start = (page - 1) * page_size
                videos = all_v[start:start + page_size]
                total = len(all_v)
                pagecount = max(1, (total + page_size - 1) // page_size)

            elif tid in ("movie", "series", "anime") or tid in self.catalog:
                catalog_id = cate if cate in self.catalog else tid
                if catalog_id not in self.catalog:
                    defaults = {"movie": "movie-all", "series": "series-all", "anime": "anime-all"}
                    catalog_id = defaults.get(tid, "movie-all")
                results, total_pages = self.tmdb_discover(catalog_id, page)
                videos = [self.item_to_vod(item, "tmdb_discover") for item in results]
                pagecount = max(1, min(int(total_pages), 500))
                total = pagecount * max(len(videos), 20)

            elif tid in ("电影", "电视剧", "综艺", "动漫", "短剧"):
                url = f"{self.site_url}/api/quark-ranking.php?channel={quote(tid)}&limit=60"
                data = self.fetch_json(url)
                all_v = [self.item_to_vod(item, "quark") for item in (data.get("items") or [])]
                page_size = 20
                start = (page - 1) * page_size
                videos = all_v[start:start + page_size]
                total = len(all_v)
                pagecount = max(1, (total + page_size - 1) // page_size)

            return self.ok_json({
                "list": videos,
                "page": page,
                "pagecount": pagecount,
                "limit": len(videos) or 20,
                "total": total,
            })
        except Exception as e:
            print(f"[categoryContent] {e}")
            return self.ok_json({"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0})

    def detailContent(self, ids):
        try:
            if not ids:
                return self.ok_json({"list": []})
            # ids 可能是 list 或 逗号分隔字符串
            if isinstance(ids, str):
                ids = [x for x in ids.split(",") if x]
            vod_id = str(ids[0])
            title = ""
            pic = ""
            desc = ""
            remarks = ""
            all_lines = []

            def merge_meta(detail):
                nonlocal title, pic, desc, remarks
                if not title:
                    title = detail.get("name") or detail.get("title") or title
                if not pic:
                    pic = detail.get("pic") or pic
                if not desc:
                    desc = detail.get("content") or detail.get("blurb") or desc
                if not remarks:
                    remarks = detail.get("remarks") or remarks

            if vod_id.startswith("col_"):
                parts = vod_id.split("_", 2)
                if len(parts) >= 3:
                    source, cid = parts[1], parts[2]
                    detail = self.collect_detail(source, cid)
                    if detail:
                        merge_meta(detail)
                        src_name = detail.get("source_name") or source
                        all_lines.extend(self.build_play_lists(detail, src_name, source))
                        if title:
                            for row in self.pick_collect_rows(title):
                                s2, id2 = row.get("source"), row.get("id")
                                if not s2 or not id2:
                                    continue
                                if s2 == source and str(id2) == str(cid):
                                    continue
                                d2 = self.collect_detail(s2, id2)
                                if not d2:
                                    continue
                                merge_meta(d2)
                                all_lines.extend(self.build_play_lists(
                                    d2, d2.get("source_name") or row.get("source_name") or s2, s2
                                ))
            else:
                if vod_id.startswith("quark_"):
                    title = unquote(vod_id.replace("quark_", "", 1))
                elif vod_id.startswith("tmdb_"):
                    parts = vod_id.split("_", 2)
                    if len(parts) == 3:
                        media, tmdb_id = parts[1], parts[2]
                        path = f"/{media}/{tmdb_id}"
                        data = self.fetch_json(
                            f"{self.site_url}/api/tmdb.php?path={path}&language=zh-CN"
                        )
                        if data:
                            title = data.get("title") or data.get("name") or ""
                            pic = self.tmdb_poster(data.get("poster_path") or "")
                            desc = data.get("overview") or ""
                else:
                    title = vod_id

                if title:
                    for row in self.pick_collect_rows(title):
                        s2, id2 = row.get("source"), row.get("id")
                        if not s2 or not id2:
                            continue
                        d2 = self.collect_detail(s2, id2)
                        if not d2:
                            continue
                        merge_meta(d2)
                        all_lines.extend(self.build_play_lists(
                            d2, d2.get("source_name") or row.get("source_name") or s2, s2
                        ))

            expanded = []
            for flag, eps in all_lines:
                if eps:
                    expanded.extend(self.expand_with_parsers(flag, eps))

            seen = set()
            play_from, play_url = [], []
            for flag, eps in expanded:
                if not eps:
                    continue
                base = flag
                n = 1
                while flag in seen:
                    n += 1
                    flag = f"{base}{n}"
                seen.add(flag)
                play_from.append(flag)
                play_url.append(eps)

            if not play_from:
                play_from = ["暂无线路"]
                play_url = ["暂无$http://127.0.0.1/none"]

            vod = {
                "vod_id": vod_id,
                "vod_name": title or vod_id,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_content": desc,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }
            return self.ok_json({"list": [vod]})
        except Exception as e:
            print(f"[detailContent] {e}")
            return self.ok_json({"list": []})

    def searchContent(self, key, quick, pg=1):
        try:
            videos = []
            for item in self.collect_search(key):
                videos.append(self.item_to_vod(item, "collect"))
            data = self.fetch_json(
                f"{self.site_url}/api/tmdb.php?path=/search/multi"
                f"&query={quote(str(key))}&page=1&language=zh-CN"
            )
            for item in (data.get("results") or []):
                if item.get("media_type") in ("movie", "tv"):
                    videos.append(self.item_to_vod(item, "tmdb"))
            seen = set()
            uniq = []
            for v in videos:
                name = v.get("vod_name") or ""
                if name in seen:
                    continue
                seen.add(name)
                uniq.append(v)
            return self.ok_json({"list": uniq})
        except Exception as e:
            print(f"[searchContent] {e}")
            return self.ok_json({"list": []})

    def play_headers_for(self, url):
        low = (url or "").lower()
        ua = self.headers["User-Agent"]
        h = {
            "User-Agent": ua,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if any(x in low for x in ["qq.com", "gtimg.com", "tc.qq.com", "apdcdn", "apd-vlive"]):
            h["Referer"] = "https://v.qq.com/"
            h["Origin"] = "https://v.qq.com"
        elif any(x in low for x in ["bilibili.com", "bilivideo.", "b23.tv", "hdslb.com"]):
            h["Referer"] = "https://www.bilibili.com/"
            h["Origin"] = "https://www.bilibili.com"
        elif any(x in low for x in ["iqiyi.com", "iqiyipic.com", "qy.net"]):
            h["Referer"] = "https://www.iqiyi.com/"
            h["Origin"] = "https://www.iqiyi.com"
        elif any(x in low for x in ["youku.com", "ykimg.com"]):
            h["Referer"] = "https://www.youku.com/"
            h["Origin"] = "https://www.youku.com"
        elif any(x in low for x in ["mgtv.com", "hitv.com"]):
            h["Referer"] = "https://www.mgtv.com/"
            h["Origin"] = "https://www.mgtv.com"
        elif any(x in low for x in ["jimaoys", "mujizy", "qlplayer", "txnp.cn", "im1907"]):
            h["Referer"] = self.site_url + "/"
            h["Origin"] = self.site_url
        else:
            h["Referer"] = self.site_url + "/"
        return h

    def playerContent(self, flag, id, vipFlags):
        try:
            play_url = id or ""
            if not play_url.startswith("http"):
                play_url = urljoin(self.site_url, play_url)
            low = play_url.lower()

            # 站内 4K 页无法在 App 授权，改公共解析
            if "json-player.php" in low:
                try:
                    from urllib.parse import urlparse, parse_qs
                    qs = parse_qs(urlparse(play_url).query)
                    raw = (qs.get("url") or [""])[0]
                    if raw:
                        self.load_parse_routes()
                        route = self.parse_routes[0] if self.parse_routes else {
                            "api": "https://svip.qlplayer.cyou/?url="
                        }
                        play_url = self.build_parse_url(route, raw)
                except Exception:
                    pass

            is_direct = self.is_direct_video(play_url) and not self.is_official_page(play_url)
            headers = self.play_headers_for(play_url)
            header_str = json.dumps(headers, ensure_ascii=False)
            return self.ok_json({
                "parse": 0 if is_direct else 1,
                "jx": "0",
                "playUrl": "",
                "url": play_url,
                "header": header_str,
                "headers": header_str,
            })
        except Exception as e:
            print(f"[playerContent] {e}")
            return self.ok_json({
                "parse": 1,
                "url": id or "",
                "header": json.dumps(self.headers, ensure_ascii=False),
            })

    def localProxy(self, param):
        return self.ok_json({"code": 404})

    def isVideoFormat(self, url):
        return any(fmt in (url or "").lower() for fmt in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass
