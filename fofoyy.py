# -*- coding: utf-8 -*-
"""
蜂蜜影视爬虫 - FoFo影院
网站: https://www.fofoyy.com/
v2.6: 详情页不预取 m3u8（动漫多集不再转圈），播放时再解析 sid
"""
import ast
import json
import re
from urllib.parse import urljoin, quote

try:
    import requests
except ImportError:
    requests = None

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def getCache(self, key): return None
        def setCache(self, key, value): return "fail"


class Spider(BaseSpider):

    def __init__(self):
        try:
            super(Spider, self).__init__()
        except Exception:
            pass
        self.site_url = "https://www.fofoyy.com"
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": self.site_url + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.categories = [
            {"type_id": "dianying", "type_name": "电影"},
            {"type_id": "dianshiju", "type_name": "电视剧"},
            {"type_id": "zongyi", "type_name": "综艺"},
            {"type_id": "dongman", "type_name": "动漫"},
        ]
        # 筛选: /{tid}/{type}-{area}-{year}-{sort}
        self._genre_movie = [
            ("全部", "0"), ("剧情", "1"), ("喜剧", "2"), ("动作", "3"), ("爱情", "4"),
            ("科幻", "5"), ("悬疑", "6"), ("惊悚", "7"), ("恐怖", "8"), ("犯罪", "9"),
            ("同性", "10"), ("音乐", "11"), ("歌舞", "12"), ("传记", "13"), ("历史", "14"),
            ("战争", "15"), ("西部", "16"), ("奇幻", "17"), ("冒险", "18"), ("灾难", "19"),
            ("武侠", "20"), ("伦理", "21"),
        ]
        self._genre_zongyi = [
            ("全部", "0"), ("真人秀", "1"), ("脱口秀", "2"), ("纪录片", "3"),
            ("传记", "4"), ("歌舞", "5"),
        ]
        self._area_full = [
            ("全部", "0"), ("中国大陆", "1"), ("美国", "2"), ("香港", "3"), ("台湾", "4"),
            ("日本", "5"), ("韩国", "6"), ("英国", "7"), ("法国", "8"), ("德国", "9"),
            ("意大利", "10"), ("西班牙", "11"), ("印度", "12"), ("泰国", "13"),
            ("俄罗斯", "14"), ("伊朗", "15"), ("加拿大", "16"), ("澳大利亚", "17"),
            ("爱尔兰", "18"), ("瑞典", "19"), ("巴西", "20"), ("丹麦", "21"),
        ]
        self._area_dongman = [
            ("全部", "0"), ("中国大陆", "1"), ("美国", "2"), ("日本", "3"), ("韩国", "4"),
        ]
        self._area_zongyi = [
            ("全部", "0"), ("中国大陆", "1"), ("美国", "2"), ("香港", "3"),
            ("台湾", "4"), ("日本", "5"), ("韩国", "6"),
        ]
        self._years = [
            ("全部", "0"), ("2026", "2026"), ("2025", "2025"), ("2024", "2024"),
            ("2023", "2023"), ("2022", "2022"), ("2021", "2021"), ("2020", "2020"),
            ("2019", "2019"), ("2018", "2018"), ("2017", "2017"), ("2016", "2016"),
            ("2015", "2015"), ("2014", "2014"), ("2013", "2013"), ("2012", "2012"),
            ("2011", "2011"), ("2010", "2010"), ("2009", "2009"), ("2008", "2008"),
            ("2007", "2007"), ("2006", "2006"), ("2005", "2005"), ("其他", "1"),
        ]
        self._sorts = [("按时间", "0"), ("按人气", "1"), ("按评分", "2")]
        self.session = requests.Session() if requests else None
        if self.session:
            self.session.headers.update(self.headers)
        self._sid_cache = {}  # sid -> m3u8，加速重复点播

    def init(self, extend=""):
        return True

    def getName(self):
        return "FoFo影院"

    def _fv(self, pairs):
        return [{"n": n, "v": v} for n, v in pairs]

    def _filters_for(self, tid):
        if tid == "zongyi":
            genres = self._genre_zongyi
            areas = self._area_zongyi
        elif tid == "dongman":
            genres = self._genre_movie
            areas = self._area_dongman
        else:
            genres = self._genre_movie
            areas = self._area_full
        return [
            {"key": "type", "name": "分类", "value": self._fv(genres)},
            {"key": "area", "name": "地区", "value": self._fv(areas)},
            {"key": "year", "name": "年代", "value": self._fv(self._years)},
            {"key": "sort", "name": "排序", "value": self._fv(self._sorts)},
        ]

    def homeContent(self, filter):
        filters = {}
        for c in self.categories:
            filters[c["type_id"]] = self._filters_for(c["type_id"])
        return {"class": self.categories, "filters": filters}

    def _parse_extend(self, extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            extend = extend.strip()
            if not extend:
                return {}
            try:
                obj = json.loads(extend)
                return obj if isinstance(obj, dict) else {}
            except Exception:
                return {}
        return {}

    def homeVideoContent(self):
        try:
            html = self._get(self.site_url)
            return {"list": self._parse_video_list(html)}
        except Exception as e:
            print("homeVideoContent error: %s" % e)
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            try:
                page = int(pg)
            except Exception:
                page = 1
            if page < 1:
                page = 1
            extend = self._parse_extend(extend)
            t = str(extend.get("type") or "0")
            a = str(extend.get("area") or "0")
            y = str(extend.get("year") or "0")
            s = str(extend.get("sort") or "0")
            # 无筛选时走简洁路径；有筛选走 type-area-year-sort
            if t == "0" and a == "0" and y == "0" and s == "0":
                if page == 1:
                    url = "%s/%s" % (self.site_url, tid)
                else:
                    url = "%s/%s/page/%s" % (self.site_url, tid, page)
            else:
                path = "%s/%s-%s-%s-%s" % (tid, t, a, y, s)
                if page == 1:
                    url = "%s/%s" % (self.site_url, path)
                else:
                    url = "%s/%s/page/%s" % (self.site_url, path, page)
            html = self._get(url)
            if not html and page > 1:
                html = self._get("%s?page=%s" % (url.split("/page/")[0], page))
            videos = self._parse_video_list(html)
            page_count = self._extract_page_count(html)
            if page_count < page:
                page_count = page
            return {
                "list": videos,
                "page": page,
                "pagecount": page_count,
                "limit": 30,
                "total": page_count * 30,
            }
        except Exception as e:
            print("categoryContent error: %s" % e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 30, "total": 0}

    def detailContent(self, ids):
        """详情：只解析线路+集数 sid，不预取 m3u8（避免动漫几十集超时转圈）"""
        try:
            video_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
            detail_url = (
                self.site_url + video_id
                if str(video_id).startswith("/")
                else "%s/%s" % (self.site_url, video_id)
            )
            html = self._get(detail_url, timeout=12)
            if not html or len(html) < 500:
                print("[detailContent] empty: %s" % detail_url)
                return {"list": []}

            title = self._extract_title(html)
            pic = self._extract_pic(html)
            desc = self._extract_desc(html)
            remark = self._extract_remark(html)
            play_lines = self._parse_playlist(html)
            print("[detailContent] id=%s lines=%s" % (video_id, len(play_lines)))

            if not play_lines:
                return {"list": [{
                    "vod_id": video_id,
                    "vod_name": title or video_id,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                    "vod_content": desc,
                    "vod_play_from": "FoFo",
                    "vod_play_url": "",
                }]}

            play_from_list = []
            play_url_list = []
            for line_name, episodes in play_lines:
                ep_strs = []
                for idx, (ep_name, sid) in enumerate(episodes):
                    # 每条线路预取第 1 集真实地址，其余点播时再取（兼顾起播速度与多集不转圈）
                    if idx == 0:
                        m3u8 = self._get_source_url(sid, detail_url)
                        if m3u8:
                            ep_strs.append("%s$%s" % (ep_name, m3u8))
                        else:
                            ep_strs.append("%s$__SID__%s" % (ep_name, sid))
                    else:
                        ep_strs.append("%s$__SID__%s" % (ep_name, sid))
                if ep_strs:
                    play_from_list.append(line_name)
                    play_url_list.append("#".join(ep_strs))

            if not play_from_list:
                return {"list": [{
                    "vod_id": video_id,
                    "vod_name": title or video_id,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                    "vod_content": desc,
                    "vod_play_from": "FoFo",
                    "vod_play_url": "",
                }]}

            return {"list": [{
                "vod_id": video_id,
                "vod_name": title or video_id,
                "vod_pic": pic,
                "vod_remarks": remark,
                "vod_content": desc,
                "vod_play_from": "$$$".join(play_from_list),
                "vod_play_url": "$$$".join(play_url_list),
            }]}
        except Exception as e:
            print("detailContent error: %s" % e)
            return {"list": []}

    def _parse_playlist(self, html):
        """解析 urlList = decryptDict({...})"""
        try:
            raw = self._extract_decrypt_dict(html)
            if not raw:
                print("[_parse_playlist] no decryptDict data")
                return []
            try:
                data = ast.literal_eval(raw)
            except Exception as e:
                print("[_parse_playlist] literal_eval fail: %s" % e)
                return []

            def dec(s):
                try:
                    return "".join(chr(ord(c) - 1) for c in s)
                except Exception:
                    return s

            def clean_str(v):
                if not isinstance(v, str):
                    return v
                s = dec(v)
                # unicode_escape: \u91cf\u5b50
                if "\\u" in s:
                    try:
                        s = s.encode("utf-8").decode("unicode_escape")
                    except Exception:
                        try:
                            s = s.encode("latin-1").decode("unicode_escape")
                        except Exception:
                            pass
                s = s.strip().strip('"').strip("'")
                if s.isdigit():
                    try:
                        return int(s)
                    except Exception:
                        return s
                return s

            def walk(o):
                if isinstance(o, dict):
                    return {dec(k) if isinstance(k, str) else k: walk(v) for k, v in o.items()}
                if isinstance(o, list):
                    return [walk(x) for x in o]
                if isinstance(o, str):
                    return clean_str(o)
                return o

            decoded = walk(data)
            sources = decoded.get("source") or []
            url_list = decoded.get("url_list") or []
            print("[_parse_playlist] sources=%s lines=%s" % (sources, len(url_list)))
            if not sources or not url_list:
                return []

            result = []
            for i, line_name in enumerate(sources):
                if i >= len(url_list):
                    break
                name = line_name if isinstance(line_name, str) else str(line_name)
                name = name.strip().strip('"').strip("'") or ("线路%d" % (i + 1))
                episodes = []
                for ep in url_list[i]:
                    if not isinstance(ep, dict):
                        continue
                    ep_name = (
                        ep.get("title")
                        or ep.get("name")
                        or ("第%s集" % (ep.get("episode") if ep.get("episode") is not None else ""))
                        or "正片"
                    )
                    ep_name = str(ep_name).strip().strip('"').strip("'") or "正片"
                    sid = ep.get("sid", "")
                    if sid is None or sid == "":
                        continue
                    episodes.append((ep_name, str(sid).strip()))
                if episodes:
                    result.append((name, episodes))
            return result
        except Exception as e:
            print("_parse_playlist error: %s" % e)
            return []

    def _extract_decrypt_dict(self, html):
        """只取 urlList = decryptDict({...}) 的数据对象，避开函数定义"""
        m = re.search(r"urlList\s*=\s*decryptDict\s*\(\s*(\{)", html)
        if not m:
            m = re.search(r"=\s*decryptDict\s*\(\s*(\{)", html)
        if not m:
            return ""
        start = m.start(1)
        depth = 0
        end = None
        for i, ch in enumerate(html[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            return ""
        return html[start:end]

    def _get_source_url(self, sid, referer_url=""):
        if not sid:
            return ""
        sid = str(sid).strip()
        if sid in self._sid_cache:
            return self._sid_cache[sid]
        try:
            url = "%s/source/" % self.site_url
            ref = referer_url or (self.site_url + "/")
            headers = {
                "User-Agent": self.headers["User-Agent"],
                "Referer": ref,
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Accept": "*/*",
                "Origin": self.site_url,
            }
            # 短超时，失败快速返回
            if self.session:
                r = self.session.post(url, data={"id": sid}, headers=headers, timeout=5)
            else:
                r = requests.post(url, data={"id": sid}, headers=headers, timeout=5)
            result = r.text.strip() if r.status_code == 200 else ""
            if not result:
                return ""
            play = ""
            if ".m3u8" in result or ".mp4" in result or result.startswith("http"):
                play = result
            elif result.startswith("{") or result.startswith("["):
                try:
                    j = json.loads(result)
                    if isinstance(j, dict):
                        for k in ("url", "data", "play_url", "m3u8", "src", "link"):
                            v = j.get(k)
                            if isinstance(v, str) and v:
                                play = v
                                break
                            if isinstance(v, dict) and v.get("url"):
                                play = v["url"]
                                break
                    elif isinstance(j, list) and j:
                        first = j[0]
                        if isinstance(first, str):
                            play = first
                        elif isinstance(first, dict):
                            for k in ("url", "play_url", "m3u8", "src"):
                                if k in first:
                                    play = first[k]
                                    break
                except Exception:
                    pass
            if play:
                if play.startswith("//"):
                    play = "https:" + play
                self._sid_cache[sid] = play
                # 防止缓存无限涨
                if len(self._sid_cache) > 500:
                    try:
                        for _ in range(100):
                            self._sid_cache.pop(next(iter(self._sid_cache)), None)
                    except Exception:
                        self._sid_cache.clear()
                return play
        except Exception as e:
            print("_get_source_url error: %s" % e)
        return ""

    def searchContent(self, key, quick, pg="1"):
        try:
            search_url = "%s/search?q=%s" % (self.site_url, quote(key))
            html = self._get(search_url)
            return {"list": self._parse_video_list(html)}
        except Exception as e:
            print("searchContent error: %s" % e)
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        try:
            play_id = str(id).strip()
            play_headers = {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.site_url + "/",
                "Origin": self.site_url,
                "Accept": "*/*",
                "Connection": "keep-alive",
            }
            if play_id.startswith("__SID__"):
                sid = play_id[len("__SID__"):]
                m3u8 = self._get_source_url(sid, self.site_url + "/")
                if m3u8:
                    return {
                        "parse": 0,
                        "jx": 0,
                        "playUrl": "",
                        "url": m3u8,
                        "header": play_headers,
                    }
                return {"parse": 0, "jx": 0, "playUrl": "", "url": "", "header": {}}

            url = play_id
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = urljoin(self.site_url, url)
            return {
                "parse": 0,
                "jx": 0,
                "playUrl": "",
                "url": url,
                "header": play_headers,
            }
        except Exception as e:
            print("playerContent error: %s" % e)
            return {"parse": 0, "playUrl": "", "url": str(id), "header": {}}

    def _get(self, url, timeout=15):
        try:
            if self.session:
                r = self.session.get(url, timeout=timeout, allow_redirects=True)
            else:
                r = requests.get(url, headers=self.headers, timeout=timeout)
            r.encoding = "utf-8"
            if r.status_code == 200:
                return r.text
        except Exception as e:
            print("_get error: %s %s" % (url, e))
        return ""

    def _parse_video_list(self, html):
        videos = []
        if not html:
            return videos
        pattern = (
            r'<li>.*?<a\s+href="(/[^/]+/(\d+))"[^>]*class="thumbnail"[^>]*>'
            r'.*?<img[^>]*src="([^"]+)"[^>]*class="thumb"[^>]*alt="([^"]*)".*?'
            r'<div class="note"><span>([^<]+)</span></div>'
            r'(?:.*?<div class="countrie"><span class="orange">(\d+)</span>'
            r'<span class="orange">([^<]+)</span></div>)?.*?'
            r'<h2><a[^>]*>([^<]+)</a></h2>.*?<span class="rate">([\d.]+)</span>'
        )
        matches = re.findall(pattern, html, re.S)
        for m in matches:
            try:
                url_path, vid, pic, alt_title, note, year, area, title, rate = m
                pic = self._abs_url(pic)
                remark_parts = []
                if note:
                    remark_parts.append(note)
                if year:
                    remark_parts.append(year)
                if area:
                    remark_parts.append(area)
                if rate and rate != "0.0":
                    remark_parts.append("评分:%s" % rate)
                videos.append({
                    "vod_id": url_path,
                    "vod_name": (title or alt_title).strip(),
                    "vod_pic": pic,
                    "vod_remarks": " ".join(remark_parts),
                })
            except Exception:
                continue
        if not videos:
            simple = re.findall(
                r'<a\s+href="(/[^/]+/(\d+))"[^>]*class="thumbnail"[^>]*>'
                r'.*?<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"',
                html, re.S,
            )
            for m in simple:
                try:
                    url_path, vid, pic, title = m
                    videos.append({
                        "vod_id": url_path,
                        "vod_name": title.strip(),
                        "vod_pic": self._abs_url(pic),
                        "vod_remarks": "",
                    })
                except Exception:
                    continue
        return videos

    def _abs_url(self, pic):
        if not pic:
            return ""
        if pic.startswith("//"):
            return "https:" + pic
        if pic.startswith("/"):
            return urljoin(self.site_url, pic)
        return pic

    def _extract_page_count(self, html):
        max_page = 1
        for p in (r"/page/(\d+)", r"[?&]page=(\d+)"):
            for m in re.findall(p, html or ""):
                try:
                    num = int(m)
                    if num > max_page:
                        max_page = num
                except Exception:
                    pass
        return min(max_page, 999)

    def _extract_title(self, html):
        for p in (
            r'<h1[^>]*class="product-title"[^>]*>(.*?)</h1>',
            r'<h2[^>]*class="product-title"[^>]*>(.*?)</h2>',
            r"<title>(.*?)</title>",
        ):
            m = re.search(p, html or "", re.S)
            if m:
                title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                title = re.sub(r"\s*\(\d+\)\s*", "", title)
                title = re.sub(r"[-_].*?FoFo.*$", "", title)
                title = re.sub(r"[-_].*?在线.*$", "", title)
                return title.strip()
        return ""

    def _extract_pic(self, html):
        for p in (
            r'property="og:image"[^>]*content="([^"]+)"',
            r'<img[^>]*class="[^"]*?thumb[^"]*"[^>]*src="([^"]+)"',
        ):
            m = re.search(p, html or "", re.S)
            if m:
                return self._abs_url(m.group(1))
        return ""

    def _extract_desc(self, html):
        for p in (
            r"剧情简介：<span>(.*?)</span>",
            r'class="[^"]*?desc[^"]*?"[^>]*>(.*?)</div>',
        ):
            m = re.search(p, html or "", re.S)
            if m:
                return re.sub(r"<[^>]+>", "", m.group(1)).strip()[:500]
        return ""

    def _extract_remark(self, html):
        remark = ""
        rate = re.search(r'class="rate">([\d.]+)<', html or "")
        if rate:
            remark = "评分:%s" % rate.group(1)
        note = re.search(r'class="note"><span>([^<]+)</span>', html or "")
        if note:
            remark = ("%s %s" % (remark, note.group(1))).strip()
        return remark

    def localProxy(self, param):
        try:
            url = (param or {}).get("url", "")
            if not url or not self.session:
                return [404, "text/plain", b"Not Found"]
            r = self.session.get(
                url,
                headers={
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.site_url + "/",
                },
                timeout=30,
            )
            ctype = r.headers.get("Content-Type", "application/octet-stream")
            return [r.status_code, ctype, r.content]
        except Exception as e:
            print("localProxy error: %s" % e)
        return [404, "text/plain", b"Not Found"]

    def isVideoFormat(self, url):
        if not url:
            return False
        low = str(url).lower()
        return any(x in low for x in (".m3u8", ".mp4", ".mkv", ".avi", ".flv", ".ts"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass


def getSpider():
    return Spider()
