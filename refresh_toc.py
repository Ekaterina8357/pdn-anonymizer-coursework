"""Update the static contents page numbers from a rendered report PDF."""
from __future__ import annotations

import json
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


def refresh(pdf_path: Path, toc_json: Path) -> dict:
    locations={}
    with fitz.open(pdf_path) as document:
        for i,page in enumerate(document):
            if i==0 or i==2:  # cover and contents; contents repeats all headings
                continue
            lines=[x.strip() for x in page.get_text().splitlines() if x.strip()]
            start=' '.join(x for x in lines[:4] if not x.isdigit())
            for key,prefix in KEY_PREFIXES.items():
                if key not in locations and prefix.casefold() in start.casefold():
                    locations[key]=i+1
    missing=set(KEY_PREFIXES)-set(locations)
    if missing: raise RuntimeError(f'TOC headings not found: {sorted(missing)}')
    toc_json.write_text(json.dumps(locations,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return locations


if __name__=='__main__':
    path=Path(sys.argv[1])
    target=Path(sys.argv[2])
    print(json.dumps(refresh(path,target),ensure_ascii=False,indent=2))
