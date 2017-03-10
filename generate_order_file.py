#!/usr/bin/env python

import json
import sys

from docxtpl import DocxTemplate


doc = DocxTemplate("order-template.docx")
context = json.load(open(sys.argv[1]))
doc.render(context)
doc.save(sys.argv[1].replace(".json", ".docx"))
#print(list(context['fields'].keys()))
#print(list(context.keys()))
