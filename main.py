#!/usr/bin/env python3

import time
import prometheus_client
from library import nicehash
import json

with open('config.json') as json_file:
    config = json.load(json_file)

host = 'https://api2.nicehash.com'
organization_id = config["org-id"]
key = config["key"]
secret = config["secret"]
withdraw_id = config["withdraw-id"]
auto_withdraw = config["auto-withdraw"]

btcbalance = prometheus_client.Gauge('btcbalance', 'The confirmed BTC balance.')
btcunpaid = prometheus_client.Gauge('btcunpaid', 'Current unconfirmed BTC.')
profit = prometheus_client.Gauge('profitability', 'The current daily profitability.',['rigname'])
profitlocal = prometheus_client.Gauge('localprofitability', 'The current daily local profitability.', ['rigname'])
balance_unpaid = prometheus_client.Gauge('unpaid', 'Balance unpaid.')
limitreach = prometheus_client.Gauge('limitreach', 'Days until withdraw limit should be reached.')
remainingpayout = prometheus_client.Gauge('remainingpayout', 'Remaining btc until payout.')
hashrate = prometheus_client.Gauge('hashrate', 'Estimate hashrate of all algorithms combined.', ['rigname'])
minersmining = prometheus_client.Gauge('minersmining', 'Amount of miners currently mining.')
hashraterejected = prometheus_client.Gauge('hashrejected', 'Amount of rejected hashrate.', ['rigname'])
mininggputemp = prometheus_client.Gauge('mininggputemp', 'Temperature of the GPU for the miner.', ['rigname','devicename'])


priv_api = nicehash.private_api(host, organization_id, key, secret)

def data():
    profit_local = 0
    profitability = 0
    totalprofitability = float(priv_api.get_rigs("MINING,ERROR")["totalProfitability"])
    hourprofit = totalprofitability/24
    get_rigs = priv_api.get_rigs("MINING,ERROR,STOPPED,BENCHMARKING")

    btc_balance = priv_api.get_accounts_for_currency("BTC")
    if auto_withdraw:
        if float(btc_balance["available"]) >= 0.0005:
            print("[*] Reached limit! Withdrawing..")
            priv_api.withdraw_request(withdraw_id,btc_balance["available"],"BTC")
    btcbalance.set(btc_balance["available"])
    balanceunpaid = float(btc_balance["available"])+float(get_rigs["unpaidAmount"])
    balance_unpaid.set(balanceunpaid)
    remaining_payout = 0.0005-balanceunpaid
    remainingpayout.set(remaining_payout)
    try:
        limit_reach = remaining_payout/hourprofit
    except:
        limit_reach = 0
    limitreach.set(limit_reach)

    for data in get_rigs["miningRigs"]:
        if data["minerStatus"] == "STOPPED":
            print("[*] Miner stopped. Starting..")
            priv_api.rig_action(data["rigId"],"START", None)
        hashratevalue = 0
        hashrate_rejected = 0
        rig_name = data["name"]
        profit_local = float(f"{data['localProfitability']:f}")
        profitability = float(f"{data['profitability']:f}")
        profit.labels(rig_name).set(f"{profitability:f}")
        profitlocal.labels(rig_name).set(profit_local)
        for devices in data["devices"]:
            if devices["deviceType"]["enumName"] != "CPU" and devices["temperature"] > 0:
                mininggputemp.labels(rig_name,devices["name"]).set(devices["temperature"])
                # print(f"[*] GPU {devices['name']} is {devices['temperature']}°C")
        try:
            for moredata in data["stats"]:
                hashratevalue += moredata["speedAccepted"]
                hashrate_rejected += moredata["speedRejectedTotal"]
            hashrate.labels(rig_name).set(hashratevalue)
            hashraterejected.labels(rig_name).set(hashrate_rejected)
        except:
            pass
    miners_mining = 0
    for data,value in get_rigs["minerStatuses"].items():
        if data == "MINING" or data == "ERROR":
            miners_mining += value

    minersmining.set(miners_mining)
    btc_unpaid = get_rigs["unpaidAmount"]
    btcunpaid.set(btc_unpaid)

def main():
    print("[*] Starting Prometheus web server.")
    prometheus_client.start_http_server(9090)
    while True:
        profitlocal.clear()
        profit.clear()
        hashrate.clear()
        hashraterejected.clear()
        mininggputemp.clear()
        data()
        time.sleep(30)


if __name__ == "__main__":
    main()
