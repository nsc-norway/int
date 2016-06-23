from genologics.lims import *
from genologics import config
import json
import re

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)


class ProjectNameError(ValueError):
    pass

def read_length(val):
    return int(re.match(r"(\d)+", val).group(0))


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
            'Sample prep requested': fields['rna_sample_preps'] or fields['dna_sample_prep'] or 'None',
            'Species': fields['species'],
            'Reference genome': fields['reference_genome'],
            'Sequencing method': fields['sequencing_type'],
            'Desired insert size': fields['insert_size'],
            'Sequencing instrument requested': fields['sequencing_instrument'],
            'Read length requested': read_length(any(fields[f] for f in read_length_fields) or "0")
            }

    return udfs



def import_package(package_data):
    package = json.loads(package_data)
    project_name = package['fields']['project_name']
    apiuser = Researcher(lims, id="3") #APIUser
    projects = lims.get_projects(name=project_name)
    if projects:
        raise ProjectNameError("Project named " + str(project_name) + " already exists")
    udfs = get_project_fields(package)
    project = lims.create_project(name=project_name, researcher=apiuser, udf=udfs)
    
    


if __name__ == "__main__":
    data = open("testorder.json").read()
    import_package(data)

