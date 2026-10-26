import base64
import html
import json
import logging
import os
import re
import sqlite3
import streamlit as st
import streamlit.components.v1 as components
from core.config import DATA, MODEL, EMBED_MODEL, MAX_UPLOAD, MAX_AI_CHUNKS, has_key, ai_enabled, PROVIDER, OLLAMA_BASE_URL
from core.database import Database
from services.library import Library
from services.search import Search
from services.evidence import Evidence
from services.ai import AI
from services.export import matrix, excel, bibtex

logging.basicConfig(level=logging.INFO)
st.set_page_config(page_title='ResearchVault AI',page_icon='📚',layout='wide')
st.markdown('''<style>.stApp {font-family:system-ui;} h1,h2,h3 {color:#24486d;}
[data-testid="stMetric"] {border:1px solid #d9e2ed;border-radius:12px;padding:18px;}
</style>''',unsafe_allow_html=True)
db=Database()
library=Library(db)
evidence=Evidence(db)
ai=AI(db)
profile=db.profile()
papers=library.papers()
by_id={p['id']:p for p in papers}
nav=st.sidebar.radio('Ruang Penyelidikan',['Dashboard','Pustaka Kertas','AI Evidence Finder','Construct Explorer','Evidence Bank','AI Literature Synthesis','Profil Penyelidikan','Tetapan'])
st.sidebar.caption('ResearchVault AI • Local-first')
st.sidebar.caption(('Ollama dipilih • semak sambungan di Tetapan' if PROVIDER == 'ollama' else 'OpenAI dikonfigurasi') if ai_enabled() else 'Mod tempatan • AI tidak dikonfigurasi')
st.sidebar.info(('AI menggunakan Ollama di '+OLLAMA_BASE_URL+'. Tiada API key diperlukan. ' if PROVIDER == 'ollama' else 'Petikan dihantar ke OpenAI apabila anda menggunakan AI atau semantic indexing. ')+'DOI lookup menghantar DOI ke Crossref. PDF asal disimpan secara tempatan.')


def attempt(fn):
    try:
        with st.spinner('Sedang memproses…'):
            return fn()
    except Exception as exc:
        logging.exception('Operation failed')
        st.error(str(exc))
        return None


def source_view(paper_id,page_index,key):
    path=library.path(paper_id)
    if not path.exists():
        st.error('Fail sumber tidak tersedia'); return
    with st.expander(f'Buka PDF asal — halaman {page_index+1}'):
        content=path.read_bytes()
        encoded=base64.b64encode(content).decode('ascii')
        components.html(f'<iframe title="Source PDF page {page_index+1}" src="data:application/pdf;base64,{encoded}#page={page_index+1}" width="100%" height="650"></iframe>',height=670)
        st.caption('Nombor halaman ialah halaman fizikal PDF. Nombor halaman bercetak dan seksyen belum dikenal pasti. Jika browser menyekat PDF tertanam, muat turun dan buka halaman yang ditunjukkan.')
        st.download_button('Muat turun PDF asal',content,file_name=by_id[paper_id]['filename'],mime='application/pdf',key='pdf'+key)


def result_view(row,key,save=True):
    with st.container(border=True):
        st.markdown(f"**{row['title']}**")
        st.caption(f"{row['authors'] or 'Not available'} · {row['year'] or 'Not available'} · PDF halaman {row['page_index']+1} · DOI: {row.get('doi') or 'Not available'}")
        # Format whitespace only for reading; keep the verified source untouched.
        readable_quote = re.sub(r'\s+', ' ', row['verified_quote']).strip()
        st.markdown(
            '<div style="line-height:1.65;overflow-wrap:anywhere;margin:0.5rem 0;">'
            + html.escape(readable_quote) + '</div>',
            unsafe_allow_html=True,
        )
        st.caption('Paparan dirapikan: jarak dan pemisahan baris sahaja. Perkataan asal dikekalkan.')
        with st.expander('Lihat teks asal hasil ekstraksi PDF'):
            st.text(row['verified_quote'])
        st.caption('Verified: padanan teks sumber PDF; ini tidak mengesahkan kebenaran dapatan kajian.')
        st.write('Klasifikasi:',row.get('classification','Inconclusive'))
        if row.get('interpretation'):
            st.write('Tafsiran AI (semak sendiri):',row['interpretation'])
        if save:
            col1,col2=st.columns(2)
            if col1.button('Simpan Evidence',key='save'+key):
                if attempt(lambda:evidence.save(row)):
                    st.success('Evidence disimpan')
            if col2.button('Klasifikasi AI',key='class'+key,disabled=not ai_enabled()):
                classified=attempt(lambda:ai.classify(row))
                if classified:
                    st.session_state['classified'+key]=classified
            if 'classified'+key in st.session_state:
                classified=st.session_state['classified'+key]
                st.json({k:classified[k] for k in ['verified_quote','classification','construct','interpretation']})
                if st.button('Simpan klasifikasi AI',key='saveclass'+key):
                    if attempt(lambda:evidence.save(classified)):
                        st.success('Disimpan')
        source_view(row['paper_id'],row['page_index'],key)


def run_search(construct=''):
    query=st.text_input('Cari bukti merentas pustaka',value=construct,key='query'+construct)
    mode=st.selectbox('Kaedah retrieval',['Keyword','Hybrid','Semantic'],key='mode'+construct)
    purpose=st.selectbox('Mod carian',['Exact Evidence Search','Conceptual Search','Cross-Paper Synthesis'],key='purpose'+construct)
    st.caption('Istilah berkaitan diperluas menggunakan profil. Sinonim carian tidak membuktikan bahawa konstruk teori adalah sama. Hasil teratas bukan liputan menyeluruh pustaka.')
    cols=st.columns(3)
    author=cols[0].text_input('Penulis',key='author'+construct)
    year=cols[1].text_input('Tahun',key='year'+construct)
    limit=cols[2].number_input('Had hasil',1,50,10,key='limit'+construct)
    selected=st.multiselect('Hadkan kepada kertas',list(by_id),format_func=lambda i:by_id[i]['title'],key='papers'+construct)
    if not construct:
        construct_filter=st.selectbox('Konstruk berkaitan',['',*profile['constructs']],key='constructfilter')
    else:
        construct_filter=construct
    state_key='results'+construct
    if st.button('Cari Evidence',type='primary',key='search'+construct):
        outcome=attempt(lambda:Search(db).search(query,mode,int(limit),selected,author,year,construct_filter))
        if outcome:
            st.session_state[state_key]=outcome
    if state_key in st.session_state:
        results,warnings=st.session_state[state_key]
        for warning in warnings: st.warning(warning)
        st.write(f'{len(results)} petikan ditemui')
        # Group by paper while preserving first appearance in rank order.
        groups={}
        for row in results:
            if row['paper_id'] in by_id:
                groups.setdefault(row['paper_id'],[]).append(row)
        for pid,group in groups.items():
            st.subheader(by_id[pid]['title'])
            for row in group: result_view(row,construct+row['id'])
        if purpose=='Cross-Paper Synthesis':
            st.info('Simpan petikan yang anda pilih ke Evidence Bank, kemudian gunakan AI Literature Synthesis untuk mengawal sumber sintesis.')
        elif purpose=='Conceptual Search' and mode=='Keyword':
            st.info('Gunakan Hybrid atau Semantic dengan provider AI dan embeddings yang telah dikonfigurasi untuk carian vektor.')


st.title('ResearchVault AI')
st.caption('Pustaka penyelidikan • Bukti berjejak • Penulisan berintegriti')
if nav=='Dashboard':
    st.subheader('Gambaran Penyelidikan')
    indexed=0
    if (db.root/'chroma').exists():
        try:
            from services.vectors import Vectors
            indexed=len(Vectors(db).indexed_papers() & set(by_id))
        except Exception as exc: st.warning(f'Vector index: {exc}')
    counts=[('Kertas Dimuat Naik',len(papers)),('Semantic Indexed',indexed),
            ('Pending / Gagal / OCR',sum(p['status'] not in ['Extracted'] for p in papers)),
            ('Highly Relevant',sum(json.loads(p['assessment']).get('category')=='High' for p in papers if p['assessment'])),
            ('Evidence Disimpan',len(evidence.all())),('Konstruk',len(profile['constructs']))]
    for col,(label,value) in zip(st.columns(3)*2,counts): col.metric(label,value)
    st.info('Mulakan dengan menyemak Profil Penyelidikan, kemudian muat naik PDF di Pustaka Kertas. Tiada contoh artikel rekaan dimasukkan ke pustaka anda.')
    st.write(profile['title'])

elif nav=='Pustaka Kertas':
    st.subheader('Pustaka Kertas')
    uploads=st.file_uploader(f'Muat naik PDF (maksimum {MAX_UPLOAD//1024//1024} MB setiap fail)',type=['pdf'],accept_multiple_files=True)
    if st.button('Proses semua PDF',disabled=not uploads):
        for upload in uploads:
            result=attempt(lambda u=upload:library.upload(u.name,u.getvalue()))
            if result: st.success(f'{upload.name}: '+('disimpan' if result[1] else 'duplikat — digunakan semula'))
        st.rerun()
    search=st.text_input('Tapis tajuk, penulis, tahun atau kata kunci')
    category=st.selectbox('Relevansi',['Semua','High','Moderate','Low','Belum dinilai'])
    visible=[]
    for p in papers:
        cat=json.loads(p['assessment']).get('category') if p['assessment'] else 'Belum dinilai'
        if search.lower() in ' '.join(str(p[k]) for k in ['title','authors','year','keywords']).lower() and (category=='Semua' or category==cat): visible.append(p)
    if visible: st.dataframe([{k:p[k] for k in ['title','authors','year','status','metadata_status']} for p in visible],hide_index=True,use_container_width=True)
    selected_bulk=st.multiselect('Pilih kertas untuk operasi AI',list(by_id),format_func=lambda i:by_id[i]['title'])
    st.caption('Embeddings dicache setiap chunk dan model. '+('Teks diproses oleh server Ollama yang dikonfigurasi.' if PROVIDER == 'ollama' else 'Operasi ini menghantar teks dokumen ke OpenAI dan mungkin dikenakan kos API.'))
    c1,c2=st.columns(2)
    if c1.button('Index Semantic — pilihan',disabled=not ai_enabled() or not selected_bulk):
        from services.vectors import Vectors
        for pid in selected_bulk:
            count=attempt(lambda p=pid:Vectors(db).index(p))
            if count is not None: st.success(f'{by_id[pid]["title"]}: {count} chunks indexed')
    if c2.button('Analyze Relevance — pilihan',disabled=not ai_enabled() or not selected_bulk):
        for pid in selected_bulk:
            result=attempt(lambda p=pid:ai.relevance(p))
            if result: st.json(result)
    if visible:
        pid=st.selectbox('Urus kertas',[p['id'] for p in visible],format_func=lambda i:by_id[i]['title'])
        p=by_id[pid]
        st.caption(f"ID: {pid} · {p['status']} · {p['pages']} halaman · Metadata: {p['metadata_status']}")
        if p['error']: st.warning(p['error'])
        with st.form('metadata'+pid):
            values={k:st.text_area(k.title(),value=p[k]) if k=='abstract' else st.text_input(k.title(),value=p[k]) for k in ['title','authors','year','journal','doi','abstract','keywords']}
            if st.form_submit_button('Simpan metadata manual'):
                try:
                    library.update(pid,**values,metadata_status='Manually entered — not externally verified')
                    st.rerun()
                except sqlite3.IntegrityError: st.error('DOI ini sudah digunakan oleh kertas lain. Semak duplikat.')
        if st.button('Semak DOI dengan Crossref'):
            if attempt(lambda:(library.crossref(pid,values['doi']),True)[1]): st.rerun()
        if st.button('Analyze Relevance',disabled=not ai_enabled()):
            if attempt(lambda:ai.relevance(pid)): st.rerun()
        if p['assessment']:
            st.warning('Skor relevansi ialah heuristik AI, bukan pengukuran saintifik yang disahkan. Analisis ialah sampel, bukan semakan menyeluruh.')
            assessment=json.loads(p['assessment'])
            if assessment.get('profile_snapshot') != profile: st.warning('Profil telah berubah. Jalankan semula analisis.')
            st.json(assessment)
        if st.button('Cuba semula pemprosesan'):
            attempt(lambda:library.process(pid)); st.rerun()
        source_view(pid,0,'library'+pid)
        confirm=st.checkbox('Padam kertas, petikan Evidence Bank dan semua embeddings berkaitan',key='confirm'+pid)
        if st.button('Padam kertas',disabled=not confirm):
            if attempt(lambda:(library.delete(pid),True)[1]):
                st.session_state.clear(); st.rerun()
    st.download_button('Eksport BibTeX (metadata lengkap sahaja)',bibtex(visible),'researchvault.bib')

elif nav=='AI Evidence Finder':
    st.subheader('AI Evidence Finder')
    run_search()

elif nav=='Construct Explorer':
    st.subheader('Construct Explorer')
    st.write('Framework aktif:',profile['framework'])
    if profile['constructs']:
        construct=st.selectbox('Pilih konstruk',list(profile['constructs']))
        st.write('Istilah berkaitan:',', '.join(profile['constructs'][construct]) or 'Belum ditetapkan')
        run_search(construct)
    else: st.info('Tambah konstruk dalam profil dahulu.')

elif nav=='Evidence Bank':
    st.subheader('Literature Evidence Matrix')
    rows=evidence.all()
    term=st.text_input('Tapis konstruk, tema, bab, seksyen atau penulis')
    rows=[r for r in rows if term.lower() in ' '.join(str(r.get(k,'')) for k in ['construct','theme','chapter','section','authors']).lower()]
    st.dataframe(matrix(rows),hide_index=True,use_container_width=True)
    st.download_button('Eksport Excel',excel(rows),'evidence_matrix.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    st.download_button('Eksport CSV',matrix(rows).to_csv(index=False).encode('utf-8-sig'),'evidence_matrix.csv',mime='text/csv')
    if rows:
        eid=st.selectbox('Edit evidence',[r['id'] for r in rows],format_func=lambda i:next(r['title']+' · '+r['verified_quote'][:50] for r in rows if r['id']==i))
        row=next(r for r in rows if r['id']==eid)
        result_view(row,'bank'+eid,False)
        with st.form('edit'+eid):
            edits={k:st.text_area(k.title(),value=row[k]) for k in ['construct','theme','interpretation','notes','chapter','section']}
            choices=['Supporting','Contradicting','Mixed','Inconclusive','Background / Conceptual']
            edits['classification']=st.selectbox('Klasifikasi',choices,index=choices.index(row['classification']))
            if st.form_submit_button('Simpan perubahan'):
                evidence.edit(eid,**edits); st.rerun()
        if st.button('Buang evidence'):
            db.execute('DELETE FROM evidence WHERE id=?',(eid,)); st.rerun()

elif nav=='AI Literature Synthesis':
    st.subheader('AI Literature Synthesis')
    st.warning('Draf AI mesti disemak penyelidik sebelum digunakan dalam tesis. Pengesahan petikan tidak menjamin semua tuntutan sintesis disokong.')
    rows=evidence.all()
    ids=st.multiselect('Pilih sumber evidence',[r['id'] for r in rows],format_func=lambda i:next(r['title']+' · '+r['construct'] for r in rows if r['id']==i))
    question=st.text_area('Arahan sintesis',value='Compare the selected evidence, cite evidence IDs, distinguish theoretical and empirical findings, and identify contradictions and limitations.')
    if st.button('Jana draf sintesis',disabled=not ai_enabled() or not ids):
        result=attempt(lambda:ai.synthesize([r for r in rows if r['id'] in ids],question))
        if result: st.session_state['synthesis']=result
    if 'synthesis' in st.session_state:
        result=st.session_state['synthesis']
        st.write(result['draft']); st.json({k:v for k,v in result.items() if k!='draft'})
        st.download_button('Muat turun draf',json.dumps(result,ensure_ascii=False,indent=2),'synthesis.json')

elif nav=='Profil Penyelidikan':
    st.subheader('Profil Penyelidikan')
    st.caption('Satu profil tempatan aktif. Contoh awal boleh diedit sepenuhnya; soalan, objektif dan definisi perlu dilengkapkan sendiri.')
    with st.form('profile'):
        updated={}
        labels={'title':'Tajuk','background':'Latar belakang','problem':'Masalah kajian','questions':'Soalan kajian','objectives':'Objektif','methodology':'Metodologi','framework':'Theoretical Framework','definitions':'Definisi konstruk','outcomes':'Outcomes','keywords':'Kata kunci'}
        for field,label in labels.items(): updated[field]=st.text_area(label,value=profile.get(field,''))
        constructs=st.text_area('Konstruk dan istilah berkaitan (JSON: nama → senarai istilah)',json.dumps(profile['constructs'],indent=2),height=350)
        if st.form_submit_button('Simpan profil'):
            try:
                parsed=json.loads(constructs)
                if not isinstance(parsed,dict) or not all(isinstance(k,str) and isinstance(v,list) and all(isinstance(x,str) for x in v) for k,v in parsed.items()):
                    raise ValueError('Gunakan objek JSON dengan senarai teks bagi setiap konstruk')
                updated['constructs']=parsed; db.save_profile(updated); st.success('Profil disimpan')
            except (ValueError,TypeError) as exc: st.error(str(exc))

elif nav=='Tetapan':
    st.subheader('Tetapan & Privasi')
    st.write('Data tempatan:',str(DATA))
    st.write('AI model:',MODEL,'· Embedding model:',EMBED_MODEL)
    st.write('AI provider:', PROVIDER)
    if PROVIDER == 'openai':
        st.write('API key:', 'Dikonfigurasi (nilai disembunyikan)' if has_key() else 'Tidak dikonfigurasi')
    else:
        st.write('Ollama:', OLLAMA_BASE_URL, '— API key tidak diperlukan')
        if st.button('Uji sambungan Ollama'):
            from services.ollama import Ollama
            status=attempt(lambda:Ollama().status())
            if status is not None:
                st.json(status)
    st.write('Had chunks untuk satu operasi AI:',MAX_AI_CHUNKS)
    st.info('Tetapkan AI_PROVIDER=openai atau ollama dalam .env dan mulakan semula aplikasi. Ollama memerlukan model dimuat turun dan perkhidmatan sedang berjalan. Jangan masukkan API key ke Git. AI hanya dijalankan atas permintaan anda.')
    st.write('Tutup aplikasi sebelum membuat sandaran keseluruhan direktori data: SQLite, uploads dan chroma. Pulihkan semuanya bersama. Tiada OCR, multi-user authentication atau Zotero dalam MVP ini.')
    st.warning('Aplikasi untuk seorang pengguna pada komputer dipercayai. Jangan dedahkan port Streamlit ke Internet tanpa kawalan akses.')
