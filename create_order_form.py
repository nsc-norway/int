#!/usr/bin/env python

# This script doesn't quite work. It is not flexible enough to have a 
# very basic template system, even though that part works. Going to 
# do more programmatic generation instead.

# Used an example from: https://esq.io/blog/posts/python-docx-mailmerge/ 
# (V. David Zvenyach)

import zipfile
import string
from lxml import etree

def read_docx(filepath):
    zfile = zipfile.ZipFile(filepath)
    return zfile.read("word/document.xml")

def replace_hash(kp, input_string):
    for key, value in kp.items():
        if key in input_string:
            return value

def replace_docx(filepath, newfilepath, newfile):
    zin = zipfile.ZipFile(filepath, 'r')
    zout = zipfile.ZipFile(newfilepath, 'w')
    for item in zin.infolist():
        buffer = zin.read(item.filename)
        if (item.filename != 'word/document.xml'):
            zout.writestr(item, buffer)
        else:
            zout.writestr('word/document.xml', newfile)
    zin.close()
    zout.close()
    return True

def check_element_is(element, type_char):
     word_schema = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
     return element.tag == '{%s}%s' % (word_schema,type_char)

def docxmerge(fname, kp, newfname):
    filexml = read_docx(fname)
    my_etree = etree.fromstring(filexml)
    for node in my_etree.iter(tag=etree.Element):

        if check_element_is(node, 'fldChar'): #Once we've hit this, we're money...

            # Now, we're looking for this attribute: w:fldCharType="separate"
            if node.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fldCharType') == "separate":
                node_value = node.getparent().getnext().getchildren()[1].text
                import sys
                sys.stdout.buffer.write(("fldChar value is " + str(node_value) + "\n").encode('utf-8'))
                node.getparent().getnext().getchildren()[1].text = replace_hash(kp, node_value)

        elif check_element_is(node, 'fldSimple'): #Once we've hit this, we're money...
            node_value = node.getchildren()[0].getchildren()[1].text
            node.getchildren()[0].getchildren()[1].text = replace_hash(kp, node_value)

    replace_docx(fname, newfname, etree.tostring(my_etree, encoding='utf8', method='xml'))

def flatten(dic):
    data = {}
    for k, v in dic.items():
        if type(v) == dict:
            for k1, v1 in flatten(v).items():
                data[k + "." + k1] = v1
        else:
            data[k] = v
    return data


if __name__ == '__main__':
    import json
    import sys
    order = json.load(open(sys.argv[1]))
    order_flat = flatten(order)
    print(order_flat)
    docxmerge("order-template.docx", order_flat, sys.argv[1].replace(".json", ".docx"))

