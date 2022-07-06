#!/usr/bin/env python3

import time
import prometheus_client
from prometheus_client.core import GaugeMetricFamily
from library import nicehash
import json
import http.server

with open('config.json') as json_file:
    config = json.load(json_file)

host = 'https://api2.nicehash.com'
organization_id = config["org-id"]
key = config["key"]
secret = config["secret"]
withdraw_id = config["withdraw-id"]
auto_withdraw = config["auto-withdraw"]

priv_api = nicehash.private_api(host, organization_id, key, secret)

class Collector:
    def __init__(self):
        self.registry = prometheus_client.CollectorRegistry()
    def collect(self):
        get_rigs = priv_api.get_rigs("MINING,ERROR,STOPPED,BENCHMARKING")

        totalprofitability = float(priv_api.get_rigs("MINING,ERROR")["totalProfitability"])
        btc_balance = priv_api.get_accounts_for_currency("BTC")
        balanceunpaid = float(btc_balance["available"])+float(get_rigs["unpaidAmount"])
        remaining_payout = 0.0005-balanceunpaid
        if auto_withdraw:
            if float(btc_balance["available"]) >= 0.0005:
                print("[*] Reached limit! Withdrawing..")
                priv_api.withdraw_request(withdraw_id,btc_balance["available"],"BTC")

        btcbalance = GaugeMetricFamily('btcbalance', 'The confirmed BTC balance.')
        btcbalance.add_metric([],btc_balance["available"])
        yield btcbalance
        btcunpaid = GaugeMetricFamily('btcunpaid', 'Current unconfirmed BTC.')
        btcunpaid.add_metric([],balanceunpaid)
        yield btcunpaid
        try:
            limit_reach = remaining_payout/totalprofitability
        except:
            limit_reach = 0
        limitreach = GaugeMetricFamily('limitreach', 'Days until withdraw limit should be reached.')
        limitreach.add_metric([], limit_reach)
        yield limitreach

        miners_mining = 0
        for data,value in get_rigs["minerStatuses"].items():
            if data == "MINING" or data == "ERROR":
                miners_mining += value


        minersmining = GaugeMetricFamily('minersmining', 'Number of miners mining.')
        minersmining.add_metric([], miners_mining)

        yield minersmining

        profit = GaugeMetricFamily('profitability', 'The current daily profitability.',labels=['rigname'])
        profitlocal = GaugeMetricFamily('localprofitability', 'The current daily local profitability.',labels=['rigname'])
        mininggputemp = GaugeMetricFamily('mininggputemp', 'GPU Miner temp.',labels=['rigname','devicename'])
        hashrate = GaugeMetricFamily('hashrate', 'Estimate hashrate for all miners.',labels=['rigname'])
        hashraterejected = GaugeMetricFamily('hashrejected', 'Estimate rejected hashrate for all miners.',labels=['rigname'])
        for data in get_rigs["miningRigs"]:
            if data["minerStatus"] == "STOPPED":
                print("[*] Miner stopped. Starting..")
                priv_api.rig_action(data["rigId"],"START", None)
            hashratevalue = 0
            hashrate_rejected = 0
            rig_name = data["name"]
            profit_local = float(f"{data['localProfitability']:f}")
            profitability = float(f"{data['profitability']:f}")
            profit.add_metric([rig_name],profitability)
            profitlocal.add_metric([rig_name],profit_local)
            for devices in data["devices"]:
                if devices["deviceType"]["enumName"] != "CPU" and devices["temperature"] > 0:
                    mininggputemp.add_metric([rig_name,devices["name"]],devices["temperature"])
                    # print(f"[*] GPU {devices['name']} is {devices['temperature']}°C")
            try:
                for moredata in data["stats"]:
                    hashratevalue += moredata["speedAccepted"]
                    hashrate_rejected += moredata["speedRejectedTotal"]
                hashrate.add_metric([rig_name],hashratevalue)
                hashraterejected.add_metric(["hashraterejected",rig_name],hashrate_rejected)
            except:
                pass
        yield profit
        yield profitlocal
        yield mininggputemp
        yield hashrate
        yield hashraterejected


def main():
    print("[*] Starting collector..")
    prometheus_client.REGISTRY.register(Collector())
    handler = prometheus_client.MetricsHandler.factory(
            prometheus_client.REGISTRY)
    print("[*] Starting Prometheus web server.")
    server = http.server.HTTPServer(
            ("0.0.0.0", 9090), handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
