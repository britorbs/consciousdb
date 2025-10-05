import os, json
from fastapi.testclient import TestClient

os.environ['USE_NORMALIZED_COH'] = 'true'
from api.main import app

c = TestClient(app)
body = {"query":"dbg","k":5,"m":120,"overrides":{"similarity_gap_margin":10.0,"coh_drop_min":0.0}}
resp = c.post('/query', json=body)
print('status', resp.status_code)
J = resp.json()
items = J['items']
diag = J['diagnostics']
coh = sum(i['energy_terms']['coherence_drop'] for i in items)
anc = sum(i['energy_terms']['anchor_drop'] for i in items)
gr  = sum(i['energy_terms']['ground_penalty'] for i in items)
component_sum = coh + anc - gr
print(json.dumps({
  'coh_sum': coh,
  'anc_sum': anc,
  'gr_sum': gr,
  'component_sum': component_sum,
  'deltaH_trace': diag['deltaH_trace'],
  'deltaH_total': diag['deltaH_total']
}, indent=2))
