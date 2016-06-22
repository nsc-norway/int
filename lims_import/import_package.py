from genologics.lims import *
from genologics import config
import json

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

def import_package(package_data):
    package = json.loads(package_data)
    project = lims.create_project()
    
    TODO


if __name__ == "__main__":
    data = open("testorder.json").read()
    import_package(data)

