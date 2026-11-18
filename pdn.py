"""Распознавание и синонимическое обезличивание российских ПДн.

Оба варианта задания: variant='odd' (нечётный), 'even' (чётный).
Без обязательных внешних зависимостей; pymorphy3 можно подключить дополнительно.
"""
from __future__ import annotations
import dataclasses
import ipaddress
import json
import random
import re
import secrets
import string

COMMON = ('SURNAME', 'NAME', 'INN', 'PASSPORT', 'CARD')
ODD = COMMON + ('SNILS', 'URL', 'PHONE', 'MARRIAGE_CERT', 'CADASTRAL')
EVEN = COMMON + ('OGRNIP', 'IP', 'EMAIL', 'BIRTH_CERT', 'KLADR')
ALL = tuple(dict.fromkeys(ODD + EVEN))
TOKEN_RE = re.compile(r'\w+|[^\w\s]', re.UNICODE)
FLAGS = re.IGNORECASE | re.UNICODE

# Подборка русских имён и фамилий; для примеров поддержана падежная парадигма.
MALE_FIRST = ['Иван','Пётр','Михаил','Алексей','Андрей','Николай','Дмитрий','Сергей','Виктор','Максим','Егор','Павел','Олег','Роман','Артём','Борис','Антон','Юрий','Константин','Фёдор']
FEMALE_FIRST = ['Анна','Мария','Елена','Ольга','Ирина','Наталья','Татьяна','Светлана','Дарья','Екатерина','Юлия','Алина','Виктория','Надежда','Полина','Ксения','София','Анастасия','Вера','Любовь']
AMBIG_FIRST = ['Саша','Женя']
MALE_LAST = ['Иванов','Петров','Сидоров','Смирнов','Кузнецов','Попов','Васильев','Соколов','Михайлов','Новиков','Фёдоров','Морозов','Волков','Алексеев','Лебедев','Семёнов','Павлов','Козлов','Белов','Захаров']
FEMALE_LAST = [x + 'а' for x in MALE_LAST]

@dataclasses.dataclass(frozen=True)
class Entity:
    label: str
    start: int
    end: int
    text: str

    def as_dict(self):
        return {'label': self.label, 'start': self.start, 'end': self.end, 'text': self.text}


def luhn_ok(num: str) -> bool:
    ds = re.sub(r'\D','',num)
    if not (13 <= len(ds) <= 19): return False
    s=0
    for i,d in enumerate(map(int, reversed(ds))):
        if i%2: d*=2; d-=9 if d>9 else 0
        s+=d
    return s%10==0


def luhn_finish(prefix: str) -> str:
    return next(prefix+str(x) for x in range(10) if luhn_ok(prefix+str(x)))


def inn_ok(num: str) -> bool:
    if not (num.isascii() and num.isdigit() and len(num) in (10,12)): return False
    d=list(map(int,num))
    def control(w): return sum(a*b for a,b in zip(d,w))%11%10
    if len(d)==10:
        return control([2,4,10,3,5,9,4,6,8])==d[9]
    return (control([7,2,4,10,3,5,9,4,6,8])==d[10] and
            control([3,7,2,4,10,3,5,9,4,6,8])==d[11])


def inn_build(prefix: str, rng: random.Random | random.SystemRandom, length: int=12, control_digits: str|None=None) -> str:
    if len(prefix)!=4 or not prefix.isdigit(): raise ValueError('Код налогового органа — 4 цифры')
    for _ in range(10000):
        d=list(map(int,prefix+''.join(str(rng.randrange(10)) for _ in range(length-4-(1 if length==10 else 2)))))
        if length==10:
            value=''.join(map(str,d))+str(sum(a*b for a,b in zip(d,[2,4,10,3,5,9,4,6,8]))%11%10)
        else:
            a=sum(x*y for x,y in zip(d,[7,2,4,10,3,5,9,4,6,8]))%11%10
            d.append(a)
            b=sum(x*y for x,y in zip(d,[3,7,2,4,10,3,5,9,4,6,8]))%11%10
            value=''.join(map(str,d))+str(b)
        if control_digits is None or value.endswith(control_digits): return value
    raise RuntimeError('Не удалось сгенерировать ИНН с заданным контролем')


def snils_control(base: str) -> int:
    s=sum(int(d)*(9-i) for i,d in enumerate(base))
    return 0 if s in (100,101) else (s%101 if s>101 else s) if s%101!=100 else 0


def snils_ok(digits: str) -> bool:
    d=re.sub(r'\D','',digits)
    if len(d)!=11 or int(d[:9])<=1001998: return False
    return snils_control(d[:9]) == int(d[9:])


def snils_build(rng):
    base=str(rng.randrange(1001999,999999999)).zfill(9)
    return f'{base[:3]}-{base[3:6]}-{base[6:9]} {snils_control(base):02d}'


def ogrnip_ok(value: str) -> bool:
    return bool(re.fullmatch(r'\d{15}',value)) and int(value[-1])==int(value[:14])%13%10


def ogrnip_build(prefix: str, rng):
    a=prefix+''.join(str(rng.randrange(10)) for _ in range(14-len(prefix)))
    return a+str(int(a)%13%10)


def token_spans(text: str):
    return [(m.group(),m.start(),m.end()) for m in TOKEN_RE.finditer(text)]


def bio_tags(text: str, entities: list[Entity]):
    result=[]
    for tok,s,e in token_spans(text):
        covering=[ent for ent in entities if s>=ent.start and e<=ent.end]
        if not covering: result.append({'token':tok,'start':s,'end':e,'tag':'O'}); continue
        ent=covering[0]
        former=not any(s2>=ent.start and e2<=ent.end and s2<s for _,s2,e2 in token_spans(text))
        result.append({'token':tok,'start':s,'end':e,'tag':('B-' if former else 'I-')+ent.label})
    return result

# Имена в падежах: компактный словарь для типичных контекстов; опционально pymorphy3.
CASE_CODES = ('nomn','gent','datv','accs','ablt','loct')
SPECIAL = {
 'Пётр': ['Пётр','Петра','Петру','Петра','Петром','Петре'],
 'Лев': ['Лев','Льва','Льву','Льва','Львом','Льве'],
 'Павел': ['Павел','Павла','Павлу','Павла','Павлом','Павле'],
 'Любовь': ['Любовь','Любови','Любови','Любовь','Любовью','Любови'],
}

def inflect_word(base: str, gender: str, case: str, kind: str='NAME') -> str:
    if case=='nomn': return base
    if base in SPECIAL: return SPECIAL[base][CASE_CODES.index(case)]
    if kind=='SURNAME':
        # фамилии типа Иванов / Иванова; имена на -а в женском роде
        if gender=='m' and base.endswith(('ов','ев','ин')):
            tails={'gent':'а','datv':'у','accs':'а','ablt':'ым','loct':'е'}
            return base+tails[case]
        if gender=='f' and base.endswith(('ова','ева','ина')):
            core=base[:-1]
            tails={'gent':'ой','datv':'ой','accs':'у','ablt':'ой','loct':'ой'}
            return core+tails[case]
    if base.endswith(('а','я')):
        stem=base[:-1]
        if base.endswith('а'): v={'gent':'ы','datv':'е','accs':'у','ablt':'ой','loct':'е'}
        else: v={'gent':'и','datv':'е','accs':'ю','ablt':'ей','loct':'е'}
        # Ж -> и, в частности Женя
        if stem[-1:] in ('ж','ш','ч','щ','г','к','х') and case=='gent': return stem+'и'
        return stem+v[case]
    if gender=='m' and base.endswith('й'):
        return base[:-1]+{'gent':'я','datv':'ю','accs':'я','ablt':'ем','loct':'е'}[case]
    if gender=='m' and base.endswith('ь'):
        return base[:-1]+{'gent':'я','datv':'ю','accs':'я','ablt':'ем','loct':'е'}[case]
    if gender=='m' and base.endswith(('ё','а')) is False:
        return base+{'gent':'а','datv':'у','accs':'а','ablt':'ом','loct':'е'}[case]
    return base


NAME_FORMS={}
for kind, male, female in [('NAME',MALE_FIRST+AMBIG_FIRST,FEMALE_FIRST+AMBIG_FIRST),('SURNAME',MALE_LAST,FEMALE_LAST)]:
    for g,words in [('m',male),('f',female)]:
        for base in words:
            for c in CASE_CODES:
                inf=inflect_word(base,g,c,kind)
                NAME_FORMS.setdefault(inf.lower(),[]).append((kind,base,g,c))

# Границы класса сущностей; слова вне словаря распознаются по явным полям.
PERSON_PATTERNS=[
 re.compile(r'\b(?:заявител[ьяюем]|клиент[ауом]?|гражданин(?:у|а|ом|е)?|гражданк[аеиуой]|получател[ьяюем]|сотрудник[ауом]?|посетител[ьяюем])\s*[:—-]?\s*([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)',re.I),
 re.compile(r'\b(?:фамилия)\s*[:=]\s*([А-ЯЁ][а-яё]+)',re.I),
 re.compile(r'\b(?:имя)\s*[:=]\s*([А-ЯЁ][а-яё]+)',re.I),
]

PATTERNS={
 'EMAIL': re.compile(r'(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w-])', FLAGS),
 'URL': re.compile(r'(?<![\w])https?://[A-Z0-9][A-Z0-9.-]+\.[A-Z]{2,}(?:/[\w~!$&\'()*+,;=:@%/?#.-]*)?',FLAGS),
 'IP': re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?!(?:\d|\.\d))'),
 'PHONE': re.compile(r'(?<!\d)(?:\+7|8)[\s-]*\(?\d{3}\)?[\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?!\d)'),
 'SNILS': re.compile(r'(?<!\d)\d{3}[- ]\d{3}[- ]\d{3}[ -]\d{2}(?!\d)'),
 'CADASTRAL': re.compile(r'(?<!\d)\d{2}:\d{2}:\d{6,7}:\d{1,6}(?!\d)'),
 'PASSPORT': re.compile(r'(?<!\d)\d{2}[\s-]?\d{2}[\s-]?\d{6}(?!\d)'),
 'CARD': re.compile(r'(?<!\d)(?:\d{4}[ -]?){3}\d{4}(?!\d)'),
 'INN': re.compile(r'(?<!\d)(?:\d{12}|\d{10})(?!\d)'),
 'OGRNIP': re.compile(r'(?<!\d)\d{15}(?!\d)'),
 'KLADR': re.compile(r'(?<!\d)\d{13}(?!\d)'),
 'CERT': re.compile(r'(?<!\w)[IVX]{1,4}[-–][А-ЯЁ]{2}\s*(?:№\s*)?\d{6}(?!\d)',FLAGS),
}
CERT_CONTEXT={'MARRIAGE_CERT':r'брак[аеиуом]?|о\s+заключении\s+брака|свидетельств[оа]\s+о\s+браке',
              'BIRTH_CERT':r'рождени[яеи]|свидетельств[оа]\s+о\s+рождении'}


def _valid(label: str, val: str, context: str) -> bool:
    d=re.sub(r'\D','',val)
    if label=='INN': return inn_ok(val)
    if label=='CARD': return luhn_ok(val)
    if label=='SNILS': return snils_ok(val)
    if label=='OGRNIP': return ogrnip_ok(val)
    if label=='IP':
        try: ipaddress.IPv4Address(val); return True
        except ipaddress.AddressValueError: return False
    if label=='KLADR': return bool(re.search(r'(?i)кла[дd]р|код\s+кладр',context))
    if label=='PASSPORT': return bool(re.search(r'паспорт',context,re.I))
    if label=='CADASTRAL': return bool(re.search(r'кадастр',context,re.I))
    if label=='INN': return inn_ok(val)
    if label=='CERT': return any(re.search(regex,context,re.I) for regex in CERT_CONTEXT.values())
    return True


def recognize(text: str, variant: str='odd') -> list[Entity]:
    if variant not in ('odd','even','all'): raise ValueError('variant: odd, even или all')
    allowed=set(ODD if variant=='odd' else EVEN if variant=='even' else ALL)
    found=[]
    occupied=[]
    def add(label,start,end):
        if label not in allowed or any(start < b and end > a for a,b in occupied): return False
        found.append(Entity(label,start,end,text[start:end])); occupied.append((start,end)); return True
    # Приоритет: структурированные выражения, затем имена. Это исключает пересечение классов.
    for label in ('EMAIL','URL','IP','PHONE','SNILS','CADASTRAL','CERT','PASSPORT','CARD','INN','OGRNIP','KLADR'):
        for m in PATTERNS[label].finditer(text):
            ctx=text[max(0,m.start()-58):m.start()].split('\n')[-1]
            actual=label
            if label=='CERT':
                if re.search(CERT_CONTEXT['MARRIAGE_CERT'],ctx,re.I): actual='MARRIAGE_CERT'
                elif re.search(CERT_CONTEXT['BIRTH_CERT'],ctx,re.I): actual='BIRTH_CERT'
                else: continue
            if actual not in allowed or not _valid(label,m.group(),ctx): continue
            end=m.end()
            if label=='URL':
                while end>m.start() and text[end-1] in '.,;!?': end-=1
            add(actual,m.start(),end)
    for pattern in PERSON_PATTERNS:
        for match in pattern.finditer(text):
            words=[(i, match.group(i),*match.span(i)) for i in range(1,match.lastindex+1)]
            if not words:continue
            # Явные поля однозначны. Для пары фамилия/имя выбирается по словарю;
            # для ранее не встречавшихся слов — порядок 'Фамилия Имя'.
            if 'фамилия' in match.group().lower()[:11]: labels=['SURNAME']
            elif re.search(r'^имя\s*[:=]',match.group(),re.I): labels=['NAME']
            elif len(words)==2:
                w1=NAME_FORMS.get(words[0][1].lower(),[])
                w2=NAME_FORMS.get(words[1][1].lower(),[])
                if any(x[0]=='NAME' for x in w1) and any(x[0]=='SURNAME' for x in w2): labels=['NAME','SURNAME']
                else: labels=['SURNAME','NAME']
            else: labels=['NAME']
            for (_,word,s,e),lbl in zip(words,labels): add(lbl,s,e)
    # Дополнительный словарный проход: в свободном тексте нет подписи «Имя:».
    # Например, в «Иван получил кредит» нужно найти самостоятельное имя.
    # Кандидаты должны начинаться с прописной буквы; конфликт с уже найденными
    # структурированными сущностями запрещён общей функцией add().
    for m in re.finditer(r'(?<![А-Яа-яЁё])([А-ЯЁ][а-яё]+)(?![А-Яа-яЁё])',text):
        forms=NAME_FORMS.get(m.group(1).lower(), [])
        if not forms: continue
        # Первое предпочтение: известная фамилия, далее известное имя.
        label='SURNAME' if any(f[0]=='SURNAME' for f in forms) else 'NAME'
        add(label,*m.span(1))
    return sorted(found,key=lambda e:(e.start,e.end))


def _pick_gender(text: str, ent: Entity, entities: list[Entity]) -> str:
    nearby=text[max(0,ent.start-70):ent.start].lower()
    if re.search(r'гражданк[аеиуой]|заявительниц[аыеуой]',nearby): return 'f'
    if re.search(r'гражданин(?:у|а|ом|е)?|заявител[ьяюем]',nearby):
        # «заявитель» не маркирует род при анонимных именах без дополнения.
        if re.search(r'гражданин(?:у|а|ом|е)?',nearby): return 'm'
    for e in entities:
        if e.label=='SURNAME' and abs(e.start-ent.start)<75:
            forms=NAME_FORMS.get(e.text.lower(),[])
            if forms: return forms[0][2]
            if e.text.lower().endswith(('ова','ева','ина','ой','ой')): return 'f'
    forms=NAME_FORMS.get(ent.text.lower(),[])
    return forms[0][2] if forms else 'm'


def _form(ent:Entity, gender: str):
    forms=NAME_FORMS.get(ent.text.lower(),[])
    for kind,base,g,case in forms:
        if kind==ent.label and g==gender: return base,case
    for kind,base,g,case in forms:
        if kind==ent.label: return base,case
    return ent.text,'nomn'


def _letters(rng,n=9): return ''.join(rng.choice(string.ascii_lowercase+string.digits) for _ in range(n))


def _replacement(ent: Entity, rng, gender: str):
    s=ent.text; label=ent.label
    if label in ('NAME','SURNAME'):
        src,case=_form(ent,gender)
        pool=(MALE_FIRST if gender=='m' else FEMALE_FIRST) if label=='NAME' else (MALE_LAST if gender=='m' else FEMALE_LAST)
        options=[n for n in pool if n!=src and inflect_word(n,gender,case,label).lower()!=s.lower()]
        chosen=rng.choice(options)
        return inflect_word(chosen,gender,case,label)
    if label=='INN': return inn_build(s[:4],rng,len(s),s[-1:] if len(s)==10 else s[-2:])
    if label=='CARD':
        ds=re.sub(r'\D','',s); new=luhn_finish(ds[:6]+''.join(str(rng.randrange(10)) for _ in range(len(ds)-7)))
        it=iter(new); return ''.join(next(it) if c.isdigit() else c for c in s)
    if label=='PASSPORT':
        ds=re.sub(r'\D','',s); new=ds[:4]+''.join(str(rng.randrange(10)) for _ in range(6)); it=iter(new)
        return ''.join(next(it) if c.isdigit() else c for c in s)
    if label=='SNILS': return snils_build(rng)
    if label=='OGRNIP': return ogrnip_build(s[:5],rng)
    if label=='PHONE':
        digits=re.sub(r'\D','',s); new=digits[:4]+''.join(str(rng.randrange(10)) for _ in range(7)); it=iter(new)
        return ''.join(next(it) if c.isdigit() else c for c in s)
    if label=='CADASTRAL':
        parts=s.split(':'); return ':'.join(parts[:3]+[str(rng.randrange(1,10**len(parts[3]))).zfill(len(parts[3]))])
    if label=='KLADR': return s[:8]+''.join(str(rng.randrange(10)) for _ in range(5))
    if label=='IP':
        arr=s.split('.'); return '.'.join(arr[:2]+[str(rng.randrange(1,254)),str(rng.randrange(1,254))])
    if label=='EMAIL':
        local,domain=s.rsplit('@',1)
        return _letters(rng,max(6,min(12,len(local))))+'@'+domain
    if label=='URL':
        m=re.match(r'(https?://)([^/]+)(.*)',s,re.I)
        if not m:return s
        hostname=m.group(2).split('.')
        if len(hostname)>=3: hostname[-3]=_letters(rng,7)
        else:hostname[0]=_letters(rng,7)
        return m.group(1)+'.'.join(hostname)+m.group(3)
    if label in ('MARRIAGE_CERT','BIRTH_CERT'):
        return re.sub(r'\d{6}$',''.join(str(rng.randrange(10)) for _ in range(6)),s)
    return s


class Anonymizer:
    """Один экземпляр = одна сессия с согласованными отображениями.

    Повторное anonymize() того же текста идемпотентно внутри сессии;
    новая сессия генерирует новые псевдонимы, включая одинаковые исходники.
    """
    def __init__(self, variant='odd', seed: int|None=None):
        self.variant=variant
        self.rng=random.Random(seed) if seed is not None else secrets.SystemRandom()
        self.mapping={}
        self.generated=set()
        self.seed=seed

    def anonymize(self, text: str):
        ents=recognize(text,self.variant)
        result=text
        for e in reversed(ents):
            gender=_pick_gender(text,e,ents) if e.label in ('NAME','SURNAME') else ''
            if e.text in self.generated: continue
            base,case=_form(e,gender) if e.label in ('NAME','SURNAME') else (e.text,'')
            key=(e.label,base.lower(),gender)
            if key not in self.mapping:
                candidate=_replacement(e,self.rng,gender)
                # Для ФИО храним лемму, чтобы разные падежи заменялись согласованно.
                if e.label in ('NAME','SURNAME'):
                    chosen_base,_=_form(Entity(e.label,0,len(candidate),candidate),gender)
                    self.mapping[key]=chosen_base
                else: self.mapping[key]=candidate
            canonical=self.mapping[key]
            replacement=inflect_word(canonical,gender,case,e.label) if e.label in ('NAME','SURNAME') else canonical
            if replacement==e.text:
                replacement=_replacement(e,self.rng,gender)
            self.generated.add(replacement)
            result=result[:e.start]+replacement+result[e.end:]
        return result,[[e.label,e.start,e.end] for e in ents]


def anon(text:str,variant='odd',seed=None):
    """API: (обезличенный текст, список [label,start,end] с исходными смещениями)."""
    return Anonymizer(variant=variant,seed=seed).anonymize(text)


def mask(text:str,entities:list[Entity]):
    result=text
    for e in reversed(entities): result=result[:e.start]+'*'*(e.end-e.start)+result[e.end:]
    return result


def mask_all_text(text: str) -> str:
    """Вторая контрольная схема из задания: каждый символ заменён на '*'."""
    return '*' * len(text)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description='Синонимическое обезличивание ПДн')
    p.add_argument('text', nargs='?', default='Гражданин Иванов Пётр, ИНН 7701291417.')
    p.add_argument('--variant',choices=('odd','even','all'),default='odd')
    p.add_argument('--seed',type=int)
    args=p.parse_args()
    print(json.dumps(anon(args.text,args.variant,args.seed),ensure_ascii=False,indent=2))
