import json
from pathlib import Path
p=Path(__file__).parent/'run_bertscore_in_colab.ipynb'
def c(typ,src):
    return {'cell_type':typ,'source':[x+'\n' for x in src.splitlines()],'metadata':{}}|({'outputs':[],'execution_count':None} if typ=='code' else {})
nb={'cells':[
 c('markdown','''# Реальный BERTScore для курсовой по ПДн
Откройте ноутбук на Google Colab. Запустите ячейки по порядку. Требуется загрузить архив `coursework_pdn.zip` из комплекта.'''),
 c('code','''!pip -q install "bert-score>=0.3.13" "transformers>=4.36,<5" sentencepiece'''),
 c('code','''from google.colab import files
uploaded = files.upload()  # выберите архив coursework_pdn.zip
import os, zipfile
archive = next(name for name in uploaded if name.endswith('.zip'))
with zipfile.ZipFile(archive) as z: z.extractall('/content')
%cd /content/coursework_pdn'''),
 c('code','''!python evaluate.py --bertscore --model DeepPavlov/rubert-base-cased'''),
 c('code','''import json
with open('results/bertscore_metrics.json',encoding='utf-8') as f: result=json.load(f)
print(json.dumps(result,ensure_ascii=False,indent=2))
files.download('results/bertscore_metrics.json')''')
], 'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python'}},'nbformat':4,'nbformat_minor':5}
p.write_text(json.dumps(nb,ensure_ascii=False,indent=2),encoding='utf-8')
print(p)
