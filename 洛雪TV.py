# -*- coding: utf-8 -*-
# 洛雪TV_蜂蜜影视 - 适配真实站点 API
# 网站: https://tv.lxyy.club/
# 列表: ranking / quark / TMDB discover 二级分类
# 播放: /api/proxy.php 采集源直链 m3u8

import requests
import json
from urllib.parse import quote, unquote, urljoin, urlencode

class Spider:

    def __init__(self):
        self.site_url = "https://tv.lxyy.club"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.site_url,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.tmdb_img = "https://image.tmdb.org/t/p/w500"
        self.source_priority = ["jl", "mj", "qilin", "360zy", "dytt", "ik", "md", "fy"]
        # 解析线路（与网页 official_routes 对齐，启动后可从接口刷新）
        self.parse_routes = [
            {"id": "official_default", "name": "默认解析", "type": "iframe",
             "api": "https://svip.qlplayer.cyou/?url="},
            {"id": "official_mugf3fgl", "name": "闪电", "type": "iframe",
             "api": "https://bfq.txnp.cn/excessive?url="},
            {"id": "official_muh2ffwq", "name": "m1907", "type": "iframe",
             "api": "https://im1907.top/?jx="},
            {"id": "official_musbpyqz", "name": "洛雪4K", "type": "json",
             "api": "/json-player.php?route=official_musbpyqz&url="},
            {"id": "official_muh2fkp2", "name": "备用", "type": "json",
             "api": "/json-player.php?route=official_muh2fkp2&url="},
            {"id": "official_mv49v5qz", "name": "备用2", "type": "json",
             "api": "/json-player.php?route=official_mv49v5qz&url="},
        ]
        self._parse_routes_loaded = False

        # 一级分类
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

        # 二级分类（与站点 CESHI_CATALOG_LISTS 一致）
        # id -> {group, name, endpoint, params, countries}
        self.catalog = {}
        self._init_catalog()

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

        # 电影
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

        # 剧集
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

        # 动漫（走 discover/tv + 动画类型）
        add("anime", "anime-all", "全部", params={"with_genres": "16"})
        add("anime", "anime-cn", "国漫", params={"with_genres": "16", "with_original_language": "zh", "with_origin_country": "CN"})
        add("anime", "anime-japan", "日漫", params={"with_genres": "16", "with_origin_country": "JP"})
        add("anime", "anime-western", "欧美", params={"with_genres": "16", "with_original_language": "en"})
        add("anime", "anime-latest", "最新", params={"with_genres": "16", "sort_by": "first_air_date.desc"})
        add("anime", "anime-rated", "高分", params={"with_genres": "16", "sort_by": "vote_average.desc", "vote_count.gte": "100"})

    def fetch(self, url, timeout=15, method="GET", data=None):
        try:
            if method == "POST":
                resp = requests.post(url, headers=self.headers, json=data, timeout=timeout, verify=False)
            else:
                resp = requests.get(url, headers=self.headers, timeout=timeout, verify=False)
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                return resp.text
        except Exception as e:
            print(f"[FETCH ERROR] {url}: {e}")
        return ""

    def fetch_json(self, url, timeout=15, method="GET", data=None):
        text = self.fetch(url, timeout, method, data)
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            return {}

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
            remarks = f"{item.get('people', '')}人在看" if item.get("people") else media
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
            media = item.get("media_type") or ("tv" if item.get("name") else "movie")
            # discover/movie 没有 media_type 字段
            if "title" in item and "name" not in item:
                media = "movie"
            elif "name" in item and "title" not in item:
                media = "tv"
            title = item.get("title") or item.get("name") or ""
            tmdb_id = str(item.get("id") or "")
            pic = self.tmdb_poster(item.get("poster_path") or "")
            remarks = item.get("release_date") or item.get("first_air_date") or ""
            if item.get("vote_average"):
                remarks = f"★{round(float(item.get('vote_average')), 1)}"
            vod_id = f"tmdb_{media}_{tmdb_id}"
        else:  # tmdb search
            media = item.get("media_type") or ("tv" if item.get("name") else "movie")
            title = item.get("title") or item.get("name") or ""
            tmdb_id = str(item.get("id") or "")
            pic = self.tmdb_poster(item.get("poster_path") or "")
            remarks = item.get("release_date") or item.get("first_air_date") or ""
            if item.get("vote_average"):
                remarks = f"★{item.get('vote_average')}"
            vod_id = f"tmdb_{media}_{tmdb_id}"

        return {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": str(remarks),
        }

    def collect_search(self, keyword, page=1):
        url = f"{self.site_url}/api/proxy.php?action=search&wd={quote(keyword)}&page={page}"
        data = self.fetch_json(url)
        return data.get("results") or []

    def collect_detail(self, source, cid):
        url = f"{self.site_url}/api/proxy.php?action=detail&source={quote(str(source))}&id={quote(str(cid))}"
        data = self.fetch_json(url)
        details = data.get("details") or []
        return details[0] if details else {}

    def load_parse_routes(self):
        """从站点配置刷新解析线路"""
        if self._parse_routes_loaded:
            return
        data = self.fetch_json(f"{self.site_url}/api/proxy.php?action=config")
        routes = data.get("official_routes") or []
        if routes:
            parsed = []
            for r in routes:
                api = (r.get("api") or "").strip()
                name = (r.get("name") or "").strip()
                if not api or not name:
                    continue
                parsed.append({
                    "id": r.get("id") or name,
                    "name": name,
                    "type": r.get("type") or "iframe",
                    "api": api,
                    "official_only": bool(r.get("official_only")),
                    "player_codes": r.get("player_codes") or [],
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
            "bilibili.com", "b23.tv", "ixigua.com", "pptv.com", "le.com"
        ])

    def is_direct_video(self, url):
        low = (url or "").lower()
        return any(x in low for x in [".m3u8", ".mp4", ".flv", ".ts", "/playback/", ".m3u"])

    def build_parse_url(self, route, raw_url):
        api = self.abs_api(route.get("api") or "")
        if not api:
            return raw_url
        # api 已含 url= 后缀
        if api.endswith("url=") or api.endswith("jx=") or api.endswith("url="):
            return api + quote(raw_url, safe="")
        sep = "&" if "?" in api else "?"
        return f"{api}{sep}url={quote(raw_url, safe='')}"

    def expand_with_parsers(self, flag, eps_joined):
        """仅对官网页面链接展开解析线路；直链采集源保持单条"""
        self.load_parse_routes()
        if not eps_joined:
            return []
        first = eps_joined.split("#")[0]
        sample = first.split("$")[-1] if "$" in first else first

        # 直链 m3u8/mp4：不展开
        if self.is_direct_video(sample) and not self.is_official_page(sample):
            return [(flag, eps_joined)]

        # 官网播放页：按全部解析接口展开
        if self.is_official_page(sample):
            out = []
            for route in self.parse_routes:
                rname = route.get("name") or "解析"
                new_flag = f"{flag}·{rname}"
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
                    out.append((new_flag, "#".join(new_eps)))
            out.append((f"{flag}·原链", eps_joined))
            return out

        # 未知链接：保留原链 + 全解析展开
        out = [(flag, eps_joined)]
        for route in self.parse_routes:
            rname = route.get("name") or "解析"
            new_flag = f"{flag}·{rname}"
            new_eps = []
            for ep in eps_joined.split("#"):
                if not ep:
                    continue
                if "$" in ep:
                    name, url = ep.split("$", 1)
                else:
                    name, url = "正片", ep
                if self.is_direct_video(url) and not self.is_official_page(url):
                    new_eps.append(f"{name}${url}")
                else:
                    new_eps.append(f"{name}${self.build_parse_url(route, url)}")
            if new_eps:
                out.append((new_flag, "#".join(new_eps)))
        return out

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
        if "ixigua.com" in u:
            return "西瓜视频"
        return fallback

    def build_play_lists(self, detail, source_name="", source_key=""):
        """从单个采集详情提取多条线路，返回 [(flag, eps_joined), ...]"""
        lines = []
        episodes_groups = detail.get("episodes") or []
        if not episodes_groups:
            # 兼容 play_url 字段
            raw = detail.get("play_url") or ""
            if raw and isinstance(raw, str) and "$" in raw:
                lines.append((source_name or source_key or "默认", raw.replace("$$$", "#")))
            return lines

        first = episodes_groups[0] if episodes_groups else {}
        # 扁平单线路
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
                # 官采按平台拆分命名
                if source_key == "qilin" or (source_name and "官采" in source_name):
                    flag = self.platform_label(sample_url, source_name or f"官方{idx+1}")
                else:
                    flag = source_name or source_key or f"线路{idx+1}"
            else:
                # 避免多源同名混淆
                if source_name and source_name not in str(flag):
                    flag = f"{source_name}·{flag}"
            lines.append((str(flag), "#".join(eps)))
        return lines

    def pick_collect_rows(self, title):
        """按源去重，优先精确片名，覆盖全部采集站"""
        results = self.collect_search(title)
        if not results:
            return []
        exact = [r for r in results if (r.get("name") or "").strip() == title.strip()]
        # 次优：标题包含或被包含（去掉空格）
        t = title.strip().replace(" ", "")
        fuzzy = []
        if not exact:
            for r in results:
                n = (r.get("name") or "").strip().replace(" ", "")
                if not n:
                    continue
                if n == t or t in n or n in t:
                    fuzzy.append(r)
        pool = exact if exact else (fuzzy if fuzzy else results)

        # 每个 source 只保留一条（优先精确且 remarks 更好的）
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
            if "解说" in name or "解读" in name or "预告" in name:
                score -= 50
            prev = by_src.get(src)
            if not prev or score > prev[0]:
                by_src[src] = (score, r)

        # 按站点优先级排序
        ordered = []
        for src in self.source_priority:
            if src in by_src:
                ordered.append(by_src.pop(src)[1])
        for score, r in sorted(by_src.values(), key=lambda x: -x[0]):
            ordered.append(r)
        return ordered

    def tmdb_discover(self, catalog_id, page=1):
        """按二级分类拉取 TMDB discover 列表"""
        conf = self.catalog.get(catalog_id)
        if not conf:
            return [], 1

        params = dict(conf["params"])
        params["page"] = str(page)
        params["language"] = "zh-CN"

        # 多国家：简化为 with_origin_country 管道拼接
        countries = conf.get("countries")
        if countries:
            params["with_origin_country"] = "|".join(countries)

        # 站点代理要求 path 单独传，其它参数作为 query
        # 例: /api/tmdb.php?path=/discover/movie&sort_by=popularity.desc&page=1
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

    # ========== 标准接口 ==========

    def homeContent(self, filter):
        classes = [{"type_id": tid, "type_name": name} for tid, name in self.primary]

        # 二级筛选（App 支持 filter 时显示）
        filters = {
            "movie": [{
                "key": "cate",
                "name": "分类",
                "value": self.filter_values_for_group("movie"),
            }],
            "series": [{
                "key": "cate",
                "name": "分类",
                "value": self.filter_values_for_group("series"),
            }],
            "anime": [{
                "key": "cate",
                "name": "分类",
                "value": self.filter_values_for_group("anime"),
            }],
        }

        data = self.fetch_json(f"{self.site_url}/api/ranking.php")
        videos = [self.item_to_vod(item, "ranking") for item in (data.get("items") or [])[:30]]
        return json.dumps({"class": classes, "filters": filters, "list": videos}, ensure_ascii=False)

    def homeVideoContent(self):
        data = self.fetch_json(f"{self.site_url}/api/ranking.php")
        videos = [self.item_to_vod(item, "ranking") for item in (data.get("items") or [])[:40]]
        return json.dumps({"list": videos}, ensure_ascii=False)

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        videos = []
        pagecount = 1
        total = 0

        # extend 可能是 JSON 字符串或 dict
        if isinstance(extend, str):
            try:
                extend = json.loads(extend) if extend else {}
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}

        cate = extend.get("cate") or ""

        # 1) 推荐
        if tid == "recommend":
            data = self.fetch_json(f"{self.site_url}/api/ranking.php")
            all_v = [self.item_to_vod(item, "ranking") for item in (data.get("items") or [])]
            page_size = 20
            start = (page - 1) * page_size
            videos = all_v[start:start + page_size]
            total = len(all_v)
            pagecount = max(1, (total + page_size - 1) // page_size)

        # 2) 夸克榜
        elif str(tid).startswith("quark_"):
            channel = str(tid).replace("quark_", "", 1)
            url = f"{self.site_url}/api/quark-ranking.php?channel={quote(channel)}&limit=60"
            data = self.fetch_json(url)
            all_v = [self.item_to_vod(item, "quark") for item in (data.get("items") or [])]
            page_size = 20
            start = (page - 1) * page_size
            videos = all_v[start:start + page_size]
            total = len(all_v)
            pagecount = max(1, (total + page_size - 1) // page_size)

        # 3) 电影 / 剧集 / 动漫 + 二级分类
        elif tid in ("movie", "series", "anime") or tid in self.catalog:
            catalog_id = cate if cate in self.catalog else tid
            if catalog_id not in self.catalog:
                # 一级入口默认「全部」
                defaults = {"movie": "movie-all", "series": "series-all", "anime": "anime-all"}
                catalog_id = defaults.get(tid, "movie-all")
            results, total_pages = self.tmdb_discover(catalog_id, page)
            videos = [self.item_to_vod(item, "tmdb_discover") for item in results]
            pagecount = max(1, min(int(total_pages), 500))
            total = pagecount * max(len(videos), 20)

        # 4) 兼容旧夸克频道名
        elif tid in ("电影", "电视剧", "综艺", "动漫", "短剧"):
            url = f"{self.site_url}/api/quark-ranking.php?channel={quote(tid)}&limit=60"
            data = self.fetch_json(url)
            all_v = [self.item_to_vod(item, "quark") for item in (data.get("items") or [])]
            page_size = 20
            start = (page - 1) * page_size
            videos = all_v[start:start + page_size]
            total = len(all_v)
            pagecount = max(1, (total + page_size - 1) // page_size)

        return json.dumps({
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos) or 20,
            "total": total,
        }, ensure_ascii=False)

    def detailContent(self, ids):
        if not ids:
            return json.dumps({"list": []}, ensure_ascii=False)

        vod_id = str(ids[0])
        title = ""
        pic = ""
        desc = ""
        remarks = ""
        all_lines = []  # [(flag, url_str), ...]

        def merge_detail_meta(detail):
            nonlocal title, pic, desc, remarks
            if not title:
                title = detail.get("name") or detail.get("title") or title
            if not pic:
                pic = detail.get("pic") or pic
            if not desc:
                desc = detail.get("content") or detail.get("blurb") or desc
            if not remarks:
                remarks = detail.get("remarks") or remarks

        # 1) 采集源直达
        if vod_id.startswith("col_"):
            parts = vod_id.split("_", 2)
            if len(parts) >= 3:
                source, cid = parts[1], parts[2]
                detail = self.collect_detail(source, cid)
                if detail:
                    merge_detail_meta(detail)
                    src_name = detail.get("source_name") or source
                    all_lines.extend(self.build_play_lists(detail, src_name, source))
                    # 用片名再补全其它源
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
                            merge_detail_meta(d2)
                            all_lines.extend(self.build_play_lists(d2, d2.get("source_name") or row.get("source_name") or s2, s2))

        # 2) TMDB / 夸克：标题 -> 全部采集源
        else:
            if vod_id.startswith("quark_"):
                title = unquote(vod_id.replace("quark_", "", 1))
            elif vod_id.startswith("tmdb_"):
                parts = vod_id.split("_", 2)
                if len(parts) == 3:
                    media, tmdb_id = parts[1], parts[2]
                    path = f"/{media}/{tmdb_id}"
                    data = self.fetch_json(f"{self.site_url}/api/tmdb.php?path={path}&language=zh-CN")
                    if data:
                        title = data.get("title") or data.get("name") or ""
                        pic = self.tmdb_poster(data.get("poster_path") or "")
                        desc = data.get("overview") or ""
            else:
                title = vod_id

            if title:
                rows = self.pick_collect_rows(title)
                for row in rows:
                    s2, id2 = row.get("source"), row.get("id")
                    if not s2 or not id2:
                        continue
                    d2 = self.collect_detail(s2, id2)
                    if not d2:
                        continue
                    merge_detail_meta(d2)
                    all_lines.extend(self.build_play_lists(d2, d2.get("source_name") or row.get("source_name") or s2, s2))

        # 官网链接按解析接口展开，再去重
        expanded = []
        for flag, eps in all_lines:
            if not eps:
                continue
            expanded.extend(self.expand_with_parsers(flag, eps))

        seen_flags = set()
        play_from, play_url = [], []
        for flag, eps in expanded:
            if not eps:
                continue
            base = flag
            n = 1
            while flag in seen_flags:
                n += 1
                flag = f"{base}{n}"
            seen_flags.add(flag)
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
        return json.dumps({"list": [vod]}, ensure_ascii=False)


    def searchContent(self, key, quick):
        videos = []
        for item in self.collect_search(key):
            videos.append(self.item_to_vod(item, "collect"))
        data = self.fetch_json(
            f"{self.site_url}/api/tmdb.php?path=/search/multi&query={quote(key)}&page=1&language=zh-CN"
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
        return json.dumps({"list": uniq}, ensure_ascii=False)

    def play_headers_for(self, url):
        """按片源域名返回播放所需请求头（腾讯/B站等 4K 链强依赖 Referer）"""
        low = (url or "").lower()
        ua = self.headers["User-Agent"]
        h = {
            "User-Agent": ua,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        # 腾讯视频 CDN / 页面
        if any(x in low for x in [
            "qq.com", "gtimg.com", "v.qq.com", "video.qq.com",
            "tc.qq.com", "apdcdn", "apd-vlive", "vinfo.ssport.qq.com"
        ]):
            h["Referer"] = "https://v.qq.com/"
            h["Origin"] = "https://v.qq.com"
        # 哔哩哔哩
        elif any(x in low for x in ["bilibili.com", "bilivideo.", "b23.tv", "hdslb.com"]):
            h["Referer"] = "https://www.bilibili.com/"
            h["Origin"] = "https://www.bilibili.com"
        # 爱奇艺
        elif any(x in low for x in ["iqiyi.com", "iqiyipic.com", "qy.net", "video.http.iqiyi"]):
            h["Referer"] = "https://www.iqiyi.com/"
            h["Origin"] = "https://www.iqiyi.com"
        # 优酷
        elif any(x in low for x in ["youku.com", "ykimg.com", "youkutv.com"]):
            h["Referer"] = "https://www.youku.com/"
            h["Origin"] = "https://www.youku.com"
        # 芒果
        elif any(x in low for x in ["mgtv.com", "hitv.com"]):
            h["Referer"] = "https://www.mgtv.com/"
            h["Origin"] = "https://www.mgtv.com"
        # 自营 / 解析站
        elif any(x in low for x in ["jimaoys", "mujizy", "qlplayer", "txnp.cn", "im1907"]):
            h["Referer"] = self.site_url + "/"
            h["Origin"] = self.site_url
        else:
            h["Referer"] = self.site_url + "/"
        return h

    def playerContent(self, flag, id, vipFlags):
        play_url = id or ""
        if not play_url.startswith("http"):
            play_url = urljoin(self.site_url, play_url)

        low = play_url.lower()
        is_parse_api = any(x in low for x in [
            "qlplayer", "txnp.cn", "im1907", "json-player.php",
            "jx=", "parse?url=", "m3u8/?url="
        ])
        is_direct = self.is_direct_video(play_url) and not self.is_official_page(play_url)

        # 直链（含解析后得到的 m3u8）直接播；解析页/官网页交给嗅探
        need_parse = 0 if is_direct else 1

        headers = self.play_headers_for(play_url)

        result = {
            "parse": need_parse,
            "playUrl": "",
            "url": play_url,
            "header": json.dumps(headers),
        }
        # 部分客户端读 headers 字段
        result["headers"] = result["header"]
        return json.dumps(result, ensure_ascii=False)

    def localProxy(self, param):
        return json.dumps({"code": 404}, ensure_ascii=False)

    def isVideoFormat(self, url):
        return any(fmt in (url or "").lower() for fmt in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass
