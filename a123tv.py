# -*- coding: utf-8 -*-
# A123TV TVBox Spider - 修复播放版
# 关键修复：detail 只收集线路/集数页面 URL，playerContent 再解析 m3u8
# 避免 detail 时并发抓取所有 m3u8 导致超时/失败

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

    def _get(self, url, referer=None):
        try:
            h = dict(self.headers)
            if referer:
                h["Referer"] = referer
            r = requests.get(url, headers=h, timeout=12)
            r.encoding = "utf-8"
            return r.text
        except Exception as e:
            print("GET ERROR:", url, e)
            return ""

    # ==================== 分类 ====================
    def homeContent(self, filter):
        # 一级分类
        classes = [
            {"type_id": "10", "type_name": "电影"},
            {"type_id": "11", "type_name": "连续剧"},
            {"type_id": "12", "type_name": "综艺"},
            {"type_id": "13", "type_name": "动漫"},
            {"type_id": "15", "type_name": "福利"},
        ]
        # 二级分类（筛选）——与官网一致
        filters = {
            "10": [{
                "key": "tid",
                "name": "类型",
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
                "key": "tid",
                "name": "类型",
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
                "key": "tid",
                "name": "类型",
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
                "key": "tid",
                "name": "类型",
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
                "key": "tid",
                "name": "类型",
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

    def homeVideoContent(self):
        html = self._get(self.host + "/")
        return {"list": self._parse_list(html)}

    def categoryContent(self, tid, pg, filter, extend):
        # 筛选二级分类时，extend 里带有实际 type_id
        real_tid = tid
        if extend and isinstance(extend, dict):
            real_tid = extend.get("tid") or tid
        real_tid = str(real_tid)
        # 分页格式：第1页 /t/10.html ，第2页起 /t/10/p2.html
        if str(pg) == "1":
            url = f"{self.host}/t/{real_tid}.html"
        else:
            url = f"{self.host}/t/{real_tid}/p{pg}.html"
        html = self._get(url)
        return {
            "list": self._parse_list(html),
            "page": int(pg) if str(pg).isdigit() else pg,
            "pagecount": 9999,
            "limit": 36,
            "total": 999999
        }

    # ==================== 列表解析 ====================
    def _parse_list(self, html):
        videos = []
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

    # ==================== 详情页基础 ====================
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

    # ==================== 解析页面内嵌 pp.la（全部线路） ====================
    def _parse_pp(self, html):
        """
        解析 var pp={...} ，返回 (vod_no, lines)
        lines: [{id, name, ep_count, m3u8}, ...]
        同 m3u8 只保留第一条（避免 98 条里大量重复源）
        """
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
                # 单集：按 m3u8 去重；多集：按线路 id 保留（集数可能不同）
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
        """根据线路 id + 集数构造选集列表 [(name, play_id), ...]"""
        lid = line["id"]
        ep_count = line["ep_count"]
        m3u8 = line.get("m3u8") or ""

        if ep_count <= 1:
            # 电影/单集：优先直接给 m3u8，播放更快
            if m3u8 and ".m3u8" in m3u8:
                return [("正片", m3u8)]
            page = urljoin(self.host, f"/v/{vod_no}/{lid}z0.html")
            return [("正片", page)]

        # 多集：集地址 /v/{no}/{line_id}z{0,1,2...}.html
        eps = []
        for i in range(ep_count):
            ep_name = f"第{i + 1:02d}集"
            ep_url = urljoin(self.host, f"/v/{vod_no}/{lid}z{i}.html")
            eps.append((ep_name, ep_url))
        return eps

    # ==================== 详情页 ====================
    def detailContent(self, ids):
        vod_id = ids[0]
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
            # 兜底：页面 data-src
            m3u8 = self._extract_m3u8(html)
            if m3u8:
                play_from.append("默认")
                play_url.append(f"正片${m3u8}")
            else:
                play_from.append("默认")
                play_url.append(f"正片${url}")

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url)
        }]}

    # ==================== 提取 m3u8 ====================
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

    # ==================== 搜索 ====================
    def searchContent(self, key, quick):
        try:
            # 站点搜索地址为 /s/{关键词}.html （由前端 JS 拼接）
            url = f"{self.host}/s/{quote(key)}.html"
            html = self._get(url)
            return {"list": self._parse_list(html)}
        except Exception as e:
            print("SEARCH ERROR:", e)
            return {"list": []}

    # ==================== 播放（关键） ====================
    def playerContent(self, flag, id, vipFlags):
        """
        id 现在是播放页 URL（或偶尔直接是 m3u8）
        在这里实时解析 m3u8，并带上正确的 Referer
        """
        try:
            # 已经是 m3u8
            if ".m3u8" in id and id.startswith("http"):
                play_domain = re.match(r'(https?://[^/]+)', id)
                play_ref = (play_domain.group(1) + "/") if play_domain else self.host + "/"
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": id,
                    "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": play_ref
                    }
                }

            # 页面 URL → 抓 m3u8
            page_url = id if id.startswith("http") else urljoin(self.host, id)
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

        # 最后兜底交给嗅探
        return {
            "parse": 1,
            "playUrl": "",
            "url": id,
            "header": self.headers
        }
