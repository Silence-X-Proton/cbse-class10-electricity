import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build

class AssemblyTests(unittest.TestCase):
    def q(self, number, marks=2, kind='short2'):
        return {'id':f'q{number}', 'text':f'Unique circuit situation number {number}: calculate resistance using the stated current and voltage.',
                'source_url':'https://cbseacademic.nic.in/example.pdf', 'source_title':'CBSE source',
                'session':'2024-25','year':'2024-25','question_number':str(number), 'original_section':'B',
                'pages':[1], 'marks':marks, 'type':kind, 'verified':False,
                'evidence_image':'evidence.png', 'compilation_section':build.section({'marks':marks,'type':kind})}
    def test_missing_gate_preserves_site(self):
        with tempfile.TemporaryDirectory(dir=build.ASSEMBLY) as tmp:
            root=Path(tmp)
            with patch.object(build,'ROOT',root):
                loaded, blockers=build.load_inputs()
            self.assertEqual(loaded,{})
            self.assertEqual(len(blockers),5)
    def test_no_invented_verification(self):
        class Assets:
            def copy(self,value): return value
        q=build.normalize_question(self.q(1),'official',Assets())
        self.assertFalse(q['verified']); self.assertFalse(q['answer_verified'])
    def test_choice_slots_and_exact_text_duplicates(self):
        qs=[self.q(n,marks,kind) for n,marks,kind in [(i,1,'mcq') for i in range(1,11)]+[(i,2,'short2') for i in range(11,26)]+[(i,3,'short3') for i in range(26,41)]+[(i,5,'long') for i in range(41,51)]]
        alt=dict(qs[10],id='q11_alt',question_number='11 OR',text='Different valid alternative for the same printed numbered source slot.')
        dup=dict(qs[11],id='same_text_other_set',question_number='99')
        docs, uses=build.compile_official(qs+[alt,dup]); lookup={q['id']:q for q in qs+[alt,dup]}
        self.assertEqual(len(docs),15)
        self.assertEqual(len({frozenset(d['question_ids']) for d in docs}),15)
        for d in docs:
            selected=[lookup[k] for k in d['question_ids']]
            self.assertEqual(len({build.source_key(q) for q in selected}),len(selected))
            self.assertEqual(len({build.fingerprint(q) for q in selected}),len(selected))
            self.assertGreaterEqual(d['marks'],30); self.assertLessEqual(d['marks'],40)
        self.assertEqual(sum(uses.values()),sum(len(d['question_ids']) for d in docs))
    def test_answer_hold_removes_published_answer_not_source_flags(self):
        class Assets:
            def copy(self,value): return value
        raw=self.q(10)
        raw.update(verified=True,answer_verified=False,answer='Known incorrect answer',
                   answer_evidence_images=['incorrect-answer.png'],answer_verification_note='Arithmetic error in official MS',
                   marking_scheme_url='https://cbseacademic.nic.in/ms.pdf')
        q=build.normalize_question(raw,'official',Assets())
        self.assertTrue(q['verified']); self.assertFalse(q['answer_verified'])
        self.assertNotIn('answer',q); self.assertFalse(build.images(q,build.ANSWER_IMAGE_FIELDS))
        self.assertIn('Arithmetic error',q['notes'])
        self.assertEqual(q['marking_scheme_url'],raw['marking_scheme_url'])
        self.assertEqual(raw['answer'],'Known incorrect answer')
        self.assertEqual(raw['answer_evidence_images'],['incorrect-answer.png'])

    def test_short1_is_searchable_not_forced_into_paper(self):
        q=self.q(22,1,'short1')
        self.assertEqual(build.eligible(q,for_paper=False),[])
        self.assertTrue(build.eligible(q,for_paper=True))

    def test_diverse_pyq_years_in_every_paper(self):
        qs=[]
        for i in range(1,81):
            marks,kind=[(1,'mcq'),(2,'short2'),(3,'short3'),(5,'long')][i%4]
            q=self.q(i,marks,kind)
            q['exam_type']='PYQ' if i<49 else 'SQP'
            q['year']=2018+((i//4)%6)
            q['session']=str(q['year']) if i<49 else str(2017+i%10)
            qs.append(q)
        docs,_=build.compile_official(qs);lookup={q['id']:q for q in qs}
        for d in docs:
            selected=[lookup[x] for x in d['question_ids']]
            self.assertGreaterEqual(len({q['year'] for q in selected if q['exam_type']=='PYQ'}),3)
            self.assertEqual({build.section(q) for q in selected},{'A','B','C','D'})
            self.assertGreaterEqual(d['marks'],30)
            self.assertLessEqual(d['marks'],40)

    def test_overlay_preserves_bank_and_rejects_verification_upgrade(self):
        bank=[self.q(1)]
        metadata={'q1':{'original_section':'Section C','metadata_review':{'pdf_page':1}}}
        result=build.apply_publication_metadata(bank,metadata)
        self.assertEqual(result[0]['original_section'],'Section C')
        self.assertEqual(bank[0]['original_section'],'B')
        self.assertFalse(result[0]['verified'])
        metadata['q1']['verified']=True
        with self.assertRaises(build.Blocked): build.apply_publication_metadata(bank,metadata)

    def test_labelled_option_objects_preserve_labels(self):
        class Assets:
            def copy(self,value): return value
        raw=self.q(1,1,'mcq');raw['options']=[{'label':'a','text':'Length'},{'label':'b','text':'Shape'}]
        q=build.normalize_question(raw,'official',Assets())
        self.assertEqual(q['options'],['a. Length','b. Shape'])
        self.assertEqual(q['source_options'],raw['options'])

    def test_tiny_inventory_blocks(self):
        with self.assertRaises(build.Blocked): build.compile_official([self.q(1)])
    def test_unresolved_or_and_non_mcq_one_mark(self):
        q=self.q(1); q['text']='Electricity question\nOR\nAnother branch'
        self.assertIn('unresolved OR block in question text',build.eligible(q))
        q['choice_resolved']=True
        self.assertNotIn('unresolved OR block in question text',build.eligible(q))
        self.assertIsNone(build.section(self.q(2,1,'short1')))
        self.assertEqual(build.section(self.q(3,4,'case')),'D')
    def test_assets_exact_hash_and_zip_rejection(self):
        source=next((build.ROOT/'research/sqp/evidence').glob('*.png'))
        with tempfile.TemporaryDirectory(dir=build.ASSEMBLY) as tmp:
            assets=build.Assets(Path(tmp)); out=assets.copy(str(source))
            self.assertEqual(build.digest(source),build.digest(Path(tmp)/out))
            with self.assertRaises(build.Blocked): assets.copy('/etc/passwd')
            with self.assertRaises(build.Blocked): assets.copy('research/fake.zip')
    def test_original_svg_keeps_question_text_and_options(self):
        import pymupdf
        with tempfile.TemporaryDirectory(dir=build.ASSEMBLY) as tmp:
            stage=Path(tmp)
            svg=stage/'original.svg'
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="70"><rect x="20" y="20" width="80" height="25" fill="none" stroke="black"/><text x="25" y="37">4 ohm</text></svg>')
            assets=build.Assets(stage)
            raw={'id':'original-figure-test','text':'Calculate current in the supplied original circuit.',
                 'options':['A. 2 A','B. 4 A'],'marks':1,'type':'MCQ','verified':True,'diagram_image':str(svg)}
            q=build.normalize_question(raw,'original',assets)
            doc={'id':'svg-check','title':'Original diagram regression','kind':'practice','status':'ready',
                 'marks':1,'question_ids':[q['id']], 'sections':[]}
            build.pdf_render(doc,{q['id']:q},stage,{})
            with pymupdf.open(stage/doc['pdf']) as pdf:
                text='\n'.join(p.get_text() for p in pdf)
                self.assertIn('Calculate current',text)
                self.assertIn('A. 2 A',text)
                self.assertIn('4 ohm',text)

    def test_actual_pdf_has_sources_reuse_and_unicode(self):
        import pymupdf
        raw=json.loads((build.ROOT/'research/sqp/batch_early.json').read_text())[0]
        with tempfile.TemporaryDirectory(dir=build.ASSEMBLY) as tmp:
            stage=Path(tmp); assets=build.Assets(stage)
            q=build.normalize_question(raw,'official',assets)
            doc={'id':'renderer-check','title':'Renderer check — Ω Ω₁ = 2 × 4', 'kind':'official','status':'draft',
                 'marks':q['marks'],'duration_minutes':6,'question_ids':[q['id']], 'sections':[]}
            build.pdf_render(doc,{q['id']:q},stage,{q['id']:['renderer-check','official-02']})
            with pymupdf.open(stage/doc['pdf']) as pdf:
                text='\n'.join(p.get_text() for p in pdf)
                self.assertIn('Per-question source appendix',text)
                self.assertIn('official-02',text)
                self.assertIn('Official answer unavailable/withheld',text)
                self.assertIn('Ω',text)
                self.assertNotIn('�',text)
                self.assertTrue(any(p.get_images() for p in pdf))

if __name__=='__main__': unittest.main()
