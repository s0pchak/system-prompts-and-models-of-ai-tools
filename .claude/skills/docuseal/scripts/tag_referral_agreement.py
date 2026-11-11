# Apply Rhode Labs Referral Agreement DocuSeal tags to a clean DOCX.
import sys, zipfile, re
src, dst = sys.argv[1], sys.argv[2]
zin = zipfile.ZipFile(src); x = zin.read('word/document.xml').decode()
n = 0
# 1. Partner legal name
k = x.count('______________________________ (“Partner”)'); assert k == 1, k
x = x.replace('______________________________ (“Partner”)', '{{Partner Legal Name;role=Partner}} (“Partner”)'); n += 1
# 2. Fee: own tiny raised run, explicit box size, no spacer
m = re.search(r'(<w:r(?: [^>]*)?>)(<w:rPr>(?:(?!</w:rPr>).)*</w:rPr>)?<w:t xml:space="preserve">____% of Net Revenue', x)
assert m, 'fee run not found'
rpr = m.group(2) or ''
tiny = '<w:rPr><w:position w:val="12"/><w:sz w:val="1"/><w:szCs w:val="1"/></w:rPr>'
x = x.replace(m.group(0),
    '<w:r>' + tiny + '<w:t xml:space="preserve">{{Referral Fee;role=RhodeLabs;width=14;height=12;font_size=10}}</w:t></w:r>'
    + m.group(1) + rpr + '<w:t xml:space="preserve">% of Net Revenue', 1); n += 1
# 3. Signature blocks: first block Rhode Labs, second Partner
labels = [('By:', 'Signature', 'signature'), ('Name:', 'Name', None), ('Title:', 'Title', None),
          ('Date:', 'Date', 'date'), ('Email:', 'Email', None)]
for role, prefix in [('RhodeLabs', 'RL'), ('Partner', 'Partner')]:
    for lab, name, typ in labels:
        tag = '{{' + f'{prefix} {name}' + (f';type={typ}' if typ else '') + f';role={role}' + '}}'
        pat = r'(<w:t[^>]*>' + re.escape(lab) + r'</w:t>(?:(?!</w:p>).)*?<w:t[^>]*>)_{28}(</w:t>)'
        x, k = re.subn(pat, lambda mm: mm.group(1) + ' ' + tag + mm.group(2), x, count=1, flags=re.S)
        assert k == 1, (role, lab); n += 1
# 4. Shrink empty paragraphs after the final table (avoid a blank trailing page)
i = x.rfind('</w:tbl>'); tail = x[i:]
assert '<w:t' not in tail[:tail.find('<w:sectPr')], 'text after final table'
tail, k = re.subn(r'<w:pPr>.*?</w:pPr>', '<w:pPr><w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/><w:rPr><w:sz w:val="2"/><w:szCs w:val="2"/></w:rPr></w:pPr>', tail, flags=re.S)
x = x[:i] + tail
print('tags', n, '| trailing paras shrunk', k)
print(re.findall(r'\{\{[^}]*\}\}', x))
zout = zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED)
for it in zin.infolist():
    zout.writestr(it, x.encode() if it.filename == 'word/document.xml' else zin.read(it.filename))
zout.close()
