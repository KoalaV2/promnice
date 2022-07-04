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
        hourprofit = totalprofitability/24
        btc_balance = priv_api.get_accounts_for_currency("BTC")
        balanceunpaid = float(btc_balance["available"])+float(get_rigs["unpaidAmount"])
        remaining_payout = 0.0005-balanceunpaid
        if auto_withdraw:
            if float(btc_balance["available"]) >= 0.0005:
                print("[*] Reached limit! Withdrawing..")
                priv_api.withdraw_request(withdraw_id,btc_balance["available"],"BTC")

        btcbalance = GaugeMetricFamily('btcbalance', 'The confirmed BTC balance.',labels=["type"])
        btcbalance.add_metric(["available"], btc_balance["available"])
        btcbalance.add_metric(["unpaid"], balanceunpaid)
        btcbalance.add_metric(["remaining"], remaining_payout)
        try:
            limit_reach = remaining_payout/hourprofit
        except:
            limit_reach = 0
        btcbalance.add_metric(["limitreach"], limit_reach)
        yield btcbalance


        minerstats = GaugeMetricFamily('minerstats', 'Stats about the miners.',labels=["type","rigname","devicename"])

        miners_mining = 0
        for data,value in get_rigs["minerStatuses"].items():
            if data == "MINING" or data == "ERROR":
                miners_mining += value

        minerstats.add_metric(["minersmining"], miners_mining)


        for data in get_rigs["miningRigs"]:
            if data["minerStatus"] == "STOPPED":
                print("[*] Miner stopped. Starting..")
                priv_api.rig_action(data["rigId"],"START", None)
            hashratevalue = 0
            hashrate_rejected = 0
            rig_name = data["name"]
            profit_local = float(f"{data['localProfitability']:f}")
            profitability = float(f"{data['profitability']:f}")
            minerstats.add_metric(["profitability",rig_name],profitability)
            minerstats.add_metric(["localprofitability",rig_name],profit_local)
            for devices in data["devices"]:
                if devices["deviceType"]["enumName"] != "CPU" and devices["temperature"] > 0:
                    minerstats.add_metric(["mininggputemp",rig_name,devices["name"]],devices["temperature"])
                    # print(f"[*] GPU {devices['name']} is {devices['temperature']}°C")
            try:
                for moredata in data["stats"]:
                    hashratevalue += moredata["speedAccepted"]
                    hashrate_rejected += moredata["speedRejectedTotal"]
                minerstats.add_metric(["hashrate",rig_name],hashratevalue)
                minerstats.add_metric(["hashraterejected",rig_name],hashrate_rejected)
            except:
                pass
        yield minerstats


def main():
    print("[*] Starting collector..")
    prometheus_client.REGISTRY.register(Collector())
    handler = prometheus_client.MetricsHandler.factory(
            prometheus_client.REGISTRY)
    print("[*] Starting Prometheus web server.")
    server = http.server.HTTPServer(
            ("127.0.0.1", 8080), handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
