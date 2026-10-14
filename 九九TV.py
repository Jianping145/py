# coding=utf-8
"""
九九TV（久久tv）— ok影视 / TVBox Python 源

站点
  APK  com.hdbox.hdhd.tv v5.0.0（业务包 jiujiutv.jiujiu.tv，梆梆加固）
  接口 http://111.170.141.168:89/api.php/gg/*   ← IP 直连，不是域名
  官网 http://www.jiujiu.me（只是展示页，接口不在这）
  片库 约 5 万部，剧集 2404 页

参数名全部实测，别按苹果CMS的习惯猜
  列表 videb?tid=&pg=       tid 不是 type_id；pg 不是 page
       page 传了会被静默忽略，永远返回第 1 页（返回体的 page 字段是回显 pg）
  详情 video_detail?id=     id 不是 vod_id / ids
  搜索 sousuo?text=         text 不是 wd / keyword / kw（试了 9 个名字只这个通）
  搜索不支持分页：pg=2 与 pg=1 返回完全一致 ⇒ 第 2 页起直接返回空，
       否则客户端会堆重复结果
  筛选 year / area / class 服务端真生效（total 会变），lang 恒 0 条
  排序 order / by / sort 全部无效（首条不变）⇒ 不放出来

播放线路（关键）
  加密串不是本地 AES —— 是丢给各线路自己的解析 API。
  我一开始拿 dex 里的密钥常量爆破 rose/NBY/ddsj 全部未命中，方向就错了。
  正解：getJson?name=parse_api 下发 17 条线路的解析配置（api_url 自带 key）。
  用法  <api_url> + urlencode(整个加密串，含前缀)  → JSON.url 就是真播放地址

  实测 / 维护说明
    bfzym3u8 / dyttm3u8  站点常直接给 m3u8 直链，优先使用  parse=0
    qsvip / PAN1 / NBY / rose / CO4K  走 parse_api 解析，带重试
    qq 等官方页  解析失败后交宿主嗅探 parse=1
    BBA/YYNB  常回 "ip未授权"，默认 BLOCKED
    部分加密串尾部带 |签名，已自动剥离再丢给解析 API

配置
  {"key":"jiujiutv","name":"九九TV","type":3,"api":"py_jiujiutv",
   "searchable":1,"quickSearch":1,"filterable":1}

可选 ext
  {"host":"http://111.170.141.168:89","lines":"all","timeout":15}
  host   IP 变了改这里
  lines  all = 连 BBA 这种未授权线路也放出来（不建议）
"""
import json
import sys
import time
from urllib.parse import quote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    HOST = "http://111.170.141.168:89"
    API = "/api.php/gg"

    # 线路白名单。顺序即优先级（直链优先，解析次之）
    # 值 = 显示名
    LINES = [
        ("bfzym3u8", "直链"),
        ("dyttm3u8", "直链2"),
        ("qsvip", "星速"),
        ("PAN1", "盘一"),
        ("NBY", "NBY"),
        ("rose", "玫瑰"),
        ("CO4K", "CO4K"),
        ("qq", "腾讯"),
    ]

    # 默认隐藏的线路（解析 API 经常失败 / IP 白名单 / 官方页无真实地址）
    # 需要时用 ext {"lines":"all"} 强制放出
    # BBA/YYNB 常回 "ip未授权"；jplink/co/NSYS ts 取不到；官方站解析不给直链
    BLOCKED = ("BBA", "jplink", "co", "qiyi", "bilibili",
               "youku", "mgtv", "NSYS", "YYNB")

    def init(self, extend=""):
        self.host = self.HOST
        self.timeout = 15
        self.allow_all = False
        try:
            if extend:
                ext = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(ext, dict):
                    self.host = (ext.get("host") or self.HOST).rstrip("/")
                    self.timeout = int(ext.get("timeout") or 15)
                    if str(ext.get("lines") or "").strip().lower() == "all":
                        self.allow_all = True
        except Exception:
            pass
        # 抓包里 App 用的就是这个 UA
        self.headers = {
            "User-Agent": "okhttp/3.12.13",
            "Accept-Encoding": "gzip",
            "Connection": "Keep-Alive",
        }
        self._nav_cache = None
        self._parse_cache = None
        # 进程内缓存：站点有频率限流，同一 URL 不重复打
        self._cache = {}

    def getName(self):
        return "九九TV"

    def isVideoFormat(self, url):
        return bool(url) and (".m3u8" in url or ".mp4" in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ==================== 请求 ====================

    def _get(self, path, params=None, retries=3):
        """GET 接口。

        站点 89 端口有频率限流：短时间打几百个请求后会直接拒连
        （curl 表现为 http_code=000 且 0.03s 就返回，不是超时）。
        我压测时踩到过，恢复要十几分钟。所以退避要拉长，
        并且做进程内缓存少打无谓请求。
        """
        url = "%s%s/%s" % (self.host, self.API, path.lstrip("/"))
        if params:
            qs = "&".join(
                "%s=%s" % (k, quote(str(v), safe="")) for k, v in params.items()
                if v not in (None, "")
            )
            if qs:
                url += ("&" if "?" in url else "?") + qs

        ck = url
        hit = self._cache.get(ck)
        if hit is not None:
            return hit

        for i in range(retries):
            try:
                r = self.fetch(url, headers=self.headers, timeout=self.timeout)
                if r and getattr(r, "text", None):
                    text = r.text.strip()
                    if not text:
                        raise ValueError("empty body")
                    d = json.loads(text)
                    # 只缓存成功结果，别把限流期的空响应 / code=2 缓存进去
                    if isinstance(d, dict) and d.get("code") != 2:
                        self._cache[ck] = d
                    return d
            except Exception:
                pass
            if i + 1 < retries:
                time.sleep(1.5 + i * 2.0)
        return {}

    def _nav(self):
        if self._nav_cache is None:
            self._nav_cache = (self._get("nav").get("list") or [])
        return self._nav_cache

    def _parse_cfg(self):
        """getJson?name=parse_api —— 17 条线路的解析配置，带 key。"""
        if self._parse_cache is None:
            d = self._get("getJson", {"name": "parse_api"})
            # 正常返回是 { "NBY": {...}, "rose": {...}, ... }，无顶层 code
            # 出错时可能是 {"code":2, "msg":"..."} 或空
            if isinstance(d, dict) and d and "code" not in d:
                self._parse_cache = d
            else:
                self._parse_cache = {}
        return self._parse_cache

    # ==================== 字段 ====================

    @staticmethod
    def _vod(o):
        return {
            "vod_id": o.get("vod_id"),
            "vod_name": o.get("vod_name") or "",
            "vod_pic": o.get("vod_pic") or "",
            "vod_remarks": o.get("vod_remarks") or "",
            "vod_year": str(o.get("vod_year") or ""),
        }

    def _vods(self, items):
        return [self._vod(o) for o in (items or []) if o.get("vod_id")]

    # ==================== 首页 ====================

    def _home_videos(self):
        """首页推荐。

        tuijian 是分组结构（轮播 + 各栏目），但实测摊平去重后只有 6 条，
        首页太空，所以再用剧集/电影第 1 页补到 40 条上下。
        """
        out, seen = [], set()

        def add(o):
            vid = o.get("vod_id")
            if vid and vid not in seen:
                seen.add(vid)
                out.append(self._vod(o))

        for grp in (self._get("tuijian").get("list") or []):
            for o in grp.get("list") or []:
                add(o)

        if len(out) < 30:
            for tid in ("2", "1", "4"):
                for o in (self._get("videb", {"tid": tid, "pg": 1}).get("list") or []):
                    add(o)
                if len(out) >= 45:
                    break
        return out[:60]

    def homeContent(self, filter):
        classes, filters = [], {}
        for x in self._nav():
            tid = str(x.get("type_id") or "")
            if not tid:
                continue
            classes.append({"type_id": tid, "type_name": x.get("type_name") or tid})
            f = self._filters(x)
            if f:
                filters[tid] = f
        return {
            "class": classes,
            "list": self._home_videos(),
            "filters": filters,
        }

    def homeVideoContent(self):
        return {"list": self._home_videos()}

    @staticmethod
    def _filters(navitem):
        """只放 year。

        nav 的 type_extend 里 area/class/lang 是 "11111" 占位符，拿不到真选项；
        version / state 有真值但接口不吃这两个参数。
        """
        te = navitem.get("type_extend") or {}
        years = [y.strip() for y in str(te.get("year") or "").split(",") if y.strip()]
        years = [y for y in years if y.isdigit() and len(y) == 4]
        if not years:
            return []
        return [{
            "key": "year",
            "name": "年份",
            "value": [{"n": "全部", "v": ""}] + [{"n": y, "v": y} for y in years],
        }]

    # ==================== 分类 ====================

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        params = {"tid": tid, "pg": page}
        ext = extend if isinstance(extend, dict) else {}
        for k in ("year", "area", "class"):
            if ext.get(k):
                params[k] = ext[k]

        d = self._get("videb", params)
        items = d.get("list") or []
        return {
            "list": self._vods(items),
            "page": page,
            "pagecount": int(d.get("pagecount") or page),
            "limit": int(d.get("limit") or 21),
            "total": int(d.get("total") or 0),
        }

    # ==================== 详情 ====================

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        o = (self._get("video_detail", {"id": vid}).get("data") or {})
        if not o:
            return {"list": []}

        froms, urls = self._playlines(o)
        vod = {
            "vod_id": o.get("vod_id") or vid,
            "vod_name": o.get("vod_name") or "",
            "vod_pic": o.get("vod_pic") or "",
            "vod_year": str(o.get("vod_year") or ""),
            "vod_area": o.get("vod_area") or "",
            "vod_lang": o.get("vod_lang") or "",
            "vod_remarks": o.get("vod_remarks") or "",
            "vod_actor": o.get("vod_actor") or "",
            "vod_director": o.get("vod_director") or "",
            "type_name": o.get("vod_class") or "",
            "vod_content": (o.get("vod_content") or "").strip(),
            "vod_play_from": "$$$".join(froms),
            "vod_play_url": "$$$".join(urls),
        }
        return {"list": [vod]}

    def _playlines(self, o):
        """挑线路。播放地址里带上 code，playerContent 才知道用哪个解析 API。"""
        order = [c for c, _ in self.LINES]
        names = dict(self.LINES)
        buckets = {}

        players = o.get("vod_url_with_player") or []
        if players:
            for p in players:
                code = str(p.get("code") or "")
                if code:
                    buckets[code] = p.get("url") or ""
        else:
            fs = (o.get("vod_play_from") or "").split("$$$")
            us = (o.get("vod_play_url") or "").split("$$$")
            for i, code in enumerate(fs):
                code = code.strip()
                if code and i < len(us):
                    buckets[code] = us[i]

        froms, urls = [], []
        for code in order + [c for c in buckets if c not in order]:
            if code not in buckets:
                continue
            if not self.allow_all and code in self.BLOCKED:
                continue
            eps = self._episodes(code, buckets[code])
            if eps:
                froms.append(names.get(code) or code)
                urls.append("#".join(eps))
        return froms, urls

    @staticmethod
    def _clean_play_url(url):
        """清理播放串：去掉尾部 |hash / 多余空白，保留前缀加密串或直链。"""
        url = (url or "").strip()
        if "|" in url:
            # 部分线路会在加密串后附加 |签名，解析 API 不认这部分
            url = url.split("|", 1)[0].strip()
        return url

    @staticmethod
    def _episodes(code, raw):
        """拆 name$url，把线路 code 编进播放 id：code@@url"""
        out = []
        for i, seg in enumerate((raw or "").split("#")):
            seg = seg.strip()
            if not seg:
                continue
            if "$" in seg:
                name, url = seg.split("$", 1)
            else:
                name, url = "第%d集" % (i + 1), seg
            url = Spider._clean_play_url(url)
            name = (name.strip() or "第%d集" % (i + 1))
            if url:
                out.append("%s$%s@@%s" % (name, code, url))
        return out

    # ==================== 搜索 ====================

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        # 站点搜索不支持分页，第 2 页起返回空，避免客户端堆重复
        if page > 1:
            return {"list": [], "page": page, "pagecount": 1,
                    "limit": 40, "total": 0}
        items = self._get("sousuo", {"text": key}).get("list") or []
        return {
            "list": self._vods(items),
            "page": 1, "pagecount": 1,
            "limit": len(items) or 40,
            "total": len(items),
        }

    # ==================== 播放 ====================

    def playerContent(self, flag, id, vipFlags):
        raw = id or ""
        code, url = (raw.split("@@", 1) if "@@" in raw else ("", raw))
        url = self._clean_play_url(url)

        # 直链：直接播
        if self.isVideoFormat(url) or url.startswith("http") and (
            ".m3u8" in url or ".mp4" in url or "/index.m3u8" in url
        ):
            return self._play(url, 0)

        real = self._resolve(code, url)
        if real:
            return self._play(real, 0)

        # 解析失败 / 官方站页面：交宿主嗅探
        return self._play(url, 1)

    def _resolve(self, code, url):
        """把加密串丢给对应线路的解析 API，取回真实地址。

        rose / CO4K 共用的那个 API 会间歇 408，所以带重试。
        部分加密串带 |签名，已在 _clean_play_url 去掉。
        """
        if not url or not code:
            return ""
        cfg = (self._parse_cfg().get(code) or {})
        api = cfg.get("api_url")
        if not api or not cfg.get("enable", True):
            return ""
        hdr = cfg.get("headers") or {"User-Agent": "Mozilla/5.0"}
        hdr = {k: v for k, v in hdr.items() if v}
        # 有的 api_url 已经以 url= 结尾，直接拼接编码后的串
        full = api + quote(url, safe="")
        for i in range(3):
            try:
                r = self.fetch(full, headers=hdr,
                               timeout=int(cfg.get("timeout") or 12))
                if r and r.text:
                    j = json.loads(r.text)
                    u = (j.get("url") or j.get("data") or "").strip()
                    if isinstance(u, dict):
                        u = (u.get("url") or "").strip()
                    if u.startswith("http"):
                        return u
                    # code=200 但 msg="ip未授权" / "url不正确" 这类，重试也没用
                    msg = str(j.get("msg") or j.get("message") or "")
                    if msg and ("未授权" in msg or "不正确" in msg or "失败" in msg):
                        return ""
            except Exception:
                pass
            if i + 1 < 3:
                time.sleep(1.5 + i)
        return ""

    def _play(self, url, parse):
        return {
            "parse": parse,
            "url": url,
            "header": {"User-Agent": "Mozilla/5.0"} if parse == 0 else self.headers,
        }

    def localProxy(self, param):
        return [200, {}, ""]
