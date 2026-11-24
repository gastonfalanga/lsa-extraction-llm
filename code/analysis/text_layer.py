import fitz,json,glob,re,unicodedata,os,sys
from collections import Counter
fitz.TOOLS.mupdf_display_errors(False)
def norm(x): return unicodedata.normalize('NFKD',x).encode('ascii','ignore').decode().lower()
c=Counter(); seg_ok=seg_total=0; missing=set(); rows=[]
cache={}
for p in sorted(glob.glob('work/outputs/raw_ocr_history/first_commit/lote_*.json')):
    if p.endswith('lote_156.json'): continue
    signs=json.load(open(p))
    for s in signs:
        b=s['ocr_data']['source_batch_file']
        if b not in cache:
            fp='data/raw/'+b.replace('_adjust_set','')
            cache[b]=''.join(pg.get_text() for pg in fitz.open(fp)) if os.path.exists(fp) else None
            if cache[b] is None: missing.add(b)
    batches=sorted({s['ocr_data']['source_batch_file'] for s in signs})
    for b in batches:
        text=cache[b]
        if text is None: continue
        t=norm(text); bs=[s for s in signs if s['ocr_data']['source_batch_file']==b]
        pos=0; starts=[]
        for s in bs:
            w=norm(re.split(r'[/(]',s['spanish_word'])[0].strip())
            i=t.find(w,pos); starts.append(i)
            if i>=0: pos=i+len(w)
        seg_total+=len(bs); seg_ok+=sum(i>=0 for i in starts)
        for k,s in enumerate(bs):
            if starts[k]<0: continue
            nxt=[x for x in starts[k+1:] if x>=0]
            seg=text[starts[k]:(nxt[0] if nxt else len(text))]
            mo=len(re.findall(r'M\s*\.\s*O\s*\.?',seg)); md=len(re.findall(r'M\s*\.\s*D\s*\.?',seg)); mi=len(re.findall(r'M\s*\.\s*[I1lJ]\s*\.?',seg))
            if not mo: continue
            hands=set()
            for v in s.get('sign_variants',[]):
                for comp in v.get('sequential_components',[]):
                    hands|={h for h in('dominant_hand','non_dominant_hand') if comp.get(h)}
            kind='M.O. only' if not md and not mi else ('M.O. + M.I.' if mi and not md else 'M.O. + M.D.')
            c[(kind,'+'.join(sorted(hands)))]+=1
            rows.append((s['sign_id'],kind,'+'.join(sorted(hands)),mo,md,mi))
print('missing pdfs',sorted(missing)); print('segments located',seg_ok,'/',seg_total)
for k,v in sorted(c.items()): print(k,v)
print('signs with M.O.',len(rows),'M.O. occurrences',sum(r[3] for r in rows))
import csv
with open('work/outputs/text_layer/signs.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['sign_id','codes','hands_extracted','n_MO','n_MD','n_MI']); w.writerows(rows)
