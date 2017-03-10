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

    output_file.write(json.dumps(order))


def main(order_id):
    apikey = open(os.path.expanduser("~/portal-apikey")).read().strip()
    with open(order_id + ".json", "w") as output_file:
        write_order_package(order_id, apikey, output_file)

if __name__ == "__main__":
    main(sys.argv[1])

