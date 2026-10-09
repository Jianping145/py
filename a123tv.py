# -*- coding: utf-8 -*-
# A123TV · 兼容 蜂蜜影视(FongMi) / PeekPro / TVBox / 影视仓
# 修复：FongMi 必需接口、分页、全线路、二级分类

import requests
import re
import json
from urllib.parse import urljoin, quote


class Spider:

    def __init__(self):
        self.host = "https://a123tv.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    # ========== FongMi 必需接口（PeekPro 不强制，缺了 FongMi 会整源空白）==========
    def init(self, extend=""):
        """FongMi 初始化入口，必须存在"""
        try:
            if extend and isinstance(extend, str) and extend.startswith("http"):
                self.host = extend.rstrip("/")
        except Exception:
            pass

    def getName(self):
        return "A123TV"

    def isVideoFormat(self, url):
        if not url:
            return False
        return bool(re.search(r'\.(m3u8|mp4|flv|mkv)(\?|$)', str(url), re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def homeVideoContent(self):
        try:
            html = self._get(self.host + "/")
            return {"list": self._parse_list(html)}
        except Exception as e:
            print("homeVideoContent ERROR:", e)
            return {"list": []}

    # ========== 网络 ==========
    def _get(self, url, referer=None):
        try:
            h = dict(self.headers)
            if referer:
                h["Referer"] = referer
            r = requests.get(url, headers=h, timeout=15)
            r.encoding = "utf-8"
            return r.text
        except Exception as e:
            print("GET ERROR:", url, e)
            return ""

    def _parse_extend(self, extend):
        """FongMi 可能传 dict，也可能传 JSON 字符串"""
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                obj = json.loads(extend)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
        return {}

    # ========== 分类 ==========
    def homeContent(self, filter):
        classes = [
            {"type_id": "10", "type_name": "电影"},
            {"type_id": "11", "type_name": "连续剧"},
            {"type_id": "12", "type_name": "综艺"},
            {"type_id": "13", "type_name": "动漫"},
            {"type_id": "15", "type_name": "福利"},
        ]
        filters = {
            "10": [{
                "key": "tid", "name": "类型",
                "value": [
                    {"n": "全部电影", "v": "10"},
                    {"n": "动作片", "v": "1001"},
                    {"n": "喜剧片", "v": "1002"},
                    {"n": "爱情片", "v": "1003"},
                    {"n": "科幻片", "v": "1004"},
                    {"n": "恐怖片", "v": "1005"},
                    {"n": "剧情片", "v": "1006"},
                    {"n": "战争片", "v": "1007"},
                    {"n": "纪录片", "v": "1008"},
                    {"n": "动漫电影", "v": "1010"},
                    {"n": "奇幻片", "v": "1011"},
                    {"n": "动画片", "v": "1013"},
                    {"n": "犯罪片", "v": "1014"},
                    {"n": "悬疑片", "v": "1016"},
                    {"n": "邵氏电影", "v": "1019"},
                    {"n": "歌舞片", "v": "1022"},
                    {"n": "家庭片", "v": "1024"},
                    {"n": "古装片", "v": "1025"},
                    {"n": "历史片", "v": "1026"},
                    {"n": "4K电影", "v": "1027"},
                ]
            }],
            "11": [{
                "key": "tid", "name": "类型",
                "value": [
                    {"n": "全部连续剧", "v": "11"},
                    {"n": "国产剧", "v": "1101"},
                    {"n": "香港剧", "v": "1102"},
                    {"n": "台湾剧", "v": "1105"},
                    {"n": "韩国剧", "v": "1103"},
                    {"n": "欧美剧", "v": "1104"},
                    {"n": "日本剧", "v": "1106"},
                    {"n": "泰国剧", "v": "1108"},
                    {"n": "港台剧", "v": "1110"},
                    {"n": "日韩剧", "v": "1111"},
                    {"n": "海外剧", "v": "1107"},
                ]
            }],
            "12": [{
                "key": "tid", "name": "类型",
                "value": [
                    {"n": "全部综艺", "v": "12"},
                    {"n": "内地综艺", "v": "1201"},
                    {"n": "港台综艺", "v": "1202"},
                    {"n": "日韩综艺", "v": "1203"},
                    {"n": "欧美综艺", "v": "1204"},
                    {"n": "国外综艺", "v": "1205"},
                ]
            }],
            "13": [{
                "key": "tid", "name": "类型",
                "value": [
                    {"n": "全部动漫", "v": "13"},
                    {"n": "国产动漫", "v": "1301"},
                    {"n": "日韩动漫", "v": "1302"},
                    {"n": "欧美动漫", "v": "1303"},
                    {"n": "海外动漫", "v": "1305"},
                    {"n": "里番", "v": "1307"},
                ]
            }],
            "15": [{
                "key": "tid", "name": "类型",
                "value": [
                    {"n": "全部福利", "v": "15"},
                    {"n": "韩国情色片", "v": "1551"},
                    {"n": "日本情色片", "v": "1552"},
                    {"n": "大陆情色片", "v": "1555"},
                    {"n": "香港情色片", "v": "1553"},
                    {"n": "台湾情色片", "v": "1554"},
                    {"n": "美国情色片", "v": "1556"},
                    {"n": "欧洲情色片", "v": "1557"},
                    {"n": "印度情色片", "v": "1558"},
                    {"n": "东南亚情色片", "v": "1559"},
                    {"n": "其它情色片", "v": "1550"},
                ]
            }],
        }
        return {"class": classes, "filters": filters}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            ext = self._parse_extend(extend)
            real_tid = str(ext.get("tid") or tid)
            if str(pg) == "1":
                url = f"{self.host}/t/{real_tid}.html"
            else:
                url = f"{self.host}/t/{real_tid}/p{pg}.html"
            html = self._get(url)
            videos = self._parse_list(html)
            return {
                "list": videos,
                "page": int(pg) if str(pg).isdigit() else 1,
                "pagecount": 9999,
                "limit": 36,
                "total": 999999
            }
        except Exception as e:
            print("categoryContent ERROR:", e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 36, "total": 0}

    def _parse_list(self, html):
        videos = []
        if not html:
            return videos
        try:
            pattern = re.compile(
                r'<a class="w4-item" href="([^"]+)".*?'
                r'<img data-src="([^"]+)" alt="([^"]+)".*?'
                r'<div class="i">([^<]*)</div>', re.S)
            for m in pattern.finditer(html):
                href, pic, name, info = m.groups()
                if pic.startswith("//"):
                    pic = "https:" + pic
                elif not pic.startswith("http"):
                    pic = urljoin(self.host, pic)
                year = ""
                ym = re.search(r'(\d{4})年', info)
                if ym:
                    year = ym.group(1)
                videos.append({
                    "vod_id": href,
                    "vod_name": name.strip(),
                    "vod_pic": pic,
                    "vod_remarks": info.strip(),
                    "vod_year": year
                })
        except Exception as e:
            print("PARSE LIST ERROR:", e)
        return videos

    def _parse_detail_base(self, html):
        name = ""
        m = re.search(r'<h1>([^<]+)</h1>', html)
        if m:
            name = m.group(1).strip()
        if not name:
            m = re.search(r'<div class="t" title="([^"]+)"', html)
            if m:
                name = m.group(1)
        if not name:
            m = re.search(r'<title>《?([^》<|-]+)', html)
            if m:
                name = m.group(1).strip()

        pic = ""
        m = re.search(r'data-poster="([^"]+)"', html)
        if m:
            pic = m.group(1)
        if not pic:
            m = re.search(r'og:image"\s+content="([^"]+)"', html)
            if m:
                pic = m.group(1)
        if pic.startswith("//"):
            pic = "https:" + pic
        elif pic and not pic.startswith("http"):
            pic = urljoin(self.host, pic)

        desc = ""
        m = re.search(r'<meta name="description" content="([^"]+)"', html)
        if m:
            desc = m.group(1).strip()
        return name, pic, desc

    def _parse_pp(self, html):
        try:
            m = re.search(r'var\s+pp\s*=\s*(\{.*?\});\s*</script>', html, re.S)
            if not m:
                m = re.search(r'var\s+pp\s*=\s*(\{.*?\});', html, re.S)
            if not m:
                return None, []
            data = json.loads(m.group(1))
            vod_no = data.get("no") or ""
            la = data.get("la") or []
            lines = []
            seen_m3u8 = set()
            seen_id = set()
            for item in la:
                if not isinstance(item, (list, tuple)) or len(item) < 5:
                    continue
                lid = str(item[0])
                lname = str(item[1]).strip() or "线路"
                try:
                    ep_count = int(item[2])
                except Exception:
                    ep_count = 1
                m3u8 = str(item[4]).strip() if item[4] else ""
                if not lid or lid in seen_id:
                    continue
                if ep_count <= 1 and m3u8:
                    if m3u8 in seen_m3u8:
                        continue
                    seen_m3u8.add(m3u8)
                seen_id.add(lid)
                lines.append({
                    "id": lid,
                    "name": lname,
                    "ep_count": max(ep_count, 1),
                    "m3u8": m3u8,
                })
            return vod_no, lines
        except Exception as e:
            print("PARSE PP ERROR:", e)
            return None, []

    def _build_episodes(self, vod_no, line):
        lid = line["id"]
        ep_count = line["ep_count"]
        m3u8 = line.get("m3u8") or ""
        if ep_count <= 1:
            if m3u8 and ".m3u8" in m3u8:
                return [("正片", m3u8)]
            page = urljoin(self.host, f"/v/{vod_no}/{lid}z0.html")
            return [("正片", page)]
        eps = []
        for i in range(ep_count):
            ep_name = f"第{i + 1:02d}集"
            ep_url = urljoin(self.host, f"/v/{vod_no}/{lid}z{i}.html")
            eps.append((ep_name, ep_url))
        return eps

    def _extract_m3u8(self, html):
        if not html:
            return None
        m = re.search(r'data-src="([^"]+\.m3u8[^"]*)"', html)
        if m:
            return m.group(1).strip()
        m = re.search(r'(https?://[^"\'\s<>]+\.m3u8[^"\'\s<>]*)', html)
        if m:
            return m.group(1).strip()
        return None

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, (list, tuple)) else ids
            url = urljoin(self.host, vod_id)
            html = self._get(url)
            if not html:
                return {"list": []}

            name, pic, desc = self._parse_detail_base(html)
            vod_no, lines = self._parse_pp(html)

            play_from = []
            play_url = []
            used_names = {}

            if lines and vod_no:
                for line in lines:
                    base_name = line["name"]
                    if base_name in used_names:
                        used_names[base_name] += 1
                        show_name = f"{base_name}({used_names[base_name]})"
                    else:
                        used_names[base_name] = 1
                        show_name = base_name
                    eps = self._build_episodes(vod_no, line)
                    if not eps:
                        continue
                    ep_list = [f"{ep_name}${ep_id}" for ep_name, ep_id in eps]
                    play_from.append(show_name)
                    play_url.append("#".join(ep_list))
            else:
                m3u8 = self._extract_m3u8(html)
                play_from.append("默认")
                play_url.append(f"正片${m3u8 if m3u8 else url}")

            return {"list": [{
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_content": desc,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url)
            }]}
        except Exception as e:
            print("detailContent ERROR:", e)
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            url = f"{self.host}/s/{quote(str(key))}.html"
            html = self._get(url)
            return {"list": self._parse_list(html)}
        except Exception as e:
            print("SEARCH ERROR:", e)
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        try:
            play_id = str(id) if id else ""
            if ".m3u8" in play_id and play_id.startswith("http"):
                play_domain = re.match(r'(https?://[^/]+)', play_id)
                play_ref = (play_domain.group(1) + "/") if play_domain else self.host + "/"
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": play_id,
                    "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": play_ref
                    }
                }

            page_url = play_id if play_id.startswith("http") else urljoin(self.host, play_id)
            html = self._get(page_url, referer=self.host + "/")
            m3u8 = self._extract_m3u8(html)
            if m3u8:
                play_domain = re.match(r'(https?://[^/]+)', m3u8)
                play_ref = (play_domain.group(1) + "/") if play_domain else self.host + "/"
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": m3u8,
                    "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": play_ref
                    }
                }
        except Exception as e:
            print("PLAYER ERROR:", e)

        return {
            "parse": 1,
            "playUrl": "",
            "url": str(id) if id else "",
            "header": self.headers
        }
