web_urls = [
    {'小猿众包': [
        ['url', '备注'],
        ['https://xyzb.yuanfudao.com/task/main']
    ]},
    {'知乎': [
        ['url', '备注'],
        ['https://www.zhihu.com/']
    ]},
    {'BOSS直聘': [
        ['url', '备注'],
        ['https://www.zhipin.com/gongsi/'],
        ['https://www.zhipin.com/school/shezhao'],
        ['https://www.zhipin.com/school/jianzhi'],
        ['https://www.zhipin.com/web/geek/jobs?city=101010100&query=%E6%95%B0%E6%8D%AE%E5%88%86%E6%9E%90%E5%B8%88'
         '&jobType=1903']
    ]},
    {'豆果美食': [
        ['url', '备注'],
        ['https://www.douguo.com/jingxuan/0']
    ]},
    {'哔哩哔哩': [
        ['url', '备注'],
        ['https://www.bilibili.com/'],
        [
            'https://upos-sz-estgcos.bilivideo.com/upgcxcode/83/42/34159464283/34159464283-1-16.mp4?e=ig8euxZM2rNcNbRVhwdVhwdlhWdVhwdVhoNvNC8BqJIzNbfq9rVEuxTEnE8L5F6VnEsSTx0vkX8fqJeYTj_lta53NCM=&trid=2a2948e275104557b1981efc47cb641h&oi=0x240e087808fb1efc01475aa60e166fe2&nbs=1&platform=html5&gen=playurlv3&og=cos&mid=0&deadline=1763906034&uipk=5&os=estgcos&upsig=d71949b6a51c1a6e0f7edd41a6ee3cce&uparams=e,trid,oi,nbs,platform,gen,og,mid,deadline,uipk,os&bvc=vod&nettype=0&bw=366258&dl=0&f=h_0_0&agrr=0&buvid=&build=0&orderid=0,1']
    ]}

]

urls = [
    {'name': '小猿众包', 'url': ['https://xyzb.yuanfudao.com/task/main'], '备注': None},
    {'name': '知乎', 'url': ['https://www.zhihu.com/'], '备注': None},
    {'name': 'BOSS直聘', 'url': ['https://www.zhipin.com/gongsi/', 'https://www.zhipin.com/school/shezhao'], '备注': None},
    {'name': '豆果美食', 'url': ['https://www.douguo.com/jingxuan/0'], '备注': None},
    {'name': '哔哩哔哩', 'url': ['https://www.bilibili.com'], '备注': None},
]


def get_urls():
    """从数据库获取网站列表，数据库为空时自动导入硬编码数据"""
    try:
        import json
        from db.session import get_db
        db = get_db()
        websites = db.get_websites()
        if not websites:
            for item in urls:
                urls_json = json.dumps(item['url'], ensure_ascii=False)
                remark = item.get('备注', '') or ''
                db.add_website(item['name'], urls_json, remark)
            websites = db.get_websites()
        result = []
        for w in websites:
            try:
                url_list = json.loads(w["url"])
            except (json.JSONDecodeError, TypeError):
                url_list = [w["url"]]
            result.append({"name": w["name"], "url": url_list, "备注": w["remark"] or None})
        return result
    except Exception:
        pass
    return urls


def get_web_urls():
    """Playwright 格式的网站列表（兼容旧代码）"""
    try:
        import json
        from db.session import get_db
        db = get_db()
        websites = db.get_websites()
        if not websites:
            for item in urls:
                urls_json = json.dumps(item['url'], ensure_ascii=False)
                remark = item.get('备注', '') or ''
                db.add_website(item['name'], urls_json, remark)
            websites = db.get_websites()
        if websites:
            result = []
            for w in websites:
                try:
                    url_list = json.loads(w["url"])
                except (json.JSONDecodeError, TypeError):
                    url_list = [w["url"]]
                result.append({w["name"]: [["url", "备注"], url_list]})
            return result
    except Exception:
        pass
    return web_urls
