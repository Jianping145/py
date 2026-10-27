# -*- coding: utf-8 -*-
import re, sys, json, base64
from Crypto.Cipher import AES
from urllib.parse import urljoin, quote
from Crypto.Util.Padding import unpad
from base.spider import Spider

sys.path.append('..')


class Spider(Spider):
    headers = {'User-Agent': 'okhttp/4.12.0'}
    parse_headers = {'User-Agent': 'okhttp-okgo/jeasonlzy'}

    FIXED_CONFIG = {
        'host': 'http://cms.lyyytv.cn',
        'cmskey': 'wP5bvxoc3yv7FoBQENFZuAF0EUYr4LTy',
        'RawPlayUrl': 0,
        # 原解析接口已失效，保留方便以后替换
        'parse_api': 'http://61.184.23.217:6163/api/index?parsesId=4&appid=10001&videoUrl='
    }

    def init(self, extend=''):
        self.host = self.FIXED_CONFIG['host']
        self.cmskey = self.FIXED_CONFIG.get('cmskey', '')
        self.parse_api = self.FIXED_CONFIG.get('parse_api', '')
        self.raw_play_url = 1 if self.FIXED_CONFIG.get('RawPlayUrl', 0) == 1 else 0

    def ldmax_decrypt(self, encrypted_base64, depth=0):
        if depth > 5:
            return None
        cleaned = re.sub(r'\s+', '', encrypted_base64)
        try:
            decoded = base64.b64decode(cleaned, validate=True).decode('utf-8', errors='ignore')
        except Exception:
            return encrypted_base64
        url = re.sub(r'\s+', '', decoded)
        if 'ldmax.cooom' not in url:
            return url
        path = re.sub(r'https?://ldmax\.cooom/', '', url)
        if len(path) < 16:
            return None
        key = path[:16][::-1].encode('utf-8')
        ciphertext_b64 = re.sub(r'\s+', '', path[16:])
        try:
            ciphertext = base64.b64decode(ciphertext_b64, validate=True)
        except Exception:
            return None
        try:
            cipher = AES.new(key, AES.MODE_CBC, key)
            decrypted = cipher.decrypt(ciphertext)
        except Exception:
            return None
        if decrypted:
            pad = decrypted[-1]
            if 0 < pad <= 16:
                decrypted = decrypted[:-pad]
        result = decrypted.decode('utf-8', errors='ignore').strip()
        if 'ldmax.cooom' in result:
            return self.ldmax_decrypt(base64.b64encode(result.encode('utf-8')).decode('utf-8'), depth + 1)
        return result

    def ldmax_parse(self, video_url):
        decrypted = self.ldmax_decrypt(video_url)
        if not decrypted or not re.match(r'^https?://', decrypted):
            return None
        try:
            parse_url = self.parse_api + quote(decrypted, safe='')
            resp = self.fetch(parse_url, headers=self.parse_headers, timeout=12).json()
        except Exception:
            return None
        if not resp or resp.get('code') != 200 or not resp.get('url'):
            return None
        final_url = self.ldmax_decrypt(resp['url'])
        if final_url and re.match(r'^https?://', final_url):
            return {'url': final_url, 'type': resp.get('type', 'video')}
        return None

    def homeVideoContent(self):
        data = self.fetch(f"{self.host}/api.php/app/index_video?token=", headers=self.headers).json()
        videos = []
        for item in data.get('list', []):
            videos.extend(item.get('vlist', []))
        return {'list': videos}

    def homeContent(self, filter):
        data = self.fetch(f"{self.host}/api.php/app/nav?token=", headers=self.headers).json()
        keys = ["class", "area", "lang", "year", "letter", "by", "sort"]
        filters = {}
        classes = []

        for item in data.get('list', []):
            has_non_empty_field = False
            jsontype_extend = item.get("type_extend") or {}
            classes.append({"type_name": item["type_name"], "type_id": item["type_id"]})

            for key in keys:
                if key in jsontype_extend and str(jsontype_extend[key]).strip() != "":
                    has_non_empty_field = True
                    break

            if has_non_empty_field:
                filters[str(item["type_id"])] = []

            for dkey in jsontype_extend:
                if dkey in keys and str(jsontype_extend[dkey]).strip() != "":
                    values = str(jsontype_extend[dkey]).split(",")
                    value_array = [{"n": v.strip(), "v": v.strip()} for v in values if v.strip()]
                    filters[str(item["type_id"])].append({"key": dkey, "name": dkey, "value": value_array})

        return {"class": classes, "filters": filters}

    def categoryContent(self, tid, pg, filter, extend):
        query_params = [f"tid={tid}", f"pg={pg}", "limit=18"]
        if extend.get('class'):
            query_params.append(f"class={extend.get('class')}")
        if extend.get('area'):
            query_params.append(f"area={extend.get('area')}")
        if extend.get('lang'):
            query_params.append(f"lang={extend.get('lang')}")
        if extend.get('year'):
            query_params.append(f"year={extend.get('year')}")

        url = f"{self.host}/api.php/app/video?" + "&".join(query_params)
        data = self.fetch(url, headers=self.headers).json()
        return data

    def searchContent(self, key, quick, pg="1"):
        data = self.fetch(f"{self.host}/api.php/app/search?text={key}&pg={pg}", headers=self.headers).json()
        videos = data.get('list', [])
        for item in videos:
            item.pop('type', None)
        return {'list': videos, 'page': pg}

    def detailContent(self, ids):
        data = self.fetch(f"{self.host}/api.php/app/video_detail?id={ids[0]}", headers=self.headers).json()['data']
        show, paly_urls = [], []

        for i in data.get('vod_url_with_player', []):
            urls = i['url'].split('#')
            urls2 = []
            for j in urls:
                if j:
                    url = j.split('$', 1)
                    urls2.append(f"{url[0]}${self.lvdou(url[1])}")
            paly_urls.append('#'.join(urls2))
            show.append(i['name'].strip())

        data.pop('vod_url_with_player', None)
        data['vod_play_from'] = '$$$'.join(show)
        data['vod_play_url'] = '$$$'.join(paly_urls)
        return {'list': [data]}

    def playerContent(self, flag, video_id, vipFlags):
        # 只清理明确错误的编码，保留正常中文百分号编码
        video_id = video_id.replace('%26', '&').replace('%20', ' ')

        is_plain = video_id.startswith(('http://', 'https://'))
        is_lyyy = is_plain and 'lyyytv.cn' in video_id
        is_direct = self.check_paly_url(video_id)

        # 1. 尝试内置 ldmax 解析（针对加密或本站伪直链）
        if (not is_plain) or is_lyyy:
            parsed = self.ldmax_parse(video_id)
            if parsed and parsed.get('url'):
                return {
                    'parse': 0,
                    'jx': 0,
                    'playUrl': '',
                    'url': parsed['url'],
                    'header': self.headers
                }

        # 2. 真正的媒体直链 → 直接播放
        if is_direct:
            return {
                'parse': 0,
                'jx': 0,
                'playUrl': '',
                'url': video_id,
                'header': self.headers
            }

        # 3. 其他情况（官方分享页 / 伪直链解析失败）→ 强制走嗅探/解析
        # 蜂蜜影视必须靠 parse=1 才会真正进入 WebView 嗅探，只写 jx=1 经常直接跳过
        return {
            'parse': 1,          # 关键：强制解析/嗅探
            'jx': 1,
            'playUrl': '',
            'url': video_id,
            'header': {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 12; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                'Referer': video_id.split('/')[0] + '//' + video_id.split('/')[2] + '/' if is_plain else ''
            }
        }

    def lvdou(self, text):
        key = self.cmskey[:16].encode("utf-8")
        iv = self.cmskey[-16:].encode("utf-8")
        original_text = text
        url_prefix = "lvdou+"

        if original_text.startswith(url_prefix):
            ciphertext_b64 = original_text[len(url_prefix):]
            try:
                cipher = AES.new(key, AES.MODE_CBC, iv)
                ct_bytes = base64.b64decode(ciphertext_b64)
                pt_bytes = cipher.decrypt(ct_bytes)
                return unpad(pt_bytes, AES.block_size).decode('utf-8')
            except Exception:
                return original_text
        return original_text

    def raw_url(self, original_url):
        try:
            response = self.fetch(original_url, allow_redirects=False, stream=True, timeout=15)
            if 300 <= response.status_code < 400:
                loc = response.headers.get('Location')
                if loc:
                    return urljoin(original_url, loc)
            return original_url
        except Exception:
            return original_url

    def check_paly_url(self, content):
        # 严格匹配真实媒体后缀，不再把 lyyytv.cn 当成直链
        pattern = r'https?://[^\s"\']+\.(?:mp4|m3u8|flv|avi|mkv|ts|mov|wmv|webm)(?:\?|$|&|#)'
        return bool(re.search(pattern, content, re.IGNORECASE))

    def getName(self):
        return '影探4K'

    def localProxy(self, param):
        pass

    def isVideoFormat(self, url):
        return self.check_paly_url(url)

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass
