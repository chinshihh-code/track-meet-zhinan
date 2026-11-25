#!/usr/bin/env python3
"""抓臺北市國小分區運動會（南區田徑・乙組）成績，只留指南實小的選手，寫成 results.json。

GitHub Actions 會每 10 分鐘跑一次；也可以手動執行：python fetch_results.py
"""
import json, os, sys, urllib.request, urllib.parse, datetime

BASE = "https://dsport.tp.edu.tw/api"
AREA = 3            # 南區
GROUP = "B"         # 乙組
SCHOOL = "指南"
ROSTER = {"3136", "3137", "3138", "3139", "3141", "4113", "4114", "4115", "4116"}
CTYPE = {"fc": "預賽", "rc": "複賽", "lc": "決賽"}
SEX = {"M": "男", "F": "女"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")


def get(path, **params):
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (track-meet-zhinan)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8-sig"))


def score_rows(item_id, ctype, tm):
    """田徑成績 API。官網用 TmId=性別+組別（例如 FB = 女生乙組），不另外帶 GroupId。
    （11/24 發現：舊寫法 TmId=F&GroupId=B 會一律回傳空陣列。）"""
    variants = [
        dict(AreaId=AREA, TmId=tm + GROUP, ItemId=item_id, Ctype=ctype, Sort="Rank"),
        dict(AreaId=AREA, TmId=tm, ItemId=item_id, Ctype=ctype, GroupId=GROUP, Sort="Rank"),
    ]
    for p in variants:
        try:
            rows = get("spscore/ScoreView", **p)
        except Exception as e:
            print(f"  抓不到 {item_id} {ctype} {tm}：{e.__class__.__name__}")
            continue
        if rows:
            return rows
    return []


def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    old = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            old = {}
    result = {"updated": now.strftime("%Y/%m/%d %H:%M"), "ok": True, "items": old.get("items", {}), "published": old.get("published", [])}
    try:
        posts = get("aditem/ScpostList", AreaId=AREA, SkId="sp", GroupId=GROUP)
    except Exception as e:
        result["ok"] = False
        result["error"] = f"連不到成績網站：{e.__class__.__name__}"
        json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(result["error"])
        return 0
    published = set(result["published"])
    for p in posts:
        for c, rnd in CTYPE.items():
            for tm, sx in SEX.items():
                if not p.get(c + tm):  # fcM / rcF / lcF ... = 這一項成績已公告
                    continue
                key = f"{p['Item']}|{rnd}|{sx}"
                rows = score_rows(p["ItemId"], c.upper(), tm)
                if not rows:
                    print(f"  {key}：已公告但抓不到成績")
                    continue
                ups_known = any((r.get("Ups") or "").strip() for r in rows)
                mine = [r for r in rows if (r.get("Abbname") or "").strip() == SCHOOL
                        and (str(r.get("PlayerNo") or "") in ROSTER or "接力" in p["Item"])]
                result["items"][key] = {
                    "upsKnown": ups_known,
                    "count": len(rows),
                    "rows": [{
                        "no": str(r.get("PlayerNo") or ""), "name": (r.get("Name") or "").replace("<br/>", "、").strip("、 "),
                        "heat": r.get("TmNo"), "lane": r.get("RdNo"),
                        "score": r.get("Score") or "", "wind": r.get("Wind") or "",
                        "rank": r.get("Rank"), "heatRank": r.get("dRank"),
                        "ups": (r.get("Ups") or "").strip(), "remark": (r.get("Remark") or "").strip(),
                    } for r in mine],
                }
                published.add(key)
    result["published"] = sorted(published)
    json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{result['updated']} 已公告 {len(published)} 項")
    return 0


if __name__ == "__main__":
    sys.exit(main())
