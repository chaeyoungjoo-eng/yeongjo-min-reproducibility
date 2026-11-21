"""Verify the published tables. Optionally compare their coordinates to the original XML."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def rows(name):
    with (ROOT / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))

def check(condition, label):
    if not condition:
        raise ValueError(label)

def verify(xml_directory):
    manifest = json.loads((ROOT / "SHA256.json").read_text("utf-8"))
    for name, expected in manifest.items():
        check(sha((ROOT / name).read_bytes()) == expected, name)
    reported = json.loads((ROOT / "paper-counts.json").read_text("utf-8"))
    files = rows("source-xml.csv")
    check(len(files) == 53 and sum(int(f["article_count"]) for f in files) == reported["article_total"], "XML inventory")
    eligible = rows("eligible-positions.csv")
    excluded = rows("excluded-positions.csv")
    positions = {r["위치ID"]: r for r in eligible + excluded}
    check(len(positions) == len(eligible) + len(excluded) == reported["literal_positions"], "unique positions")
    check(len(eligible) == reported["eligible"] and len(excluded) == reported["excluded"], "eligibility")
    check(len({r["기사ID"] for r in positions.values()}) == reported["articles_containing_min"], "articles containing 民")
    check(Counter(r["제외유형"] for r in excluded) == {"인명":169, "악곡명":12, "문서명":10, "서명":9, "원주":5, "지명":3}, "exclusion types")
    serials = {r["일련번호"]: r for r in eligible}
    read = [r for r in eligible if r["문맥판정기록"] == "예"]
    check(len(read) == reported["context_records"] and len({r["기사ID"] for r in read}) == reported["context_articles"], "context records")
    check(len(eligible)-len(read) == reported["unread"], "unread")
    check(sum(int(r["항목확인용례"]) for r in read) == reported["at_least_one_field_checked"], "partial confirmation")
    check(sum(r["귀속"] == "보류" or r["기록기능"] == "H" for r in read) == reported["source_or_function_held"], "held")
    history = rows("verification/development-204.csv")
    linked = [r for r in history if r["원고_적격"] == "1"]
    changed = [r for r in linked if (r["과거저장_귀속"],r["과거저장_기능"]) != (r["원고_귀속"],r["원고_기능"])]
    check(len(history) == 204 and len({r["기사ID"] for r in history}) == 100, "development records")
    check(len(linked) == 203 and len(linked)-len(changed) == 199 and len(changed) == 4, "historical-field comparison")
    check({positions[r["위치ID"]]["일련번호"] for r in changed} == {"37","38","4176","6192"}, "historical differences")
    evidence = rows("verification/development-evidence.csv")
    checks = rows("verification/development-checks.csv")
    check(len(evidence) == 631 and len(checks) == 42 and all(r["passed"] == "True" for r in checks), "stored development checks")
    comparisons = rows("verification/first-and-agreed-55.csv")
    selected = rows("verification/selected-30-articles.csv")
    check(len(selected) == 30 and len(comparisons) == 55, "comparison units")
    check({r["기사ID"] for r in comparisons} == {r["article_id"] for r in selected}, "comparison articles")
    rules = json.loads((ROOT/"verification/comparison-rules.json").read_text("utf-8"))
    for prefix, label in [("", "current_counts"), ("이전규칙_", "previous_counts")]:
        for axis, expected in rules[label].items():
            den = sum(r[prefix+axis+"분모포함"] == "True" for r in comparisons)
            agree = sum(r[prefix+axis+"일치"] == "True" for r in comparisons)
            check((agree,den) == (expected["일치"],expected["분모"]), axis)
    differences = [r for r in comparisons if any(r[axis+"일치"] == "False" for axis in rules["current_counts"])]
    def followed_codex(r):
        return (r["Codex최초_귀속"],r["Codex최초_기능"]) == (r["협의후_귀속"],r["협의후_기능"])
    check(len(differences) == 11 and sum(map(followed_codex, differences)) == 9, "differences after discussion")
    check(sum(map(followed_codex, comparisons)) == 53, "post-agreement comparison")
    for r in rows("cases/paper-table-locations.csv") + rows("cases/case-position-index.csv"):
        check(serials[r["일련번호"]]["기사ID"] == r["기사ID"], "case link")
    relations = rows("cases/status-evidence.csv")
    check(len(relations) == 120 and sum(r["주집계대상"] == "True" for r in relations) == 117, "status evidence records")
    if xml_directory is not None:
        texts = {}
        for f in files:
            raw = (xml_directory/f["file"]).read_bytes()
            check(sha(raw) == f["sha256"], f["file"])
            for article in ElementTree.fromstring(raw).iter("level5"):
                content = article.find("text/content")
                texts[article.attrib["id"]] = "".join(content.itertext()).strip()
        check(len(texts) == reported["article_total"], "XML articles")
        for pid, row in positions.items():
            text = texts[row["기사ID"]]
            offset = int(row["원문위치_0기준"])
            check(text[offset] == "民" and sha(text.encode("utf-8")) == row["본문_SHA256"], pid)
        for r in evidence:
            text = texts[r["위치ID"].split(":")[0]]
            check(text[int(r["시작"]):int(r["끝"])] == r["원문구절"], r["위치ID"])
    print("PASS: published data, manuscript counts, comparisons and case links.")
    if xml_directory is not None:
        print("PASS: 53 source XML hashes, 7,041 coordinates and 631 historical evidence spans.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml-dir", type=Path, help="Directory containing the 53 original XML files")
    verify(parser.parse_args().xml_dir)
