import io
import re
import pandas as pd

def matrix(rows):
    keys={'authors':'Authors','year':'Year','title':'Paper Title','doi':'DOI','construct':'Construct',
          'verified_quote':'Exact Quote','classification':'Evidence Type','interpretation':'AI Interpretation',
          'notes':'Researcher Notes','chapter':'Thesis Chapter','section':'Thesis Section','paper_id':'Paper ID',
          'source_chunk_id':'Source Chunk ID','verification_status':'Verification Status'}
    records=[]
    for r in rows:
        record={label:r.get(key,'') for key,label in keys.items()}
        record['PDF Page']=r['page_index']+1
        # Spreadsheet formula injection protection, including source text.
        records.append({k:("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v) for k,v in record.items()})
    return pd.DataFrame(records,columns=[*keys.values(),'PDF Page'])

def excel(rows):
    buffer=io.BytesIO()
    matrix(rows).to_excel(buffer,index=False,engine='openpyxl')
    return buffer.getvalue()

def bibtex(papers):
    def escape(s):
        return str(s).replace('\\',r'\textbackslash{}').replace('{',r'\{').replace('}',r'\}').replace('\n',' ')
    entries=[]
    for p in papers:
        if not all(p.get(k) for k in ('title','authors','year')):
            continue
        fields={'title':p['title'],'author':p['authors'].replace(';',' and'),'year':p['year']}
        if p.get('doi'): fields['doi']=p['doi']
        if p.get('journal'): fields['journal']=p['journal']
        entries.append('@article{rv'+p['id']+',\n'+',\n'.join(f'  {k} = {{{escape(v)}}}' for k,v in fields.items())+'\n}')
    return '\n\n'.join(entries)
