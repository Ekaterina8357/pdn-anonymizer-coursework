"""Воспроизводимая генерация 300 синтетических тестовых текстов и BIO-разметки.

Внимание: это НЕ factRuEval: исходный корпус рекомендуемый, но не обязательный
согласно пункту 'набор данных может быть составлен самостоятельно'.
"""
import json
import random
import csv
from collections import Counter
from pathlib import Path
from pdn import (MALE_FIRST,FEMALE_FIRST,MALE_LAST,FEMALE_LAST,ODD,EVEN,
                 inn_build,luhn_finish,snils_build,ogrnip_build,inflect_word,bio_tags,Entity)

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'data'


def build_record(variant:str,index:int,rng:random.Random):
    parts=[]; spans=[]; pos=0
    def append(piece,label=None):
        nonlocal pos
        if label: spans.append({'label':label,'start':pos,'end':pos+len(piece),'text':piece})
        parts.append(piece);pos+=len(piece)
    female=(index%2==1)
    gender='f' if female else 'm'
    n=rng.choice(FEMALE_FIRST if female else MALE_FIRST)
    s=rng.choice(FEMALE_LAST if female else MALE_LAST)
    case=['nomn','gent','datv'][index%3]
    nm=inflect_word(n,gender,case,'NAME')
    sn=inflect_word(s,gender,case,'SURNAME')
    append('Карточка обращения № '+str(1500+index)+'. Тестовые сведения, созданные программно.\n')
    if case=='nomn': append('Заявитель: ' if index%4 else ('Гражданка ' if female else 'Гражданин '))
    if case=='gent': append('Обращение от гражданки ' if female else 'Обращение от гражданина ')
    if case=='datv': append('Ответ передан гражданке ' if female else 'Ответ передан гражданину ')
    if index%7==0:
        append(nm,'NAME');append(' ');append(sn,'SURNAME')
    else:
        append(sn,'SURNAME');append(' ');append(nm,'NAME')
    append('.\n')
    possible=[x for x in (ODD if variant=='odd' else EVEN) if x not in ('NAME','SURNAME')]
    # 150 x 5/8 => минимум 93 упоминания каждого специального класса.
    chosen=[possible[(index*5+j)%len(possible)] for j in range(5)]
    rng.shuffle(chosen)
    for label in chosen:
        if label=='INN':
            value=inn_build(rng.choice(('7701','5038','7810','6602')),rng,12 if index%2 else 10)
            prefix='ИНН: '
        elif label=='PASSPORT':
            value=f'{rng.choice((45,46,40))} {rng.randrange(1,100):02d} {rng.randrange(100000,999999):06d}'
            prefix='Паспорт: '
        elif label=='CARD':
            digits=luhn_finish(rng.choice(('220001','427612','553691'))+''.join(str(rng.randrange(10)) for _ in range(9)))
            value=' '.join(digits[k:k+4] for k in range(0,16,4));prefix='Карта: '
        elif label=='SNILS':value=snils_build(rng);prefix='СНИЛС: '
        elif label=='OGRNIP':value=ogrnip_build('32677',rng);prefix='ОГРНИП: '
        elif label=='URL':value=f'https://client{rng.randrange(100,999)}.example.ru/profile/{rng.randrange(1000,9999)}';prefix='URL: '
        elif label=='IP':value=f'192.168.{rng.randrange(1,255)}.{rng.randrange(1,255)}';prefix='IP: '
        elif label=='PHONE':value=f'+7 (916) {rng.randrange(100,999)}-{rng.randrange(10,99):02d}-{rng.randrange(10,99):02d}';prefix='Телефон: '
        elif label=='EMAIL':value=f'client{rng.randrange(1000,9999)}@example.ru';prefix='E-mail: '
        elif label=='MARRIAGE_CERT':value=f'II-МЮ № {rng.randrange(100000,999999)}';prefix='Свидетельство о браке: '
        elif label=='BIRTH_CERT':value=f'IV-АГ № {rng.randrange(100000,999999)}';prefix='Свидетельство о рождении: '
        elif label=='CADASTRAL':value=f'77:01:0004012:{rng.randrange(1000,9999)}';prefix='Кадастровый номер: '
        elif label=='KLADR':value=f'77000001000{rng.randrange(10,99):02d}';prefix='Код КЛАДР: '
        else: raise ValueError(label)
        append(prefix);append(value,label);append('.\n')
    # Ложные кандидаты для проверки отсутствия ошибочного распознавания.
    if index%4==0:
        invalid=inn_build('7701',rng,10)
        corrupted=invalid[:-1]+str((int(invalid[-1])+1)%10)
        append('Контрольный неверный ИНН: '+corrupted+'.\n')
    if index%9==0: append('Учебная дата: 20.10.2026. Версия системы 2.0.3.\n')
    return {'id':f'{variant}_{index+1:03d}','variant':variant,'text':''.join(parts),'entities':spans}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rng=random.Random(20261020)
    records=[build_record(v,i,rng) for v in ('odd','even') for i in range(150)]
    rng.shuffle(records)
    labels=Counter()
    counts={'odd':0,'even':0}
    with (OUT/'test.jsonl').open('w',encoding='utf-8') as f, (OUT/'test_bio.jsonl').open('w',encoding='utf-8') as bio:
        for row in records:
            f.write(json.dumps(row,ensure_ascii=False)+'\n')
            bio.write(json.dumps({'id':row['id'],'variant':row['variant'],
                                  'tokens':bio_tags(row['text'],[Entity(**e) for e in row['entities']])},ensure_ascii=False)+'\n')
            counts[row['variant']]+=1
            labels.update(e['label'] for e in row['entities'])
    summary={'texts':len(records),'texts_by_variant':counts,'entities_by_label':dict(sorted(labels.items())),
             'total_entities':sum(labels.values()),'source':'самостоятельно составленный синтетический корпус',
             'seed':20261020,'type':'test-only (правила не обучаются на тестовой выборке)'}
    (OUT/'dataset_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
