"""Unit-тесты стандартной библиотекой unittest (без зависимостей)."""
import unittest
import random
import json
from pathlib import Path
from pdn import (Anonymizer,anon,recognize,bio_tags,Entity,inn_build,inn_ok,luhn_ok,
                 luhn_finish,snils_build,snils_ok,ogrnip_build,ogrnip_ok,mask,mask_all_text)

class TestPDN(unittest.TestCase):
    def test_inn10_and12_checksums(self):
        for length in (10,12):
            v=inn_build('7701',random.Random(9),length)
            self.assertTrue(inn_ok(v))
            self.assertFalse(inn_ok(v[:-1]+str((int(v[-1])+1)%10)))
    def test_inn_control_and_prefix_preserved(self):
        for n in (10,12):
            old=inn_build('7701',random.Random(24),n)
            new,_=anon('ИНН: '+old,'odd',seed=15)
            value=new.split()[-1]
            self.assertNotEqual(value,old)
            self.assertTrue(inn_ok(value))
            self.assertEqual(value[:4],old[:4])
            self.assertEqual(value[-(1 if n==10 else 2):],old[-(1 if n==10 else 2):])
    def test_credit_card_luhn(self):
        v=luhn_finish('427612'+ '123456789')
        self.assertTrue(luhn_ok(v));self.assertFalse(luhn_ok(v[:-1]+'0') if v[-1]!='0' else luhn_ok(v[:-1]+'1'))
        out,_=anon('Карта: '+' '.join(v[i:i+4] for i in range(0,16,4)),seed=42)
        new=out.split(': ',1)[1]
        self.assertTrue(luhn_ok(new));self.assertEqual(new.replace(' ', '')[:6],v[:6])
    def test_snils(self):
        v=snils_build(random.Random(5))
        self.assertTrue(snils_ok(v))
        self.assertEqual([e.label for e in recognize('СНИЛС: '+v)],['SNILS'])
    def test_ogrnip(self):
        v=ogrnip_build('32677',random.Random(5))
        self.assertTrue(ogrnip_ok(v))
        self.assertEqual([e.label for e in recognize('ОГРНИП: '+v,'even')],['OGRNIP'])
    def test_female_sasha_gender_from_adjacent_surname(self):
        text='Гражданка Иванова Саша представила документы.'
        a=Anonymizer(seed=11)
        changed,tags=a.anonymize(text)
        self.assertEqual([x[0] for x in tags],['SURNAME','NAME'])
        self.assertNotIn('Иванова Саша',changed)
        self.assertTrue(any(x in changed for x in ('ова ','ева ','ина ')))
    def test_name_case_inflection(self):
        for text in ['Ответ передан гражданину Иванову Петру.',
                     'Обращение от гражданки Ивановой Марии.']:
            changed,tags=Anonymizer(seed=12).anonymize(text)
            self.assertEqual(len(tags),2)
            self.assertNotEqual(text,changed)
            self.assertEqual(len(recognize(changed)),2)
    def test_idempotence_session_and_randomness(self):
        text='Гражданин Иванов Пётр. ИНН: '+inn_build('7701',random.Random(1),10)
        a=Anonymizer(seed=999)
        once,_=a.anonymize(text)
        twice,_=a.anonymize(once)
        self.assertEqual(once,twice)
        alternative,_=Anonymizer(seed=500).anonymize(text)
        self.assertNotEqual(once,alternative)
    def test_priority_and_disjointness(self):
        text='Заявитель: Иванов Антон. E-mail: anton.ivanov@example.ru. IP: 192.168.1.10.'
        entities=recognize(text,'even')
        self.assertEqual({e.label for e in entities},{'SURNAME','NAME','EMAIL','IP'})
        for i,x in enumerate(entities):
            for y in entities[i+1:]: self.assertFalse(x.start<y.end and y.start<x.end)
    def test_no_invalid_ip(self):
        self.assertEqual(recognize('IP: 999.999.999.999','even'),[])
    def test_mask_length(self):
        txt='Гражданин Иванов Пётр.'
        m=mask(txt,recognize(txt))
        self.assertEqual(len(txt),len(m));self.assertNotIn('Иванов',m)
        self.assertEqual(mask_all_text(txt),'*'*len(txt))
    def test_standalone_name_without_explicit_label(self):
        text='Иван получил кредит.'
        changed, tags=anon(text, seed=3)
        self.assertEqual(tags, [['NAME',0,4]])
        self.assertNotEqual(changed,text)
        self.assertEqual(len(recognize(changed)),1)
    def test_repeated_name_has_consistent_pseudonym(self):
        text='Иван получил кредит. Иван погасил кредит.'
        changed, entities=Anonymizer(seed=52).anonymize(text)
        self.assertEqual(len(entities),2)
        tokens=changed.split()
        self.assertEqual(tokens[0],tokens[3])
        self.assertNotEqual(tokens[0],'Иван')
    def test_bio_unique_tag(self):
        txt='Гражданин Иванов Иван.'
        tags=bio_tags(txt,recognize(txt))
        self.assertEqual(len(tags),len(set((a['start'],a['end']) for a in tags)))
        self.assertEqual(len([x for x in tags if x['tag']!='O']),2)
    def test_data_corpus(self):
        path=Path(__file__).parent/'data/test.jsonl'
        if not path.exists():self.skipTest('dataset not yet generated')
        rows=[json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
        self.assertGreaterEqual(len(rows),100)
        from collections import Counter
        counts=Counter(e['label'] for r in rows for e in r['entities'])
        self.assertTrue(all(n>=50 for n in counts.values()))

if __name__=='__main__': unittest.main(verbosity=2)
