"""Subset the licensed Noto CJK font for existing game text only."""
from pathlib import Path
from fontTools import subset
import sys

root=Path(__file__).resolve().parent.parent
source=Path(sys.argv[1])
text=''.join(path.read_text(encoding='utf-8',errors='ignore') for path in (root/'YugiriVillage/Assets').rglob('*') if path.is_file() and path.suffix in ['.cs','.unity','.json'])
characters=set(range(32,127))|{ord(c) for c in text if ord(c)>=127}
options=subset.Options()
options.name_IDs=['*']
options.name_legacy=True
options.name_languages=['*']
font=subset.load_font(str(source),options)
subsetter=subset.Subsetter(options=options)
subsetter.populate(unicodes=characters)
subsetter.subset(font)
for record in font['name'].names:
    if record.nameID in [1,3,4,6,16]:
        value='YugiriGameUI' if record.nameID==6 else 'Yugiri Game UI'
        record.string=value.encode(record.getEncoding(),errors='replace')
if 'CFF ' in font:
    cff=font['CFF '].cff
    cff.fontNames=['YugiriGameUI']
    for top in cff.topDictIndex:
        top.FamilyName='Yugiri Game UI'
        top.FullName='Yugiri Game UI'
destination=root/'tools/web-font/YugiriWebFont.otf'
destination.parent.mkdir(parents=True,exist_ok=True)
subset.save_font(font,str(destination),options)
print(f'Subset font: {destination.stat().st_size} bytes, {len(characters)} characters')
