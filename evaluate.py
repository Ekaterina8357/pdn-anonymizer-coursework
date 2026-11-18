"""Оценка метрик классификации по токенам (включая BIO) и подготовка BERTScore.

Встроенные F1 воспроизводимы на Python stdlib. Для BERTScore требуется
pip install -r requirements-bertscore.txt и скачанная модель на машине пользователя.
"""
import argparse
import json
import hashlib
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from pdn import recognize,bio_tags,Anonymizer,mask,mask_all_text,ALL,ODD,EVEN,Entity

ROOT=Path(__file__).resolve().parent

def cls(tag): return tag[2:] if tag!='O' else 'O'

def run_dataset(dataset=None):
    dataset=Path(dataset or ROOT/'data/test.jsonl')
    rows=[json.loads(x) for x in dataset.read_text(encoding='utf-8').splitlines() if x.strip()]
    conf=Counter(); conf_by_variant={'odd':Counter(),'even':Counter()}
    all_true=[];all_pred=[]
    samples=[]
    for r in rows:
        gold=[Entity(**e) for e in r['entities']]
        found=recognize(r['text'],r['variant'])
        g=bio_tags(r['text'],gold);p=bio_tags(r['text'],found)
        assert len(g)==len(p)
        assert all(x['start']==y['start'] and x['end']==y['end'] for x,y in zip(g,p))
        for x,y in zip(g,p):
            a,b=cls(x['tag']),cls(y['tag'])
            conf[(a,b)]+=1
            conf_by_variant[r['variant']][(a,b)]+=1
            all_true.append(x['tag']);all_pred.append(y['tag'])
        stable_seed=int.from_bytes(hashlib.sha256(r['id'].encode('utf-8')).digest()[:8],'big')
        anon,_=Anonymizer(r['variant'],seed=stable_seed).anonymize(r['text'])
        masked=mask(r['text'],gold)
        samples.append({'id':r['id'],'variant':r['variant'],'source':r['text'],
                        'synonym':anon,'masked':masked,
                        'masked_full':mask_all_text(r['text'])})
    report=[]
    for label in ALL:
        tp=conf[(label,label)]
        fn=sum(v for (g,p),v in conf.items() if g==label and p!=label)
        fp=sum(v for (g,p),v in conf.items() if p==label and g!=label)
        support=tp+fn
        precision=tp/(tp+fp) if tp+fp else 0.
        recall=tp/support if support else 0.
        f1=2*precision*recall/(precision+recall) if precision+recall else 0.
        report.append({'label':label,'support_tokens':support,'tp':tp,'fp':fp,'fn':fn,
                       'precision':round(precision,5),'recall':round(recall,5),'f1':round(f1,5)})
    active=[x for x in report if x['support_tokens']]
    weighted=sum(x['f1']*x['support_tokens'] for x in active)/sum(x['support_tokens'] for x in active)
    macro=sum(x['f1'] for x in active)/len(active)
    # Отдельно можно оценить точность на схемах BIO, исключив O.
    tags=sorted(set(all_true+all_pred)-{'O'})
    bio_f1=[]
    for tag in tags:
        tp=sum(1 for a,b in zip(all_true,all_pred) if a==tag==b)
        ntrue=sum(a==tag for a in all_true)
        npred=sum(b==tag for b in all_pred)
        bio_f1.append({'tag':tag,'support':ntrue,'f1':2*tp/(ntrue+npred) if ntrue+npred else 0.})
    source_synonym_ratio=sum(SequenceMatcher(None,x['source'],x['synonym']).ratio() for x in samples)/len(samples)
    source_mask_ratio=sum(SequenceMatcher(None,x['source'],x['masked']).ratio() for x in samples)/len(samples)
    source_mask_full_ratio=sum(SequenceMatcher(None,x['source'],x['masked_full']).ratio() for x in samples)/len(samples)
    variant_summary={}
    for variant,counts in conf_by_variant.items():
        class_set=ODD if variant=='odd' else EVEN
        scores=[]
        for label in class_set:
            tp=counts[(label,label)]
            ntrue=sum(n for (g,p),n in counts.items() if g==label)
            npred=sum(n for (g,p),n in counts.items() if p==label)
            scores.append((2*tp/(ntrue+npred) if ntrue+npred else 0.0,ntrue))
        variant_summary[variant]={
            'texts':sum(r['variant']==variant for r in rows),
            'weighted_f1_non_o':round(sum(f*n for f,n in scores)/sum(n for _,n in scores),5),
            'macro_f1_non_o':round(sum(f for f,_ in scores)/len(scores),5),
        }
    result={'by_variant':variant_summary,
            'mean_character_similarity_synonym':round(source_synonym_ratio,5),
            'mean_character_similarity_mask':round(source_mask_ratio,5),
            'mean_character_similarity_mask_full':round(source_mask_full_ratio,5),
            'note_character_similarity':'Коэффициент SequenceMatcher — не BERTScore и не оценка семантики',
            'texts':len(rows),'tokens_total':len(all_true),'labels_evaluated':len(active),
            'weighted_f1_non_o':round(weighted,5),'macro_f1_non_o':round(macro,5),
            'weighted_bio_f1_non_o':round(sum(x['f1']*x['support'] for x in bio_f1)/sum(x['support'] for x in bio_f1),5),
            'per_label':report,
            'evaluation_note':'Только синтетические тексты, близкие к шаблонам правила; перенос на реальные документы не доказан'}
    (ROOT/'results').mkdir(exist_ok=True)
    (ROOT/'results/recognition_metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    with (ROOT/'results/anonymized_comparison.jsonl').open('w',encoding='utf-8') as f:
        for x in samples: f.write(json.dumps(x,ensure_ascii=False)+'\n')
    return result,samples


def run_bertscore(samples,model_type='DeepPavlov/rubert-base-cased',batch_size=8,num_layers=12):
    try: from bert_score import BERTScorer
    except ImportError as exc: raise RuntimeError('Для BERTScore установите: pip install -r requirements-bertscore.txt') from exc
    ref=[s['source'] for s in samples]
    a=[s['synonym'] for s in samples]; b=[s['masked'] for s in samples]
    c=[s['masked_full'] for s in samples]
    scorer=BERTScorer(model_type=model_type,num_layers=num_layers,batch_size=batch_size)
    pa,ra,fa=scorer.score(a,ref,batch_size=batch_size,verbose=True)
    pb,rb,fb=scorer.score(b,ref,batch_size=batch_size,verbose=True)
    pc,rc,fc=scorer.score(c,ref,batch_size=batch_size,verbose=True)
    out={'model_type':model_type,'num_layers':num_layers,'texts':len(samples),
         'synonym':{'p':float(pa.mean()),'r':float(ra.mean()),'f1':float(fa.mean())},
         'mask':{'p':float(pb.mean()),'r':float(rb.mean()),'f1':float(fb.mean())},
         'full_mask':{'p':float(pc.mean()),'r':float(rc.mean()),'f1':float(fc.mean())},
         'delta_f1':float(fa.mean()-fb.mean()),
         'delta_f1_full_mask':float(fa.mean()-fc.mean()),'status':'computed'}
    (ROOT/'results/bertscore_metrics.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    return out

if __name__=='__main__':
    cli=argparse.ArgumentParser()
    cli.add_argument('--bertscore',action='store_true',help='Выполнить настоящий BERTScore при наличии библиотеки и весов')
    cli.add_argument('--model',default='DeepPavlov/rubert-base-cased')
    args=cli.parse_args()
    report,samples=run_dataset()
    print(json.dumps({k:v for k,v in report.items() if k!='per_label'},ensure_ascii=False,indent=2))
    if args.bertscore: print(json.dumps(run_bertscore(samples,args.model),ensure_ascii=False,indent=2))
