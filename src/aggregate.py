"""Read-only sensitivity tables; main writes only the two named new outputs."""
from pathlib import Path
import collections
import hashlib
import heapq
import json
import runpy
ROOT = Path(__file__).resolve().parent
RESULT = '46_보류영향과왕신료_조건별비교.json'
DOCUMENT = '09_보류가왕신료비교에미치는영향.md'
PRIMARY = {'발언', '문서', '인용', '문헌 인용', '비발화'}
REPORT = {'발언 보고', '문서 보고'}
METRICS = ('CJK', 'min_positions', 'general_direct', 'expanded_people_relations',
           'semantic_direct', 'semantic_held', 'CJK_in_zero_Min_runs', 'runs')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def rate(numerator, denominator):
    return numerator / denominator * 10000 if denominator else None


def percentage(numerator, denominator):
    return numerator / denominator * 100 if denominator else None


def add(target, source):
    for key in METRICS:
        target[key] += source.get(key, 0)


def holds(E, genre, function):
    e = E is None
    f = function is None and genre not in REPORT
    return {'E_held': e, 'F_held_nonreport': f, 'E_and_F_held_nonreport': e and f,
            'E_known_F_held_nonreport': not e and f, 'unresolved_union': e or f,
            'indirect_report': genre in REPORT}


def layer(E, genre, function):
    if E is None:
        if genre in REPORT:
            return 'E보류_간접보고'
        if function is None:
            return 'E보류_기능보류_비보고'
        return 'E보류_기능있음'
    if genre in REPORT:
        return 'E확정_간접보고'
    if function is None:
        return 'E확정_기능보류_비보고'
    return 'E기능확정_본문층' if genre in PRIMARY else 'E기능확정_기타층'


def reign_group(year):
    if year == 0:
        return '00_즉위년'
    start = (year - 1) // 10 * 10 + 1
    return f'{start:02d}-{start + 9:02d}년'


def compute(data, table03, table13, delta18, scopes, raw_articles, cjk, e_ledger=None):
    """Pure aggregation over supplied objects/iterator; never assigns E/function."""
    positions = data['positions']
    meta = data['metadata']
    by_article = collections.defaultdict(list)
    for p in positions:
        if p['denominator_eligible']:
            by_article[p['article_id']].append(p)
    for pp in by_article.values():
        pp.sort(key=lambda p: p['local_position'])
    scope_iter = iter(scopes['articles'])
    e_reviews = collections.defaultdict(list)
    for r in (e_ledger or {}).get('records', []):
        e_reviews[r['article_id']].append(r)
    cells = collections.defaultdict(collections.Counter)
    annual_cells = collections.defaultdict(collections.Counter)
    article_holds = collections.defaultdict(collections.Counter)
    grouped_articles = collections.defaultdict(set)
    top_runs = []
    excluded = collections.Counter()
    seen_articles = set()
    seen_pids = set()
    zero_literal_Min_articles = set()
    zero_eligible_Min_articles = set()
    serial = 0
    for a in raw_articles:
        aid, raw = a['article_id'], a['raw']
        assert aid not in seen_articles
        seen_articles.add(aid)
        scope = next(scope_iter)
        assert scope["article_id"] == aid
        bodysha = hashlib.sha256(raw.encode('utf-8')).hexdigest()
        assert bodysha == a['body_sha256'] == scope['body_sha256'], aid
        year = int(scope['iso_date'][:4]) - 1724
        pp = by_article.get(aid, [])
        if '民' not in raw:
            zero_literal_Min_articles.add(aid)
        if not pp:
            zero_eligible_Min_articles.add(aid)
        pointer = 0
        runs = scope['exclusive_runs']
        assert runs[0]['span'][0] == 0 and runs[-1]['span'][1] == len(raw)
        assert all(x['span'][1] == y['span'][0] for x, y in zip(runs, runs[1:]))
        nodes = {n['node_id']: n for n in scope['nodes']}
        for run in runs:
            start, stop = run['span']
            assert 0 <= start < stop <= len(raw)
            count = sum(cjk(ch) for ch in raw[start:stop])
            local = []
            while pointer < len(pp) and pp[pointer]['local_position'] < stop:
                p = pp[pointer]
                assert start <= p['local_position']
                local.append(p)
                pointer += 1
            if run['annotation_excluded'] or run['person_name_excluded']:
                assert not local, (aid, run['span'])
                excluded['원주_한자' if run['annotation_excluded'] else '인명_한자'] += count
                continue
            E, genre, function = run['E'], run['genre'], run['function']
            stats = collections.Counter(CJK=count, min_positions=len(local), runs=1,
                                        CJK_in_zero_Min_runs=count if not local else 0)
            for p in local:
                assert raw[p['local_position']] == '民'
                assert p['body_sha256'] == bodysha and p['source_node_id'] == run['node_id']
                assert (p['candidate_source_E'], p['source_genre'], p['candidate_function']) == (E, genre, function)
                assert p['position_id'] not in seen_pids
                seen_pids.add(p['position_id'])
                stats['general_direct'] += p['primary_commoner_comparison'] is True
                stats['expanded_people_relations'] += p['people_reference'] is True
                stats['semantic_direct'] += p['semantic_kind'] == '사람·집단 지칭'
                stats['semantic_held'] += p['people_reference'] is None
            key = (E, genre, function)
            add(cells[key], stats)
            add(annual_cells[(year,) + key], stats)
            if count:
                grouped_articles[(E, genre)].add(aid)
            for flag, active in holds(E, genre, function).items():
                if active:
                    add(article_holds[(flag, aid)], stats)
            if E is None and count:
                n = nodes.get(run['node_id'])
                parent_value = n.get('parent') if n else None
                parent = nodes.get(parent_value) if isinstance(parent_value, str) else None
                overlaps = [r for r in e_reviews.get(aid, [])
                            if r['span'][0] < stop and start < r['span'][1]]
                basis = list(dict.fromkeys(code for r in overlaps for code in r.get('decision_codes', [])))
                if 'COURT' in run.get('rule', ''):
                    basis.append('현재 rule의 명시 COURT 표지')
                if n and '비관료' in str(n.get('role', '')):
                    basis.append('현재 node의 명시 비관료 role')
                item = {
                    'article_id': aid, 'iso_date': scope['iso_date'], 'span': [start, stop],
                    'CJK': count, 'genre': genre, 'function_preserved': function,
                    'rule': run.get('rule'), 'node_id': run['node_id'], 'E_preserved': None,
                    'body_sha256': bodysha, 'eligible_Min_in_run': len(local),
                    'literal_Min_in_article': raw.count('民'),
                    'eligible_Min_in_article': len(pp),
                    'article_literal_Min_zero': '民' not in raw,
                    'E_held_Min_in_article': sum(p['candidate_source_E'] is None for p in pp),
                    'article_intro_120': raw[:120],
                    'run_intro_120': raw[start:min(stop, start + 120)],
                    'before_120': raw[max(0, start - 120):start],
                    'run_end_120': raw[max(start, stop - 120):stop],
                    'after_120': raw[stop:min(len(raw), stop + 120)],
                    'parent_reference_preserved': parent_value,
                    'parent': ({'node_id': parent['node_id'], 'span': parent['span'],
                                'E': parent.get('E'), 'function': parent.get('function'),
                                'rule': parent.get('rule'),
                                'intro_120': raw[parent['span'][0]:min(parent['span'][1], parent['span'][0] + 120)]}
                               if parent else None),
                    'basis_tags_only_no_new_classification': list(dict.fromkeys(basis)),
                    'existing_E123_review_overlap_nodes': [r['node_id'] for r in overlaps],
                    'overlap_does_not_assign_policy_to_other_ranges': True,
                    'new_E_prediction': False,
                }
                serial += 1
                entry = (count, serial, item)
                if len(top_runs) < 20:
                    heapq.heappush(top_runs, entry)
                elif entry[:2] > top_runs[0][:2]:
                    heapq.heapreplace(top_runs, entry)
        assert pointer == len(pp), aid
    assert len(seen_articles) == 36725
    assert next(scope_iter, None) is None
    assert seen_pids == {p['position_id'] for p in positions if p['denominator_eligible']}

    # Independent aggregation checks the existing tables, not source-label accuracy.
    group03 = collections.defaultdict(collections.Counter)
    for (E, genre, function), stats in cells.items():
        add(group03[(E or 'E보류', genre)], stats)
    left03 = {(r['candidate_E'], r['source_genre']): r for r in table03['rows']}
    assert set(group03) == set(left03)
    left13 = {(r['E'], r['갈래']): r for r in table13['rows']}
    for key, stats in group03.items():
        r, q = left03[key], left13[key]
        assert stats['CJK'] == r['분모_한자'] == q['한자분모'], key
        assert stats['min_positions'] == r.get('民_字位置', 0) == q.get('民位置', 0), key
        assert stats['semantic_direct'] == r.get('직접지칭', 0), key
        assert stats['expanded_people_relations'] == r.get('지칭_관계포함', 0) == q.get('확장_사람관계포함', 0), key
        assert stats['general_direct'] == q.get('일반주민_직접지칭', 0), key
        assert len(grouped_articles[(None if key[0] == 'E보류' else key[0], key[1])]) == r['분모기사수'], key
    total = collections.Counter()
    for stats in cells.values():
        add(total, stats)
    assert total['CJK'] == meta['analysis_CJK_denominator'] == delta18['grand_CJK_before'] == delta18['grand_CJK_after']
    assert total['min_positions'] == meta['denominator_eligible_min']
    assert dict(excluded) == meta['excluded_CJK']
    assert sum(s['general_direct'] for (E, g, f), s in cells.items()
               if E is not None and g in PRIMARY and f is not None) == meta['primary_lexical_min']

    strict = lambda E, g, f: E in ('K', 'O') and g in PRIMARY and f is not None
    definitions = [
        ('strict_primary', '현재 엄격 주 비교', strict),
        ('plus_known_E_Fheld', '엄격층+E확정 기능보류 비보고층',
         lambda E, g, f: strict(E, g, f) or E in ('K', 'O') and f is None and g not in REPORT),
        ('Fheld_only', 'E확정 기능보류 비보고층만',
         lambda E, g, f: E in ('K', 'O') and f is None and g not in REPORT),
        ('direct_only', '직접 발화만', lambda E, g, f: strict(E, g, f) and f == '직접 발화'),
        ('document_only', '문서 소개만', lambda E, g, f: strict(E, g, f) and f == '문서 소개'),
        ('quoted_only', '인용 발화만', lambda E, g, f: strict(E, g, f) and f == '인용 발화'),
        ('direct_document', '직접 발화+문서 소개',
         lambda E, g, f: strict(E, g, f) and f in ('직접 발화', '문서 소개')),
    ]
    condition_rows = []
    for condition, label_text, select in definitions:
        owners = {}
        for E in ('K', 'O'):
            stats = collections.Counter()
            for (owner, genre, function), source in cells.items():
                if owner == E and select(owner, genre, function):
                    assert genre not in REPORT
                    add(stats, source)
            owners[E] = {**dict(stats), 'general_direct_per_10000': rate(stats['general_direct'], stats['CJK']),
                         'expanded_people_relations_per_10000': rate(stats['expanded_people_relations'], stats['CJK'])}
        contrasts = {}
        for numerator in ('general_direct', 'expanded_people_relations'):
            K, O = owners['K'], owners['O']
            kr, ore = rate(K.get(numerator, 0), K.get('CJK', 0)), rate(O.get(numerator, 0), O.get('CJK', 0))
            sign = (K.get(numerator, 0) * O.get('CJK', 0) - O.get(numerator, 0) * K.get('CJK', 0)) if K.get('CJK') and O.get('CJK') else None
            contrasts[numerator] = {'K_minus_O_per_10000': kr - ore if kr is not None and ore is not None else None,
                                    'K_divided_by_O': kr / ore if ore else None,
                                    'ordering': None if sign is None else 'K>O' if sign > 0 else 'K<O' if sign < 0 else 'K=O'}
        condition_rows.append({'condition': condition, 'label': label_text, 'owners': owners, 'contrasts': contrasts,
                               'indirect_reports_included': False, 'E_or_function_assigned': False})
    base = condition_rows[0]
    for row in condition_rows:
        for numerator, contrast in row['contrasts'].items():
            old = base['contrasts'][numerator]
            contrast['ordering_changed_from_strict'] = (contrast['ordering'] != old['ordering']
                                                        if contrast['ordering'] and old['ordering'] else None)
            contrast['gap_change_from_strict_per_10000'] = (contrast['K_minus_O_per_10000'] - old['K_minus_O_per_10000']
                                                           if contrast['K_minus_O_per_10000'] is not None and old['K_minus_O_per_10000'] is not None else None)

    burden = collections.defaultdict(collections.Counter)
    disjoint = collections.defaultdict(collections.Counter)
    by_year = collections.defaultdict(collections.Counter)
    by_period = collections.defaultdict(collections.Counter)
    time_total = collections.defaultdict(collections.Counter)
    for (E, genre, function), stats in cells.items():
        add(disjoint[layer(E, genre, function)], stats)
        for flag, active in holds(E, genre, function).items():
            if active:
                add(burden[flag], stats)
    assert sum(v['CJK'] for v in disjoint.values()) == total['CJK']
    assert sum(v['min_positions'] for v in disjoint.values()) == total['min_positions']
    for (year, E, genre, function), stats in annual_cells.items():
        add(time_total[('year', year)], stats)
        add(time_total[('period', reign_group(year))], stats)
        for flag, active in holds(E, genre, function).items():
            if active:
                add(by_year[(year, flag)], stats)
                add(by_period[(reign_group(year), flag)], stats)
    for flag, stats in burden.items():
        articles = [s for (f, aid), s in article_holds.items() if f == flag]
        stats['articles_with_CJK'] = sum(s['CJK'] > 0 for s in articles)
        stats['CJK_in_articles_without_this_held_Min'] = sum(s['CJK'] for s in articles if s['min_positions'] == 0)
        stats['articles_without_this_held_Min'] = sum(s['CJK'] > 0 and s['min_positions'] == 0 for s in articles)
        stats['CJK_in_articles_with_zero_literal_Min'] = sum(s['CJK'] for (f, aid), s in article_holds.items()
                                                            if f == flag and aid in zero_literal_Min_articles)
        stats['CJK_in_articles_with_zero_eligible_Min'] = sum(s['CJK'] for (f, aid), s in article_holds.items()
                                                             if f == flag and aid in zero_eligible_Min_articles)
    coverage = {}
    for metric in ('min_positions', 'CJK'):
        denominator = total[metric]
        coverage[metric] = {
            'total': denominator, 'E_held': burden['E_held'][metric],
            'E_known': denominator - burden['E_held'][metric],
            'E_known_percent': percentage(denominator - burden['E_held'][metric], denominator),
            'F_held_nonreport': burden['F_held_nonreport'][metric],
            'E_known_F_held_nonreport': burden['E_known_F_held_nonreport'][metric],
            'unresolved_union': burden['unresolved_union'][metric],
            'outside_unresolved_union_percent': percentage(denominator - burden['unresolved_union'][metric], denominator),
            'indirect_report_separate': burden['indirect_report'][metric],
            'warning': '분모 통합률 또는 원문 품질의 완성률이 아님; 민 위치와 CJK를 서로 대체하지 않음',
        }
    def time_rows(source, kind):
        out = []
        for (period, flag), stats in sorted(source.items()):
            all_period = time_total[(kind, period)]
            out.append({'period': period, 'scope': flag, **dict(stats),
                        'CJK_percent_of_period': percentage(stats['CJK'], all_period['CJK']),
                        'Min_percent_of_period': percentage(stats['min_positions'], all_period['min_positions']),
                        'CJK_percent_of_scope_total': percentage(stats['CJK'], burden[flag]['CJK']),
                        'Min_percent_of_scope_total': percentage(stats['min_positions'], burden[flag]['min_positions'])})
        return out
    strata = [{'E_preserved': E, 'genre_preserved': g, 'function_preserved': f, **dict(s)}
              for (E, g, f), s in sorted(cells.items(), key=lambda x: tuple('' if v is None else str(v) for v in x[0]))]
    assert burden['E_held']['min_positions'] == meta['source_E_held_min']
    assert burden['F_held_nonreport']['min_positions'] == meta['function_hold_excluding_report_strata']
    assert burden['indirect_report']['min_positions'] == meta['indirect_report_min']
    return {'schema': 'dev103c1_conditional_comparison_v1', 'analysis_version': meta['analysis_version'],
            'purpose': '논문표 입력 준비를 위한 기존 판정의 조건별 집계',
            'E_or_function_values_assigned': False, 'source_or_existing_results_modified': False,
            'independent_performance_evaluation': False,
            'numerator_definitions': {'general_direct': 'primary_commoner_comparison is True; 기존13 주 비교',
                                      'expanded_people_relations': 'people_reference is True; 기존13 확장 비교',
                                      'semantic_direct': 'semantic_kind=사람·집단 지칭; 기존03 대조용'},
            'rate_formula': '해당 조건의 분자 합 / 동일 조건의 마스킹 후 CJK 합 * 10000',
            'same_selection_applied_to_K_and_O_separate_own_denominators': True,
            'total': dict(total), 'excluded_CJK_verified': dict(excluded),
            'coverage_position_and_denominator_separate': coverage,
            'conditions': condition_rows, 'strata_E_genre_function': strata,
            'function_null_within_existing_primary_genres': [
                {'E_preserved': E, 'genre_preserved': g, **dict(s)}
                for (E, g, f), s in cells.items() if E is not None and g in PRIMARY and f is None],
            'group03_13_alone_limits': 'E×갈래 재합산과 E보류 총량은 가능하나, function=null인 기존 primary 갈래 구간이 있으므로 기능확정 엄격표·기능보류 전체 문량·시기 및 民0 노출은 01/02와 원문 좌표가 필요함',
            'burden_overlapping_scopes': {k: dict(v) for k, v in burden.items()},
            'mutually_exclusive_layers': {k: dict(v) for k, v in disjoint.items()},
            'by_reign_year': time_rows(by_year, 'year'),
            'by_ten_reign_years': time_rows(by_period, 'period'),
            'period_definition': '즉위년 별도, 이후1-10·11-20 등 계산용 열 해 묶음; 역사적 시기 판정 아님',
            'E_held_top20_exclusive_runs': [entry[2] for entry in sorted(top_runs, reverse=True)],
            'validation': {'all_03_13_group_numerators_denominators_equal': True,
                           'all_18_total_denominators_equal': True,
                           'all_raw_body_hashes_and_position_links_equal': True,
                           'article_count': len(seen_articles), 'eligible_position_count': len(seen_pids)},
            'interpretation_limit': '조건 사이의 기술적 차이만 측정한다. E보류를 K/O에 배분하지 않으며 새 사료 판정·전체 원문 품질 완성률·최종 역사적 결론을 주장하지 않는다.'}

