import sys
import os
import requests
import base64
import json
import io

SERVER="https://portal.sequencing.uio.no"
FILES=["sample_file"]

def write_order_package(order_id, apikey, output_file):
    order = requests.get(
            '{SERVER}/api/v1/order/{order_id}'.format(SERVER=SERVER, order_id=order_id),
            headers = {'X-OrderPortal-API-key': apikey}
            ).json()
    account = order['owner']['email']
    owner = requests.get(
            '{SERVER}/api/v1/account/{account}'.format(SERVER=SERVER, account=account),
            headers = {'X-OrderPortal-API-key': apikey}
            ).json()
    order['owner'] = owner # Replacing with more detailed representation
    order['files'] = {}
    for f in FILES:
        filename = order['fields'][f]
        data = requests.get(
                '{SERVER}/order/{order_id}/file/{filename}'.format(
                    SERVER=SERVER, order_id=order_id, filename=filename
                    )
                ).content
        #order['files'][f] = base64.b64encode(data).decode('us-ascii')

    output_file.write(json.dumps(order))


def main():
    apikey = open(os.path.expanduser("~/portal-apikey")).read().strip()
    with open("testorder.json", "w") as output_file:
    #with io.StringIO() as output_file:
        write_order_package("5739fee09fda4461ba6df4f0364271ef", apikey, output_file)
        #print(output_file.getvalue())

if __name__ == "__main__":
    main()

