from genologics.lims import *
from genologics import config
import json
import re
import sys
import base64
import datetime

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)


class ProjectNameError(ValueError):
    pass

def read_length(val):
    return int(re.match(r"(\d)+", val).group(0))

def any_val(xs, default=None):
    try:
        return next(x for x in xs if x)
    except StopIteration:
        return default

def get_project_fields(package):

    fields = package['fields']

    read_length_fields = [
            "read_length_h2500",
            "read_length_h2500_rapid",
            "read_length_4000",
            "read_length_hX",
            "read_length_nextseq_mid",
            "read_length_nextseq_high",
            "read_length_miseq"
            ]

    udfs = {
            'Project type': 'Sensitive' if fields['sensitive_data'] else 'Non-sensitive',
            'Method used to purify DNA/RNA': fields['purify_method'],
            'Method used to determine concentration': fields['concentration_method'],
            'Sample buffer': fields['buffer'],
            'Sample prep requested': fields.get('rna_sample_preps') or fields.get('dna_sample_prep') or 'None',
            'Species': fields['species'],
            'Reference genome': fields['reference_genome'],
            'Sequencing method': fields['sequencing_type'],
            'Desired insert size': fields['insert_size'],
            'Sequencing instrument requested': fields['sequencing_instrument'],
            'Read length requested': read_length(any_val((fields[f] for f in read_length_fields), "0")),
            }
    return udfs

def get_sample_fields(project_fields, sample):
    udfs_raw = {
            'Sample type': 'TEST',
            'Sample conc. (ng/ul)': sample['conc'],
            'A260/280': sample['a_260_280'],
            'A260/230': sample['a_260_230'],
            'Volume (ul)': sample['volume'],
            'Total DNA/RNA (ug)': sample['total_dna_rna'],
            'Primers, Linkers or RE sites present': sample['primers'],
            'Approx no. reads Gb or lanes requested': sample['num_reads'],
            'Index requested/used': sample['index_seq'],
            }
    return dict(
            (k, v)
            for k, v in udfs_raw.items()
            if v is not None
            )

def import_package(package_data):
    package = json.loads(package_data)
    project_name = package['fields']['project_name']
    apiuser = Researcher(lims, id="3") #APIUser
    projects = lims.get_projects(name=project_name)
    if projects:
        raise ProjectNameError("Project named " + str(project_name) + " already exists")
    udfs = get_project_fields(package)
    project = lims.create_project(
            name=project_name,
            researcher=apiuser,
            open_date=datetime.date.today(),
            udf=udfs
            )

    samples = package['samples']

    container_names = set(sample['plate'] for sample in samples if sample['plate'])
    containers = {}
    if container_names:
        plate96 = lims.get_container_types(name="96 well plate")[0]
        for cn in container_names:
            containers[cn] = lims.create_container(type=plate96, name=cn)
    for sample in samples:
        sample_udf = get_sample_fields(package['fields'], sample)
        lims.create_sample(sample['sample_name'], project, containers.get(sample['plate']),
                sample['position'], udf=sample_udf)

    for f in package['files']:
        gls = lims.glsstorage(project, f['filename'])
        f_obj = gls.post()
        data = base64.b64decode(f['content'])
        f_obj.upload(data)

if __name__ == "__main__":
    data = open(sys.argv[1]).read()
    import_package(data)

