"""Recompute published counts from frozen source labels; Python 3.10+, stdlib only."""
from pathlib import Path
from collections import defaultdict
from fractions import Fraction
import sys,json,gzip,hashlib
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
import aggregate

def load(p):
    with (gzip.open(p,'rt',encoding='utf8') if str(p).endswith('.gz') else p.open(encoding='utf8')) as f:return json.load(f)
def lines(p):
    with gzip.open(p,'rt',encoding='utf8') as f:
        for line in f:
            if line.strip():yield json.loads(line)
def scopes():
    for p in sorted((ROOT/'data').glob('scopes-*.jsonl.gz')):yield from lines(p)
def cjk(ch):return '\u3400'<=ch<='\u9fff' or '\U00020000'<=ch<='\U0002fa1f'
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def extrema(d0,m0,gg):
    out={}
    for label,reverse in [('minimum',False),('maximum',True)]:
        order=sorted(gg,key=lambda g:(Fraction(g['numerator'],g['CJK']),g['id']),reverse=reverse)
        d,m=d0,m0;best=(Fraction(m,d),m,d,0)
        for i,g in enumerate(order,1):
            d+=g['CJK'];m+=g['numerator'];v=Fraction(m,d)
            if label=='minimum' and v<best[0] or label=='maximum' and v>best[0]:best=(v,m,d,i)
        out[label]={'numerator':best[1],'CJK':best[2],'per_10000':float(best[0]*10000),'included_node_count':best[3],'included_node_ids':[g['id'] for g in order[:best[3]]]}
    return out

def bounds(data,raw,sens):
    pp=defaultdict(list)
    for p in data['positions']:
        if p['denominator_eligible']:pp[p['article_id']].append(p)
    known={'K':{},'O':{}};unknown={};unknown_D=0;report={'발언 보고','문서 보고'};primary={'발언','문서','인용','문헌 인용','비발화'}
    for a in scopes():
        aid=a['article_id'];text=raw[aid]['raw']
        for r in a['exclusive_runs']:
            if r['person_name_excluded'] or r['annotation_excluded']:continue
            d=sum(map(cjk,text[slice(*r['span'])]));e=r['E']
            if e is None:unknown_D+=d
            is_known=e in known and r['function'] is None and r['genre'] not in report
            is_unknown=e is None and r['genre'] not in report and (r['function'] is None or r['genre'] in primary)
            if not d or not (is_known or is_unknown):continue
            key=('E_NULL|' if is_unknown else '')+aid+'|'+str(r['node_id']);target=unknown if is_unknown else known[e]
            g=target.setdefault(key,{'id':key,'CJK':0,'min_positions':0,'general_direct':0,'expanded_people_relations':0});g['CJK']+=d
            for p in pp[aid]:
                if r['span'][0]<=p['local_position']<r['span'][1]:
                    g['min_positions']+=1;g['general_direct']+=p['primary_commoner_comparison'] is True;g['expanded_people_relations']+=p['people_reference'] is True
    strict=next(r for r in sens['conditions'] if r['condition']=='strict_primary');held=next(r for r in sens['conditions'] if r['condition']=='Fheld_only')
    assert unknown_D==sens['burden_overlapping_scopes']['E_held']['CJK']
    for e in known:
        for k in ['CJK','min_positions','general_direct','expanded_people_relations']:assert sum(g[k] for g in known[e].values())==held['owners'][e][k]
    results={}
    for mode in ['known','outer']:
        metrics={}
        for metric in ['general_direct','expanded_people_relations']:
            owners={}
            for e in ['K','O']:
                groups=list(known[e].values())+(list(unknown.values()) if mode=='outer' else [])
                owners[e]=extrema(strict['owners'][e]['CJK'],strict['owners'][e][metric],[{'id':g['id'],'CJK':g['CJK'],'numerator':g[metric]} for g in groups])
                if mode=='outer':
                    index={g['id']:i for i,g in enumerate(groups)}
                    for v in owners[e].values():v['included_candidate_indexes']=[index[k] for k in v.pop('included_node_ids')]
            lo,hi=owners['K']['minimum'],owners['O']['maximum'];flag=lo['numerator']*hi['CJK']>hi['numerator']*lo['CJK']
            metrics[metric]={'owners':owners}
            if mode=='known':metrics[metric].update(K_min_greater_than_O_max=flag,K_minus_O_lower_bound_per_10000=lo['per_10000']-hi['per_10000'],candidate_node_counts={e:len(known[e]) for e in known})
            else:metrics[metric].update(K_greater_than_O_certified_by_separated_outer_bounds=flag,interpretation='separation_certifies_order_under_this_relaxation' if flag else 'outer_ranges_overlap_or_touch; this test does not certify order; it does not prove a feasible historical reversal')
        results[mode]={'metrics':metrics}
    return results

def main():
    manifest=load(ROOT/'FILES.sha256.json')
    for name,h in manifest['files'].items():assert digest(ROOT/name)==h,'File checksum mismatch: '+name
    data=load(ROOT/'data/positions.json.gz');raw={a['article_id']:a for a in lines(ROOT/'data/articles.jsonl.gz')};assert len(raw)==36725 and len(data['positions'])==7041
    sens=aggregate.compute(data,load(ROOT/'data/table03.json'),load(ROOT/'data/table13.json'),load(ROOT/'data/delta18.json'),{'articles':scopes()},iter(raw.values()),cjk,load(ROOT/'data/evidence44.json'))
    expected=load(ROOT/'expected/conditions46.json')
    keys=['total','conditions','coverage_position_and_denominator_separate','strata_E_genre_function','burden_overlapping_scopes','mutually_exclusive_layers','by_reign_year','by_ten_reign_years']
    for key in keys:assert sens[key]==expected[key],'Conditional result mismatch: '+key
    bb=bounds(data,raw,sens)
    for mode,name in [('known','known_function_bounds58.json'),('outer','outer_bounds59.json')]:assert bb[mode]['metrics']==load(ROOT/'expected'/name)['metrics'],mode+' bound mismatch'
    out=ROOT/'output';out.mkdir(exist_ok=True)
    for name,value in [('conditions.json',sens),('known_function_bounds.json',bb['known']),('outer_bounds.json',bb['outer'])]:(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    k,o=sens['conditions'][0]['owners']['K'],sens['conditions'][0]['owners']['O']
    receipt={'passed':True,'data_version':'sillok-min-analysis-dev103c1-20261028','source_classification_regenerated_from_XML':False,'fixed_source_labels_reaggregated_from_full_raw_articles':True,'articles':36725,'literal_Min_positions':7041,'CJK':sens['total']['CJK'],'K_CJK':k['CJK'],'O_CJK':o['CJK'],'K_basic':k['general_direct'],'O_basic':o['general_direct'],'K_over_O':sens['conditions'][0]['contrasts']['general_direct']['K_divided_by_O'],'all_7_conditions_and_both_bound_metrics_match':True,'checksummed_files':len(manifest['files']),'independent_historical_accuracy_evaluation':False}
    (out/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
