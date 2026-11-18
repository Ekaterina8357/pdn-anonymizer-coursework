"""Определение номеров страниц разделов и подразделов для поля оглавления Word."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz

KEY_PREFIXES = {
    'РЕФЕРАТ': 'РЕФЕРАТ',
    'ПЕРЕЧЕНЬ СОКРАЩЕНИЙ И ОБОЗНАЧЕНИЙ': 'ПЕРЕЧЕНЬ СОКРАЩЕНИЙ И ОБОЗНАЧЕНИЙ',
    'ВВЕДЕНИЕ': 'ВВЕДЕНИЕ',
    '1 ТЕОРЕТИЧЕСКИЕ ОСНОВЫ': '1 Теоретические основы',
    '2 ФОРМИРОВАНИЕ И РАЗМЕТКА': '2 Формирование и разметка',
    '3 АРХИТЕКТУРА И РЕАЛИЗАЦИЯ': '3 Архитектура и реализация',
    '4 МЕТОДИКА ЭКСПЕРИМЕНТА': '4 Методика экспериментального',
    '5 ОЦЕНКА СОХРАНЕНИЯ СЕМАНТИКИ': '5 Оценка сохранения',
    '6 ОГРАНИЧЕНИЯ И НАПРАВЛЕНИЯ РАЗВИТИЯ': '6 Ограничения и направления',
    'ЗАКЛЮЧЕНИЕ': 'ЗАКЛЮЧЕНИЕ',
    'СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ': 'СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ',
    'ПРИЛОЖЕНИЕ А': 'ПРИЛОЖЕНИЕ А',
    'ПРИЛОЖЕНИЕ Б': 'ПРИЛОЖЕНИЕ Б',
    'ПРИЛОЖЕНИЕ В': 'ПРИЛОЖЕНИЕ В',
}
SUBSECTIONS = {
    '1.1','1.2','1.3','2.1','2.2','2.3',
    '3.1','3.2','3.3','3.4','3.5','3.6',
    '4.1','4.2','4.3','5.1','5.2','5.3',
    '6.1','6.2','6.3',
}


def refresh(pdf_path: Path, toc_json: Path) -> dict:
    locations={}
    body_started=False
    with fitz.open(pdf_path) as document:
        for i,page in enumerate(document):
            if i==0:
                continue
            lines=[x.strip() for x in page.get_text().splitlines() if x.strip()]
            content_lines=[line for line in lines if not line.isdigit()]
            start=' '.join(content_lines[:4])
            if i==1:
                locations['РЕФЕРАТ']=i+1
                continue
            # В оглавлении заголовки перечислены повторно. Их нельзя
            # принимать за реальные положения подразделов на страницах.
            if not body_started:
                if not content_lines or content_lines[0].upper() != 'ПЕРЕЧЕНЬ СОКРАЩЕНИЙ И ОБОЗНАЧЕНИЙ':
                    continue
                body_started=True
            for key,prefix in KEY_PREFIXES.items():
                if key not in locations and prefix.casefold() in start.casefold():
                    locations[key]=i+1
            for line in content_lines:
                m=re.match(r'^(\d+\.\d+)\s+[А-ЯЁ]',line)
                if m and m.group(1) in SUBSECTIONS and m.group(1) not in locations:
                    locations[m.group(1)]=i+1
    missing=set(KEY_PREFIXES)-set(locations)
    missing.update(SUBSECTIONS-set(locations))
    if missing: raise RuntimeError(f'TOC headings not found: {sorted(missing)}')
    toc_json.write_text(json.dumps(locations,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return locations


if __name__=='__main__':
    path=Path(sys.argv[1])
    target=Path(sys.argv[2])
    print(json.dumps(refresh(path,target),ensure_ascii=False,indent=2))
