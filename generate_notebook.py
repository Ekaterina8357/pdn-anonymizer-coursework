import json
from pathlib import Path
p=Path(__file__).parent/'run_bertscore_in_colab.ipynb'
def c(typ,src):
    return {'cell_type':typ,'source':[x+'\n' for x in src.splitlines()],'metadata':{}}|({'outputs':[],'execution_count':None} if typ=='code' else {})
nb={'cells':[
 c('markdown','''# Семантическая оценка обезличивания: BERTScore
Эксперимент для варианта № 15. Русскоязычная модель DeepPavlov/rubert-base-cased; сравнение синонимического обезличивания и двух видов маскирования на 150 синтетических текстах.'''),
 c('code','''!pip -q install "bert-score>=0.3.13" "transformers>=4.36,<5" sentencepiece'''),
 c('code','''!git clone -q https://github.com/Ekaterina8357/pdn-anonymizer-coursework.git /content/pdn-anonymizer-coursework
%cd /content/pdn-anonymizer-coursework'''),
 c('code','''!python evaluate.py --bertscore --model DeepPavlov/rubert-base-cased'''),
 c('code','''import json
from google.colab import files
with open('results/bertscore_metrics.json',encoding='utf-8') as f: result=json.load(f)
print(json.dumps(result,ensure_ascii=False,indent=2))
files.download('results/bertscore_metrics.json')''')
], 'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python'}},'nbformat':4,'nbformat_minor':5}
p.write_text(json.dumps(nb,ensure_ascii=False,indent=2),encoding='utf-8')
print(p)
