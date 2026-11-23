"""Read frozen release; apply only named local scenarios in memory.
No original/source/state/manuscript is written. Outputs reproduce accepted local corrections.
"""
from pathlib import Path
from zipfile import ZipFile
from collections import Counter,defaultdict
from fractions import Fraction
from copy import deepcopy
import json,gzip,hashlib,sys
sys.stdout.reconfigure(encoding='utf-8')
W=Path(__file__).parent
SOURCE=json.loads((W/'source.json').read_text(encoding='utf-8'))
SOURCE['zip']=str(Path(sys.argv[1]).resolve()) if len(sys.argv)>1 else str(W/SOURCE['asset_name'])
RANGES=json.loads((W/'target_ranges.json').read_text(encoding='utf-8'))
EVID={'articles':{},'scopes':{}}
with ZipFile(SOURCE['zip']) as base_zip:
 for name in base_zip.namelist():
  if '/data/scopes-' in name:
   with gzip.GzipFile(fileobj=base_zip.open(name)) as stream:
    for line in stream:
     item=json.loads(line)
     if item['article_id'] in RANGES:EVID['scopes'][item['article_id']]=item
 name=next(n for n in base_zip.namelist() if n.endswith('articles.jsonl.gz'))
 with gzip.GzipFile(fileobj=base_zip.open(name)) as stream:
  for line in stream:
   item=json.loads(line)
   if item['article_id'] in RANGES:EVID['articles'][item['article_id']]=item
assert set(EVID['articles'])==set(EVID['scopes'])==set(RANGES)
OUT=W/'output';OUT.mkdir(exist_ok=True)
PRIMARY={'발언','문서','인용','문헌 인용','비발화'}
REPORT={'발언 보고','문서 보고'}
METRICS=('CJK','min_positions','general_direct','expanded_people_relations','semantic_direct','semantic_held','CJK_in_zero_Min_runs','runs')
CASE_A='wua_12008008_002';CASE_B='wua_12212027_001'
CASE_C={'wua_12812018_001','wua_13011020_002'}
SCENARIOS={'A':['A'],'B':['B'],'AB':['A','B'],'C':['C'],'ABC':['A','B','C'],'D':['D'],'ABD':['A','B','D'],'ABCD':['A','B','C','D']}
def cjk(ch):return '\u3400'<=ch<='\u9fff' or '\U00020000'<=ch<='\U0002fa1f'
def hsh(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dumps(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def counts(raw,r,pp):
 lo,hi=r['span'];local=[p for p in pp if lo<=p['local_position']<hi]
 if r['person_name_excluded'] or r['annotation_excluded']:
  assert not local
  return None
 n=sum(cjk(ch) for ch in raw[lo:hi])
 return Counter(CJK=n,min_positions=len(local),
  general_direct=sum(p['primary_commoner_comparison'] is True for p in local),
  expanded_people_relations=sum(p['people_reference'] is True for p in local),
  semantic_direct=sum(p['semantic_kind']=='사람·집단 지칭' for p in local),
  semantic_held=sum(p['people_reference'] is None for p in local),
  CJK_in_zero_Min_runs=n if not local else 0,runs=1)
def emptygroups():return {'K':{},'O':{},'unknown':{}}
def addrun(cells,groups,aid,r,st):
 if st is None:return
 key=(r['E'],r['genre'],r['function']);cells[key].update(st)
 owner,genre,func=key
 known=owner in ('K','O') and func is None and genre not in REPORT
 unknown=owner is None and genre not in REPORT and (func is None or genre in PRIMARY)
 if st['CJK'] and (known or unknown):
  gid=('E_NULL|' if unknown else '')+aid+'|'+r['node_id']
  group=groups['unknown' if unknown else owner].setdefault(gid,Counter())
  group.update({k:st[k] for k in ('CJK','min_positions','general_direct','expanded_people_relations')})
def local(raw,s,pp):
 cells=defaultdict(Counter);groups=emptygroups()
 for r in s['exclusive_runs']:addrun(cells,groups,s['article_id'],r,counts(raw,r,pp))
 return cells,groups
def operations(aid,letters):
 out=[]
 if aid==CASE_A and 'A' in letters:
  out.append({'case':'A','span':RANGES[aid]['span'],'E':'K','genre':'발언','function':'직접 발화','node_id':aid+':W1A_K'})
 if aid==CASE_B and 'B' in letters:
  out.append({'case':'B','span':RANGES[aid]['span'],'E':'U','genre':'문헌 인용','function':'비발화','node_id':aid+':W1B_QUOTE'})
 if aid==CASE_B and 'D' in letters:
  node=next(n for n in EVID['scopes'][aid]['nodes'] if n['node_id'].endswith(':S34_2'))
  out.append({'case':'D','span':node['span'],'E':'K','genre':'발언','function':'직접 발화','node_id':aid+':W1D_K','decision_status':'researcher_approved'})
 if aid in CASE_C and 'C' in letters:
  out.append({'case':'C','span':RANGES[aid]['span'],'E':'C','genre':'기록서술','function':'기록서술','node_id':aid+':W1C_COMMENTARY','decision_status':'researcher_approved'})
 return out
def patch_scope(s,letters):
 out=deepcopy(s);ops=operations(s['article_id'],letters);new=[]
 for r in s['exclusive_runs']:
  lo,hi=r['span'];cuts=sorted({lo,hi}|{v for op in ops for v in op['span'] if lo<v<hi})
  for a,b in zip(cuts,cuts[1:]):
   x=deepcopy(r);x['span']=[a,b]
   for op in ops:
    if op['span'][0]<=a and b<=op['span'][1]:
     for k in ('E','genre','function','node_id'):x[k]=op[k]
     x['audit_case']=op['case']
   new.append(x)
 assert new[0]['span'][0]==s['exclusive_runs'][0]['span'][0]
 assert new[-1]['span'][1]==s['exclusive_runs'][-1]['span'][1]
 assert all(a['span'][1]==b['span'][0] for a,b in zip(new,new[1:]))
 out['exclusive_runs']=new
 return out
def selections():
 strict=lambda e,g,f:e in ('K','O') and g in PRIMARY and f is not None
 return [
 ('strict_primary',strict),
 ('plus_known_E_Fheld',lambda e,g,f:strict(e,g,f) or e in ('K','O') and f is None and g not in REPORT),
 ('Fheld_only',lambda e,g,f:e in ('K','O') and f is None and g not in REPORT),
 ('direct_only',lambda e,g,f:strict(e,g,f) and f=='직접 발화'),
 ('document_only',lambda e,g,f:strict(e,g,f) and f=='문서 소개'),
 ('quoted_only',lambda e,g,f:strict(e,g,f) and f=='인용 발화'),
 ('direct_document',lambda e,g,f:strict(e,g,f) and f in ('직접 발화','문서 소개'))]
def conditions(cells):
 out={}
 for name,select in selections():
  owners={}
  for e in ('K','O'):
   st=Counter({k:0 for k in METRICS})
   for key,v in cells.items():
    if key[0]==e and select(*key):st.update(v)
   owners[e]=dict(st)
   for metric in ('general_direct','expanded_people_relations'):owners[e][metric+'_per_10000']=st[metric]/st['CJK']*10000 if st['CJK'] else None
  out[name]={'owners':owners}
  for m in ('general_direct','expanded_people_relations'):
   kr=owners['K'][m+'_per_10000'];orr=owners['O'][m+'_per_10000']
   out[name][m+'_K_over_O']=kr/orr if orr else None
 return out
def extrema(d0,m0,groups,metric):
 out={}
 for name,reverse in [('minimum',False),('maximum',True)]:
  rows=sorted(groups.items(),key=lambda x:(Fraction(x[1][metric],x[1]['CJK']),x[0]),reverse=reverse)
  d,m=d0,m0;best=(Fraction(m,d),m,d,0)
  for i,(gid,g) in enumerate(rows,1):
   d+=g['CJK'];m+=g[metric];v=Fraction(m,d)
   if (name=='minimum' and v<best[0]) or (name=='maximum' and v>best[0]):best=(v,m,d,i)
  out[name]={'numerator':best[1],'CJK':best[2],'per_10000':float(best[0]*10000),'included_node_count':best[3]}
 return out
def bounds(cond,groups):
 out={}
 for mode in ('known','outer'):
  out[mode]={}
  for m in ('general_direct','expanded_people_relations'):
   owners={}
   for e in ('K','O'):
    gg=dict(groups[e])
    if mode=='outer':gg.update(groups['unknown'])
    seed=cond['strict_primary']['owners'][e]
    owners[e]=extrema(seed['CJK'],seed[m],gg,m)
   lo=owners['K']['minimum'];hi=owners['O']['maximum']
   out[mode][m]={'owners':owners,'K_min_gt_O_max':lo['numerator']*hi['CJK']>hi['numerator']*lo['CJK']}
 return out
def apply_local_delta(global_cells,global_groups,before,after):
 bc,bg=before;ac,ag=after
 for key in set(bc)|set(ac):
  target=global_cells.setdefault(key,Counter())
  for m in METRICS:target[m]+=ac.get(key,{}).get(m,0)-bc.get(key,{}).get(m,0)
  assert all(v>=0 for v in target.values()),key
 for kind in ('K','O','unknown'):
  for gid in set(bg[kind])|set(ag[kind]):
   target=global_groups[kind].setdefault(gid,Counter())
   for m in ('CJK','min_positions','general_direct','expanded_people_relations'):
    target[m]+=ag[kind].get(gid,{}).get(m,0)-bg[kind].get(gid,{}).get(m,0)
   assert all(v>=0 for v in target.values()),gid
   if target['CJK']==0:del global_groups[kind][gid]
def derived(cells):
 total={m:sum(s[m] for s in cells.values()) for m in METRICS}
 e=sum(s['CJK'] for (E,g,f),s in cells.items() if E is None)
 f=sum(s['CJK'] for (E,g,f),s in cells.items() if f is None and g not in REPORT)
 both=sum(s['CJK'] for (E,g,f),s in cells.items() if E is None and f is None and g not in REPORT)
 union=e+f-both
 return {'total':total,'E_held_CJK':e,'F_held_nonreport_CJK':f,'E_and_F_held_nonreport_CJK':both,'unresolved_union_CJK':union,'outside_unresolved_union_CJK_percent':(total['CJK']-union)/total['CJK']*100,'C_CJK':sum(s['CJK'] for (E,g,f),s in cells.items() if E=='C')}
def frozen_lines(z,name):
 with gzip.GzipFile(fileobj=z.open(name)) as f:
  for line in f:
   if line.strip():yield json.loads(line)
def scopes(z):
 for name in sorted(n for n in z.namelist() if '/data/scopes-' in n):yield from frozen_lines(z,name)
assert hsh(SOURCE['zip'])==SOURCE['sha256']
with ZipFile(SOURCE['zip']) as z:
 find=lambda suffix:next(n for n in z.namelist() if n.endswith(suffix))
 data=json.loads(gzip.decompress(z.read(find('positions.json.gz'))))
 expected=json.loads(z.read(find('conditions46.json')))
 expected_bounds={mode:json.loads(z.read(find(name))) for mode,name in [('known','known_function_bounds58.json'),('outer','outer_bounds59.json')]}
 pp=defaultdict(list)
 for p in data['positions']:
  if p['denominator_eligible']:pp[p['article_id']].append(p)
 cells=defaultdict(Counter);groups=emptygroups();si=iter(scopes(z));article_count=0
 for a in frozen_lines(z,find('articles.jsonl.gz')):
  s=next(si);assert a['article_id']==s['article_id'];article_count+=1
  raw=a['raw'];aid=a['article_id']
  for r in s['exclusive_runs']:addrun(cells,groups,aid,r,counts(raw,r,pp[aid]))
 assert next(si,None) is None and article_count==36725
 for row in expected['strata_E_genre_function']:
  key=tuple(row[k] for k in ('E_preserved','genre_preserved','function_preserved'))
  assert all(cells[key][m]==row[m] for m in METRICS),(key,cells[key],row)
 assert len(cells)==len(expected['strata_E_genre_function'])
 basecond=conditions(cells);basebounds=bounds(basecond,groups)
 for row in expected['conditions']:
  ours=basecond[row['condition']]['owners']
  for e in ('K','O'):
   for m in METRICS:assert ours[e][m]==row['owners'][e][m],(row['condition'],e,m)
 for mode in ('known','outer'):
  for m in ('general_direct','expanded_people_relations'):
   for e in ('K','O'):
    for extreme in ('minimum','maximum'):
     actual=basebounds[mode][m]['owners'][e][extreme]
     old=expected_bounds[mode]['metrics'][m]['owners'][e][extreme]
     assert all(actual[k]==old[k] for k in actual),(mode,m,e,extreme,actual,old)
 verification={'original_strata_all_match':True,'original_seven_conditions_match':True,'original_both_bound_metrics_match':True,'article_records':article_count,'historical_classification_regenerated':False}
 output={'baseline':{'conditions':basecond,'bounds':basebounds,'derived':derived(cells)},'scenarios':{},'validation':verification}
 total0={m:sum(v[m] for v in cells.values()) for m in ('CJK','min_positions','general_direct','expanded_people_relations')}
 basegroup_totals={k:sum(v['CJK'] for v in gg.values()) for k,gg in groups.items()}
 patches={}
 for name,letters in SCENARIOS.items():
  cc=deepcopy(cells);gg=deepcopy(groups);ops=[]
  for aid in (CASE_A,CASE_B,*sorted(CASE_C)):
   raw=EVID['articles'][aid]['raw'];s=EVID['scopes'][aid]
   ps=patch_scope(s,letters)
   apply_local_delta(cc,gg,local(raw,s,pp[aid]),local(raw,ps,pp[aid]))
   ops.extend([{'article_id':aid,**o} for o in operations(aid,letters)])
  total={m:sum(v[m] for v in cc.values()) for m in total0}
  assert total==total0,(name,total,total0)
  co=conditions(cc);bb=bounds(co,gg)
  output['scenarios'][name]={'case_letters':letters,'researcher_approved_C':'C' in letters,'researcher_approved_D':'D' in letters,'conditions':co,'bounds':bb,'group_CJK':{k:sum(v['CJK'] for v in vv.values()) for k,vv in gg.items()},'total_conserved':total,'derived':derived(cc)}
  patches[name]=ops
  st=co['strict_primary'];print(name,'K',st['owners']['K']['general_direct'],st['owners']['K']['CJK'],'O',st['owners']['O']['general_direct'],st['owners']['O']['CJK'],'RATIO',st['general_direct_K_over_O'])
 output['baseline']['group_CJK']=basegroup_totals
 for name,o in output['scenarios'].items():
  o['delta_vs_baseline']={}
  for condition in basecond:
   o['delta_vs_baseline'][condition]={e:{m:o['conditions'][condition]['owners'][e][m]-basecond[condition]['owners'][e][m] for m in ('CJK','general_direct','expanded_people_relations')} for e in ('K','O')}
 expected_path=W/'expected_impact_results.json'
 if expected_path.exists():
  expected_public=json.loads(expected_path.read_text(encoding='utf-8'));assert expected_public['baseline']==output['baseline'] and expected_public['adopted']==output['scenarios']['ABCD'],'Published expected result mismatch'
 dumps(OUT/'impact_results.json',output);dumps(OUT/'patch_scenarios.json',patches);dumps(OUT/'baseline_validation.json',verification)
 print('VALIDATED',json.dumps(verification,ensure_ascii=False))
assert hsh(SOURCE['zip'])==SOURCE['sha256']

