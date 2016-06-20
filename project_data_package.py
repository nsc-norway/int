import sys
import os
import requests

def write_order_package(order_id, apikey, output_file):
    order = requests.get(
            'https://portal.sequencing.uio.no/api/v1/order/{0}'.format(order_id),
            headers = {'X-OrderPortal-API-key': apikey}
            )
    print(order.text)

def main():
    apikey = open(os.path.expanduser("~/portal-apikey")).read().strip()
    with open("testorder.json", "w") as output_file:
        write_order_package("d6b4c1d7ffae4d1e9e9065e4e7e4a97d", apikey, output_file)

if __name__ == "__main__":
    main()

